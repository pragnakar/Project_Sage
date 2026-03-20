"""Sage Cloud — Background solver runner.

Polls blob store for queued jobs, executes them using solve_with_callbacks,
writes progress back to blobs. Runs as an asyncio task inside the server
process, using the ArtifactStore directly (no HTTP round-trips).

Pause/Resume
------------
Pause is implemented via a temp file flag.  The monitor coroutine watches the
job blob for ``pause_requested=True`` and creates a flag file in
PAUSE_FLAG_DIR.  The worker process (in ProcessPoolExecutor) checks for the
file in its ``check_pause`` callback; when the file exists HiGHS sets
``user_interrupt=True`` and the solve stops at the next callback boundary.
After the worker returns the runner inspects whether the flag existed, marks
the job "paused", and saves the last incumbent solution.

Resume is handled by the normal queued-job poll loop: ``jobs_api.resume_job``
sets ``status="queued"`` and clears ``pause_requested``.  The runner then
picks up the job, injects ``incumbent_solution`` into ``SolverInput.initial_solution``
for warm-start, and re-runs the solve.

Progress Monitoring
-------------------
A progress JSON file path is passed to the worker. The worker writes progress
updates to it on each HiGHS callback. An async monitor coroutine reads it
every 3 seconds and writes the latest values to the blob store for dashboard
polling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sage_cloud.artifact_store import ArtifactStore

logger = logging.getLogger("sage.runner")

# ---------------------------------------------------------------------------
# Pause/progress flag directory — shared between the asyncio event loop and
# worker threads via the filesystem.
# ---------------------------------------------------------------------------
PAUSE_FLAG_DIR = Path(tempfile.gettempdir()) / "sage_pause_flags"
PAUSE_FLAG_DIR.mkdir(parents=True, exist_ok=True)


def _safe_float(val):
    """Convert inf/nan to None for JSON-safe output."""
    if val is None:
        return None
    try:
        return val if math.isfinite(val) else None
    except (TypeError, ValueError):
        return None


def _sanitize_history(history: list) -> list:
    """Replace inf/nan floats in bound_history entries with None."""
    return [
        [(_safe_float(v) if isinstance(v, float) else v) for v in entry]
        if isinstance(entry, list) else entry
        for entry in history
    ]


class SolverRunner:
    """Background runner that polls for queued solver jobs and executes them.

    Uses the ArtifactStore directly — no HTTP calls needed since the runner
    lives in the same process as the server.

    Uses ThreadPoolExecutor: HiGHS is a C extension that releases the GIL
    during h.run(), so the asyncio event loop stays responsive. No pickling,
    no spawn/fork, no sys.path issues.
    """

    def __init__(self, store: "ArtifactStore", max_workers: int = 2) -> None:
        self.store = store
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False

    async def start(self) -> None:
        """Start polling for queued jobs."""
        self._running = True
        logger.info("SolverRunner started (max_workers=%d, context=spawn)", self.max_workers)
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
        """Execute a single job, supporting pause/resume and live progress."""
        pause_flag_path = str(PAUSE_FLAG_DIR / f"{task_id}.pause")
        progress_file = str(PAUSE_FLAG_DIR / f"{task_id}.progress.json")

        try:
            # Update status to running
            job["status"] = "running"
            job["started_at"] = datetime.now(timezone.utc).isoformat()
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(task_id, "running")

            # Start monitors alongside the solve
            pause_monitor = asyncio.create_task(
                self._monitor_pause(task_id, pause_flag_path)
            )
            progress_monitor = asyncio.create_task(
                self._monitor_progress(task_id, progress_file)
            )

            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    self._executor,
                    partial(_solve_job, job, pause_flag_path, progress_file),
                )
            finally:
                pause_monitor.cancel()
                progress_monitor.cancel()
                try:
                    await pause_monitor
                except asyncio.CancelledError:
                    pass
                try:
                    await progress_monitor
                except asyncio.CancelledError:
                    pass

            # Clean up progress file
            try:
                Path(progress_file).unlink(missing_ok=True)
            except Exception:
                pass

            # Determine if this was a genuine pause
            pause_flag = Path(pause_flag_path)
            was_paused = pause_flag.exists()
            try:
                pause_flag.unlink(missing_ok=True)
            except Exception:
                pass

            safe_history = _sanitize_history(result.get("bound_history", []))
            solver_status = result.get("status", "unknown")

            # BUG 6 FIX: If pause was requested but solver finished optimally,
            # let it complete normally (user gets their result faster).
            if was_paused and solver_status == "time_limit_reached":
                # Solver was interrupted by pause request — save state
                logger.info("Job %s paused after %.1fs", task_id, result.get("elapsed_seconds", 0))
                job["status"] = "paused"
                job["pause_requested"] = False
                job["incumbent_solution"] = (
                    result.get("last_incumbent")
                    or result.get("solution")
                    or {}
                )
                job["best_incumbent"] = _safe_float(result.get("best_incumbent"))
                job["best_bound"] = _safe_float(result.get("best_bound"))
                job["gap_pct"] = _safe_float(result.get("gap_pct"))
                job["elapsed_seconds"] = result.get("elapsed_seconds", 0)
                job["bound_history"] = safe_history
                await self._write_blob(f"jobs/{task_id}", job)
                await self._update_index(
                    task_id, "paused",
                    best_incumbent=job.get("best_incumbent"),
                    elapsed_seconds=job.get("elapsed_seconds"),
                    gap_pct=job.get("gap_pct"),
                )
                return

            # Normal completion
            if solver_status == "optimal":
                final_status = "complete"
            elif solver_status == "infeasible":
                final_status = "infeasible"
            elif solver_status == "time_limit_reached":
                final_status = "complete" if result.get("solution") else "stalled"
            else:
                final_status = "complete"

            job["status"] = final_status
            job["pause_requested"] = False
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            job["solution"] = result.get("solution")
            job["explanation"] = result.get("explanation")
            job["best_bound"] = _safe_float(result.get("best_bound"))
            job["best_incumbent"] = _safe_float(result.get("best_incumbent"))
            job["gap_pct"] = _safe_float(result.get("gap_pct"))
            job["elapsed_seconds"] = result.get("elapsed_seconds", 0)
            job["bound_history"] = safe_history
            await self._write_blob(f"jobs/{task_id}", job)
            await self._update_index(
                task_id, final_status,
                best_incumbent=job.get("best_incumbent"),
                elapsed_seconds=job.get("elapsed_seconds"),
                gap_pct=job.get("gap_pct"),
            )

        except Exception as exc:
            logger.error("Job %s failed: %s", task_id, exc, exc_info=True)
            exc_str = str(exc).lower()
            # If the exception is from IIS computation on an infeasible problem,
            # mark as infeasible rather than failed
            if "infeasible" in exc_str or "iis" in exc_str:
                job["status"] = "infeasible"
                job["explanation"] = f"Problem is infeasible. IIS computation failed: {exc}"
                await self._write_blob(f"jobs/{task_id}", job)
                await self._update_index(task_id, "infeasible")
            else:
                job["status"] = "failed"
                job["explanation"] = f"Solver error: {exc}"
                await self._write_blob(f"jobs/{task_id}", job)
                await self._update_index(task_id, "failed")

    async def _monitor_pause(self, task_id: str, pause_flag_path: str) -> None:
        """Watch the job blob for pause_requested and create the flag file."""
        while True:
            await asyncio.sleep(2)
            job = await self._read_blob(f"jobs/{task_id}")
            if job and job.get("pause_requested"):
                try:
                    Path(pause_flag_path).touch()
                    logger.info("Pause flag created for job %s", task_id)
                except Exception as exc:
                    logger.warning("Could not create pause flag for %s: %s", task_id, exc)
                break

    async def _monitor_progress(self, task_id: str, progress_file: str) -> None:
        """Read progress from a file written by the worker and update the blob.

        The worker writes a JSON file at progress_file on each callback.
        This coroutine reads it every 3s and propagates to the blob store
        so the dashboard can poll live progress.
        """
        while True:
            await asyncio.sleep(3)
            try:
                with open(progress_file) as f:
                    latest = json.load(f)
            except Exception:
                continue

            try:
                job = await self._read_blob(f"jobs/{task_id}")
                if not job or job.get("status") != "running":
                    continue
                job["gap_pct"] = _safe_float(latest.get("gap_pct"))
                job["elapsed_seconds"] = latest.get("elapsed_seconds", 0)
                job["best_bound"] = _safe_float(latest.get("best_bound"))
                job["best_incumbent"] = _safe_float(latest.get("best_incumbent"))
                bh_entry = latest.get("bound_history_entry")
                if bh_entry:
                    existing = job.get("bound_history", [])
                    existing.append(
                        [(_safe_float(v) if isinstance(v, float) else v) for v in bh_entry]
                        if isinstance(bh_entry, list) else bh_entry
                    )
                    job["bound_history"] = existing
                await self._write_blob(f"jobs/{task_id}", job)
                await self._update_index(
                    task_id, "running",
                    best_incumbent=job.get("best_incumbent"),
                    elapsed_seconds=job.get("elapsed_seconds"),
                    gap_pct=job.get("gap_pct"),
                )
            except Exception as exc:
                logger.debug("Progress update failed for %s: %s", task_id, exc)

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


# ---------------------------------------------------------------------------
# Worker function (runs in ProcessPoolExecutor — must be picklable)
# ---------------------------------------------------------------------------


def _solve_job(
    job: dict,
    pause_flag_path: str = "",
    progress_file: str = "",
) -> dict:
    """Run a solver job in a separate process. Returns result dict.

    Args:
        job: Job dict with ``solver_input`` and optionally ``incumbent_solution``.
        pause_flag_path: Path to a temp file that signals pause.
        progress_file: Path to a JSON file for writing live progress updates.
    """
    from sage_solver_core.models import SolverInput
    from sage_solver_core.solver import solve_with_callbacks

    si_data = job.get("solver_input")
    if not si_data:
        raise ValueError("Job blob missing 'solver_input' field")

    # Inject incumbent solution for warm-start (resume after pause)
    incumbent = job.get("incumbent_solution")
    if incumbent:
        si_data = dict(si_data)
        si_data["initial_solution"] = incumbent

    si = SolverInput.model_validate(si_data)

    bound_history: list[list] = []
    last_incumbent: dict = {}

    def _write_progress(entry, update):
        """Write latest progress to file for the monitor coroutine to read."""
        if not progress_file:
            return
        try:
            import json as _json
            with open(progress_file, "w") as f:
                _json.dump({
                    "gap_pct": _safe_float(update.mip_gap * 100) if hasattr(update, "mip_gap") and update.mip_gap is not None else None,
                    "elapsed_seconds": update.elapsed_seconds,
                    "best_incumbent": _safe_float(update.primal_bound),
                    "best_bound": _safe_float(update.dual_bound),
                    "bound_history_entry": entry,
                }, f)
        except Exception:
            pass

    def on_incumbent(update):  # type: ignore[no-untyped-def]
        nonlocal last_incumbent
        entry = [update.elapsed_seconds, update.dual_bound, update.primal_bound, "incumbent"]
        bound_history.append(entry)
        if hasattr(update, "solution") and update.solution:
            last_incumbent = update.solution
        _write_progress(entry, update)

    def on_progress(update):  # type: ignore[no-untyped-def]
        entry = [update.elapsed_seconds, update.dual_bound, update.primal_bound, "progress"]
        bound_history.append(entry)
        _write_progress(entry, update)

    def check_pause() -> bool:
        return bool(pause_flag_path) and os.path.exists(pause_flag_path)

    result = solve_with_callbacks(
        si,
        on_incumbent=on_incumbent,
        on_progress=on_progress,
        check_pause=check_pause,
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
        "last_incumbent": last_incumbent,
    }
