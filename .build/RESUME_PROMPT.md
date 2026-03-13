# SAGE — Resume Development Prompt for Claude Opus

> Paste this entire document into a new Claude Opus conversation to resume development.

---

## Context

You are resuming development of **SAGE** (Solver-Augmented Grounding Engine), a published open-source MCP server that gives LLMs certified mathematical optimization capabilities via the HiGHS solver.

**Repo:** https://github.com/pragnakar/Project_Sage
**Current version:** sage-solver-core 0.1.3 + sage-solver-mcp 0.1.3
**Tests:** 470 passing, 0 failing (393 core + 77 MCP)
**Published:** PyPI (`pip install sage-solver-mcp`), MCP Registry, Claude Desktop Extensions

---

## Terminology — Two Distinct Naming Systems

| Term | Meaning |
|---|---|
| **Stage N** | Internal build pipeline step (historical, all complete) |
| **Roadmap Phase N** | Strategic product vision milestone |
| **v0.x.y** | Semantic version of shipped packages |

Roadmap Phase 1 (local MCP server) = **COMPLETE** as v0.1.3. Next: Roadmap Phase 2 (sage-solver-cloud).

---

## What Was Built — All 7 Build Stages Complete

| Stage | File | Tests | Status |
|---|---|---|---|
| Stage 1 | `models.py` — Pydantic schemas | 95 | COMPLETE |
| Stage 2 | `solver.py` — HiGHS LP/MIP/QP/IIS/sensitivity | 59 | COMPLETE |
| Stage 3 | `builder.py` — JSON → SolverInput | 98 | COMPLETE |
| Stage 4 | `fileio.py` — Excel/CSV read/write, templates | 68 | COMPLETE |
| Stage 5 | `explainer.py` + `relaxation.py` — IIS + narration | 62 | COMPLETE |
| Stage 6 | `server.py` — 7 MCP tools + `local_io.py` | 53 | COMPLETE |
| Stage 7 | `examples/`, README, CONTRIBUTING, packaging | 24 | COMPLETE |
| Post-Stage 7 | MCP transport fix, repo cleanup | 35 | COMPLETE |
| **Total** | | **470** | **v0.1.3 SHIPPED** |

---

## Repo Structure

```
Project_Sage/
├── CLAUDE.md                    ← @.build/AGENT.md (one-liner import)
├── README.md                    ← Public docs with 5 usage examples
├── ROADMAP.md                   ← 5-phase product vision
├── .build/
│   ├── AGENT.md                 ← FULL DEV INSTRUCTIONS — read first
│   ├── SAGE_SPEC.md             ← Architecture spec and component contracts
│   ├── BUILD_LOG.md             ← Stage-by-stage history + decisions
│   └── HANDOFF.md               ← Full handoff report
├── sage-solver-core/            ← Pure engine (NO filesystem, NO HTTP)
│   └── sage_solver_core/
│       ├── models.py
│       ├── solver.py
│       ├── builder.py
│       ├── fileio.py
│       ├── explainer.py
│       └── relaxation.py
├── sage-solver-mcp/             ← Local MCP server
│   └── sage_solver_mcp/
│       ├── server.py            ← 7 MCP tools
│       ├── local_io.py          ← Filesystem bridge
│       └── __main__.py
├── sage-solver-cloud/           ← PLACEHOLDER ONLY — stubs, do not build yet
└── examples/                    ← Ready-to-use Excel/CSV files
```

---

## Critical Design Rules — Never Violate

1. `sage-solver-core` **never touches the filesystem**. Functions receive DataFrames, bytes, or model objects.
2. Every solver call returns a `SolverResult`. Never expose raw HiGHS output.
3. All errors are `SAGEError` subclasses with `details: dict` and `suggestions: list[str]`. No bare exceptions.
4. Infeasibility is a first-class result — compute IIS, explain, suggest relaxations.
5. No PuLP. Direct `highspy` bindings only.
6. No `print()`. Return structured data or `logging`.
7. Do not use `WidthType.PERCENTAGE` in Excel formatting (breaks Google Docs).
8. Do not build `sage-solver-cloud` yet — placeholder only.

