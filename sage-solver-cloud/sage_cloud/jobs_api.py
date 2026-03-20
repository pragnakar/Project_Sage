"""Sage Cloud — Jobs REST API.

Full lifecycle: submit, list, get, progress, pause, resume, delete.
Uses the blob store as the database — no separate DB needed.
"""

from __future__ import annotations

import json
import secrets
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from sage_cloud.auth import AuthContext, verify_api_key
from sage_cloud.schemas import SageJob, SageJobIndex, SageJobIndexEntry

logger = logging.getLogger("sage.jobs_api")

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SubmitJobRequest(BaseModel):
    """Body for POST /api/jobs."""

    solver_input: dict
    problem_name: str = "unnamed"
    description: str | None = None
    problem_type: str | None = None
    assumed_constraints: list | None = None


class SubmitJobResponse(BaseModel):
    task_id: str
    status: str


class ProgressResponse(BaseModel):
    task_id: str
    status: str
    elapsed_seconds: float
    gap_pct: float | None
    best_bound: float | None
    best_incumbent: float | None
    node_count: int | None
    stall_detected: bool
    last_bound_entry: list | None = None


class PauseResponse(BaseModel):
    task_id: str
    pause_requested: bool


class ResumeResponse(BaseModel):
    task_id: str
    status: str


class DeleteResponse(BaseModel):
    task_id: str
    status: str


class CompleteJobRequest(BaseModel):
    """Body for PATCH /api/jobs/{task_id}/complete."""
    solver_result: dict
    elapsed_seconds: float = 0.0
    explanation: str | None = None


class CompleteJobResponse(BaseModel):
    task_id: str
    status: str


class DeleteJobRequest(BaseModel):
    deleted_by: Literal["user_ui", "user_chat"] = "user_ui"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_from_solver_input(si: dict) -> str:
    """Lightweight complexity classification from raw SolverInput dict.

    Applies the same threshold rules as sage_solver_core.classifier.classify
    but works directly on the SolverInput fields.
    """
    n_vars = si.get("num_variables", 0)
    var_types = si.get("variable_types", [])
    n_binary = sum(1 for vt in var_types if vt in ("binary", "integer"))

    if n_binary > 500 or n_vars > 50_000:
        return "background"
    if n_binary > 100:
        return "fast"
    return "instant"


def _detect_problem_type(si: dict) -> str:
    """Infer problem_type from SolverInput fields."""
    var_types = si.get("variable_types", [])
    has_quadratic = bool(si.get("objective_quadratic"))
    has_binary = any(vt in ("binary", "integer") for vt in var_types)

    if has_quadratic:
        return "QP"
    if has_binary:
        return "MIP"
    return "LP"


def _generate_task_id(problem_type: str) -> str:
    """Generate a task_id like 'lp-a1f3' or 'mip-7b2c'."""
    short = problem_type.lower().replace("portfolio", "pf").replace("scheduling", "sch")
    hex4 = secrets.token_hex(2)  # 4 hex chars
    return f"{short}-{hex4}"


async def _read_job(store: Any, task_id: str) -> SageJob | None:
    """Read a SageJob blob, returning None if not found."""
    try:
        blob = await store.read_blob(f"jobs/{task_id}")
        return SageJob.model_validate(json.loads(blob.data))
    except (KeyError, Exception):
        return None


async def _write_job(store: Any, job: SageJob) -> None:
    """Write a SageJob blob."""
    await store.write_blob(
        f"jobs/{job.task_id}",
        job.model_dump_json(),
        "application/json",
    )


async def _read_index(store: Any) -> SageJobIndex:
    """Read the jobs/index blob, returning empty index if not found."""
    try:
        blob = await store.read_blob("jobs/index")
        return SageJobIndex.model_validate(json.loads(blob.data))
    except (KeyError, Exception):
        return SageJobIndex()


async def _write_index(store: Any, index: SageJobIndex) -> None:
    """Write the jobs/index blob."""
    await store.write_blob(
        "jobs/index",
        index.model_dump_json(),
        "application/json",
    )


