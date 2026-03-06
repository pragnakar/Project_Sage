# SAGE Build Log

## Ship Summary — v0.1.0

**Date:** 2026-03-05
**Total tests:** 459 passing, 0 failing
**Total commits:** 32
**Packages:** sage-core 0.1.0, sage-mcp 0.1.0
**Bugs caught by verification (all phases):**
1. HiGHS float `inf` → `None` conversion (Phase 2)
2. Binary variable upper_bound set to 0 by mistake (Phase 2)
3. Scheduling consecutive_days constraint off-by-one (Phase 5)
4. MCP server entry point pointing to `__main__:main` instead of `server:main` (Phase 6)
5. `read_data()` called with bytes instead of filepath (Phase 6)
6. `ValidationError` not caught in handler direct calls (Phase 6)
7. Example xlsx column/sheet names not matching fileio.py parsers (Phase 7 verification)
8. `[project.urls]` in pyproject.toml captured `dependencies` as a URL key — broke `pip install -e` (Phase 7 verification)
9. `==` Excel formula issue — equality constraints in generic_lp must be split into `>=`/`<=` pair (Phase 7 verification)

**Lines of code (production):** 5,861 (11 files across sage-core + sage-mcp)
**Example problems:** portfolio (5 assets, optimal), nurse scheduling (8 nurses, intentionally infeasible), transport routing (3 warehouses → 5 stores, optimal $2,472), blending (6 ingredients, optimal $23.47/100kg)

---

## Session Tracker

| Session | Date | Phase | Duration | Credits Used (est.) | Notes |
|---------|------|-------|----------|---------------------|-------|
| 1       | 2026-03-05 | Phase 1 | Session 1 | — | Monorepo init, all schemas, 95 tests passing, merged to develop |
| 2       | 2026-03-05 | Phase 1 verification | Session 2 | — | All checks passed, deps verified, on develop, ready for Phase 2 |
| 3       | 2026-03-05 | Phase 2 | Session 3 | — | solver.py complete — LP/MIP/QP/IIS/sensitivity, 56/56 tests, merged to develop |
| 4       | 2026-03-05 | Phase 2 verification | Session 4 | — | 154/154 tests pass, float inf fix, integration tests, QP verified, ready for Phase 3 |
| 5       | 2026-03-05 | Phase 3 | Session 5 | — | builder.py complete — LP/MIP/Portfolio/Scheduling/validate_model, 94 tests, 248 total |
| 6       | 2026-03-05 | Phase 3 verification | Session 6 | — | solver binary-var ub=0 fix, test_full_pipeline.py (4 tests), 252 total, merged to develop |
| 7       | 2026-03-05 | Phase 4 | Session 7 | — | fileio.py complete — read/write/template/bridge, 68 tests, 320 total, merged to develop |
| 8       | 2026-03-05 | Phase 5 | Session 8 | — | explainer.py + relaxation.py complete — 62 new tests, 382 total; builder consecutive_days bug fix |
| 9       | 2026-03-05 | Phase 6 | Session 9 | — | sage-mcp complete — server.py (7 tools), local_io.py, __main__.py, 53 tests, 435 total; entry point fix |
| 10      | 2026-03-05 | Phase 7 | Session 10 | — | Polish + v0.1.0 — 4 example files, 19 smoke tests, README (174 lines), CONTRIBUTING.md, .gitignore, metadata; 454/454 tests; tagged v0.1.0 |
| 11      | 2026-03-05 | Phase 7 verification | Session 11 | — | Ship-readiness check: found and fixed 4 blockers (example column/sheet names, pyproject.toml [project.urls] TOML bug); 459/459 tests; pip install works; re-tagged v0.1.0 |

Update this table at the start and end of each session.

---

## Current Status

