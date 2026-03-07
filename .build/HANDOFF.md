# SAGE — Development Handoff Report

**Prepared:** 2026-03-07
**For:** Claude Opus (resuming development in ~1 week)
**Repo:** https://github.com/pragnakar/Project_Sage
**Author:** Pragnakar Pedapenki

---

## What SAGE Is

SAGE (Solver-Augmented Grounding Engine) is a local MCP server that gives Claude Desktop — and any MCP-compatible LLM client — the ability to formulate, solve, and certify mathematical optimization problems using production-grade open-source solvers.

**The core insight:** LLMs hallucinate math. Solvers can't interpret intent. SAGE sits at the junction — the LLM translates human intent into structured problem definitions, SAGE translates those into solver-native format, dispatches to HiGHS/OSQP, and returns certified results with sensitivity analysis, infeasibility certificates, and plain-language explanations.

**Key differentiator:** SAGE returns provably optimal solutions. When problems are infeasible, it identifies the exact minimal set of conflicting constraints (IIS — Irreducible Infeasible Subsystem) and ranks relaxation suggestions by least disruption.

---

## Current State

| Item | Value |
|---|---|
| Version | sage-solver-core 0.1.3, sage-solver-mcp 0.1.3 |
| Tests | 470 passing, 0 failing (393 core + 77 MCP) |
| Published | PyPI (`pip install sage-solver-mcp`), MCP Registry, Claude Desktop Extensions |
| Claude Desktop config | `command: "/opt/homebrew/bin/uvx"`, `args: ["sage-solver-mcp"]` |
| Branch | `main` (all development merged, no open branches) |
| Active Phase | Phase 1 COMPLETE. Next: Phase 2 (sage-cloud FastAPI) |

---

## Repo Structure

```
Project_Sage/
├── CLAUDE.md                    ← One-liner: @.build/AGENT.md (Claude Code entry point)
├── README.md                    ← Public-facing docs with 5 usage examples
├── ROADMAP.md                   ← 5-phase vision document
├── CONTRIBUTING.md              ← Dev setup and contribution guide
├── .gitignore
│
├── .build/                      ← Internal dev docs (not shipped)
│   ├── AGENT.md                 ← Full dev instructions (for any AI coding assistant)
│   ├── SAGE_SPEC.md             ← Architecture spec and component contracts
│   ├── BUILD_LOG.md             ← Phase-by-phase build history + decisions log
│   └── HANDOFF.md               ← This file
│
├── sage-solver-core/            ← Pure optimization engine (NO filesystem, NO HTTP)
│   ├── sage_solver_core/
│   │   ├── models.py            ← All Pydantic v2 schemas
│   │   ├── solver.py            ← HiGHS wrapper (LP/MIP/QP/IIS/sensitivity)
│   │   ├── builder.py           ← JSON → SolverInput (LP/MIP/Portfolio/Scheduling)
│   │   ├── fileio.py            ← Excel/CSV read/write, template generation
│   │   ├── explainer.py         ← Natural language narration (brief/standard/detailed)
│   │   └── relaxation.py        ← IIS extraction + ranked relaxation suggestions
│   └── tests/                   ← 393 tests
│
├── sage-solver-mcp/             ← Local MCP server (thin wrapper over core)
│   ├── sage_solver_mcp/
│   │   ├── server.py            ← 7 MCP tools
│   │   ├── local_io.py          ← Filesystem bridge (resolve paths, output dirs)
│   │   └── __main__.py          ← Entry point
│   ├── tests/                   ← 77 tests
│   └── claude_desktop_config.json
│
├── sage-cloud/                  ← PLACEHOLDER ONLY — do not build yet
│   └── sage_cloud/
│       ├── __init__.py
│       ├── api.py               ← FastAPI routes (stub)
│       ├── auth.py              ← API key / OAuth (stub)
│       ├── queue.py             ← Async job management (stub)
│       └── storage.py           ← S3/GCS file bridge (stub)
│
└── examples/                    ← Ready-to-use Excel/CSV files
    ├── portfolio_5_assets.xlsx
    ├── nurse_scheduling.xlsx    ← Intentionally infeasible (tests IIS)
    ├── transport_routing.xlsx
    ├── blending_problem.xlsx
    ├── blending_problem.csv
    ├── portfolio_template.xlsx  ← Blank template (generate_template output)
    └── scheduling_template.xlsx
```