def _get_store(request: Request) -> Any:
    return request.app.state.store


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201, response_model=SubmitJobResponse)
async def submit_job(
    body: SubmitJobRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Submit a new optimization job."""
    store = _get_store(request)
    si = body.solver_input

    # Detect / override problem type
    problem_type = body.problem_type or _detect_problem_type(si)
    complexity_tier = _classify_from_solver_input(si)

    # Generate task_id
    task_id = _generate_task_id(problem_type)

    # Count dimensions
    n_vars = si.get("num_variables", 0)
    n_constraints = si.get("num_constraints", 0)
    var_types = si.get("variable_types", [])
    n_binary = sum(1 for vt in var_types if vt in ("binary", "integer"))

    now = _now()

    job = SageJob(
        task_id=task_id,
        problem_name=body.problem_name,
        problem_type=problem_type,
        complexity_tier=complexity_tier,
        description=body.description,
        status="queued",
        created_at=now,
        n_vars=n_vars,
        n_constraints=n_constraints,
        n_binary=n_binary,
        assumed_constraints=body.assumed_constraints,
    )

    # Store solver_input in the blob as extra data (SageJob doesn't have it as a field,
    # so we serialize manually)
    job_data = json.loads(job.model_dump_json())
    job_data["solver_input"] = si
    await store.write_blob(f"jobs/{task_id}", json.dumps(job_data), "application/json")

    # Update index
    index = await _read_index(store)
    index.jobs.append(SageJobIndexEntry(
        task_id=task_id,
        created_at=now,
        status="queued",
        problem_name=body.problem_name,
        problem_type=problem_type,
        complexity_tier=complexity_tier,
    ))
    await _write_index(store, index)

    return SubmitJobResponse(task_id=task_id, status="queued")


@router.get("", response_model=list[SageJobIndexEntry])
async def list_jobs(
    request: Request,
    status: str | None = None,
    problem_type: str | None = None,
    auth: AuthContext = Depends(verify_api_key),
):
    """List all jobs, optionally filtered by status and/or problem_type."""
    store = _get_store(request)
    index = await _read_index(store)

    entries = index.jobs

    if status:
        entries = [e for e in entries if e.status == status]
    if problem_type:
        entries = [e for e in entries if e.problem_type == problem_type]

    # Sort most recent first
    entries.sort(key=lambda e: e.created_at, reverse=True)

    return entries


@router.get("/{task_id}")
async def get_job(
    task_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Get full job blob."""
    store = _get_store(request)
    try:
        blob = await store.read_blob(f"jobs/{task_id}")
        return json.loads(blob.data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")


@router.get("/{task_id}/progress", response_model=ProgressResponse)
async def get_progress(
    task_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Lightweight progress for a job."""
    store = _get_store(request)
    job = await _read_job(store, task_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")

    last_entry = job.bound_history[-1] if job.bound_history else None

    return ProgressResponse(
        task_id=job.task_id,
        status=job.status,
        elapsed_seconds=job.elapsed_seconds,
        gap_pct=job.gap_pct,
        best_bound=job.best_bound,
        best_incumbent=job.best_incumbent,
        node_count=job.node_count,
        stall_detected=job.stall_detected,
        last_bound_entry=last_entry,
    )


@router.post("/{task_id}/pause", response_model=PauseResponse)
async def pause_job(
    task_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Pause a running job."""
    store = _get_store(request)
    job = await _read_job(store, task_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")

    if job.status != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause job with status '{job.status}'. Only running jobs can be paused.",
        )

    job.pause_requested = True
    await _write_job(store, job)

    return PauseResponse(task_id=task_id, pause_requested=True)


@router.post("/{task_id}/resume", response_model=ResumeResponse)
async def resume_job(
    task_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Resume a paused job."""
    store = _get_store(request)
    job = await _read_job(store, task_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")

    if job.status != "paused":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resume job with status '{job.status}'. Only paused jobs can be resumed.",
        )

    if job.incumbent_solution is None:
        raise HTTPException(
            status_code=400,
            detail="Cannot resume without an incumbent solution.",
        )

    job.status = "queued"
    job.pause_requested = False
    job.bound_history.append(["resume"])
    await _write_job(store, job)

    # Update index
    index = await _read_index(store)
    for entry in index.jobs:
        if entry.task_id == task_id:
            entry.status = "queued"
            break
    await _write_index(store, index)

    return ResumeResponse(task_id=task_id, status="queued")


@router.patch("/{task_id}/complete", response_model=CompleteJobResponse)
async def complete_job(
    task_id: str,
    body: CompleteJobRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Mark a job as complete with solver results."""
    store = _get_store(request)

    # Read existing job blob (may have solver_input and other metadata)
    try:
        raw = await store.read_blob(f"jobs/{task_id}")
        job_data = json.loads(raw.data)
    except (KeyError, Exception):
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")

    # Update with results
    job_data["status"] = "complete"
    job_data["completed_at"] = _now()
    job_data["elapsed_seconds"] = body.elapsed_seconds
    job_data["explanation"] = body.explanation

    # Extract key fields from solver_result
    sr = body.solver_result
    job_data["solution"] = sr.get("variable_values")
    job_data["best_bound"] = sr.get("bound")
    job_data["best_incumbent"] = sr.get("objective_value")
    if sr.get("gap") is not None:
        job_data["gap_pct"] = sr["gap"] * 100
    else:
        job_data["gap_pct"] = 0.0

    await store.write_blob(f"jobs/{task_id}", json.dumps(job_data), "application/json")

    # Update index with result fields so the dashboard can show them without expanding
    index = await _read_index(store)
    for entry in index.jobs:
        if entry.task_id == task_id:
            entry.status = "complete"
            entry.best_incumbent = job_data.get("best_incumbent")
            entry.elapsed_seconds = body.elapsed_seconds
            entry.gap_pct = job_data.get("gap_pct")
            break
    await _write_index(store, index)

    return CompleteJobResponse(task_id=task_id, status="complete")


@router.delete("/{task_id}", response_model=DeleteResponse)
async def delete_job(
    task_id: str,
    request: Request,
    body: DeleteJobRequest | None = None,
    deleted_by: str | None = None,
    auth: AuthContext = Depends(verify_api_key),
):
    """Soft delete a job."""
    store = _get_store(request)
    job = await _read_job(store, task_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {task_id}")

    # Resolve deleted_by: body takes precedence, then query param, then default
    resolved_deleted_by = "user_ui"
    if body and body.deleted_by:
        resolved_deleted_by = body.deleted_by
    elif deleted_by:
        resolved_deleted_by = deleted_by

    job.status = "deleted"
    job.deleted_at = _now()
    job.deleted_by = resolved_deleted_by
    await _write_job(store, job)

    # Update index
    index = await _read_index(store)
    for entry in index.jobs:
        if entry.task_id == task_id:
            entry.status = "deleted"
            break
    await _write_index(store, index)

    return DeleteResponse(task_id=task_id, status="deleted")
