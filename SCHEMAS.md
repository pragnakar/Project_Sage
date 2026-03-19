# SCHEMAS.md — Sage Cloud Job Blob Schemas (v2.0)

This document describes the three JSON blob schemas used by Sage Cloud to track long-running optimization jobs. Each blob is stored in the Sage Cloud artifact store under the specified key.

---

## 1. SageJob (v2.0)

**Blob key:** `jobs/{task_id}`

The canonical state of a single optimization job. Written by `sage-solver-mcp` as the solver progresses; read by the UI to display status and results.

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `str` | `"2.0"` | Schema version for forward compatibility |
| `task_id` | `str` | *required* | Unique job identifier |
| `problem_name` | `str` | *required* | Human-readable problem name |
| `problem_type` | `Literal` | *required* | One of: `LP`, `MIP`, `QP`, `PORTFOLIO`, `SCHEDULING` |
| `complexity_tier` | `Literal` | *required* | One of: `instant`, `fast`, `background` |
| `description` | `str \| None` | `None` | Optional longer description |
| `status` | `Literal` | *required* | One of: `queued`, `running`, `paused`, `complete`, `failed`, `stalled`, `deleted` |
| `created_at` | `str \| None` | `None` | ISO 8601 UTC timestamp of job creation |
| `started_at` | `str \| None` | `None` | ISO 8601 UTC timestamp of solver start |
| `completed_at` | `str \| None` | `None` | ISO 8601 UTC timestamp of completion |
| `deleted_at` | `str \| None` | `None` | ISO 8601 UTC timestamp of soft-delete |
| `deleted_by` | `Literal \| None` | `None` | One of: `user_ui`, `user_chat` (who deleted it) |
| `n_vars` | `int` | `0` | Number of decision variables |
| `n_constraints` | `int` | `0` | Number of constraints |
| `n_binary` | `int` | `0` | Number of binary/integer variables |
| `elapsed_seconds` | `float` | `0.0` | Wall-clock time spent solving |
| `gap_pct` | `float \| None` | `None` | Optimality gap as percentage |
| `best_bound` | `float \| None` | `None` | Best dual bound (LP relaxation) |
| `best_incumbent` | `float \| None` | `None` | Best feasible objective value found |
| `node_count` | `int \| None` | `None` | Branch-and-bound node count |
| `stall_detected` | `bool` | `False` | Whether the solver has stalled |
| `pause_requested` | `bool` | `False` | Whether the user has requested a pause |
| `bound_history` | `list` | `[]` | Time-series: `[[elapsed, dual_bound, primal_incumbent, event_type], ...]` |
| `incumbent_solution` | `dict \| None` | `None` | Current best solution during solve |
| `solution` | `dict \| None` | `None` | Final variable values when status is `complete` |
| `explanation` | `str \| None` | `None` | Human-readable explanation of the solution |
| `assumed_constraints` | `list \| None` | `None` | Constraints assumed/relaxed by the solver |
| `clickup_task_id` | `str \| None` | `None` | Linked ClickUp task ID for tracking |
| `notified_at` | `str \| None` | `None` | ISO 8601 UTC when notification was sent |
| `output_webhooks` | `list` | `[]` | Webhook URLs to call on completion |

### Writer/Reader

| Field | Written by | Read by |
|---|---|---|
| `status`, `best_bound`, `best_incumbent`, `gap_pct`, `elapsed_seconds`, `bound_history`, `solution`, `explanation`, `stall_detected`, `node_count` | sage-solver-mcp | UI |
| `pause_requested`, `deleted_at`, `deleted_by` | UI | sage-solver-mcp |
| `task_id`, `created_at`, `problem_type`, `problem_name`, `description`, `n_vars`, `n_constraints`, `n_binary`, `complexity_tier` | sage-solver-mcp (at creation) | UI |

### Example JSON

```json
{
  "schema_version": "2.0",
  "task_id": "job-abc123",
  "problem_name": "Portfolio Optimization Q1",
  "problem_type": "PORTFOLIO",
  "complexity_tier": "fast",
  "description": "Minimize risk for target return of 8%",
  "status": "complete",
  "created_at": "2026-03-19T10:00:00Z",
  "started_at": "2026-03-19T10:00:01Z",
  "completed_at": "2026-03-19T10:00:42Z",
  "n_vars": 100,
  "n_constraints": 50,
  "n_binary": 0,
  "elapsed_seconds": 41.2,
  "gap_pct": 0.0,
  "best_bound": 0.042,
  "best_incumbent": 0.042,
  "node_count": null,
  "stall_detected": false,
  "pause_requested": false,
  "bound_history": [[1.0, 0.05, 0.06, "progress"], [5.0, 0.042, 0.042, "optimal"]],
  "incumbent_solution": null,
  "solution": {"AAPL": 0.15, "GOOGL": 0.25, "MSFT": 0.60},
  "explanation": "Optimal portfolio: 60% MSFT, 25% GOOGL, 15% AAPL. Risk=4.2%",
  "assumed_constraints": null,
  "clickup_task_id": null,
  "notified_at": null,
  "output_webhooks": []
}
```

---

## 2. SageJobIndex

**Blob key:** `jobs/index`

A lightweight index of all known jobs. Avoids listing individual blobs to discover jobs. Written by `sage-solver-mcp` whenever a job is created or its status changes.

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `str` | `"2.0"` | Schema version |
| `jobs` | `list[SageJobIndexEntry]` | `[]` | List of job summaries |

**SageJobIndexEntry:**

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Job identifier |
| `created_at` | `str` | ISO 8601 UTC creation timestamp |
| `status` | `str` | Current job status |
| `problem_name` | `str` | Human-readable name |
| `problem_type` | `str` | Problem type (LP, MIP, etc.) |
| `complexity_tier` | `str` | Complexity tier |

### Example JSON

```json
{
  "schema_version": "2.0",
  "jobs": [
    {
      "task_id": "job-abc123",
      "created_at": "2026-03-19T10:00:00Z",
      "status": "complete",
      "problem_name": "Portfolio Optimization Q1",
      "problem_type": "PORTFOLIO",
      "complexity_tier": "fast"
    },
    {
      "task_id": "job-def456",
      "created_at": "2026-03-19T11:30:00Z",
      "status": "running",
      "problem_name": "Shift Scheduling March",
      "problem_type": "SCHEDULING",
      "complexity_tier": "background"
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
| `schema_version` | `str` | `"2.0"` | Schema version |
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
  "schema_version": "2.0",
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
