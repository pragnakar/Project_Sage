# SAGE — Back-to-Work Specification

## Resume Guide for v0.2.0 Development

**Prepared:** 2026-03-19
**Replaces:** Previous v0.2 cloud spec (FastAPI SaaS architecture — scrapped)
**Current state:** sage-solver-core 0.1.3, sage-solver-mcp 0.1.3, sage-solver-cloud 0.3.0 (Groot scaffold, running), 470 tests passing
**Terminology:** Vision has **phases** (ROADMAP.md). Build has **stages** (BUILD_LOG.md). Release has **versions** (PyPI).

---

## 1. What Changed and Why

The original v0.2 spec planned a hosted FastAPI server (auth, S3, job queue, web UI, SSE transport for ChatGPT). That architecture is scrapped for three reasons:

1. **Wrong cost model.** Running solver jobs on your own server for users who don't yet exist is expensive before any traction.
2. **Wrong customer.** Light users (ChatGPT curiosity) don't pay. Heavy users (enterprise, multi-day solves) have entrenched stacks and won't switch.
3. **Already solved differently.** Groot, forked as sage-solver-cloud, already provides persistence, page hosting, blob storage, and a live dashboard. The integration primitive (the blob) already exists. Nothing new needs to be hosted.

**The new model:** sage-solver-cloud runs locally on the user's machine (same as sage-solver-mcp). It is not a SaaS server. It is a local persistence, dashboard, and async job runtime — accessible to Claude via sage-solver-mcp and to the user via browser. The blob is the universal integration primitive for downstream workflows.

---

## 2. Current State of Each Package

| Package | Version | State |
|---|---|---|
| sage-solver-core | 0.1.3 | Complete. 393 tests. All modules shipped. |
| sage-solver-mcp | 0.1.3 | Complete. 77 tests. 7 MCP tools. Local stdio only. |
| sage-solver-cloud | 0.3.0 | Groot scaffold running at dynamic port. 3 pages (sage-dashboard, sage-artifacts, sage-jobs). No solver API yet. sage-jobs returns 400 — UI exists but no backend. |

**sage-solver-cloud location:** `sage-solver-cloud/` in the monorepo. Running at a dynamic port (e.g. 54734). Port changes on each start.

---

## 3. Architecture

```
Claude Desktop / Claude Code / Cursor
        │
        │ MCP stdio
        │
┌───────▼──────────────────────────────┐
│         sage-solver-mcp              │
│  (discovers cloud via ~/.sage/cloud.json)  │
│                                      │
│  Instant jobs → solve inline         │
│  Fast/Background → submit to cloud   │
│  All results → persist to cloud blob │
└───────┬──────────────────────────────┘
        │ HTTP  (localhost, dynamic port)
        │
┌───────▼──────────────────────────────┐
│       sage-solver-cloud              │
│       (Groot fork, local)            │
│                                      │
│  /api/jobs  ← job lifecycle API      │
│  Solver runner (background process)  │
│  Blob store  ← all job state         │
│  sage-jobs page ← live dashboard     │
└───────┬──────────────────────────────┘
        │
┌───────▼──────────────────────────────┐
│      sage-solver-core                │
│      (unchanged, pure logic)         │
│  classifier · solver · builder       │
│  explainer · relaxation · fileio     │
└──────────────────────────────────────┘
```

**Key principle:** sage-solver-core never changes between layers. sage-solver-cloud calls the same functions sage-solver-mcp calls. The cloud layer adds async execution, blob persistence, and a browser UI — not intelligence.

---

## 4. Port Discovery

sage-solver-cloud writes a discovery file at startup:

```python
# Written by sage-solver-cloud on startup, deleted on shutdown
~/.sage/cloud.json
{
  "url": "http://localhost:54734",
  "port": 54734,
  "pid": 12345,
  "version": "0.3.0",
  "started_at": "2026-03-19T18:00:00"
}
```

sage-solver-mcp reads this file lazily on each request, hits `GET {url}/health` to verify the cloud is alive, and falls back gracefully if it isn't. Zero configuration. Works regardless of what port the OS assigned. ~30 lines total.

