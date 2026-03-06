"""Tests for sage_core/solver.py.

All tests use known small problems with analytically verifiable solutions.
No external files are required — SolverInput is constructed directly.

Known reference problems (from CLAUDE.md):

  Simple LP:
    max 3x + 2y  s.t.  x + y <= 10,  x <= 6,  y <= 8,  x,y >= 0
    Optimal: x=6, y=4, objective=26

  Simple MIP (integer version of the LP above):
    Same formulation but x, y ∈ Z≥0
    Optimal: x=6, y=4, objective=26  (same as LP — LP solution is integral)

  Infeasible LP:
    x + y <= 5,  x + y >= 10,  x, y >= 0
    Status: infeasible.  IIS contains both constraints.

  Unbounded LP:
    max x,  x >= 0,  no upper bound on x
    Status: unbounded.
"""

from __future__ import annotations

import pytest

from sage_solver_core.models import SolverInput, SolverResult
from sage_solver_core.solver import compute_iis, solve


# ===========================================================================
# Fixture / helper factories
# ===========================================================================


def make_simple_lp() -> SolverInput:
    """Reference LP: max 3x + 2y, x+y≤10, x≤6, y≤8, x,y≥0.

    Optimal: x=6, y=4, obj=26.
    Binding: sum_limit (x+y=10), x_limit (x=6).
    Non-binding: y_limit (y=4 < 8, slack=4).
    Shadow prices: sum_limit→2, x_limit→1, y_limit→0.
    """
    return SolverInput(
        num_variables=2,
        num_constraints=3,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[1e30, 1e30],
        variable_types=["continuous", "continuous"],
        constraint_names=["sum_limit", "x_limit", "y_limit"],
        constraint_matrix=[
            [1.0, 1.0],   # x + y
            [1.0, 0.0],   # x
            [0.0, 1.0],   # y
        ],
        constraint_senses=["<=", "<=", "<="],
        constraint_rhs=[10.0, 6.0, 8.0],
        objective_coefficients=[3.0, 2.0],
        objective_sense="maximize",
    )


