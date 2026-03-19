"""Tests for the SolverRunner and _solve_job helper."""

from __future__ import annotations

import pytest
from concurrent.futures import ProcessPoolExecutor

from sage_cloud.runner import SolverRunner, _solve_job


# ---------------------------------------------------------------------------
# Helper: build a minimal valid job dict
# ---------------------------------------------------------------------------

def _make_job(
    objective_sense: str = "maximize",
    variable_types: list[str] | None = None,
) -> dict:
    """Build a job dict wrapping a simple MIP/LP SolverInput.

    Maximize 3x + 2y  s.t.  x + y <= 10, x <= 6, y <= 8.
    """
    return {
        "solver_input": {
            "num_variables": 2,
            "num_constraints": 3,
            "variable_names": ["x", "y"],
            "variable_lower_bounds": [0.0, 0.0],
            "variable_upper_bounds": [1e30, 1e30],
            "variable_types": variable_types or ["integer", "integer"],
            "constraint_names": ["c1", "c2", "c3"],
            "constraint_matrix": [
                [1.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            "constraint_senses": ["<=", "<=", "<="],
            "constraint_rhs": [10.0, 6.0, 8.0],
            "objective_coefficients": [3.0, 2.0],
            "objective_sense": objective_sense,
            "time_limit_seconds": 30.0,
        },
    }


# ---------------------------------------------------------------------------
# 9. _solve_job returns a valid result dict
# ---------------------------------------------------------------------------

class TestSolveJob:
    def test_returns_result_dict(self) -> None:
        result = _solve_job(_make_job())
        assert result["status"] == "optimal"
        assert result["solution"] is not None
        assert result["solution"]["x"] == pytest.approx(6.0)
        assert result["solution"]["y"] == pytest.approx(4.0)
        assert result["best_incumbent"] == pytest.approx(26.0)
        assert result["elapsed_seconds"] >= 0
        assert isinstance(result["bound_history"], list)

    def test_lp_job(self) -> None:
        result = _solve_job(_make_job(variable_types=["continuous", "continuous"]))
        assert result["status"] == "optimal"
        assert result["solution"]["x"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# 10. _solve_job handles errors
# ---------------------------------------------------------------------------

class TestSolveJobErrors:
    def test_missing_solver_input(self) -> None:
        with pytest.raises(ValueError, match="missing 'solver_input'"):
            _solve_job({})

    def test_invalid_solver_input(self) -> None:
        with pytest.raises(Exception):
            _solve_job({"solver_input": {"num_variables": -1}})


# ---------------------------------------------------------------------------
# 11. ProcessPoolExecutor isolation (pickling works)
# ---------------------------------------------------------------------------

class TestProcessPoolIsolation:
    def test_solve_in_process_pool(self) -> None:
        job = _make_job()
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_solve_job, job)
            result = future.result(timeout=30)
        assert result["status"] == "optimal"
        assert result["solution"]["x"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# 12. SolverRunner can be instantiated
# ---------------------------------------------------------------------------

class TestSolverRunnerInit:
    def test_init(self) -> None:
        runner = SolverRunner(
            blob_url="http://localhost:8080",
            api_key="test-key",
            max_workers=1,
        )
        assert runner.blob_url == "http://localhost:8080"
        assert runner.api_key == "test-key"
        assert runner.max_workers == 1
        assert runner._running is False
        runner.stop()

    def test_stop(self) -> None:
        runner = SolverRunner(
            blob_url="http://localhost:8080",
            api_key="test-key",
        )
        runner._running = True
        runner.stop()
        assert runner._running is False