---

## 5. Problem Classifier

**Location:** `sage-solver-core/sage_solver_core/classifier.py` — pure function, no solver calls.

**Output:** Three tiers.

| Tier | Expected solve time | Routing |
|---|---|---|
| `instant` | < 2 seconds | Solve inline in sage-solver-mcp, then persist blob |
| `fast` | 2 – 60 seconds | Solve inline, write progress to blob while running |
| `background` | > 60 seconds | Submit to cloud immediately, return task_id, close chat |

**Classification signals:**
- `n_binary > 500` or `n_vars > 50,000` → background
- `n_binary > 100` or explicit `time_limit > 60s` → fast
- Pure LP, QP/portfolio, small MIP → instant
- Scheduling problems → fast by default (can escalate to background)
- 50ms probe solve: HiGHS LP relaxation bound returned immediately gives scale signal

**All three tiers write a blob to sage-solver-cloud.** The blob is the permanent record for every solve — sensitivity analysis, follow-up questions, assumed constraint refinement all work because the blob exists. The module-level `ServerState` singleton in sage-solver-mcp is eliminated entirely.

---

## 6. Job Blob Schema

**Key format:** `jobs/{task_id}` (e.g. `jobs/mip-7b2c`)
**Public endpoint:** `GET /blobs/jobs/{task_id}` — returns the full blob as JSON. This is the daisy-chain integration primitive.

```python
JobBlob = {
    # Identity
    "schema_version": "2.0",
    "task_id": str,               # e.g. "mip-7b2c"
    "problem_name": str,
    "problem_type": "LP" | "MIP" | "QP" | "PORTFOLIO" | "SCHEDULING",
    "complexity_tier": "instant" | "fast" | "background",
    "description": str | None,

    # Lifecycle
    "status": "queued" | "running" | "paused" | "complete" | "failed" | "stalled" | "deleted",
    "created_at": str,            # ISO datetime
    "started_at": str | None,
    "completed_at": str | None,
    "deleted_at": str | None,
    "deleted_by": "user_ui" | "user_chat" | None,

    # Model dimensions
    "n_vars": int,
    "n_constraints": int,
    "n_binary": int,

    # Live fields — updated by solver callback every N seconds
    "elapsed_seconds": float,
    "gap_pct": float | None,
    "best_bound": float | None,
    "best_incumbent": float | None,
    "node_count": int | None,
    "stall_detected": bool,
    "pause_requested": bool,      # set by API, polled by callback

    # bound_history: each entry is [elapsed_seconds, dual_bound, primal_incumbent, event_type]
    # event_type: "progress" | "incumbent" | "pause" | "resume" | "complete"
    "bound_history": list,

    # Solution — populated when complete or when incumbent exists
    "incumbent_solution": dict | None,    # variable_name → value
    "solution": dict | None,             # full SolverResult when complete
    "explanation": str | None,           # plain-language narrative

    # Assumed constraints — see Stage 12
    "assumed_constraints": list | None,

    # Notifications
    "clickup_task_id": str | None,
    "notified_at": str | None,
    "output_webhooks": list,             # URLs to POST on completion
}
```

---

## 7. HiGHS Callback Integration

**Current state:** `solver.py` calls `h.run()` — blocking, no callbacks, no intermediate results.

**Required change:** Register two callbacks before `h.run()`:

### Callback 1 — `kCallbackMipSolution`
Fires on every new integer-feasible incumbent.
- Reads: `output.mip_solution` (full variable values), `output.mip_primal_bound`, `output.mip_dual_bound`, `output.mip_gap`, `output.mip_node_count`, `output.running_time`
- Writes: updates `incumbent_solution` and appends `[elapsed, bound, incumbent, "incumbent"]` to `bound_history` in the blob