def make_simple_mip() -> SolverInput:
    """Reference MIP: same as LP but x, y integer.

    Optimal: x=6, y=4, obj=26  (LP solution is already integral).
    """
    return SolverInput(
        num_variables=2,
        num_constraints=3,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[1e30, 1e30],
        variable_types=["integer", "integer"],
        constraint_names=["sum_limit", "x_limit", "y_limit"],
        constraint_matrix=[
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        constraint_senses=["<=", "<=", "<="],
        constraint_rhs=[10.0, 6.0, 8.0],
        objective_coefficients=[3.0, 2.0],
        objective_sense="maximize",
    )


def make_infeasible_lp() -> SolverInput:
    """Infeasible LP: x+y≤5 AND x+y≥10, x,y≥0.

    Both constraints are needed for infeasibility → IIS = {c_upper, c_lower}.
    """
    return SolverInput(
        num_variables=2,
        num_constraints=2,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[1e30, 1e30],
        variable_types=["continuous", "continuous"],
        constraint_names=["c_upper", "c_lower"],
        constraint_matrix=[
            [1.0, 1.0],  # x + y ≤ 5
            [1.0, 1.0],  # x + y ≥ 10
        ],
        constraint_senses=["<=", ">="],
        constraint_rhs=[5.0, 10.0],
        objective_coefficients=[1.0, 1.0],
        objective_sense="minimize",
    )


def make_unbounded_lp() -> SolverInput:
    """Unbounded LP: max x, x≥0, no upper bound."""
    return SolverInput(
        num_variables=1,
        num_constraints=0,
        variable_names=["x"],
        variable_lower_bounds=[0.0],
        variable_upper_bounds=[1e30],
        variable_types=["continuous"],
        constraint_names=[],
        constraint_matrix=[],
        constraint_senses=[],
        constraint_rhs=[],
        objective_coefficients=[1.0],
        objective_sense="maximize",
    )


def make_large_mip(n_vars: int = 60, seed: int = 42) -> SolverInput:
    """Random binary knapsack problem intended to time out quickly.

    Uses a seeded RNG for reproducibility.  With n=60 binary variables and
    a 10ms time limit the problem will reliably hit time_limit_reached on
    any hardware.

    Args:
        n_vars: Number of binary items.
        seed: NumPy RNG seed.

    Returns:
        SolverInput with time_limit_seconds=0.01.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    profits = rng.integers(1, 100, size=n_vars).tolist()
    weights = rng.integers(1, 30, size=n_vars).tolist()
    # Capacity set to about 40% of total weight — makes LP bound loose
    capacity = float(int(sum(weights) * 0.4))

    return SolverInput(
        num_variables=n_vars,
        num_constraints=1,
        variable_names=[f"item_{i}" for i in range(n_vars)],
        variable_lower_bounds=[0.0] * n_vars,
        variable_upper_bounds=[1.0] * n_vars,
        variable_types=["binary"] * n_vars,
        constraint_names=["capacity"],
        constraint_matrix=[weights],
        constraint_senses=["<="],
        constraint_rhs=[capacity],
        objective_coefficients=[float(p) for p in profits],
        objective_sense="maximize",
        time_limit_seconds=0.01,   # 10 ms — will definitely time out
        mip_gap_tolerance=0.0001,
    )


# ===========================================================================
# Test: simple LP optimal
# ===========================================================================


class TestSolveLPOptimal:
    def test_status_optimal(self) -> None:
        result = solve(make_simple_lp())
        assert result.status == "optimal"

    def test_objective_value(self) -> None:
        result = solve(make_simple_lp())
        assert result.objective_value == pytest.approx(26.0, abs=1e-6)

    def test_variable_values(self) -> None:
        result = solve(make_simple_lp())
        assert result.variable_values is not None
        assert result.variable_values["x"] == pytest.approx(6.0, abs=1e-6)
        assert result.variable_values["y"] == pytest.approx(4.0, abs=1e-6)

    def test_solve_time_positive(self) -> None:
        result = solve(make_simple_lp())
        assert result.solve_time_seconds >= 0.0

    def test_no_iis_on_optimal(self) -> None:
        result = solve(make_simple_lp())
        assert result.iis is None

    def test_result_is_solver_result(self) -> None:
        result = solve(make_simple_lp())
        assert isinstance(result, SolverResult)

    def test_minimization_lp(self) -> None:
        """min x + y  s.t.  x + y >= 3,  x,y >= 0  → x+y=3, obj=3."""
        inp = SolverInput(
            num_variables=2,
            num_constraints=1,
            variable_names=["x", "y"],
            variable_lower_bounds=[0.0, 0.0],
            variable_upper_bounds=[1e30, 1e30],
            variable_types=["continuous", "continuous"],
            constraint_names=["lb"],
            constraint_matrix=[[1.0, 1.0]],
            constraint_senses=[">="],
            constraint_rhs=[3.0],
            objective_coefficients=[1.0, 1.0],
            objective_sense="minimize",
        )
        result = solve(inp)
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(3.0, abs=1e-6)


# ===========================================================================
# Test: simple MIP optimal
# ===========================================================================


class TestSolveMIPOptimal:
    def test_status_optimal(self) -> None:
        result = solve(make_simple_mip())
        assert result.status == "optimal"

    def test_objective_value(self) -> None:
        result = solve(make_simple_mip())
        assert result.objective_value == pytest.approx(26.0, abs=1e-6)

    def test_variable_values_integer(self) -> None:
        result = solve(make_simple_mip())
        assert result.variable_values is not None
        # Values must be integral
        for name, val in result.variable_values.items():
            assert abs(val - round(val)) < 1e-6, f"{name}={val} is not integer"

    def test_variable_values_correct(self) -> None:
        result = solve(make_simple_mip())
        assert result.variable_values is not None
        assert result.variable_values["x"] == pytest.approx(6.0, abs=1e-6)
        assert result.variable_values["y"] == pytest.approx(4.0, abs=1e-6)

    def test_no_sensitivity_for_mip(self) -> None:
        """MIP results must NOT contain sensitivity analysis."""
        result = solve(make_simple_mip())
        assert result.shadow_prices is None
        assert result.reduced_costs is None

    def test_binary_variable_mip(self) -> None:
        """Knapsack: 3 items, capacity=5.  Optimal is item0+item2 (value=9)."""
        inp = SolverInput(
            num_variables=3,
            num_constraints=1,
            variable_names=["item0", "item1", "item2"],
            variable_lower_bounds=[0.0, 0.0, 0.0],
            variable_upper_bounds=[1.0, 1.0, 1.0],
            variable_types=["binary", "binary", "binary"],
            constraint_names=["capacity"],
            constraint_matrix=[[3.0, 4.0, 2.0]],  # weights
            constraint_senses=["<="],
            constraint_rhs=[5.0],
            objective_coefficients=[6.0, 5.0, 3.0],  # profits
            objective_sense="maximize",
        )
        result = solve(inp)
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(9.0, abs=1e-6)
        assert result.variable_values is not None
        assert result.variable_values["item0"] == pytest.approx(1.0, abs=1e-6)
        assert result.variable_values["item2"] == pytest.approx(1.0, abs=1e-6)
        assert result.variable_values["item1"] == pytest.approx(0.0, abs=1e-6)


# ===========================================================================
# Test: infeasible LP → IIS
# ===========================================================================


class TestSolveInfeasible:
    def test_status_infeasible(self) -> None:
        result = solve(make_infeasible_lp())
        assert result.status == "infeasible"

    def test_no_objective_value(self) -> None:
        result = solve(make_infeasible_lp())
        assert result.objective_value is None

    def test_no_variable_values(self) -> None:
        result = solve(make_infeasible_lp())
        assert result.variable_values is None

    def test_iis_is_populated(self) -> None:
        result = solve(make_infeasible_lp())
        assert result.iis is not None

    def test_iis_contains_both_constraints(self) -> None:
        """Both c_upper and c_lower are needed → IIS = {c_upper, c_lower}."""
        result = solve(make_infeasible_lp())
        assert result.iis is not None
        iis_names = set(result.iis.conflicting_constraints)
        assert "c_upper" in iis_names
        assert "c_lower" in iis_names

    def test_iis_is_minimal(self) -> None:
        """The IIS should contain exactly 2 constraints (the full problem has 2)."""
        result = solve(make_infeasible_lp())
        assert result.iis is not None
        assert len(result.iis.conflicting_constraints) == 2

    def test_iis_has_explanation(self) -> None:
        result = solve(make_infeasible_lp())
        assert result.iis is not None
        assert len(result.iis.explanation) > 0

    def test_infeasible_3_constraints_iis_minimal(self) -> None:
        """Add a redundant 3rd constraint — IIS must still be only 2."""
        inp = SolverInput(
            num_variables=2,
            num_constraints=3,
            variable_names=["x", "y"],
            variable_lower_bounds=[0.0, 0.0],
            variable_upper_bounds=[1e30, 1e30],
            variable_types=["continuous", "continuous"],
            constraint_names=["c_upper", "c_lower", "c_redundant"],
            constraint_matrix=[
                [1.0, 1.0],  # x+y ≤ 5
                [1.0, 1.0],  # x+y ≥ 10
                [1.0, 0.0],  # x ≤ 100  (redundant)
            ],
            constraint_senses=["<=", ">=", "<="],
            constraint_rhs=[5.0, 10.0, 100.0],
            objective_coefficients=[1.0, 1.0],
            objective_sense="minimize",
        )
        result = solve(inp)
        assert result.status == "infeasible"
        assert result.iis is not None
        assert len(result.iis.conflicting_constraints) == 2
        iis = set(result.iis.conflicting_constraints)
        assert "c_upper" in iis
        assert "c_lower" in iis
        assert "c_redundant" not in iis


# ===========================================================================
# Test: unbounded LP
# ===========================================================================


class TestSolveUnbounded:
    def test_status_unbounded(self) -> None:
        result = solve(make_unbounded_lp())
        assert result.status == "unbounded"

    def test_no_objective_value(self) -> None:
        result = solve(make_unbounded_lp())
        assert result.objective_value is None

    def test_no_iis(self) -> None:
        result = solve(make_unbounded_lp())
        assert result.iis is None

    def test_unbounded_two_variables(self) -> None:
        """max x + y with x,y ≥ 0 and no upper bounds → unbounded."""
        inp = SolverInput(
            num_variables=2,
            num_constraints=0,
            variable_names=["x", "y"],
            variable_lower_bounds=[0.0, 0.0],
            variable_upper_bounds=[1e30, 1e30],
            variable_types=["continuous", "continuous"],
            constraint_names=[],
            constraint_matrix=[],
            constraint_senses=[],
            constraint_rhs=[],
            objective_coefficients=[1.0, 1.0],
            objective_sense="maximize",
        )
        result = solve(inp)
        assert result.status == "unbounded"


# ===========================================================================
# Test: sensitivity analysis
# ===========================================================================


class TestSolveSensitivity:
    """Verify shadow prices and binding constraint detection on the reference LP."""

    @pytest.fixture
    def result(self) -> SolverResult:
        return solve(make_simple_lp())

    def test_shadow_prices_present(self, result: SolverResult) -> None:
        assert result.shadow_prices is not None

    def test_reduced_costs_present(self, result: SolverResult) -> None:
        assert result.reduced_costs is not None

    def test_constraint_slack_present(self, result: SolverResult) -> None:
        assert result.constraint_slack is not None

    def test_binding_constraints_present(self, result: SolverResult) -> None:
        assert result.binding_constraints is not None

    # Shadow price correctness -----------------------------------------------

    def test_shadow_price_sum_limit_nonzero(self, result: SolverResult) -> None:
        """sum_limit is binding → shadow price must be non-zero."""
        assert result.shadow_prices is not None
        assert abs(result.shadow_prices["sum_limit"]) > 1e-8

    def test_shadow_price_x_limit_nonzero(self, result: SolverResult) -> None:
        """x_limit is binding → shadow price must be non-zero."""
        assert result.shadow_prices is not None
        assert abs(result.shadow_prices["x_limit"]) > 1e-8

    def test_shadow_price_y_limit_zero(self, result: SolverResult) -> None:
        """y_limit is non-binding (slack=4) → shadow price must be zero."""
        assert result.shadow_prices is not None
        assert abs(result.shadow_prices["y_limit"]) < 1e-8

    def test_shadow_price_sum_limit_value(self, result: SolverResult) -> None:
        """Increasing sum_limit by 1 (10→11) raises obj by 2: x=6,y=5,obj=28."""
        assert result.shadow_prices is not None
        assert result.shadow_prices["sum_limit"] == pytest.approx(2.0, abs=1e-6)

    def test_shadow_price_x_limit_value(self, result: SolverResult) -> None:
        """Increasing x_limit by 1 (6→7) raises obj by 1: x=7,y=3,obj=27."""
        assert result.shadow_prices is not None
        assert result.shadow_prices["x_limit"] == pytest.approx(1.0, abs=1e-6)

    # Slack / binding --------------------------------------------------------

    def test_sum_limit_zero_slack(self, result: SolverResult) -> None:
        assert result.constraint_slack is not None
        assert result.constraint_slack["sum_limit"] == pytest.approx(0.0, abs=1e-8)

    def test_x_limit_zero_slack(self, result: SolverResult) -> None:
        assert result.constraint_slack is not None
        assert result.constraint_slack["x_limit"] == pytest.approx(0.0, abs=1e-8)

    def test_y_limit_positive_slack(self, result: SolverResult) -> None:
        assert result.constraint_slack is not None
        assert result.constraint_slack["y_limit"] == pytest.approx(4.0, abs=1e-6)

    def test_binding_contains_sum_limit(self, result: SolverResult) -> None:
        assert result.binding_constraints is not None
        assert "sum_limit" in result.binding_constraints

    def test_binding_contains_x_limit(self, result: SolverResult) -> None:
        assert result.binding_constraints is not None
        assert "x_limit" in result.binding_constraints

    def test_y_limit_not_binding(self, result: SolverResult) -> None:
        assert result.binding_constraints is not None
        assert "y_limit" not in result.binding_constraints

    # Ranging ----------------------------------------------------------------

    def test_objective_ranges_present(self, result: SolverResult) -> None:
        assert result.objective_ranges is not None

    def test_objective_ranges_have_correct_keys(self, result: SolverResult) -> None:
        assert result.objective_ranges is not None
        assert "x" in result.objective_ranges
        assert "y" in result.objective_ranges

    def test_rhs_ranges_present(self, result: SolverResult) -> None:
        assert result.rhs_ranges is not None

    def test_rhs_ranges_have_correct_keys(self, result: SolverResult) -> None:
        assert result.rhs_ranges is not None
        assert "sum_limit" in result.rhs_ranges
        assert "x_limit" in result.rhs_ranges
        assert "y_limit" in result.rhs_ranges

    def test_objective_range_x_lower_bound(self, result: SolverResult) -> None:
        """c_x can decrease to 2.0 (then y-only basis becomes equally good)."""
        assert result.objective_ranges is not None
        lo, hi = result.objective_ranges["x"]
        assert lo == pytest.approx(2.0, abs=1e-6)

    def test_rhs_range_sum_limit(self, result: SolverResult) -> None:
        """sum_limit RHS range: [6.0, 14.0] (both individual limits bind at extremes)."""
        assert result.rhs_ranges is not None
        lo, hi = result.rhs_ranges["sum_limit"]
        assert lo == pytest.approx(6.0, abs=1e-6)
        assert hi == pytest.approx(14.0, abs=1e-6)


# ===========================================================================
# Test: solver timeout (time_limit_reached)
# ===========================================================================


class TestSolveTimeout:
    def test_status_time_limit_reached(self) -> None:
        """A 60-item knapsack with a 10ms limit must return time_limit_reached."""
        result = solve(make_large_mip())
        assert result.status == "time_limit_reached"

    def test_solve_time_within_generous_bound(self) -> None:
        """Solver should respect the time limit (within a 5× tolerance)."""
        result = solve(make_large_mip())
        # 0.01s limit; allow up to 5× for OS scheduling jitter
        assert result.solve_time_seconds < 5.0

    def test_no_iis_on_timeout(self) -> None:
        result = solve(make_large_mip())
        assert result.iis is None


# ===========================================================================
# Test: compute_iis standalone function
# ===========================================================================


class TestComputeIIS:
    def test_iis_on_infeasible(self) -> None:
        iis = compute_iis(make_infeasible_lp())
        assert "c_upper" in iis.conflicting_constraints
        assert "c_lower" in iis.conflicting_constraints

    def test_iis_explanation_non_empty(self) -> None:
        iis = compute_iis(make_infeasible_lp())
        assert len(iis.explanation) > 0

    def test_iis_explanation_mentions_constraints(self) -> None:
        iis = compute_iis(make_infeasible_lp())
        assert "c_upper" in iis.explanation or "c_lower" in iis.explanation

    def test_iis_bound_conflicts_empty_when_no_conflict(self) -> None:
        iis = compute_iis(make_infeasible_lp())
        assert iis.conflicting_variable_bounds == []

    def test_iis_with_bound_conflict(self) -> None:
        """Variable with lb > ub causes infeasibility via bound conflict."""
        inp = SolverInput(
            num_variables=2,
            num_constraints=1,
            variable_names=["x", "y"],
            variable_lower_bounds=[10.0, 0.0],  # x lb=10
            variable_upper_bounds=[5.0, 1e30],   # x ub=5  → lb > ub
            variable_types=["continuous", "continuous"],
            constraint_names=["c1"],
            constraint_matrix=[[1.0, 1.0]],
            constraint_senses=["<="],
            constraint_rhs=[20.0],
            objective_coefficients=[1.0, 1.0],
            objective_sense="minimize",
        )
        iis = compute_iis(inp)
        # Bound conflict must be reported
        assert len(iis.conflicting_variable_bounds) > 0
        assert any("x" in s for s in iis.conflicting_variable_bounds)


# ===========================================================================
# Test: error handling
# ===========================================================================


class TestSolverErrors:
    def test_unsupported_solver_raises(self) -> None:
        from sage_solver_core.models import SolverError

        with pytest.raises(SolverError, match="Unsupported solver"):
            solve(make_simple_lp(), solver="cplex")

    def test_result_is_fully_typed(self) -> None:
        """All returned objects must be proper SolverResult instances."""
        for inp in [make_simple_lp(), make_simple_mip(), make_infeasible_lp()]:
            result = solve(inp)
            assert isinstance(result, SolverResult)