---

## 7 MCP Tool Names (fixed — do not rename)

```
solve_optimization     read_data_file     solve_from_file
explain_solution       check_feasibility  generate_template
suggest_relaxations
```

---

## Key Technical Details

**Pydantic transport quirks (v0.1.2+):** All top-level models have `model_validator(mode="before")` that:
- Calls `json.loads()` on string-typed nested fields (`variables`, `constraints`, `objective`, `assets`, `covariance_matrix`, `workers`, `shifts`)
- Accepts aliases: `lb`/`ub` → `lower_bound`/`upper_bound`; `expression` → `coefficients`; `operator` → `sense`; `direction` → `sense`

**Model type auto-detection order:** explicit `problem_type` → portfolio → scheduling → mip → lp

**Bugs fixed — do not re-introduce:**
- Binary `ub=0` → pass `min(1.0, ub)` to HiGHS `addVar` (not hardcoded 1.0)
- Scheduling consecutive_days RHS = `max_consecutive_days × num_shifts`
- `path.resolve()` must come AFTER existence check (macOS firmlink issue)
- `default_output_dir()` falls back to `Path.home()` when CWD is `/`
- Removed `ffill()` from Excel reader (propagated headers into data cells)
- `console_scripts` → `sage_solver_mcp.server:main` (not `__main__:main`)

---

## Tech Stack

| Component | Library | Installed Version |
|---|---|---|
| Solver LP/MIP/QP | `highspy` | 1.13.1 |
| Solver CP | `ortools` | 9.15.6755 |
| Schemas | `pydantic` | 2.12.5 |
| Data I/O | `pandas` | 3.0.1 |
| Excel | `openpyxl` | 3.1.5 |
| Numerics | `numpy` | 2.4.2 |
| MCP server | `mcp` | 1.26.0 |
| Python | | 3.11+ |

---

## Dev Setup

```bash
git clone https://github.com/pragnakar/Project_Sage && cd Project_Sage
pip install -e sage-solver-core/ && pip install -e sage-solver-mcp/
cd sage-solver-core && pytest tests/ -v   # expect 393 passed
cd ../sage-solver-mcp && pytest tests/ -v # expect 77 passed
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "sage": { "command": "/opt/homebrew/bin/uvx", "args": ["sage-solver-mcp"] }
  }
}
```

---

## What to Build Next — Roadmap Phase 2: sage-solver-cloud

FastAPI server so ChatGPT and any SSE-capable LLM can call SAGE remotely.

```
sage-solver-cloud/
└── sage_solver_cloud/
    ├── api.py           ← FastAPI; HTTP routes mirror the 7 MCP tools
    ├── auth.py          ← API key auth (header-based)
    ├── jobs.py          ← Async job manager (long-running solves)
    ├── storage.py       ← S3/GCS file bridge
    ├── mcp_transport.py ← Remote MCP via SSE (unlocks ChatGPT)
    └── web/             ← Interactive result UI (Jinja2)
```

**Constraints:**
- `sage_solver_cloud` imports `sage-solver-core` — never re-implements solver logic
- Multi-tenant: isolated state per request (no module-level `ServerState`)
- Async-first: long-running solves must not block the event loop
- SSE transport, not stdio
- API key auth (V1 is auth-free — V2 is not)

---

## Before Writing Any Code

1. Run tests to confirm green baseline
2. Read `.build/AGENT.md` — rules, style, constraints
3. Read `.build/SAGE_SPEC.md` sections 2–3 for component contracts
4. Read `ROADMAP.md` Roadmap Phase 2 section for full feature scope
5. Read `.build/HANDOFF.md` for exhaustive details on all decisions and limitations
