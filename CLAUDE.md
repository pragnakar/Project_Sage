# CLAUDE.md — Instructions for Claude Code

## Project

SAGE (Solver-Augmented Grounding Engine) — an MCP server that gives LLMs certified mathematical optimization capabilities via open-source solvers.

## Read First

Before writing any code, read `SAGE_SPEC.md` in this repo. It contains the complete architecture, component specs, schemas, and build sequence. That document is the source of truth.

## Architecture

Three packages in a monorepo:

- **sage-solver-core/** — Pure logic. Solver wrappers, model building, file I/O, result explanation. NO deployment opinions. NO file system calls. NO print statements. Takes Python objects in, returns Python objects out.
- **sage-solver-mcp/** — Local MCP server. Thin wrapper. Imports sage-solver-core, exposes MCP tools, bridges local filesystem. This is V1.
- **sage-cloud/** — DO NOT BUILD YET. Placeholder structure only.

## Tech Stack

- Python 3.11+
- HiGHS via `highspy` — primary solver (LP, MIP, QP)
- OR-Tools via `ortools` — secondary solver (constraint programming)
- Pydantic v2 — all schemas
- pandas + openpyxl — Excel/CSV I/O
- MCP Python SDK — MCP server implementation
- pytest — testing

## Build Order

Follow this sequence. Do not skip ahead.

1. Set up monorepo structure with all three package directories and pyproject.toml files
2. Implement `sage-solver-core/sage_solver_core/models.py` — all Pydantic schemas
3. Implement `sage-solver-core/sage_solver_core/solver.py` — HiGHS wrapper, SolverResult extraction
4. Write tests for solver against known LP/MIP solutions
5. Implement `sage-solver-core/sage_solver_core/builder.py` — portfolio→QP, scheduling→MIP, validation
6. Implement `sage-solver-core/sage_solver_core/fileio.py` — Excel/CSV read/write, templates, messy data handling
7. Write tests for file I/O round-trips
8. Implement `sage-solver-core/sage_solver_core/explainer.py` — result narration, sensitivity narrative
9. Implement `sage-solver-core/sage_solver_core/relaxation.py` — IIS extraction, relaxation suggestions
10. Implement `sage-solver-mcp/sage_solver_mcp/server.py` — all 7 MCP tools
11. Create example Excel/CSV files in `examples/`
12. End-to-end integration tests
13. README.md, packaging, entry points

## Critical Design Rules

- **sage-solver-core functions NEVER access the filesystem directly.** They receive DataFrames, bytes, or model objects as arguments. The MCP layer or cloud layer handles file access.
- **Every solver call returns a SolverResult** — never raw HiGHS output. The SolverResult includes status, variable values, sensitivity data, and IIS if infeasible.
- **All errors are structured** — SAGEError subclasses with details dict and suggestions list. Never bare exceptions.
- **Infeasibility is a first-class result, not an error.** When a model is infeasible, compute IIS, explain why, suggest relaxations.
- **Excel templates must be analyst-friendly** — column headers with descriptions, example data, data validation, instructions sheet.

## Code Style

- Type hints everywhere
- Docstrings on all public functions
- Pydantic models for all data structures crossing boundaries
- No global state
- No print() — return structured data or use logging module
- Tests alongside implementation (write test → implement → verify)

## Testing

Run tests: `cd sage-solver-core && pytest tests/ -v`

Known test values to verify solver correctness:

**Simple LP:**
- Maximize 3x + 2y subject to x + y <= 10, x <= 6, y <= 8, x,y >= 0
- Optimal: x=6, y=4, objective=26

**Simple MIP:**
- Same as above but x, y integer
- Optimal: x=6, y=4, objective=26 (same in this case)

**Infeasible LP:**
- x + y <= 5, x + y >= 10, x,y >= 0
- Status: infeasible, IIS should contain both constraints

## MCP Tool Names

These exact tool names must be used in the MCP server:
1. `solve_optimization`
2. `read_data_file`
3. `solve_from_file`
4. `explain_solution`
5. `check_feasibility`
6. `generate_template`
7. `suggest_relaxations`

## Dependencies

```
# sage-solver-core
highspy>=1.7.0
ortools>=9.9
pandas>=2.1
openpyxl>=3.1
pydantic>=2.5
numpy>=1.24

# sage-solver-mcp (additional)
mcp>=1.0
```

## What NOT To Do

- Do not use PuLP — direct highspy bindings are cleaner
- Do not build sage-cloud yet — structure only
- Do not use WidthType.PERCENTAGE in Excel formatting — breaks in Google Docs
- Do not build a web UI — the LLM IS the UI
- Do not add authentication to V1 — it's local only
- Do not write freeform natural language → model translation — the LLM fills structured schemas, SAGE validates and solves
