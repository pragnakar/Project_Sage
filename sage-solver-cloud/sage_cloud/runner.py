"""Sage Cloud — Background solver runner.

Polls blob store for queued jobs, executes them using solve_with_callbacks,
writes progress back to blobs. Runs as an asyncio task inside the server
process, using the ArtifactStore directly (no HTTP round-trips).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sage_cloud.artifact_store import ArtifactStore

logger = logging.getLogger("sage.runner")


def _safe_float(val):
    """Convert inf/nan to None for JSON-safe output."""
    if val is None:
        return None
    try:
        return val if math.isfinite(val) else None
    except (TypeError, ValueError):
        return None


class SolverRunner:
    """Background runner that polls for queued solver jobs and executes them.

    Uses the ArtifactStore directly — no HTTP calls needed since the runner
    lives in the same process as the server.
    """

    def __init__(self, store: ArtifactStore, max_workers: int = 2) -> None:
        self.store = store
        self.max_workers = max_workers
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._running = False

    async def start(self) -> None:
        """Start polling for queued jobs."""
        self._running = True
        logger.info("SolverRunner started (max_workers=%d)", self.max_workers)
        while self._running:
            try:
                await self._poll_and_run()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Runner poll error: %s", exc)
            await asyncio.sleep(2)

    def stop(self) -> None:
        """Stop the runner and shut down the process pool."""
        self._running = False
        self._executor.shutdown(wait=False)

    async def _poll_and_run(self) -> None:
        """Check for queued jobs and submit them."""
        index_data = await self._read_blob("jobs/index")
        if not index_data:
            return

        for entry in index_data.get("jobs", []):
            if entry.get("status") == "queued":
                task_id = entry["task_id"]
                job = await self._read_blob(f"jobs/{task_id}")
                if job and job.get("status") == "queued":
                    asyncio.create_task(self._run_job(task_id, job))

    async def _run_job(self, task_id: str, job: dict) -> None:
        """Execute a single job."""
        try:
            # Update status to running
            job["status"] = "running"
            job["started_at"] = datetime.now(timezone.utc).isoformat()
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(task_id, "running")

            # Run solver in process pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                _solve_job,
                job,
            )

            # Update blob with results
            job["status"] = result.get("status", "complete")
            if job["status"] == "optimal":
                job["status"] = "complete"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            job["solution"] = result.get("solution")
            job["explanation"] = result.get("explanation")
            job["best_bound"] = _safe_float(result.get("best_bound"))
            job["best_incumbent"] = _safe_float(result.get("best_incumbent"))
            job["gap_pct"] = _safe_float(result.get("gap_pct"))
            job["elapsed_seconds"] = result.get("elapsed_seconds", 0)
            job["bound_history"] = result.get("bound_history", [])
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(
                task_id, job["status"],
                best_incumbent=job.get("best_incumbent"),
                elapsed_seconds=job.get("elapsed_seconds"),
                gap_pct=job.get("gap_pct"),
            )

        except Exception as exc:
            logger.error("Job %s failed: %s", task_id, exc)
            job["status"] = "failed"
            job["explanation"] = f"Solver error: {exc}"
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(task_id, "failed")

    async def _read_blob(self, key: str) -> dict | None:
        """Read a JSON blob directly from the store."""
        try:
            blob = await self.store.read_blob(key)
            data = blob.data if hasattr(blob, "data") else blob
            return json.loads(data) if isinstance(data, str) else data
        except (KeyError, Exception):
            return None

    async def _write_blob(self, key: str, data: dict) -> None:
        """Write a JSON blob directly to the store."""
        await self.store.write_blob(key, json.dumps(data), "application/json")

    async def _update_index(
        self, task_id: str, status: str, **extra: object
    ) -> None:
        """Update a job's status (and optional result fields) in the index blob."""
        index = await self._read_blob("jobs/index") or {
            "schema_version": "2.0",
            "jobs": [],
        }
        for entry in index["jobs"]:
            if entry["task_id"] == task_id:
                entry["status"] = status
                for k, v in extra.items():
                    entry[k] = v
                break
        await self._write_blob("jobs/index", index)


def _solve_job(job: dict) -> dict:
    """Run a solver job in a separate process. Returns result dict.

    This is a module-level function so it can be pickled by
    :class:`ProcessPoolExecutor`.
    """
    from sage_solver_core.models import SolverInput
    from sage_solver_core.solver import solve_with_callbacks

    si_data = job.get("solver_input")
    if not si_data:
        raise ValueError("Job blob missing 'solver_input' field")

    si = SolverInput.model_validate(si_data)

    bound_history: list[list] = []

    def on_incumbent(update):  # type: ignore[no-untyped-def]
        bound_history.append([
            update.elapsed_seconds, update.dual_bound,
            update.primal_bound, "incumbent",
        ])

    def on_progress(update):  # type: ignore[no-untyped-def]
        bound_history.append([
            update.elapsed_seconds, update.dual_bound,
            update.primal_bound, "progress",
        ])

    result = solve_with_callbacks(
        si, on_incumbent=on_incumbent, on_progress=on_progress,
    )

    return {
        "solution": result.variable_values,
        "best_bound": _safe_float(result.bound),
        "best_incumbent": _safe_float(result.objective_value),
        "gap_pct": _safe_float(result.gap * 100) if result.gap is not None else None,
        "elapsed_seconds": result.solve_time_seconds,
        "bound_history": bound_history,
        "explanation": None,
        "status": result.status,
    }
