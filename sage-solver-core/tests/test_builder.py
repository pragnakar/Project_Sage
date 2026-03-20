"""Tests for sage_core/builder.py — Stage 3 Model Builder.

Coverage:
- build_from_lp: variable names/bounds/types, constraint matrix, objective,
  error cases (undefined variables)
- build_from_mip: type mapping, binary bounds, solver parameter forwarding
- build_from_portfolio: variable bounds, quadratic matrix, constraints
  (allocation, sector), forbidden assets, asymmetric covariance error
- build_from_scheduling: variable count/naming, coverage/max-hours/consecutive
  constraints, unavailability/skill restrictions, objective
- validate_model: all six checks
- Integration: LP build+solve, portfolio 5-asset weights sum, scheduling
  coverage verification, infeasible scheduling detection
"""

from __future__ import annotations

import pytest

from sage_solver_core.builder import (
    ValidationIssue,
    build_from_lp,
    build_from_mip,
    build_from_portfolio,
    build_from_scheduling,
    validate_model,
)
from sage_solver_core.models import (
    Asset,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    MIPModel,
    MIPVariable,
    ModelBuildError,
    PortfolioConstraints,
    PortfolioModel,
    SchedulingModel,
    Shift,
    SolverInput,
    Worker,
)
from sage_solver_core.solver import solve

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_canonical_lp() -> LPModel:
    """Canonical LP: max 3x + 2y  s.t.  x+y≤10, x≤6, y≤8, x,y≥0."""
    return LPModel(
        name="canonical",
        variables=[
            LPVariable(name="x", lower_bound=0.0),
            LPVariable(name="y", lower_bound=0.0),
        ],
        constraints=[
            LinearConstraint(name="sum_limit", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=10.0),
            LinearConstraint(name="x_limit", coefficients={"x": 1.0}, sense="<=", rhs=6.0),
            LinearConstraint(name="y_limit", coefficients={"y": 1.0}, sense="<=", rhs=8.0),
        ],
        objective=LinearObjective(sense="maximize", coefficients={"x": 3.0, "y": 2.0}),
    )


def _make_canonical_mip() -> MIPModel:
    """Canonical MIP: same as LP but x integer, y binary."""
    return MIPModel(
        name="canonical_mip",
        variables=[
            MIPVariable(name="x", lower_bound=0.0, var_type="integer"),
            MIPVariable(name="y", var_type="binary"),
            MIPVariable(name="z", lower_bound=0.0, var_type="continuous"),
        ],
        constraints=[
            LinearConstraint(name="c1", coefficients={"x": 1.0, "y": 1.0, "z": 1.0}, sense="<=", rhs=10.0),
        ],
        objective=LinearObjective(sense="minimize", coefficients={"x": 1.0, "y": 2.0, "z": 3.0}),
        time_limit_seconds=30.0,
        mip_gap_tolerance=0.001,
    )


def _make_5asset_portfolio() -> PortfolioModel:
    """5-asset portfolio with diagonal covariance."""
    return PortfolioModel(
        assets=[
            Asset(name="AAPL", expected_return=0.12, sector="Tech"),
            Asset(name="MSFT", expected_return=0.10, sector="Tech"),
            Asset(name="JPM",  expected_return=0.08, sector="Finance"),
            Asset(name="JNJ",  expected_return=0.06, sector="Healthcare"),
            Asset(name="BND",  expected_return=0.03, sector="Bonds"),
        ],
        covariance_matrix=[
            [0.04, 0.02, 0.01, 0.00, 0.00],
            [0.02, 0.03, 0.01, 0.00, 0.00],
            [0.01, 0.01, 0.02, 0.00, 0.00],
            [0.00, 0.00, 0.00, 0.01, 0.00],
            [0.00, 0.00, 0.00, 0.00, 0.005],
        ],
        risk_aversion=2.0,
        constraints=PortfolioConstraints(
            max_allocation_per_asset=0.40,
            min_total_allocation=1.0,
            max_total_allocation=1.0,
        ),
    )


def _make_scheduling_3w2s() -> SchedulingModel:
    """3 workers, 2 shifts, 1 day — simple feasible scheduling problem."""
    return SchedulingModel(
        workers=[
            Worker(name="Alice", max_hours=8.0),
            Worker(name="Bob",   max_hours=8.0),
            Worker(name="Charlie", max_hours=8.0),
        ],
        shifts=[
            Shift(name="Morning", duration_hours=4.0, required_workers=1),
            Shift(name="Evening", duration_hours=4.0, required_workers=1),
        ],
        planning_horizon_days=1,
        max_consecutive_days=None,  # keep it simple for unit tests
        min_rest_hours=None,
    )


