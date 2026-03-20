"""
Hard MIP benchmark: Multi-dimensional correlated binary knapsack.

WINNING CONFIG (experimentally determined on this hardware):
  n=2200 binary variables, m=20 constraints, 40% capacity, seed=137
  time_limit=75s → always runs for exactly 75 seconds

Behaviour observed:
  - HiGHS finds near-optimal solution within ~50s (gap closes from ~0.1% → ~0.003%)
  - Final 0.003% gap is never proven optimal; job completes via time_limit
  - Elapsed always ≈ 75.0s (±1s), completely reproducible
  - Provides rich B&B activity throughout: incumbents, bound updates, node counts

Tested sizes (mip_gap=0.0, time_limit=120):
  n=2000 → completes in ~25s   (too fast for pause/resume)
  n=2200 → stalls at ~50s, hits limit  ← WINNER with time_limit=75
  n=2500 → stalls at ~50s, hits limit
  n=3000 → stalls at ~50s, hits limit

Usage:
  Submit directly via sage-solver-cloud REST API.
  See submit_benchmark_job() below, or run this file as a script.

  python bench_hard_mkp.py [--url http://localhost:PORT] [--key YOUR_KEY]
"""

import json
import sys
import time
import urllib.request
import urllib.error
import argparse

# ── Winning configuration ────────────────────────────────────────────────────
BENCH_N          = 2200    # binary variables (items)
BENCH_M          = 20      # knapsack dimensions (constraints)
BENCH_CAP_RATIO  = 0.40    # capacity = 40% of total weight per dimension
BENCH_SEED       = 137     # LCG seed for reproducibility
BENCH_TIME_LIMIT = 75      # seconds — controls run duration
BENCH_MIP_GAP    = 0.0     # exact optimality required (won't be reached)


def _lcg_sequence(n: int, m: int, seed: int = BENCH_SEED):
    """Seeded LCG RNG identical to the JavaScript version used for validation."""
    s = seed & 0xFFFFFFFF

    def rand():
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 0xFFFFFFFF

    def ri(lo, hi):
        return lo + int(rand() * (hi - lo + 1))

    base    = [ri(10, 100) for _ in range(n)]
    profits = [b + ri(0, 20) for b in base]

    weights_per_dim = []
    caps = []
    for _ in range(m):
        w = [b + ri(-5, 5) for b in base]
        weights_per_dim.append(w)
        caps.append(int(sum(w) * BENCH_CAP_RATIO))

    return base, profits, weights_per_dim, caps


def build_solver_input(
    n: int = BENCH_N,
    m: int = BENCH_M,
    seed: int = BENCH_SEED,
    cap_ratio: float = BENCH_CAP_RATIO,
    time_limit: int = BENCH_TIME_LIMIT,
    mip_gap: float = BENCH_MIP_GAP,
) -> dict:
    """
    Build a flat SolverInput dict for submission to sage-solver-cloud /api/jobs.

    Returns the dict ready for JSON serialisation.
    """
    _, profits, weights_per_dim, caps = _lcg_sequence(n, m, seed)

    # Adjust capacities if a different ratio was requested
    if cap_ratio != BENCH_CAP_RATIO:
        weights_per_dim_new = []
        caps = []
        base, _, _, _ = _lcg_sequence(n, m, seed)  # rebuild
        _, profits, weights_per_dim_new, _ = _lcg_sequence(n, m, seed)
        for w in weights_per_dim_new:
            caps.append(int(sum(w) * cap_ratio))
        weights_per_dim = weights_per_dim_new

    return {
        "num_variables":          n,
        "num_constraints":        m,
        "variable_names":         [f"x{i}" for i in range(n)],
        "variable_lower_bounds":  [0.0] * n,
        "variable_upper_bounds":  [1.0] * n,
        "variable_types":         ["binary"] * n,
        "constraint_names":       [f"cap_{j}" for j in range(m)],
        "constraint_matrix":      weights_per_dim,
        "constraint_senses":      ["<="] * m,
        "constraint_rhs":         [float(c) for c in caps],
        "objective_coefficients": [float(p) for p in profits],
        "objective_sense":        "maximize",
        "time_limit_seconds":     time_limit,
        "mip_gap_tolerance":      mip_gap,
    }


