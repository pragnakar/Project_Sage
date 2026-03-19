"""Sage Cloud — Background solver runner.

Polls blob store for queued jobs, executes them using solve_with_callbacks,
writes progress back to blobs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger("sage.runner")


class SolverRunner:
    """Background process that polls for queued solver jobs and executes them.

    Args:
        blob_url: Base URL of the blob store API.
        api_key: Authentication key for blob store requests.
        max_workers: Maximum concurrent solver processes.
    """

    def __init__(self, blob_url: str, api_key: str, max_workers: int = 2) -> None:
        self.blob_url = blob_url
        self.api_key = api_key
        self.max_workers = max_workers
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._running = False

    async def start(self) -> None:
        """Start polling for queued jobs."""
        self._running = True
        while self._running:
            try:
                await self._poll_and_run()
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
            job["status"] = "complete"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            job["solution"] = result.get("solution")
            job["explanation"] = result.get("explanation")
            job["best_bound"] = result.get("best_bound")
            job["best_incumbent"] = result.get("best_incumbent")
            job["gap_pct"] = result.get("gap_pct")
            job["elapsed_seconds"] = result.get("elapsed_seconds", 0)
            job["bound_history"] = result.get("bound_history", [])
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(task_id, "complete")

        except Exception as exc:
            logger.error("Job %s failed: %s", task_id, exc)
            job["status"] = "failed"
            job["explanation"] = f"Solver error: {exc}"
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(task_id, "failed")

    async def _read_blob(self, key: str) -> dict | None:
        """Read a JSON blob from the blob store."""
        try:
            req = urllib.request.Request(
                f"{self.blob_url}/api/tools/read_blob",
                data=json.dumps({"key": key}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Sage-Key": self.api_key,
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read())
            if result.get("data"):
                return (
                    json.loads(result["data"])
                    if isinstance(result["data"], str)
                    else result["data"]
                )
        except Exception:
            pass
        return None

    async def _write_blob(self, key: str, data: dict) -> None:
        """Write a JSON blob to the blob store."""
        body = json.dumps({
            "key": key,
            "data": json.dumps(data),
            "content_type": "application/json",
        }).encode()
        req = urllib.request.Request(
            f"{self.blob_url}/api/tools/write_blob",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Sage-Key": self.api_key,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)

    async def _update_index(self, task_id: str, status: str) -> None:
        """Update a job's status in the jobs/index blob."""
        index = await self._read_blob("jobs/index") or {
            "schema_version": "2.0",
            "jobs": [],
        }
        for entry in index["jobs"]:
            if entry["task_id"] == task_id:
                entry["status"] = status
                break
        await self._write_blob("jobs/index", index)


def _solve_job(job: dict) -> dict:
    """Run a solver job in a separate process. Returns result dict.

    This is a module-level function so it can be pickled by
    :class:`ProcessPoolExecutor`.

    Args:
        job: Job dictionary containing a ``solver_input`` field with the
            serialized :class:`SolverInput`.

    Returns:
        Dict with solution, bounds, gap, timing, and history.

    Raises:
        ValueError: If the job blob is missing the ``solver_input`` field.
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
        "best_bound": result.bound,
        "best_incumbent": result.objective_value,
        "gap_pct": result.gap * 100 if result.gap is not None else None,
        "elapsed_seconds": result.solve_time_seconds,
        "bound_history": bound_history,
        "explanation": None,  # TODO: wire explainer when model is available
        "status": result.status,
    }