**Active Phase:** COMPLETE — v0.1.0 VERIFIED AND SHIPPED
**Active Branch:** main (tagged v0.1.0)
**Last Completed Task:** Phase 7 final verification — 4 ship blockers caught and fixed; 459/459 tests; pip install -e works; all 4 examples solve end-to-end; re-tagged v0.1.0
**Next Task:** Phase 8 (sage-cloud FastAPI) or PyPI publish
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
- [x] test_full_pipeline.py — 4 end-to-end tests (LP, MIP, Portfolio QP, Scheduling binary MIP)
- [x] fix(solver) — binary variable ub=0 now respected (skill/unavailability blocking)
- [x] Committed to feature/phase-3-builder
- [x] Merged to develop
- [x] **PHASE 3 COMPLETE & VERIFIED** — 252/252 tests, on develop

### Phase 4 — File I/O (Excel/CSV) (COMPLETE)
- [x] fileio.py — read_data (Excel + CSV, auto-detect, encoding fallback)
- [x] fileio.py — read_data_from_bytes (same from bytes buffer)
- [x] fileio.py — write_results_excel (5-sheet formatted workbook)
- [x] fileio.py — write_results_csv (flat CSV output)
- [x] fileio.py — generate_template (portfolio, scheduling, transport, generic_lp)
- [x] fileio.py — dataframe_to_model (LP/MIP/Portfolio/Scheduling bridge)
- [x] test_fileio.py — 68 tests: read, write, template, bridge, messy data, round-trip, error handling
- [x] Committed to feature/phase-4-fileio
- [x] Merged to develop
- [x] **PHASE 4 COMPLETE & VERIFIED** — 320/320 tests, on develop

### Phase 5 — Explainer & Relaxation (COMPLETE)
- [x] explainer.py — explain_result (brief/standard/detailed)
- [x] explainer.py — explain_infeasibility with quantitative demand/capacity
- [x] explainer.py — domain-specific language (portfolio/scheduling/LP/MIP)
- [x] explainer.py — no Markdown output enforced throughout
- [x] relaxation.py — suggest_relaxations with binary-search RHS bisection
- [x] relaxation.py — ranking by minimal disruption (relaxation_percent)
- [x] relaxation.py — variable bound relaxation support
- [x] relaxation.py — domain constraint context in explanations
- [x] test_explainer.py — 38 tests (detail levels, binding constraints, domain language, infeasibility, non-optimal statuses, integration)
- [x] test_relaxation.py — 24 tests (suggestion correctness, ranking, re-solve verification, full pipeline, edge cases)
- [x] Integration test — infeasible → explain → relax → re-solve → feasible (LP, scheduling, portfolio)
- [x] fix(builder) — consecutive_days RHS corrected: mc × S (was just mc, wrong for multi-shift)
- [x] Committed to feature/phase-5-intelligence
- [x] Merged to develop
- [x] **PHASE 5 COMPLETE & VERIFIED** — 382/382 tests, on develop