---

## Architecture — Critical Design Rules

These are non-negotiable constraints. Do not violate them.

1. **sage-solver-core never touches the filesystem.** Functions receive DataFrames, bytes, or model objects. The MCP and cloud layers handle I/O.
2. **Every solver call returns a `SolverResult`.** Never expose raw HiGHS output.
3. **All errors are structured** — `SAGEError` subclasses with `details: dict` and `suggestions: list[str]`. Never bare exceptions.
4. **Infeasibility is a first-class result, not an error.** When infeasible: compute IIS, explain the conflict, suggest ranked relaxations.
5. **No PuLP.** Direct `highspy` bindings only.
6. **No web UI.** The LLM is the UI.
7. **No print().** Return structured data or use the logging module.
8. **Do not use `WidthType.PERCENTAGE` in Excel formatting** — breaks in Google Docs.

---

## Tech Stack

| Component | Library | Version |
|---|---|---|
| Solver (LP/MIP/QP) | `highspy` | 1.13.1 |
| Solver (CP) | `ortools` | 9.15.6755 |
| Schemas | `pydantic` | 2.12.5 |
| Data I/O | `pandas` | 3.0.1 |
| Excel | `openpyxl` | 3.1.5 |
| Numerics | `numpy` | 2.4.2 |
| MCP server | `mcp` | 1.26.0 |
| Python | | 3.11+ |

---

## Pydantic Schemas (models.py)

All schemas support two transport quirks added in v0.1.2:

**Field aliases** — the LLM may use shorthand names:
- `lb` / `ub` → `lower_bound` / `upper_bound` (on `LPVariable`, `MIPVariable`)
- `expression` → `coefficients` (on `LinearConstraint`)
- `operator` → `sense` (on `LinearConstraint`)
- `direction` → `sense` (on `LinearObjective`)

**String deserialization** — MCP transport may deliver lists/dicts as JSON strings. `model_validator(mode="before")` on `LPModel`, `MIPModel`, `PortfolioModel`, `SchedulingModel` calls `json.loads()` on string-typed `variables`, `constraints`, `objective`, `assets`, `covariance_matrix`, `workers`, `shifts` fields before Pydantic parses them.

### Core Schema Summary

```python
# LP
LPVariable(name, lower_bound=0, upper_bound=None)
LinearConstraint(name, coefficients: dict[str,float], sense: "<="|">="|"==", rhs)
LinearObjective(sense: "minimize"|"maximize", coefficients: dict[str,float])
LPModel(name, variables, constraints, objective)

# MIP extends LP with:
MIPVariable(..., var_type: "continuous"|"integer"|"binary" = "continuous")
MIPModel(..., time_limit_seconds=60, mip_gap_tolerance=0.0001)

# Portfolio (Markowitz QP)
Asset(name, expected_return, sector=None)
PortfolioConstraints(max/min_allocation_per_asset, max_sector_allocation, target_return, min/max_total_allocation=1.0)
PortfolioModel(assets, covariance_matrix: list[list[float]], risk_aversion=1.0, constraints)

# Scheduling (binary MIP)
Worker(name, cost_per_shift, max_shifts_per_week, skills=[], unavailable_shifts=[])
Shift(name, day, start_hour, end_hour, required_workers, required_skills=[])
SchedulingModel(workers, shifts, planning_horizon_days=7, max_consecutive_days=5)

# Solver I/O
SolverInput(variables, constraints, objective_coefficients, variable_types, bounds, time_limit, mip_gap)
SolverResult(status: "optimal"|"infeasible"|"unbounded"|"time_limit"|"error",
             objective_value, variable_values, dual_values, reduced_costs,
             objective_ranges, rhs_ranges, iis_constraints, iis_bounds, iis_explanation,
             solve_time_seconds)
```

---

## MCP Tools (server.py)

Seven tools registered with the MCP server. Tool names are fixed — do not rename.

