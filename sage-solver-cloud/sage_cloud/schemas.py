"""Pydantic v2 models for Sage Cloud job blob schemas (v2.0).

These schemas define the structured JSON blobs stored in the artifact store
for long-running optimization jobs:

- SageJob         -> blob key ``jobs/{task_id}``
- SageJobIndex    -> blob key ``jobs/index``
- SageNotifications -> blob key ``notifications/pending``
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SageJob v2.0 -- stored at blob key `jobs/{task_id}`
# ---------------------------------------------------------------------------

class SageJob(BaseModel):
    """Full state of a single optimization job (v2.0)."""

    schema_version: str = "2.0"
    task_id: str
    problem_name: str
    problem_type: Literal["LP", "MIP", "QP", "PORTFOLIO", "SCHEDULING"]
    complexity_tier: Literal["instant", "fast", "background"]
    description: str | None = None
    status: Literal[
        "queued", "running", "paused", "complete", "failed", "stalled", "deleted"
    ]

    # Timestamps
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    deleted_at: str | None = None
    deleted_by: Literal["user_ui", "user_chat"] | None = None

    # Problem dimensions
    n_vars: int = 0
    n_constraints: int = 0
    n_binary: int = 0

    # Solver progress
    elapsed_seconds: float = 0.0
    gap_pct: float | None = None
    best_bound: float | None = None
    best_incumbent: float | None = None
    node_count: int | None = None
    stall_detected: bool = False
    pause_requested: bool = False

    # Bound history: [[elapsed, dual_bound, primal_incumbent, event_type], ...]
    bound_history: list = []

    # Solution data
    incumbent_solution: dict | None = None
    solution: dict | None = None
    explanation: str | None = None
    assumed_constraints: list | None = None

    # Integration
    clickup_task_id: str | None = None
    notified_at: str | None = None
    output_webhooks: list = []


# ---------------------------------------------------------------------------
# SageJobIndex -- stored at blob key `jobs/index`
# ---------------------------------------------------------------------------

class SageJobIndexEntry(BaseModel):
    """Summary entry for one job in the index."""

    task_id: str
    created_at: str  # ISO 8601 UTC
    status: str
    problem_name: str
    problem_type: str = ""
    complexity_tier: str = ""


class SageJobIndex(BaseModel):
    """Lightweight index of all known jobs."""

    schema_version: str = "2.0"
    jobs: list[SageJobIndexEntry] = []


# ---------------------------------------------------------------------------
# SageNotifications -- stored at blob key `notifications/pending`
# ---------------------------------------------------------------------------

class SageNotificationEntry(BaseModel):
    """One pending completion notification."""

    task_id: str
    completed_at: str  # ISO 8601 UTC
    problem_name: str
    status: str


class SageNotifications(BaseModel):
    """Queue of notifications the UI has not yet consumed."""

    schema_version: str = "2.0"
    pending: list[SageNotificationEntry] = []
