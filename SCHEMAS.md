# SCHEMAS.md — Sage Cloud Job Blob Schemas

This document describes the three JSON blob schemas used by Sage Cloud to track long-running optimization jobs. Each blob is stored in the Sage Cloud artifact store under the specified key.

---

## 1. SageJob

**Blob key:** `jobs/{task_id}`

The canonical state of a single optimization job. Written by `sage-solver-mcp` as the solver progresses; read by the UI to display status and results.

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `str` | `"1.0"` | Schema version for forward compatibility |
| `task_id` | `str` | *required* | Unique job identifier |
| `created_at` | `str` | *required* | ISO 8601 UTC timestamp of job creation |
| `updated_at` | `str` | *required* | ISO 8601 UTC timestamp of last update |
| `status` | `Literal` | *required* | One of: `queued`, `running`, `paused`, `complete`, `failed` |
| `problem_type` | `Literal` | *required* | One of: `lp`, `mip`, `scheduling`, `portfolio`, `nlp` |
| `problem_name` | `str` | *required* | Human-readable problem name |
| `description` | `str` | `""` | Optional longer description |
| `variable_count` | `int` | `0` | Number of decision variables |
| `constraint_count` | `int` | `0` | Number of constraints |
| `objective_sense` | `Literal` | `"minimize"` | One of: `minimize`, `maximize` |
| `best_bound` | `float \| None` | `None` | Best dual bound (LP relaxation) |
| `best_incumbent` | `float \| None` | `None` | Best feasible objective value found |
| `gap_pct` | `float \| None` | `None` | Optimality gap as percentage |
| `elapsed_seconds` | `int` | `0` | Wall-clock time spent solving |
| `bound_history` | `list[list[float]]` | `[]` | Time-series: `[[elapsed, bound, incumbent], ...]` |
| `cost_breakdown` | `dict[str, float] \| None` | `None` | Compute/storage cost tracking |
| `solver_log` | `list[str]` | `[]` | Rolling log of solver progress messages |
| `solution` | `dict \| None` | `None` | Variable values when status is `complete` |
| `solution_summary` | `str` | `""` | Human-readable one-line summary |
| `tags` | `list[str]` | `[]` | User-defined tags for filtering |
| `control` | `Literal` | `"run"` | One of: `run`, `pause`, `stop` — written by UI, read by solver |

### Writer/Reader

| Field | Written by | Read by |
|---|---|---|
| `status`, `best_bound`, `best_incumbent`, `gap_pct`, `elapsed_seconds`, `bound_history`, `solver_log`, `solution`, `solution_summary` | sage-solver-mcp | UI |
| `control` | UI | sage-solver-mcp |
| `task_id`, `created_at`, `problem_type`, `problem_name`, `description`, `variable_count`, `constraint_count`, `objective_sense`, `tags` | sage-solver-mcp (at creation) | UI |

### Example JSON

```json
{
  "schema_version": "1.0",
  "task_id": "job-abc123",
  "created_at": "2026-03-19T10:00:00Z",
  "updated_at": "2026-03-19T10:00:42Z",
  "status": "complete",
  "problem_type": "lp",
  "problem_name": "Portfolio Optimization Q1",
  "description": "Minimize risk for target return of 8%",
  "variable_count": 100,
  "constraint_count": 50,
  "objective_sense": "minimize",
  "best_bound": 0.042,
  "best_incumbent": 0.042,
  "gap_pct": 0.0,
  "elapsed_seconds": 42,
  "bound_history": [[1.0, 0.05, 0.06], [5.0, 0.042, 0.042]],
  "cost_breakdown": {"compute": 0.003, "storage": 0.001},
  "solver_log": ["Iteration 1: bound=0.05", "Optimal found at 42s"],
  "solution": {"AAPL": 0.15, "GOOGL": 0.25, "MSFT": 0.60},
  "solution_summary": "Optimal portfolio: 60% MSFT, 25% GOOGL, 15% AAPL. Risk=4.2%",
  "tags": ["portfolio", "q1-2026"],
  "control": "run"
}
```

---

## 2. SageJobIndex

**Blob key:** `jobs/index`

A lightweight index of all known jobs. Avoids listing individual blobs to discover jobs. Written by `sage-solver-mcp` whenever a job is created or its status changes.

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `str` | `"1.0"` | Schema version |
| `jobs` | `list[SageJobIndexEntry]` | `[]` | List of job summaries |

**SageJobIndexEntry:**

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Job identifier |
| `created_at` | `str` | ISO 8601 UTC creation timestamp |
| `status` | `str` | Current job status |
| `problem_name` | `str` | Human-readable name |

### Example JSON

```json
{
  "schema_version": "1.0",
  "jobs": [
    {
      "task_id": "job-abc123",
      "created_at": "2026-03-19T10:00:00Z",
      "status": "complete",
      "problem_name": "Portfolio Optimization Q1"
    },
    {
      "task_id": "job-def456",
      "created_at": "2026-03-19T11:30:00Z",
      "status": "running",
      "problem_name": "Shift Scheduling March"
    }
  ]
}
```

---

## 3. SageNotifications

**Blob key:** `notifications/pending`

A queue of completion notifications that the UI has not yet consumed. Written by `sage-solver-mcp` when a job reaches `complete` or `failed`; read and cleared by the UI.

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `str` | `"1.0"` | Schema version |
| `pending` | `list[SageNotificationEntry]` | `[]` | Unread notification entries |

**SageNotificationEntry:**

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Job identifier |
| `completed_at` | `str` | ISO 8601 UTC completion timestamp |
| `problem_name` | `str` | Human-readable name |
| `status` | `str` | Final status (`complete` or `failed`) |

### Example JSON

```json
{
  "schema_version": "1.0",
  "pending": [
    {
      "task_id": "job-abc123",
      "completed_at": "2026-03-19T10:00:42Z",
      "problem_name": "Portfolio Optimization Q1",
      "status": "complete"
    }
  ]
}
```