### Phase 6 — MCP Server (COMPLETE)
- [x] server.py — MCP server setup with official Python MCP SDK (mcp>=1.0), stdio transport
- [x] server.py — Tool: solve_optimization (LP/MIP/portfolio/scheduling, auto type detect)
- [x] server.py — Tool: read_data_file (Excel/CSV preview with sheet/row/column summary)
- [x] server.py — Tool: solve_from_file (read → build → solve → write _optimized.xlsx)
- [x] server.py — Tool: explain_solution (brief/standard/detailed from stored state)
- [x] server.py — Tool: check_feasibility (feasibility + IIS + relaxation suggestions)
- [x] server.py — Tool: generate_template (all 4 problem types)
- [x] server.py — Tool: suggest_relaxations (ranked from stored infeasible IIS)
- [x] server.py — ServerState stores last result/model/solver_input/iis for follow-up tools
- [x] server.py — Error handling: SAGEError, ValidationError, FileNotFoundError, unexpected all caught
- [x] local_io.py — resolve_path (~, relative→absolute, existence check), ensure_output_dir, output_path_for
- [x] __main__.py — entry point for python -m sage_mcp
- [x] claude_desktop_config.json — example Claude Desktop configuration (python + uvx variants)
- [x] test_server.py — 53 tests: tool registration, all 7 tools, state sequences, 8 error cases
- [x] fix: console_scripts entry point corrected to sage_mcp.server:main
- [x] Committed to feature/phase-6-mcp-server
- [x] Merged to develop
- [x] **PHASE 6 COMPLETE & VERIFIED** — 435/435 tests, on develop

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
| 8 | 2026-03-05 | Binary variable ub=0 must be passed to HiGHS via addVar, not just SolverInput | _build_highs() was hardcoding addVar(0.0, 1.0) for all binary vars. Skill/unavailability blocks (ub=0 in SolverInput) were silently ignored. Fix: use min(1.0, ub) in addVar. |
| 9 | 2026-03-05 | `ffill()` removed from Excel/CSV reader path | `df.ffill()` propagated description-row strings into blank data cells. openpyxl returns `None` for blank cells; ffill then filled those Nones with previous row's text. Template round-trips would fail. Removed `_forward_fill_headers()` from `_read_excel_bytes` and `_read_csv_bytes`. |
| 10 | 2026-03-05 | Percentage strings parsed as fractions in `_parse_number` | `"8%"` → `0.08`, `"5.5 %"` → `0.055`. Consistent with financial domain expectations where returns and allocations are entered as percentages in Excel but stored as fractions in the model. |
| 11 | 2026-03-05 | Column header normalisation deferred to parse time via `_normalise_cols()` | Column headers are preserved as-is at read time. `_normalise_cols()` maps `str(col).strip().lower().replace(" ","_") → actual_col` at parse time. This avoids mutating the DataFrames and allows callers to inspect original headers while still matching case/whitespace variants. |
| 12 | 2026-03-05 | Empty sheet check before `_normalise_cols()` in `_parse_portfolio` | `_strip_blank()` on a header-only DataFrame drops all columns (trivially all-null), causing `_normalise_cols()` to return `{}` and producing a misleading "Required column not found" error. Added `if len(assets_df) == 0: raise DataValidationError(...)` before any column resolution. |
| 13 | 2026-03-05 | explain_result domain dispatch uses isinstance priority order | PortfolioModel and SchedulingModel are checked before MIPModel/LPModel so domain-specific formatting (%, asset names, shift assignments) applies correctly. Falls through to LP/MIP generic formatting if neither matches. |
| 14 | 2026-03-05 | Binary search: exponential probe then 25-iteration bisection | Probe multiplies max(|rhs|, 1.0) by factors [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 100.0, 1000.0] to bound the feasible region, then bisection finds minimum relaxation. Returns None if probe fails (model too infeasible for single-constraint fix — this is a known limitation, not a bug). |
| 15 | 2026-03-05 | consecutive_days RHS corrected to mc × S for multi-shift models | Original builder used float(mc); the constraint sums assignments across all shifts in the window, so limit must be max_consecutive_days × num_shifts. For S=3 and mc=5, RHS was 5 (1.67 days) instead of 15 (5 days). Fix makes relaxation tractable for multi-shift infeasible models. |
| 16 | 2026-03-05 | MCP server stores last result in ServerState dataclass (module-level singleton) | ServerState holds last_result, last_model, last_solver_input, last_iis. Module-level (not per-request) because MCP stdio server has one process/one user — no concurrency. All follow-up tools (explain_solution, suggest_relaxations) read from this state. |
| 17 | 2026-03-05 | Tool responses formatted as plain text, not JSON or structured objects | MCP text content is what the LLM sees and relays to the user. Plain text explanations (same format as sage-core's explain_result) are more LLM-friendly than JSON. File paths included verbatim so the LLM can tell the user where output was saved. |
| 18 | 2026-03-05 | Model type auto-detected from JSON structure if problem_type not provided | Detection priority: explicit problem_type field → portfolio (has assets+covariance_matrix) → scheduling (has workers+shifts) → MIP (has non-continuous var_type) → LP. This lets the LLM omit problem_type for obvious cases. |
| 19 | 2026-03-05 | pyproject.toml console_scripts pointed to __main__:main instead of server:main | __main__.py imports main from server.py and re-executes it under __name__=="__main__", but the module-level name 'main' doesn't exist in __main__.py's namespace for pip script wrappers. Fixed to point directly to sage_mcp.server:main. |

---

## Roadblocks & Resolutions

| # | Date | Blocker | Status | Resolution |
|---|------|---------|--------|------------|
| 1 | 2026-03-05 | `getRanging()` returns tuple not HighsRanging directly | RESOLVED | Unpack: `ranging_status, ranging = h.getRanging()` |
| 2 | 2026-03-05 | `passHessian` format code 2 returned kError | RESOLVED | Format code 1 (triangular row-wise) works; confirmed via QP test |
| 3 | 2026-03-05 | `float('inf')` in ranging serializes to null in JSON | RESOLVED | Added `_safe_range_float()` in solver.py; changed type to `float \| None` in models.py |
| 4 | 2026-03-05 | Integration test: `x_limit` shadow price was 0 when var had explicit ub | RESOLVED | Remove variable upper bound; enforce via constraint only (matches CLAUDE.md known values) |
| 5 | 2026-03-05 | Scheduling binary vars with ub=0 (skill block) not respected by solver | RESOLVED | `_build_highs()` was hardcoding [0,1] for all binary vars. Fixed to use `min(1.0, ub)` so that ub=0 blocks are passed to HiGHS correctly. |
| 6 | 2026-03-05 | Template `Workers` sheet — `Unavailable_Shifts` showed description text instead of empty string | RESOLVED | `_forward_fill_headers()` (df.ffill()) in `_read_excel_bytes` propagated the description row into blank cells. Removed ffill calls from both Excel and CSV reader paths. |
| 7 | 2026-03-05 | `_strip_blank` drops all columns from header-only (empty data) DataFrame | RESOLVED | `dropna(axis=1, how="all")` on a DataFrame with zero rows drops all columns since every column is trivially all-null. Added explicit `if len(df) == 0` early-exit in `_parse_portfolio` before calling `_normalise_cols`. |
| 8 | 2026-03-05 | consecutive_days RHS wrong for multi-shift models — relaxation probe fails | RESOLVED | builder.py line 566: `float(mc)` → `float(mc * S)`. The rolling window constraint sums assignments across all S shifts, so RHS must be mc×S. Buggy RHS=mc made models far more infeasible than intended and blocked probe from ever finding feasibility for single-constraint relaxation. |
| 9 | 2026-03-05 | Deeply infeasible scheduling model (demand >> capacity) returns 0 relaxation suggestions | KNOWN LIMITATION | When demand exceeds total system capacity (e.g., 28 required assignments vs 18 max capacity), no single constraint relaxation can restore feasibility. suggest_relaxations returns [] correctly; this is documented behavior, not a bug. |
| 10 | 2026-03-05 | console_scripts entry point sage_mcp.__main__:main fails for pip-installed script | RESOLVED | __main__.py imports main but doesn't define it as a module-level name; pip's script wrapper calls `__main__.main()` which fails with AttributeError. Fixed pyproject.toml to point to `sage_mcp.server:main` directly. |

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
| mcp     | 1.26.0  | verified | Phase 6 — stdio transport, 7 tools registered, anyio/httpx/starlette installed as deps |
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
| 3 ver | 4             | 4             | 0             | Full pipeline: LP, MIP knapsack, Portfolio QP, Scheduling binary MIP (end-to-end) |
| 4     | 68            | 68            | 0             | Excel/CSV read, write results, templates, DataFrame→model, messy data, round-trip, errors |
| 5     | 62            | 62            | 0             | explainer: 38 tests (detail levels, domain language, infeasibility, integration); relaxation: 24 tests (suggestions, ranking, re-solve, pipeline, edge cases) |
| 6     | 53            | 53            | 0             | MCP server: 7 tool registration, all tool handlers, state sequences, 8 error cases, conversation simulations |
| Total | 435           | 435           | 0             | All phases combined (382 sage-core + 53 sage-mcp) |
| 7     |               |               |               |       |
| 6     |               |               |               |       |
| 7     |               |               |               |       |