### Callback 2 — `kCallbackMipInterrupt`
Heartbeat — fires on B&B node intervals regardless of incumbents.
- Time-checks: if > N seconds since last blob write, write a `"progress"` entry
- Pause-checks: reads `pause_requested` from blob; if True, sets `cbdata.user_interrupt = True`
- Stall-detection: if `bound_history` shows < 0.01% improvement over last 90 minutes, sets `stall_detected: True`

### Resume (warm start)
On resume, load saved `incumbent_solution` into `HighsCallbackInput.user_has_solution = True` and `user_solution = [...]`. HiGHS establishes the incumbent immediately. Not a true B&B tree continuation (HiGHS cannot serialize the tree), but starts with a known-good solution and closes the remaining gap. For practical long-running jobs the distinction is immaterial.

**Important:** These callbacks live in the solver runner process, not in sage-solver-mcp. The runner is a subprocess; the callbacks write to the blob via HTTP. sage-solver-mcp is not involved during solve execution.

---

## 8. Build Stages (v0.2.0)

### Stage 8 — Port Discovery + Blob Schema
- `sage-solver-cloud`: write `~/.sage/cloud.json` on startup, delete on shutdown
- `sage-solver-cloud`: define JobBlob schema via `/api/tools/define_schema`
- `sage-solver-mcp`: `_find_cloud()` helper that reads discovery file + health check
- Tests: discovery roundtrip, graceful fallback when cloud is absent

### Stage 9 — Problem Classifier
- `sage-solver-core/classifier.py`: `classify(model) → ClassificationResult(tier, reasoning, estimated_seconds, signals)`
- Pure function. No solver calls for LP/QP. 50ms probe for ambiguous MIP.
- Tests: known models classified correctly, probe timeout handled

### Stage 10 — HiGHS Callbacks + Solver Runner
- `sage-solver-core/solver.py`: add `solve_with_callbacks(solver_input, blob_writer_fn)` alongside existing `solve()`
- `sage-solver-cloud/runner.py`: background process. Reads queued jobs, calls `solve_with_callbacks`, writes to blob on each callback.
- `ProcessPoolExecutor` — HiGHS is CPU-bound, must not block the event loop
- Tests: callback fires on incumbent, pause flag stops solve, progress entries appear in bound_history

### Stage 11 — sage-solver-cloud Jobs API
- `POST /api/jobs` — submit job (returns task_id immediately)
- `GET /api/jobs` — list jobs with optional status/type filters
- `GET /api/jobs/{task_id}` — get full job blob
- `GET /api/jobs/{task_id}/progress` — lightweight: gap, elapsed, latest bound_history entry
- `POST /api/jobs/{task_id}/pause` — sets `pause_requested: True` in blob
- `POST /api/jobs/{task_id}/resume` — warm-starts solver runner with saved incumbent
- `DELETE /api/jobs/{task_id}` — soft delete only: sets `status: "deleted"`, records `deleted_at` and `deleted_by`. Blob is never removed.
- Tests: job lifecycle (queued→running→complete), pause/resume roundtrip, soft delete, progress polling

### Stage 12 — sage-solver-mcp Cloud Integration
- Remove `ServerState` singleton — state lives in blob
- On every solve: classify first, then route by tier
- All tiers: create blob in cloud before solve, update on completion
- Background tier: submit to cloud, return `task_id` to user immediately
- New MCP tools:
  - `pause_job(task_id)` → calls `POST /api/jobs/{id}/pause`
  - `resume_job(task_id)` → calls `POST /api/jobs/{id}/resume`
  - `get_job_progress(task_id)` → reads blob, narrates gap + convergence rate + current incumbent
  - `check_notifications()` → reads `notifications/pending` blob, surfaces completed jobs
- Update existing tools (`explain_solution`, `suggest_relaxations`) to read from blob by task_id rather than ServerState
- Tests: routing by tier, blob created for instant solve, new tools, notification check

### Stage 13 — sage-jobs UI (real backend)
- Fix the 400 error: wire sage-jobs page to real `/api/jobs` endpoint
- **Filter axes (two rows):**
  - Row 1 (status): All · Running · Paused · Complete · Failed · Deleted
  - Row 2 (type): All · LP · MIP · Portfolio · Scheduling
