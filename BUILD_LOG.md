# SAGE Build Log

## Session Tracker

| Session | Date | Phase | Duration | Credits Used (est.) | Notes |
|---------|------|-------|----------|---------------------|-------|
| 1       | 2026-03-05 | Phase 1 | Session 1 | — | Monorepo init, all schemas, 95 tests passing, merged to develop |
| 2       | 2026-03-05 | Phase 1 verification | Session 2 | — | All checks passed, deps verified, on develop, ready for Phase 2 |
| 3       | 2026-03-05 | Phase 2 | Session 3 | — | solver.py complete — LP/MIP/QP/IIS/sensitivity, 56/56 tests, merged to develop |
| 4       | 2026-03-05 | Phase 2 verification | Session 4 | — | 154/154 tests pass, float inf fix, integration tests, QP verified, ready for Phase 3 |
| 5       | 2026-03-05 | Phase 3 | Session 5 | — | builder.py complete — LP/MIP/Portfolio/Scheduling/validate_model, 94 tests, 248 total |

Update this table at the start and end of each session.

---

## Current Status

**Active Phase:** Phase 3 COMPLETE — awaiting review
**Active Branch:** feature/phase-3-builder (ready to merge)
**Last Completed Task:** Phase 3 — builder.py + test_builder.py, 94 new tests, 248 total passing
**Next Task:** Phase 4 — File I/O (fileio.py)
**Blockers:** None

---

## Phase Progress

### Phase 1 — Project Structure & Schemas
- [x] Monorepo structure created
- [x] pyproject.toml files (sage-core, sage-mcp, sage-cloud placeholder)
- [x] ruff.toml and .pre-commit-config.yaml
- [x] sage_core/__init__.py with version
- [x] models.py — LP schemas (LPVariable, LinearConstraint, LinearObjective, LPModel)
- [x] models.py — MIP schemas (MIPVariable, MIPModel)
- [x] models.py — Portfolio schemas (Asset, PortfolioConstraints, PortfolioModel)
- [x] models.py — Scheduling schemas (Worker, Shift, SchedulingModel)
- [x] models.py — Solver schemas (SolverInput, SolverResult, IISResult)
- [x] models.py — Error hierarchy (SAGEError, DataValidationError, ModelBuildError, SolverError, FileIOError)
- [x] test_models.py — all tests written and passing (95/95)
- [x] Committed to feature/phase-1-project-structure
- [x] **PHASE 1 COMPLETE** — awaiting review

### Phase 2 — Solver Wrapper (VERIFIED)
- [x] solver.py — HiGHS LP wrapper
- [x] solver.py — HiGHS MIP wrapper
- [x] solver.py — QP mode for quadratic objectives
- [x] solver.py — Sensitivity extraction (shadow prices, reduced costs, ranges)
- [x] solver.py — IIS computation
- [x] solver.py — Time limit and parameter handling
- [x] test_solver.py — LP optimal test
- [x] test_solver.py — MIP optimal test
- [x] test_solver.py — Infeasible + IIS test
- [x] test_solver.py — Unbounded test
- [x] test_solver.py — Sensitivity test
- [x] test_solver.py — Timeout test
- [x] Committed to feature/phase-2-solver
- [x] **PHASE 2 COMPLETE** — merged to develop
- [x] **PHASE 2 VERIFIED** — 154/154 tests, float inf fix, integration + QP check done

### Phase 3 — Model Builder (COMPLETE)
- [x] builder.py — build_from_lp (var bounds, constraint matrix, obj, ModelBuildError)
- [x] builder.py — build_from_mip (type mapping, binary bounds, solver params)
- [x] builder.py — build_from_portfolio (Markowitz QP: negated returns, 2λCov, allocation + sector constraints, forbidden assets, symmetry check)
- [x] builder.py — build_from_scheduling (binary MIP: coverage, max hours, consecutive days, unavailability, skill matching)
- [x] builder.py — validate_model (empty constraints, unused vars, unbounded obj, magnitude ratio, duplicates)
- [x] test_builder.py — 22 LP/MIP unit tests
- [x] test_builder.py — 22 Portfolio unit tests
- [x] test_builder.py — 21 Scheduling unit tests
- [x] test_builder.py — 11 validate_model tests
- [x] test_builder.py — 9 integration tests (LP, MIP, portfolio weights, scheduling coverage, 2× infeasible)
- [x] Committed to feature/phase-3-builder
- [x] **PHASE 3 COMPLETE** — awaiting review