| Tool | Description |
|---|---|
| `solve_optimization` | Solve LP / MIP / portfolio / scheduling from JSON. Auto-detects type. |
| `read_data_file` | Read Excel or CSV; return sheet/column/row preview. |
| `solve_from_file` | Read + build + solve + write `_optimized.xlsx` in one step. |
| `explain_solution` | Narrate last solve result (detail_level: brief/standard/detailed). |
| `check_feasibility` | Check feasibility; compute IIS + relaxations if infeasible. |
| `generate_template` | Create blank Excel template (portfolio/scheduling/generic_lp). |
| `suggest_relaxations` | Rank constraint relaxations for the last infeasible result. |

**State:** `ServerState` (module-level dataclass) holds `last_result`, `last_model`, `last_solver_input`, `last_iis`. Single-user, single-process — no concurrency needed for V1.

**Model type auto-detection order:**
1. Explicit `problem_type` field
2. `portfolio` — has `assets` + `covariance_matrix`
3. `scheduling` — has `workers` + `shifts`
4. `mip` — has any variable with non-continuous `var_type`
5. `lp` — default

---

## Key Implementation Decisions

These decisions resolved ambiguities in the spec. Respect them in future work.

| # | Decision | Rationale |
|---|---|---|
| 1 | `objective_ranges`/`rhs_ranges` bounds typed as `float \| None` | HiGHS returns `kHighsInf` (~1e30) for unbounded ranging; `float('inf')` is not valid JSON. `None` = "unbounded in this direction". |
| 2 | QP ranging returns `None` | HiGHS does not support ranging for QP problems, only LP. |
| 3 | `_safe_range_float` clips values ≥ 1e29 or NaN to `None` | Catches both `kHighsInf` and Python `float('inf')` uniformly. |
| 4 | Portfolio builder uses `minimize` sense | HiGHS QP requires minimize + positive semi-definite Q. Negate returns (`c_i = -r_i`), use `Q = 2λCov`. |
| 5 | Scheduling consecutive-days: rolling window sum constraint | `sum_{d'=d}^{d+mc} sum_s x[w,s,d'] <= mc × S` (RHS is `max_consecutive_days × num_shifts`, NOT just `max_consecutive_days`). This was a bug fixed in Phase 5. |
| 6 | Unavailability + skill blocks: `variable.upper_bound = 0` | Cleaner than equality constraints; HiGHS handles bound reductions efficiently. |
| 7 | Binary variable `ub=0` must be passed to HiGHS via `addVar` | `_build_highs()` was hardcoding `addVar(0.0, 1.0)` for all binary vars. Fix: `min(1.0, ub)` in `addVar`. |
| 8 | `ffill()` removed from Excel/CSV reader | `df.ffill()` propagated description-row strings into blank data cells. Removed `_forward_fill_headers()` from both reader paths. |
| 9 | Relaxation: exponential probe then 25-iteration bisection | Probe with factors `[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 100.0, 1000.0]`, then bisect. Returns `None` if probe fails — single-constraint relaxation can't restore feasibility. |
| 10 | `console_scripts` points to `sage_solver_mcp.server:main` | `__main__.py` imports `main` but doesn't define it as a module-level name; pip's script wrapper fails. |
| 11 | `default_output_dir()` falls back to `Path.home()` when CWD is `/` | MCP server CWD may be `/` (read-only). Fixed in `local_io.py`. |
| 12 | `path.resolve()` called after existence check | macOS `Path.resolve()` before existence check translates `/home` → `/System/Volumes/Data/home` via firmlinks. |

---

## Known Limitations (v0.1.3)

- **Deterministic only** — no stochastic programming, no scenario analysis (Phase 2 scope)
- **Single-period models** — no multi-stage or time-series optimization
- **No nonlinear support** — QP only (Markowitz portfolio); no general NLP
- **Deeply infeasible models** — when demand far exceeds total system capacity, `suggest_relaxations` returns `[]`. This is correct behavior (no single-constraint fix possible), not a bug.
- **No NL → model translation** — the LLM fills structured schemas; SAGE validates and solves. Phase 1.5 scope.
- **Local only** — no ChatGPT integration (requires remote SSE server). Phase 2 scope.

---

