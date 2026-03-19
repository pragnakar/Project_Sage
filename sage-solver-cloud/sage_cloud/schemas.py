"""Pydantic v2 models for Sage Cloud job blob schemas.

These schemas define the structured JSON blobs stored in the artifact store
for long-running optimization jobs:

- SageJob         → blob key ``jobs/{task_id}``
- SageJobIndex    → blob key ``jobs/index``
- SageNotifications → blob key ``notifications/pending``
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SageJob — stored at blob key `jobs/{task_id}`
# ---------------------------------------------------------------------------

class SageJob(BaseModel):
    """Full state of a single optimization job."""

    schema_version: str = "1.0"
    task_id: str
    created_at: str  # ISO 8601 UTC
    updated_at: str  # ISO 8601 UTC
    status: Literal["queued", "running", "paused", "complete", "failed"]
    problem_type: Literal["lp", "mip", "scheduling", "portfolio", "nlp"]
    problem_name: str
    description: str = ""
    variable_count: int = 0
    constraint_count: int = 0
    objective_sense: Literal["minimize", "maximize"] = "minimize"
    best_bound: float | None = None
    best_incumbent: float | None = None
    gap_pct: float | None = None
    elapsed_seconds: int = 0
    bound_history: list[list[float]] = []  # [[elapsed, bound, incumbent], ...]
    cost_breakdown: dict[str, float] | None = None
    solver_log: list[str] = []
    solution: dict | None = None
    solution_summary: str = ""
    tags: list[str] = []
    control: Literal["run", "pause", "stop"] = "run"


# ---------------------------------------------------------------------------
# SageJobIndex — stored at blob key `jobs/index`
# ---------------------------------------------------------------------------

class SageJobIndexEntry(BaseModel):
    """Summary entry for one job in the index."""

    task_id: str
    created_at: str  # ISO 8601 UTC
    status: str
    problem_name: str


class SageJobIndex(BaseModel):
    """Lightweight index of all known jobs."""

    schema_version: str = "1.0"
    jobs: list[SageJobIndexEntry] = []


# ---------------------------------------------------------------------------
# SageNotifications — stored at blob key `notifications/pending`
# ---------------------------------------------------------------------------

class SageNotificationEntry(BaseModel):
    """One pending completion notification."""

    task_id: str
    completed_at: str  # ISO 8601 UTC
    problem_name: str
    status: str


class SageNotifications(BaseModel):
    """Queue of notifications the UI has not yet consumed."""

    schema_version: str = "1.0"
    pending: list[SageNotificationEntry] = []