# ===========================================================================
# TestBuildFromLP
# ===========================================================================


class TestBuildFromLP:
    def test_returns_solver_input(self) -> None:
        model = _make_canonical_lp()
        result = build_from_lp(model)
        assert isinstance(result, SolverInput)

    def test_variable_count(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.num_variables == 2

    def test_constraint_count(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.num_constraints == 3

    def test_variable_names(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.variable_names == ["x", "y"]

    def test_variable_types_all_continuous(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert all(t == "continuous" for t in inp.variable_types)

    def test_variable_lb_explicit(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", lower_bound=2.5)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=10.0)],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        inp = build_from_lp(model)
        assert inp.variable_lower_bounds[0] == pytest.approx(2.5)

    def test_variable_lb_none_maps_to_neg_inf(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", lower_bound=None)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=10.0)],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        inp = build_from_lp(model)
        assert inp.variable_lower_bounds[0] == pytest.approx(-1e30)

    def test_variable_ub_none_maps_to_pos_inf(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        # y has no upper bound (None → 1e30)
        assert inp.variable_upper_bounds[1] == pytest.approx(1e30)

    def test_variable_ub_explicit(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", upper_bound=5.0)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=10.0)],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        inp = build_from_lp(model)
        assert inp.variable_upper_bounds[0] == pytest.approx(5.0)

    def test_objective_sense(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.objective_sense == "maximize"

    def test_objective_coefficients(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.objective_coefficients[0] == pytest.approx(3.0)  # x
        assert inp.objective_coefficients[1] == pytest.approx(2.0)  # y

    def test_objective_variable_not_in_objective_gets_zero(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="y")],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=10.0)],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0}),
            # y intentionally absent from objective
        )
        inp = build_from_lp(model)
        assert inp.objective_coefficients[1] == pytest.approx(0.0)  # y gets 0

    def test_constraint_names(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.constraint_names == ["sum_limit", "x_limit", "y_limit"]

    def test_constraint_senses(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.constraint_senses == ["<=", "<=", "<="]

    def test_constraint_rhs(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.constraint_rhs == pytest.approx([10.0, 6.0, 8.0])

    def test_constraint_matrix_shape(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert len(inp.constraint_matrix) == 3
        assert all(len(row) == 2 for row in inp.constraint_matrix)

    def test_constraint_matrix_values(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        # sum_limit: [1, 1]; x_limit: [1, 0]; y_limit: [0, 1]
        assert inp.constraint_matrix[0] == pytest.approx([1.0, 1.0])
        assert inp.constraint_matrix[1] == pytest.approx([1.0, 0.0])
        assert inp.constraint_matrix[2] == pytest.approx([0.0, 1.0])

    def test_variable_absent_from_constraint_gets_zero_coeff(self) -> None:
        """Variable x not in constraint c2 → zero in that row."""
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="y")],
            constraints=[
                LinearConstraint(name="c1", coefficients={"x": 2.0, "y": 3.0}, sense="<=", rhs=5.0),
                LinearConstraint(name="c2", coefficients={"y": 1.0}, sense=">=", rhs=1.0),
            ],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0, "y": 1.0}),
        )
        inp = build_from_lp(model)
        assert inp.constraint_matrix[1][0] == pytest.approx(0.0)  # x in c2
        assert inp.constraint_matrix[1][1] == pytest.approx(1.0)  # y in c2

    def test_undefined_variable_in_constraint_raises(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x")],
            constraints=[
                LinearConstraint(name="c1", coefficients={"x": 1.0, "ghost": 2.0}, sense="<=", rhs=5.0)
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        with pytest.raises(ModelBuildError, match="undefined variable 'ghost'"):
            build_from_lp(model)

    def test_undefined_variable_in_objective_raises(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x")],
            constraints=[LinearConstraint(name="c1", coefficients={"x": 1.0}, sense="<=", rhs=5.0)],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0, "ghost": 3.0}),
        )
        with pytest.raises(ModelBuildError, match="undefined variable 'ghost'"):
            build_from_lp(model)

    def test_no_quadratic_term(self) -> None:
        inp = build_from_lp(_make_canonical_lp())
        assert inp.objective_quadratic is None

    def test_mixed_senses(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="y")],
            constraints=[
                LinearConstraint(name="le", coefficients={"x": 1.0}, sense="<=", rhs=5.0),
                LinearConstraint(name="ge", coefficients={"y": 1.0}, sense=">=", rhs=1.0),
                LinearConstraint(name="eq", coefficients={"x": 1.0, "y": 1.0}, sense="==", rhs=4.0),
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0, "y": 1.0}),
        )
        inp = build_from_lp(model)
        assert inp.constraint_senses == ["<=", ">=", "=="]


# ===========================================================================
# TestBuildFromMIP
# ===========================================================================


class TestBuildFromMIP:
    def test_returns_solver_input(self) -> None:
        assert isinstance(build_from_mip(_make_canonical_mip()), SolverInput)

    def test_variable_count(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.num_variables == 3

    def test_variable_types(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.variable_types == ["integer", "binary", "continuous"]

    def test_binary_bounds_forced_to_01(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        # y is binary → lb=0.0, ub=1.0 regardless of model defaults
        y_idx = inp.variable_names.index("y")
        assert inp.variable_lower_bounds[y_idx] == pytest.approx(0.0)
        assert inp.variable_upper_bounds[y_idx] == pytest.approx(1.0)

    def test_integer_bounds_preserved(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        x_idx = inp.variable_names.index("x")
        assert inp.variable_lower_bounds[x_idx] == pytest.approx(0.0)
        # No upper bound set → 1e30
        assert inp.variable_upper_bounds[x_idx] == pytest.approx(1e30)

    def test_time_limit_forwarded(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.time_limit_seconds == pytest.approx(30.0)

    def test_mip_gap_forwarded(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.mip_gap_tolerance == pytest.approx(0.001)

    def test_objective_coefficients(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.objective_coefficients == pytest.approx([1.0, 2.0, 3.0])

    def test_objective_sense_minimize(self) -> None:
        inp = build_from_mip(_make_canonical_mip())
        assert inp.objective_sense == "minimize"

    def test_undefined_variable_in_constraint_raises(self) -> None:
        model = MIPModel(
            name="t",
            variables=[MIPVariable(name="x", var_type="binary")],
            constraints=[
                LinearConstraint(name="c1", coefficients={"x": 1.0, "ghost": 1.0}, sense="<=", rhs=1.0)
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        with pytest.raises(ModelBuildError, match="undefined variable 'ghost'"):
            build_from_mip(model)


# ===========================================================================
# TestBuildFromPortfolio
# ===========================================================================


class TestBuildFromPortfolio:
    def test_returns_solver_input(self) -> None:
        assert isinstance(build_from_portfolio(_make_5asset_portfolio()), SolverInput)

    def test_variable_count(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert inp.num_variables == 5

    def test_variable_names(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert inp.variable_names == ["AAPL", "MSFT", "JPM", "JNJ", "BND"]

    def test_all_continuous(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert all(t == "continuous" for t in inp.variable_types)

    def test_objective_sense_minimize(self) -> None:
        """Portfolio builder always uses 'minimize' (negative Markowitz utility)."""
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert inp.objective_sense == "minimize"

    def test_objective_linear_coeffs_negated_returns(self) -> None:
        """c_i = -expected_return_i."""
        model = _make_5asset_portfolio()
        inp = build_from_portfolio(model)
        for i, asset in enumerate(model.assets):
            assert inp.objective_coefficients[i] == pytest.approx(-asset.expected_return)

    def test_quadratic_matrix_present(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert inp.objective_quadratic is not None

    def test_quadratic_matrix_shape(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        Q = inp.objective_quadratic
        assert len(Q) == 5
        assert all(len(row) == 5 for row in Q)

    def test_quadratic_matrix_values(self) -> None:
        """Q_ij = 2 * risk_aversion * Cov[i][j]."""
        model = _make_5asset_portfolio()
        inp = build_from_portfolio(model)
        lam = model.risk_aversion
        cov = model.covariance_matrix
        Q = inp.objective_quadratic
        for i in range(5):
            for j in range(5):
                assert Q[i][j] == pytest.approx(2.0 * lam * cov[i][j], abs=1e-12)

    def test_quadratic_matrix_symmetric(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        Q = inp.objective_quadratic
        for i in range(5):
            for j in range(5):
                assert Q[i][j] == pytest.approx(Q[j][i], abs=1e-12)

    def test_total_allocation_equality_constraint(self) -> None:
        """When min == max == 1.0, a single == constraint is created."""
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert "total_allocation" in inp.constraint_names
        idx = inp.constraint_names.index("total_allocation")
        assert inp.constraint_senses[idx] == "=="
        assert inp.constraint_rhs[idx] == pytest.approx(1.0)
        assert inp.constraint_matrix[idx] == pytest.approx([1.0] * 5)

    def test_total_allocation_split_when_range(self) -> None:
        """When min != max, two separate constraints are created."""
        model = PortfolioModel(
            assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
            covariance_matrix=[[0.01, 0.0], [0.0, 0.005]],
            constraints=PortfolioConstraints(min_total_allocation=0.8, max_total_allocation=1.0),
        )
        inp = build_from_portfolio(model)
        assert "total_allocation_min" in inp.constraint_names
        assert "total_allocation_max" in inp.constraint_names
        min_idx = inp.constraint_names.index("total_allocation_min")
        max_idx = inp.constraint_names.index("total_allocation_max")
        assert inp.constraint_senses[min_idx] == ">="
        assert inp.constraint_senses[max_idx] == "<="
        assert inp.constraint_rhs[min_idx] == pytest.approx(0.8)
        assert inp.constraint_rhs[max_idx] == pytest.approx(1.0)

    def test_per_asset_upper_bound(self) -> None:
        """max_allocation_per_asset sets variable upper bound."""
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert all(ub == pytest.approx(0.40) for ub in inp.variable_upper_bounds)

    def test_per_asset_lower_bound_default_zero(self) -> None:
        inp = build_from_portfolio(_make_5asset_portfolio())
        assert all(lb == pytest.approx(0.0) for lb in inp.variable_lower_bounds)

    def test_per_asset_lower_bound_explicit(self) -> None:
        model = PortfolioModel(
            assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
            covariance_matrix=[[0.01, 0.0], [0.0, 0.005]],
            constraints=PortfolioConstraints(min_allocation_per_asset=0.05),
        )
        inp = build_from_portfolio(model)
        assert all(lb == pytest.approx(0.05) for lb in inp.variable_lower_bounds)

    def test_forbidden_asset_zeroed(self) -> None:
        """Forbidden assets get lb = ub = 0."""
        model = PortfolioModel(
            assets=[
                Asset(name="A", expected_return=0.1),
                Asset(name="B", expected_return=0.05),
                Asset(name="C", expected_return=0.08),
            ],
            covariance_matrix=[[0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]],
            constraints=PortfolioConstraints(forbidden_assets=["B"]),
        )
        inp = build_from_portfolio(model)
        b_idx = inp.variable_names.index("B")
        assert inp.variable_lower_bounds[b_idx] == pytest.approx(0.0)
        assert inp.variable_upper_bounds[b_idx] == pytest.approx(0.0)
        # A and C are not forbidden
        assert inp.variable_upper_bounds[0] == pytest.approx(1.0)
        assert inp.variable_upper_bounds[2] == pytest.approx(1.0)

    def test_sector_constraint_created(self) -> None:
        """A sector cap creates a <= constraint summing assets in that sector."""
        model = PortfolioModel(
            assets=[
                Asset(name="AAPL", expected_return=0.12, sector="Tech"),
                Asset(name="MSFT", expected_return=0.10, sector="Tech"),
                Asset(name="BND",  expected_return=0.03, sector="Bonds"),
            ],
            covariance_matrix=[[0.04, 0.02, 0.0], [0.02, 0.03, 0.0], [0.0, 0.0, 0.005]],
            constraints=PortfolioConstraints(
                max_sector_allocation={"Tech": 0.60},
            ),
        )
        inp = build_from_portfolio(model)
        assert "sector_Tech_max" in inp.constraint_names
        idx = inp.constraint_names.index("sector_Tech_max")
        assert inp.constraint_senses[idx] == "<="
        assert inp.constraint_rhs[idx] == pytest.approx(0.60)
        # AAPL and MSFT are Tech (indices 0 and 1); BND is not
        assert inp.constraint_matrix[idx][0] == pytest.approx(1.0)
        assert inp.constraint_matrix[idx][1] == pytest.approx(1.0)
        assert inp.constraint_matrix[idx][2] == pytest.approx(0.0)

    def test_asymmetric_covariance_raises(self) -> None:
        model = PortfolioModel(
            assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
            covariance_matrix=[[0.01, 0.005], [0.006, 0.01]],  # [0][1] ≠ [1][0]
        )
        with pytest.raises(ModelBuildError, match="not symmetric"):
            build_from_portfolio(model)

    def test_symmetric_covariance_passes(self) -> None:
        model = PortfolioModel(
            assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
            covariance_matrix=[[0.01, 0.005], [0.005, 0.01]],
        )
        inp = build_from_portfolio(model)
        assert inp.num_variables == 2


# ===========================================================================
# TestBuildFromScheduling
# ===========================================================================


class TestBuildFromScheduling:
    def test_returns_solver_input(self) -> None:
        assert isinstance(build_from_scheduling(_make_scheduling_3w2s()), SolverInput)

    def test_variable_count(self) -> None:
        model = _make_scheduling_3w2s()
        inp = build_from_scheduling(model)
        # 3 workers × 2 shifts × 1 day = 6
        assert inp.num_variables == 3 * 2 * 1

    def test_variable_count_multi_day(self) -> None:
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=40.0), Worker(name="W2", max_hours=40.0)],
            shifts=[Shift(name="S1", duration_hours=8.0, required_workers=1)],
            planning_horizon_days=7,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        assert inp.num_variables == 2 * 1 * 7

    def test_all_binary(self) -> None:
        inp = build_from_scheduling(_make_scheduling_3w2s())
        assert all(t == "binary" for t in inp.variable_types)

    def test_variable_names_format(self) -> None:
        inp = build_from_scheduling(_make_scheduling_3w2s())
        assert "x_Alice_Morning_d0" in inp.variable_names
        assert "x_Bob_Evening_d0" in inp.variable_names
        assert "x_Charlie_Morning_d0" in inp.variable_names

    def test_variable_names_ordering(self) -> None:
        """Variables are ordered: worker, shift, day (outer to inner)."""
        inp = build_from_scheduling(_make_scheduling_3w2s())
        expected = [
            "x_Alice_Morning_d0", "x_Alice_Evening_d0",
            "x_Bob_Morning_d0",   "x_Bob_Evening_d0",
            "x_Charlie_Morning_d0", "x_Charlie_Evening_d0",
        ]
        assert inp.variable_names == expected

    def test_coverage_constraint_count(self) -> None:
        """num_shifts × planning_horizon_days coverage constraints."""
        model = _make_scheduling_3w2s()
        inp = build_from_scheduling(model)
        coverage_names = [n for n in inp.constraint_names if n.startswith("coverage_")]
        # 2 shifts × 1 day = 2
        assert len(coverage_names) == 2

    def test_coverage_constraint_names(self) -> None:
        inp = build_from_scheduling(_make_scheduling_3w2s())
        assert "coverage_Morning_d0" in inp.constraint_names
        assert "coverage_Evening_d0" in inp.constraint_names

    def test_coverage_rhs(self) -> None:
        """Coverage RHS equals shift.required_workers."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=16.0), Worker(name="W2", max_hours=16.0), Worker(name="W3", max_hours=16.0)],
            shifts=[Shift(name="Night", duration_hours=8.0, required_workers=2)],
            planning_horizon_days=1,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        idx = inp.constraint_names.index("coverage_Night_d0")
        assert inp.constraint_rhs[idx] == pytest.approx(2.0)
        assert inp.constraint_senses[idx] == ">="

    def test_coverage_constraint_coefficients(self) -> None:
        """Coverage row has coefficient 1 for each worker's assignment variable."""
        inp = build_from_scheduling(_make_scheduling_3w2s())
        idx = inp.constraint_names.index("coverage_Morning_d0")
        row = inp.constraint_matrix[idx]
        # Workers: Alice(0), Bob(1), Charlie(2) on Morning(shift 0) day 0
        # idx = w*2*1 + 0*1 + 0 = w*2
        assert row[0] == pytest.approx(1.0)  # Alice_Morning_d0
        assert row[2] == pytest.approx(1.0)  # Bob_Morning_d0
        assert row[4] == pytest.approx(1.0)  # Charlie_Morning_d0
        assert row[1] == pytest.approx(0.0)  # Alice_Evening_d0 (different shift)

    def test_max_hours_constraint_count(self) -> None:
        """One max_hours constraint per worker."""
        inp = build_from_scheduling(_make_scheduling_3w2s())
        hours_names = [n for n in inp.constraint_names if n.startswith("max_hours_")]
        assert len(hours_names) == 3

    def test_max_hours_rhs(self) -> None:
        model = _make_scheduling_3w2s()
        inp = build_from_scheduling(model)
        assert inp.constraint_rhs[inp.constraint_names.index("max_hours_Alice")] == pytest.approx(8.0)
        assert inp.constraint_rhs[inp.constraint_names.index("max_hours_Bob")] == pytest.approx(8.0)

    def test_max_hours_coefficients(self) -> None:
        """Hours constraint uses shift.duration_hours as coefficient."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=40.0)],
            shifts=[
                Shift(name="Short", duration_hours=4.0, required_workers=1),
                Shift(name="Long",  duration_hours=8.0, required_workers=1),
            ],
            planning_horizon_days=2,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        idx = inp.constraint_names.index("max_hours_W1")
        row = inp.constraint_matrix[idx]
        # Variables: x_W1_Short_d0, x_W1_Short_d1, x_W1_Long_d0, x_W1_Long_d1
        # Short duration = 4.0, Long duration = 8.0
        assert row[0] == pytest.approx(4.0)  # Short d0
        assert row[1] == pytest.approx(4.0)  # Short d1
        assert row[2] == pytest.approx(8.0)  # Long d0
        assert row[3] == pytest.approx(8.0)  # Long d1

    def test_unavailability_zeroed(self) -> None:
        """Unavailable (worker, shift) pairs have var_ub = 0 for all days."""
        model = SchedulingModel(
            workers=[
                Worker(name="Alice", max_hours=16.0, unavailable_shifts=["Night"]),
                Worker(name="Bob",   max_hours=16.0),
            ],
            shifts=[
                Shift(name="Day",   duration_hours=8.0, required_workers=1),
                Shift(name="Night", duration_hours=8.0, required_workers=1),
            ],
            planning_horizon_days=2,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        # Alice_Night_d0 and Alice_Night_d1 must have ub=0
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Alice_Night_d0")] == pytest.approx(0.0)
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Alice_Night_d1")] == pytest.approx(0.0)
        # Alice_Day_* and Bob_* should be ub=1
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Alice_Day_d0")] == pytest.approx(1.0)
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Bob_Night_d0")] == pytest.approx(1.0)

    def test_skill_mismatch_zeroed(self) -> None:
        """Workers without required skills get ub = 0 for that shift."""
        model = SchedulingModel(
            workers=[
                Worker(name="Expert", max_hours=16.0, skills=["surgery"]),
                Worker(name="Junior", max_hours=16.0, skills=[]),  # no surgery skill
            ],
            shifts=[
                Shift(name="OR",     duration_hours=8.0, required_workers=1, required_skills=["surgery"]),
                Shift(name="Admin",  duration_hours=4.0, required_workers=1),
            ],
            planning_horizon_days=1,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        # Junior cannot work OR (missing "surgery")
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Junior_OR_d0")] == pytest.approx(0.0)
        # Expert can work OR
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Expert_OR_d0")] == pytest.approx(1.0)
        # Both can work Admin
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Junior_Admin_d0")] == pytest.approx(1.0)
        assert inp.variable_upper_bounds[inp.variable_names.index("x_Expert_Admin_d0")] == pytest.approx(1.0)

    def test_objective_minimize_weighted_labor_cost(self) -> None:
        inp = build_from_scheduling(_make_scheduling_3w2s())
        assert inp.objective_sense == "minimize"
        # Non-uniform costs in [1.0, 2.0) — deterministic, varies by worker×shift
        assert all(1.0 <= c < 2.0 for c in inp.objective_coefficients)
        # Not all the same (non-trivial for MIP solver)
        assert len(set(round(c, 4) for c in inp.objective_coefficients)) > 1

    def test_consecutive_days_constraints_present(self) -> None:
        """With max_consecutive_days=5 and 7-day horizon: 2 windows per worker."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=56.0), Worker(name="W2", max_hours=56.0)],
            shifts=[Shift(name="S1", duration_hours=8.0, required_workers=1)],
            planning_horizon_days=7,
            max_consecutive_days=5,
        )
        inp = build_from_scheduling(model)
        consec_names = [n for n in inp.constraint_names if n.startswith("consec_")]
        # 2 workers × 2 windows = 4 constraints
        assert len(consec_names) == 4

    def test_consecutive_days_no_constraint_when_horizon_le_max(self) -> None:
        """No consecutive constraint when planning_horizon_days <= max_consecutive_days."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=40.0)],
            shifts=[Shift(name="S1", duration_hours=8.0, required_workers=1)],
            planning_horizon_days=5,
            max_consecutive_days=5,
        )
        inp = build_from_scheduling(model)
        consec_names = [n for n in inp.constraint_names if n.startswith("consec_")]
        assert len(consec_names) == 0

    def test_consecutive_days_none_skipped(self) -> None:
        """No consecutive constraints when max_consecutive_days is None."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=56.0)],
            shifts=[Shift(name="S1", duration_hours=8.0, required_workers=1)],
            planning_horizon_days=7,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        assert all(not n.startswith("consec_") for n in inp.constraint_names)

    def test_consecutive_days_rhs(self) -> None:
        """Consecutive days constraint RHS = max_consecutive_days."""
        model = SchedulingModel(
            workers=[Worker(name="W1", max_hours=56.0)],
            shifts=[Shift(name="S1", duration_hours=8.0, required_workers=1)],
            planning_horizon_days=7,
            max_consecutive_days=5,
        )
        inp = build_from_scheduling(model)
        for name in inp.constraint_names:
            if name.startswith("consec_"):
                idx = inp.constraint_names.index(name)
                assert inp.constraint_rhs[idx] == pytest.approx(5.0)
                assert inp.constraint_senses[idx] == "<="

    def test_all_lower_bounds_zero(self) -> None:
        inp = build_from_scheduling(_make_scheduling_3w2s())
        assert all(lb == pytest.approx(0.0) for lb in inp.variable_lower_bounds)

    def test_default_upper_bounds_one(self) -> None:
        """Non-blocked variables have ub = 1.0."""
        inp = build_from_scheduling(_make_scheduling_3w2s())
        # No restrictions in the basic model → all ub = 1.0
        assert all(ub == pytest.approx(1.0) for ub in inp.variable_upper_bounds)


# ===========================================================================
# TestValidateModel
# ===========================================================================


class TestValidateModel:
    def test_clean_lp_no_issues(self) -> None:
        model = _make_canonical_lp()
        issues = validate_model(model)
        assert issues == []

    def test_returns_list(self) -> None:
        assert isinstance(validate_model(_make_canonical_lp()), list)

    def test_empty_constraints_warning(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x")],
            constraints=[],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        issues = validate_model(model)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "no constraints" in issues[0].message.lower()

    def test_variable_not_in_any_constraint_or_objective(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="unused")],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=5.0)],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        issues = validate_model(model)
        assert any("unused" in i.message for i in issues)
        assert any(i.severity == "warning" for i in issues)

    def test_variable_in_objective_only_not_flagged(self) -> None:
        """A variable in the objective but not constraints is OK (not flagged as unused)."""
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", upper_bound=10.0), LPVariable(name="y", upper_bound=10.0)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=5.0)],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0, "y": 1.0}),
        )
        issues = validate_model(model)
        # y is in objective → not flagged as unused
        assert not any("unused" in i.message.lower() and "y" in i.message for i in issues)

    def test_unbounded_maximize_warning(self) -> None:
        """Variable with positive obj coeff, no upper bound, no <= constraint → warning."""
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", lower_bound=0.0)],  # ub=None (no bound)
            constraints=[],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0}),
        )
        issues = validate_model(model)
        assert any("unbounded" in i.message.lower() or "upper bound" in i.message.lower() for i in issues)

    def test_no_unbounded_warning_when_upper_bound_set(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", lower_bound=0.0, upper_bound=10.0)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=10.0)],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0}),
        )
        issues = validate_model(model)
        # No issues at all: x has finite ub and a bounding constraint
        assert issues == []

    def test_no_unbounded_warning_for_minimize(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x", lower_bound=0.0)],
            constraints=[LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<=", rhs=5.0)],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        issues = validate_model(model)
        assert not any("unbounded" in i.message.lower() for i in issues)

    def test_coefficient_magnitude_warning(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="y")],
            constraints=[
                LinearConstraint(name="c", coefficients={"x": 1.0, "y": 2e7}, sense="<=", rhs=1e8)
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0, "y": 1.0}),
        )
        issues = validate_model(model)
        assert any("magnitude" in i.message.lower() or "numerical" in i.message.lower() for i in issues)

    def test_coefficient_magnitude_ok_when_ratio_small(self) -> None:
        model = LPModel(
            name="t",
            variables=[LPVariable(name="x"), LPVariable(name="y")],
            constraints=[
                LinearConstraint(name="c", coefficients={"x": 1.0, "y": 100.0}, sense="<=", rhs=500.0)
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0, "y": 1.0}),
        )
        issues = validate_model(model)
        assert not any("magnitude" in i.message.lower() for i in issues)

    def test_issue_str_format(self) -> None:
        issue = ValidationIssue(severity="warning", message="Test message")
        assert "[WARNING]" in str(issue)
        assert "Test message" in str(issue)

    def test_validation_issue_details(self) -> None:
        issue = ValidationIssue(severity="error", message="Bad", details={"key": "val"})
        assert issue.details == {"key": "val"}


# ===========================================================================
# Integration tests — build + solve end-to-end
# ===========================================================================


class TestIntegration:
    def test_lp_build_and_solve(self) -> None:
        """build_from_lp → solve() → correct optimal solution."""
        inp = build_from_lp(_make_canonical_lp())
        result = solve(inp)

        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0, abs=1e-6)
        assert result.variable_values["x"] == pytest.approx(6.0, abs=1e-6)
        assert result.variable_values["y"] == pytest.approx(4.0, abs=1e-6)

    def test_mip_build_and_solve(self) -> None:
        """build_from_mip with integer/binary variables → solve() → optimal."""
        model = MIPModel(
            name="simple_mip",
            variables=[
                MIPVariable(name="x", lower_bound=0.0, var_type="integer"),
                MIPVariable(name="y", lower_bound=0.0, var_type="integer"),
            ],
            constraints=[
                LinearConstraint(name="sum_limit", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=10.0),
                LinearConstraint(name="x_limit",   coefficients={"x": 1.0},             sense="<=", rhs=6.0),
                LinearConstraint(name="y_limit",   coefficients={"y": 1.0},             sense="<=", rhs=8.0),
            ],
            objective=LinearObjective(sense="maximize", coefficients={"x": 3.0, "y": 2.0}),
        )
        inp = build_from_mip(model)
        result = solve(inp)

        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0, abs=1e-6)
        assert result.variable_values["x"] == pytest.approx(6.0, abs=1e-6)
        assert result.variable_values["y"] == pytest.approx(4.0, abs=1e-6)

    def test_portfolio_build_and_solve_weights_sum_to_one(self) -> None:
        """5-asset Markowitz QP: optimal weights sum to 1.0."""
        inp = build_from_portfolio(_make_5asset_portfolio())
        result = solve(inp)

        assert result.status == "optimal"
        assert result.variable_values is not None

        total_weight = sum(result.variable_values.values())
        assert total_weight == pytest.approx(1.0, abs=1e-4)

    def test_portfolio_build_and_solve_bounds_respected(self) -> None:
        """All weights are within [0, max_allocation_per_asset]."""
        inp = build_from_portfolio(_make_5asset_portfolio())
        result = solve(inp)

        assert result.variable_values is not None
        for name, w in result.variable_values.items():
            assert w >= -1e-4, f"Weight for {name} is negative: {w}"
            assert w <= 0.40 + 1e-4, f"Weight for {name} exceeds 0.40: {w}"

    def test_portfolio_forbidden_asset_zero(self) -> None:
        """Forbidden asset receives zero weight in optimal solution."""
        model = PortfolioModel(
            assets=[
                Asset(name="A", expected_return=0.15),
                Asset(name="B", expected_return=0.10),
                Asset(name="C", expected_return=0.05),
            ],
            covariance_matrix=[
                [0.04, 0.01, 0.00],
                [0.01, 0.02, 0.00],
                [0.00, 0.00, 0.01],
            ],
            constraints=PortfolioConstraints(forbidden_assets=["B"]),
        )
        inp = build_from_portfolio(model)
        result = solve(inp)

        assert result.status == "optimal"
        assert result.variable_values["B"] == pytest.approx(0.0, abs=1e-4)

    def test_scheduling_build_and_solve_coverage_met(self) -> None:
        """3 workers, 2 shifts (each needing 1): coverage is met optimally."""
        model = _make_scheduling_3w2s()
        inp = build_from_scheduling(model)
        result = solve(inp)

        assert result.status == "optimal"
        assert result.variable_values is not None

        # Verify coverage for Morning and Evening on day 0
        morning_coverage = sum(
            result.variable_values.get(f"x_{w.name}_Morning_d0", 0.0)
            for w in model.workers
        )
        evening_coverage = sum(
            result.variable_values.get(f"x_{w.name}_Evening_d0", 0.0)
            for w in model.workers
        )
        assert morning_coverage >= 1.0 - 1e-4, f"Morning coverage insufficient: {morning_coverage}"
        assert evening_coverage >= 1.0 - 1e-4, f"Evening coverage insufficient: {evening_coverage}"

    def test_scheduling_build_and_solve_min_cost(self) -> None:
        """Minimisation objective: total weighted labor cost (non-uniform costs)."""
        model = _make_scheduling_3w2s()
        inp = build_from_scheduling(model)
        result = solve(inp)

        assert result.status == "optimal"
        # 2 assignments needed (1 Morning + 1 Evening), costs in [1.0, 2.0)
        # Total should be between 2.0 and 4.0
        assert 2.0 <= result.objective_value < 4.0

    def test_scheduling_infeasible_too_few_workers(self) -> None:
        """1 worker, shift requiring 2: coverage constraint infeasible."""
        model = SchedulingModel(
            workers=[Worker(name="Solo", max_hours=16.0)],
            shifts=[Shift(name="Busy", duration_hours=8.0, required_workers=2)],
            planning_horizon_days=1,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        result = solve(inp)

        assert result.status == "infeasible"
        assert result.iis is not None
        # IIS should reference the coverage constraint
        assert any("coverage" in c for c in result.iis.conflicting_constraints)

    def test_scheduling_infeasible_hours_too_tight(self) -> None:
        """Worker with 4 max hours, shift is 8 hours: max_hours constraint impossible."""
        model = SchedulingModel(
            workers=[
                Worker(name="W1", max_hours=4.0),
                Worker(name="W2", max_hours=4.0),
            ],
            shifts=[Shift(name="AllDay", duration_hours=8.0, required_workers=2)],
            planning_horizon_days=1,
            max_consecutive_days=None,
        )
        inp = build_from_scheduling(model)
        result = solve(inp)

        assert result.status == "infeasible"