### Phase 4 — File I/O (Excel/CSV)
- [ ] fileio.py — read_data (Excel + CSV)
- [ ] fileio.py — read_data_from_bytes
- [ ] fileio.py — write_results_excel (formatted multi-sheet)
- [ ] fileio.py — write_results_csv
- [ ] fileio.py — generate_template (portfolio, scheduling, transport, generic_lp)
- [ ] fileio.py — dataframe_to_model (messy data handling)
- [ ] test fixtures — test Excel files in tests/fixtures/
- [ ] test_fileio.py — round-trip test
- [ ] test_fileio.py — messy data test
- [ ] test_fileio.py — error handling test
- [ ] test_fileio.py — write results test
- [ ] Committed to feature/phase-4-fileio
- [ ] **PHASE 4 COMPLETE** — awaiting review

### Phase 5 — Explainer & Relaxation
- [ ] explainer.py — explain_result (brief/standard/detailed)
- [ ] explainer.py — explain_infeasibility
- [ ] explainer.py — domain-specific language (portfolio vs scheduling)
- [ ] relaxation.py — suggest_relaxations with re-solving
- [ ] relaxation.py — ranking by minimal disruption
- [ ] test_explainer.py — detail level tests
- [ ] test_explainer.py — infeasibility explanation test
- [ ] test_relaxation.py — suggestion correctness
- [ ] test_relaxation.py — re-solve verification
- [ ] Integration test — infeasible → explain → relax → re-solve → feasible
- [ ] Committed to feature/phase-5-intelligence
- [ ] **PHASE 5 COMPLETE** — awaiting review

### Phase 6 — MCP Server
- [ ] server.py — MCP server setup with official SDK
- [ ] server.py — Tool: solve_optimization
- [ ] server.py — Tool: read_data_file
- [ ] server.py — Tool: solve_from_file
- [ ] server.py — Tool: explain_solution
- [ ] server.py — Tool: check_feasibility
- [ ] server.py — Tool: generate_template
- [ ] server.py — Tool: suggest_relaxations
- [ ] server.py — Server state (last result storage)
- [ ] server.py — Error handling (never crash)
- [ ] local_io.py — path resolution, file read/write
- [ ] __main__.py — entry point
- [ ] claude_desktop_config.json — example config
- [ ] test_server.py — tool input validation
- [ ] test_server.py — solve flow
- [ ] test_server.py — error handling
- [ ] Committed to feature/phase-6-mcp-server
- [ ] **PHASE 6 COMPLETE** — awaiting review

### Phase 7 — Examples, Docs & Polish
- [ ] examples/portfolio_5_assets.xlsx
- [ ] examples/nurse_scheduling.xlsx
- [ ] examples/transport_routing.xlsx
- [ ] examples/blending_problem.csv
- [ ] End-to-end smoke test on all examples
- [ ] README.md
- [ ] CONTRIBUTING.md
- [ ] .gitignore
- [ ] pyproject.toml metadata finalized
- [ ] Full installation flow verified
- [ ] All tests passing across both packages
- [ ] Merged to develop, merged to main, tagged v0.1.0
- [ ] **PHASE 7 COMPLETE — MVP SHIPPED**

---

## Design Decisions Log

Record any decision made during implementation that deviates from or clarifies the spec.

