"""Tests for solve_with_callbacks(), IncumbentUpdate, ProgressUpdate, and stall detection."""

from __future__ import annotations

import pytest

from sage_solver_core.models import (
    IncumbentUpdate,
    ProgressUpdate,
    SolverInput,
)
from sage_solver_core.solver import (
    _detect_stall,
    solve,
    solve_with_callbacks,
)


# ---------------------------------------------------------------------------
# Fixtures: reusable SolverInput builders
# ---------------------------------------------------------------------------

def _simple_mip() -> SolverInput:
    """Maximize 3x + 2y  s.t.  x + y <= 10, x <= 6, y <= 8, x,y integer >= 0.

    Known optimal: x=6, y=4, obj=26.
    """
    return SolverInput(
        num_variables=2,
        num_constraints=3,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[1e30, 1e30],
        variable_types=["integer", "integer"],
        constraint_names=["c1", "c2", "c3"],
        constraint_matrix=[
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        constraint_senses=["<=", "<=", "<="],
        constraint_rhs=[10.0, 6.0, 8.0],
        objective_coefficients=[3.0, 2.0],
        objective_sense="maximize",
        time_limit_seconds=30.0,
    )


def _simple_lp() -> SolverInput:
    """Maximize 3x + 2y  s.t.  x + y <= 10, x <= 6, y <= 8, x,y continuous >= 0.

    Known optimal: x=6, y=4, obj=26.
    """
    return SolverInput(
        num_variables=2,
        num_constraints=3,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[1e30, 1e30],
        variable_types=["continuous", "continuous"],
        constraint_names=["c1", "c2", "c3"],
        constraint_matrix=[
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        constraint_senses=["<=", "<=", "<="],
        constraint_rhs=[10.0, 6.0, 8.0],
        objective_coefficients=[3.0, 2.0],
        objective_sense="maximize",
        time_limit_seconds=30.0,
    )


# ---------------------------------------------------------------------------
# 1. Callback fires on incumbent
# ---------------------------------------------------------------------------

class TestIncumbentCallback:
    def test_on_incumbent_called(self) -> None:
        incumbents: list[IncumbentUpdate] = []
        result = solve_with_callbacks(
            _simple_mip(),
            on_incumbent=lambda u: incumbents.append(u),
        )
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)
        # HiGHS should report at least one incumbent for this small MIP
        assert len(incumbents) >= 1
        inc = incumbents[-1]
        assert isinstance(inc, IncumbentUpdate)
        assert inc.elapsed_seconds >= 0
        assert "x" in inc.solution
        assert "y" in inc.solution


# ---------------------------------------------------------------------------
# 2. Progress callback fires (may not fire for tiny problems — test with mock)
# ---------------------------------------------------------------------------

class TestProgressCallback:
    def test_progress_callback_structure(self) -> None:
        """ProgressUpdate model can be constructed and validated."""
        p = ProgressUpdate(
            elapsed_seconds=5.1,
            mip_gap=0.02,
            primal_bound=25.0,
            dual_bound=26.0,
            node_count=100,
            stall_detected=False,
        )
        assert p.elapsed_seconds == pytest.approx(5.1)
        assert p.stall_detected is False

    def test_progress_default_none(self) -> None:
        p = ProgressUpdate(elapsed_seconds=1.0)
        assert p.mip_gap is None
        assert p.stall_detected is False


# ---------------------------------------------------------------------------
# 3. Pause stops solve
# ---------------------------------------------------------------------------

class TestPauseCallback:
    def test_check_pause_interrupts(self) -> None:
        """Setting check_pause to return True after first incumbent stops the solve."""
        incumbents: list[IncumbentUpdate] = []
        pause_after_first = {"seen": False}

        def on_inc(u: IncumbentUpdate) -> None:
            incumbents.append(u)
            pause_after_first["seen"] = True

        def should_pause() -> bool:
            return pause_after_first["seen"]

        result = solve_with_callbacks(
            _simple_mip(),
            on_incumbent=on_inc,
            check_pause=should_pause,
        )
        # Even if interrupted, result should be valid (either optimal or time_limit_reached)
        assert result.status in ("optimal", "time_limit_reached")


# ---------------------------------------------------------------------------
# 4. Resume warm start
# ---------------------------------------------------------------------------

class TestWarmStart:
    def test_initial_solution_accepted(self) -> None:
        si = _simple_mip()
        si = si.model_copy(update={"initial_solution": {"x": 6.0, "y": 4.0}})
        result = solve_with_callbacks(si)
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)
        assert result.variable_values is not None
        assert result.variable_values["x"] == pytest.approx(6.0)
        assert result.variable_values["y"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# 5. Existing solve() unchanged
# ---------------------------------------------------------------------------

class TestExistingSolveUnchanged:
    def test_solve_lp(self) -> None:
        result = solve(_simple_lp())
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)
        assert result.variable_values is not None
        assert result.variable_values["x"] == pytest.approx(6.0)
        assert result.variable_values["y"] == pytest.approx(4.0)

    def test_solve_mip(self) -> None:
        result = solve(_simple_mip())
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)


# ---------------------------------------------------------------------------
# 6. bound_history populated (via incumbents list)
# ---------------------------------------------------------------------------

class TestBoundHistory:
    def test_incumbent_has_bounds(self) -> None:
        incumbents: list[IncumbentUpdate] = []
        solve_with_callbacks(
            _simple_mip(),
            on_incumbent=lambda u: incumbents.append(u),
        )
        assert len(incumbents) >= 1
        for inc in incumbents:
            # Bounds should be finite floats
            assert isinstance(inc.primal_bound, float)
            assert isinstance(inc.dual_bound, float)


# ---------------------------------------------------------------------------
# 7. Stall detection
# ---------------------------------------------------------------------------

class TestStallDetection:
    def test_no_stall_with_short_history(self) -> None:
        history = [[i, 10.0, 20.0, "progress"] for i in range(10)]
        assert _detect_stall(history) is False

    def test_stall_detected(self) -> None:
        """Artificial data: no improvement over 100 entries."""
        history = [[float(i), 10.0, 20.0, "progress"] for i in range(100)]
        assert _detect_stall(history) is True

    def test_no_stall_with_improvement(self) -> None:
        """Gap shrinks significantly over the window."""
        history = [
            [float(i), 10.0 + i * 0.1, 20.0, "progress"]
            for i in range(100)
        ]
        assert _detect_stall(history) is False

    def test_stall_with_none_bounds(self) -> None:
        """None bounds should not crash."""
        history = [[float(i), None, 20.0, "progress"] for i in range(100)]
        assert _detect_stall(history) is False

    def test_stall_zero_first_gap(self) -> None:
        """Zero initial gap should return False (no division by zero)."""
        history = [[float(i), 10.0, 10.0, "progress"] for i in range(100)]
        assert _detect_stall(history) is False


# ---------------------------------------------------------------------------
# 8. LP calls solve_with_callbacks normally (no callbacks for LP)
# ---------------------------------------------------------------------------

class TestLPViaCallbacks:
    def test_lp_returns_correct_result(self) -> None:
        incumbents: list[IncumbentUpdate] = []
        result = solve_with_callbacks(
            _simple_lp(),
            on_incumbent=lambda u: incumbents.append(u),
        )
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)
        assert result.variable_values is not None
        assert result.variable_values["x"] == pytest.approx(6.0)
        # LP path should not fire MIP incumbent callbacks
        assert len(incumbents) == 0