- **Job card:** type icon + status badge, task_id (click to copy), vars/constraints/tier/elapsed, gap progress bar, bound/best, convergence chart
- **Convergence chart:** `bound_history` rendered as a line. Pause/resume events marked as vertical markers with distinct color. Stall periods shown as shaded regions.
- **Expanded job panel** (click card to open):
  - *Progress section* (running/paused): live gap %, bound, best, node count, elapsed. Pause / Resume / Peek buttons.
  - *Result section* (complete/paused-with-incumbent): objective value, variable values table (top decisions), plain-language narrative.
  - *Analysis section* (complete LP): shadow prices as horizontal bar chart, binding constraints highlighted, sensitivity ranges as "safe zone" indicators.
  - *Assumed constraints section* (when present): each assumption listed with confidence badge (green/amber/red), source, and a warning flag if assumed value is outside safe sensitivity range.
  - *Actions section*: Explain (depth picker: brief/standard/detailed) · Export Excel · Copy output URL · Send to ClickUp · Configure webhook · Delete
- **Delete:** confirm dialog → soft delete → card moves to Deleted filter → never shown by default. "Show deleted" toggle in footer.
- **Daisy chain Actions:**
  - "Copy output URL" → copies `http://localhost:{port}/blobs/jobs/{task_id}` to clipboard
  - "Send to ClickUp" → creates ClickUp task with result summary + output URL
  - "Configure webhook" → stores URL in blob `output_webhooks`; cloud POSTs blob to URL on completion
- **Bottom hint bar:** "In a new chat session, say `check task {task_id}` and Claude will retrieve this job."
- 5-second polling interval. `Last-Modified` check to avoid unnecessary re-renders.
- Tests: UI integration tests for job list, filter combinations, soft delete flow, expanded panel sections

### Stage 14 — Notifications + ClickUp
- On job completion: sage-solver-cloud writes `task_id` to `notifications/pending` blob (append-only list)
- On job completion: if `clickup_task_id` set in blob, post comment with result summary
- If no `clickup_task_id`, optionally create a new ClickUp task in the SAGE list
- `check_notifications()` MCP tool: reads `notifications/pending`, reads each blob, narrates completed jobs, clears the pending list
- Tests: notification blob written, ClickUp comment posted, pending list cleared after check

---

## 9. Assumed Constraints (Stage 15, v0.2.x)

Real-world problems rarely arrive with complete data. Assumed constraints make SAGE honest about what it doesn't know.

### Schema (in sage-solver-core/models.py)
```python
class AssumedConstraint(BaseModel):
    constraint_name: str          # links to a named LinearConstraint
    assumed_value: float          # RHS or coefficient used
    confidence: Literal["high", "medium", "low"]
    source: Literal[
        "user_stated",
        "historical_average",
        "industry_benchmark",
        "web_research",
        "regulatory_default",
        "expert_estimate"
    ]
    rationale: str                # "Based on 2024 average fuel costs"
    actual_value: float | None    # populated when user provides real data
    sensitivity_safe: bool | None # populated post-solve
```

### Explainer integration
Post-solve, the explainer cross-references each assumed constraint against HiGHS sensitivity ranges:
- Assumed value inside allowable RHS range → `sensitivity_safe: True`, brief mention
- Assumed value outside range OR high shadow price + low confidence → flag loudly:
  > "This solution assumes fuel cost ≤ $0.18/km (medium confidence, 2024 average). The shadow price is $4,200 — meaning a 10% cost increase reverses the optimal routing decision. Verify this estimate before acting."

### Research path
When `confidence` is unspecified, the MCP layer can optionally invoke web search to find industry benchmarks and propose a sourced value with `source: "web_research"`. The user sees the source and can replace it with real data to trigger a re-solve.

---

## 10. Baker & Powell Gaps (Vision Phase 2, future stages)

From the Management Science textbook (Baker & Powell). Three capability gaps remain:

| Gap | Status | Notes |
|---|---|---|
| Nonlinear programming (NLP) | Planned | IPOPT for convex NLP. New solver dispatch branch in solver.py. |
| Decision analysis | Planned | EMV, EVPI, backward induction. New module `decisiontree.py`. No external solver needed. |
| Monte Carlo simulation | Planned | Parameterize assumed constraints as distributions, run batch solves, return output distribution. Connects Phase E directly to simulation. EVPI from decision analysis tells you whether it's worth researching an assumed constraint before simulating. |

These are independent and do not block v0.2.0.

---

## 11. Daisy Chain Architecture (Vision Phase 3 assumption)

The integration primitive is already built: `GET /blobs/jobs/{task_id}` returns the full JobBlob as JSON. Any downstream system that can read a URL can consume a SAGE result.

**Current surfaces (Stage 13):**
- Copy output URL → paste into any tool that reads JSON
- Send to ClickUp → human-readable notification + machine-readable link in one
- Configure webhook → cloud POSTs JobBlob to URL on completion

**Phase 3 vision (future):**
A `chain_to` field in job submission tells sage-solver-cloud to automatically map specific output variable values to input constraint RHS values of a downstream job on completion. A completed supply chain LP feeds its allocation outputs directly into a downstream inventory scheduling MIP. The blob schema's named, typed variable values are already structured for this — the `chain_to` spec is the only addition needed.

---

## 12. UI/UX Principles

- **Job type is always visible** — type icon in card header (LP graph, MIP tree, calendar grid for scheduling, pie for portfolio). Filter by type is second-row axis.
- **Convergence chart is the primary visualization** — shows bound closing toward optimal over time. Pause/resume markers as vertical lines. Stall regions shaded. Event types from `bound_history[*].event_type`.
- **Deleted ≠ invalid** — soft delete sets status, retains blob. Claude in new chat responds specifically: "Job mip-7b2c was deleted from the dashboard on March 19. The task_id is no longer active." Different response from unknown ID (error).
- **The hint bar stays** — "In a new chat session, say `check task sc-4f9a`..." is the most important affordance for cross-session continuity. Always visible.
- **Actions are state-aware** — Pause visible only when Running. Resume only when Paused. Peek available when Running or Paused with incumbent. Export available when any solution exists.

---

## 13. Resume Checklist

When resuming work on this, follow this sequence:

```
[ ] 1. Read this document (BACK_TO_WORK_SPEC.md)
[ ] 2. Read .build/BUILD_LOG.md (decision history, design decisions log)
[ ] 3. Read .build/SAGE_SPEC.md (core architecture reference)
[ ] 4. Read ROADMAP.md (vision phases for context)
[ ] 5. Check sage-solver-cloud is running: open http://localhost:{port}/
[ ] 6. Run verification:
        cd sage-solver-core && pytest tests/ -v   (expect 393+ passed)
        cd sage-solver-mcp && pytest tests/ -v    (expect 77+ passed)
[ ] 7. Check Groot placeholder at localhost:8000 for UI inspiration
[ ] 8. Give Claude this context:
        a. Read .build/AGENT.md, .build/SAGE_SPEC.md, .build/BUILD_LOG.md,
           .build/BACK_TO_WORK_SPEC.md
        b. "We're building v0.2.0. Start with Stage 8 from BACK_TO_WORK_SPEC.md."
[ ] 9. Follow the same stage protocol as v0.1:
        stage prompt → build → verify → approve → next stage
        Update BUILD_LOG.md session tracker at start and end of each session.
```

---

## 14. What Is Explicitly NOT Being Built

- No hosted server (no cloud.pragnakar.com or equivalent)
- No multi-tenant SaaS
- No authentication layer (local only, v0.2)
- No SSE/remote MCP transport (ChatGPT integration deferred)
- No web UI framework (Groot's page system handles the dashboard)
- No S3 or external file storage (blob store is local)
- No sage-solver-cloud PyPI publish for v0.2 (local install only)

---

*SAGE v0.1.3 is shipped. The solver works. The cloud scaffold exists. The callbacks are documented. The build sequence is clear.*
*Next: Stage 8.*