| # | Date | Decision | Rationale |
|---|------|----------|-----------|
| 1 | 2026-03-05 | `objective_ranges`/`rhs_ranges` bounds typed as `float \| None` | HiGHS returns kHighsInf for unbounded ranging; `float('inf')` is not valid JSON. `None` cleanly represents "unbounded in this direction" and round-trips via Pydantic. |
| 2 | 2026-03-05 | QP ranging returns `None` (not populated) | HiGHS does not support ranging for QP; only LP. Confirmed via QP smoke test. |
| 3 | 2026-03-05 | `_safe_range_float` clips values >= 1e29 or NaN to `None` | Catches both HiGHS kHighsInf (~1e30) and Python float('inf') uniformly. |
| 4 | 2026-03-05 | Portfolio builder uses `minimize` sense (not `maximize`) | HiGHS QP works best with minimize + positive semi-definite Q. We negate returns (c_i = -r_i) and use Q = 2λCov. Objective value = negative Markowitz utility; weights are correct. |
| 5 | 2026-03-05 | Scheduling consecutive-days encoded as rolling window sum constraint | True consecutive-days MIP encoding requires auxiliary binary vars. Rolling window `sum_{d'=d}^{d+mc} sum_s x[w,s,d'] <= mc` is a valid relaxation and catches violations without extra variables. |
| 6 | 2026-03-05 | Unavailability and skill restrictions encoded as variable upper bounds (ub=0) | Cleaner than adding equality constraints; reduces model size; HiGHS handles bound reductions efficiently. |
| 7 | 2026-03-05 | validate_model accepts LPModel \| MIPModel (not Portfolio/Scheduling) | Portfolio and Scheduling have their own domain-specific validation in their builders. validate_model targets generic LP/MIP models. |

---

## Roadblocks & Resolutions

| # | Date | Blocker | Status | Resolution |
|---|------|---------|--------|------------|
| 1 | 2026-03-05 | `getRanging()` returns tuple not HighsRanging directly | RESOLVED | Unpack: `ranging_status, ranging = h.getRanging()` |
| 2 | 2026-03-05 | `passHessian` format code 2 returned kError | RESOLVED | Format code 1 (triangular row-wise) works; confirmed via QP test |
| 3 | 2026-03-05 | `float('inf')` in ranging serializes to null in JSON | RESOLVED | Added `_safe_range_float()` in solver.py; changed type to `float \| None` in models.py |
| 4 | 2026-03-05 | Integration test: `x_limit` shadow price was 0 when var had explicit ub | RESOLVED | Remove variable upper bound; enforce via constraint only (matches CLAUDE.md known values) |

---

## Dependencies Installed

Track what was installed and any issues encountered.

| Package | Version | Status | Notes |
|---------|---------|--------|-------|
| highspy | 1.13.1  | verified | HiGHS solver v1.13.1, ARM Mac OK, h.version() confirmed |
| ortools | 9.15.6755 | verified | CP-SAT + LP/MIP wrappers import OK |
| pandas  | 3.0.1   | verified | Phase 1 + ortools dep |
| openpyxl| 3.1.5   | verified | Phase 1 dev install succeeded |
| pydantic| 2.12.5  | verified | All 95 schema tests pass |
| numpy   | 2.4.2   | verified | Phase 1 + highspy dep |
| mcp     |         | pending | sage-mcp not yet installed |
| ruff    | >=0.1   | installed | Configured via ruff.toml |

---

## Test Results

Update after each phase.

| Phase | Tests Written | Tests Passing | Tests Failing | Notes |
|-------|---------------|---------------|---------------|-------|
| 1     | 95            | 95            | 0             | All schema validation, serialization, edge case tests pass |
| 2     | 56            | 56            | 0             | LP/MIP/infeasible/unbounded/sensitivity/timeout all pass |
| 2 ver | 3             | 3             | 0             | Cross-phase integration: LP roundtrip, infeasible IIS, JSON completeness |
| 3     | 94            | 94            | 0             | LP/MIP/Portfolio/Scheduling build + integration tests (weights sum, coverage, infeasible) |
| Total | 248           | 248           | 0             | All phases combined |
| 4     |               |               |               |       |
| 5     |               |               |               |       |
| 6     |               |               |               |       |
| 7     |               |               |               |       |