## Phase Completion Status

| Phase | Status | Version | Tests |
|---|---|---|---|
| Phase 1 — Schemas (models.py) | COMPLETE | v0.1.0 | 95 |
| Phase 2 — Solver (solver.py) | COMPLETE | v0.1.0 | 59 |
| Phase 3 — Builder (builder.py) | COMPLETE | v0.1.0 | 98 |
| Phase 4 — File I/O (fileio.py) | COMPLETE | v0.1.0 | 68 |
| Phase 5 — Intelligence (explainer + relaxation) | COMPLETE | v0.1.0 | 62 |
| Phase 6 — MCP Server (server.py) | COMPLETE | v0.1.0 | 53 |
| Phase 7 — Examples, Docs & Polish | COMPLETE | v0.1.0 | 24 |
| Post-Phase 7 — MCP transport hardening + repo cleanup | COMPLETE | v0.1.3 | 35 |
| **Phase 1.5 — NL → Optimization Model** | **NEXT** | v0.3 planned | — |
| Phase 2 — sage-cloud FastAPI | Planned | v0.2 planned | — |
| Phase 2.5 — Domain Template Library | Planned | v0.6 planned | — |
| Phase 3 — Decision Intelligence Platform | Planned | v1.0 planned | — |
| Phase 4 — Planetary-Scale Solver | Moonshot | v2.0+ | — |

---

## Next Phase — sage-cloud (v0.2)

**Goal:** Make SAGE accessible remotely so any LLM client (including ChatGPT) can call it via SSE/HTTP.

**What to build in `sage-cloud/`:**

```
sage-cloud/
└── sage_cloud/
    ├── api.py       ← FastAPI app; routes mirror the 7 MCP tools
    ├── auth.py      ← API key authentication (simple header-based for v0.2)
    ├── queue.py     ← Async job management (asyncio or Celery)
    └── storage.py   ← S3/GCS bridge for file upload/download
```

**Key constraints:**
- `sage_cloud` imports `sage-solver-core` — never re-implements solver logic
- Multi-tenant: each request gets isolated state (no module-level `ServerState`)
- Async-first: long-running solves must not block the event loop
- Remote MCP transport: SSE (Server-Sent Events), not stdio
- Auth in V2 (unlike V1 local which has none)

**Reference the ROADMAP.md Phase 2 section** for full feature scope before building.

---

## Dev Setup

```bash
# Clone
git clone https://github.com/pragnakar/Project_Sage
cd Project_Sage

# Install both packages (editable)
pip install -e sage-solver-core/
pip install -e sage-solver-mcp/

# Run tests
cd sage-solver-core && pytest tests/ -v   # expect 393 passed
cd sage-solver-mcp  && pytest tests/ -v   # expect 77 passed

# Run MCP server locally (for Claude Desktop)
uvx sage-solver-mcp
# or with full path if uvx not on PATH:
/opt/homebrew/bin/uvx sage-solver-mcp
```

**Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "sage": {
      "command": "/opt/homebrew/bin/uvx",
      "args": ["sage-solver-mcp"]
    }
  }
}
```

---

## Verification Checklist (run before resuming)

Before writing any code in the next session, verify:

- [ ] `cd sage-solver-core && pytest tests/ -v` → 393 passed, 0 failed
- [ ] `cd sage-solver-mcp && pytest tests/ -v` → 77 passed, 0 failed
- [ ] `pip install sage-solver-mcp` installs without error
- [ ] `uvx sage-solver-mcp` launches server (no crash)
- [ ] Read `.build/SAGE_SPEC.md` sections 3–5 for component contracts before modifying any core file

---

## Key Files to Read Before Coding

| File | Purpose |
|---|---|
| `.build/AGENT.md` | Full dev instructions and code style rules |
| `.build/SAGE_SPEC.md` | Component specifications and schema contracts |
| `.build/BUILD_LOG.md` | All decisions made, bugs fixed, and known limitations |
| `sage-solver-core/sage_solver_core/models.py` | Authoritative schema definitions |
| `sage-solver-mcp/sage_solver_mcp/server.py` | MCP tool implementations |
| `ROADMAP.md` | Product vision for all future phases |