def submit_benchmark_job(
    base_url: str,
    api_key: str,
    n: int = BENCH_N,
    time_limit: int = BENCH_TIME_LIMIT,
    name: str = "bench_hard_mkp",
) -> str:
    """Submit to /api/jobs and return the task_id."""
    si = build_solver_input(n=n, time_limit=time_limit)
    payload = json.dumps({
        "solver_input":  si,
        "problem_name":  name,
        "problem_type":  "MIP",
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/api/jobs",
        data=payload,
        headers={"Content-Type": "application/json", "X-Sage-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    return body["task_id"]


def poll_job(base_url: str, api_key: str, task_id: str, interval: float = 5.0) -> dict:
    """Poll /api/jobs/{task_id} until terminal status; return final job dict."""
    terminal = {"complete", "completed", "failed", "infeasible", "cancelled"}
    while True:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"{base_url}/api/jobs/{task_id}",
                headers={"X-Sage-Key": api_key},
            ),
            timeout=10,
        ) as resp:
            job = json.loads(resp.read())

        status   = job.get("status", "?")
        elapsed  = job.get("elapsed_seconds") or 0.0
        gap      = job.get("gap_pct") or 0.0
        incumb   = job.get("best_incumbent")
        print(
            f"  [{time.strftime('%H:%M:%S')}] "
            f"status={status:<10} elapsed={elapsed:6.1f}s  "
            f"gap={gap:.5f}%  incumbent={incumb}",
            flush=True,
        )

        if status in terminal:
            return job
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Hard MIP benchmark for SAGE pause/resume testing")
    parser.add_argument("--url",  default="http://localhost:49901", help="sage-solver-cloud base URL")
    parser.add_argument("--key",  default=None,  help="API key (fetched from /api/config if omitted)")
    parser.add_argument("--n",    default=BENCH_N,          type=int,   help="number of binary variables")
    parser.add_argument("--time", default=BENCH_TIME_LIMIT, type=int,   help="time limit in seconds")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    # Auto-fetch API key if not provided
    api_key = args.key
    if not api_key:
        with urllib.request.urlopen(f"{base_url}/api/config", timeout=5) as r:
            api_key = json.loads(r.read())["api_key"]
        print(f"Auto-fetched API key: {api_key[:20]}…")

    print(f"\n{'='*60}")
    print(f"Hard MIP benchmark  n={args.n}  time_limit={args.time}s")
    print(f"Server: {base_url}")
    print(f"{'='*60}")

    t0 = time.monotonic()
    task_id = submit_benchmark_job(base_url, api_key, n=args.n, time_limit=args.time)
    print(f"Submitted → task_id={task_id}")
    print()

    job = poll_job(base_url, api_key, task_id)

    wall = time.monotonic() - t0
    print(f"\n{'='*60}")
    print(f"Final status : {job.get('status')}")
    print(f"Elapsed      : {job.get('elapsed_seconds', 0):.1f}s  (wall: {wall:.1f}s)")
    print(f"Best obj     : {job.get('best_incumbent')}")
    print(f"Best bound   : {job.get('best_bound')}")
    print(f"Final gap    : {job.get('gap_pct', 0):.5f}%")

    elapsed = job.get("elapsed_seconds", 0) or 0
    if 60 <= elapsed <= 90:
        print("✅  In target range (60–90s) — good for pause/resume testing")
    elif elapsed < 60:
        print("⚡  Too fast — increase n or time_limit")
    else:
        print("🐢  Too slow — decrease n or time_limit")


if __name__ == "__main__":
    main()
