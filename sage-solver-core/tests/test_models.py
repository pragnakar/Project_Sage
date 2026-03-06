"""Tests for sage_core/models.py.

Covers schema validation, serialization/deserialization, edge cases,
and error hierarchy construction.  All tests are pure Python — no solver
or file I/O dependencies.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sage_solver_core.models import (
    Asset,
    DataValidationError,
    FileIOError,
    IISResult,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    MIPModel,
    MIPVariable,
    ModelBuildError,
    PortfolioConstraints,
    PortfolioModel,
    RelaxationSuggestion,
    SAGEError,
    SAGEErrorResponse,
    SchedulingModel,
    Shift,
    SolverError,
    SolverInput,
    SolverResult,
    Worker,
)


# ===========================================================================
# Helpers
# ===========================================================================


def make_lp_variable(name: str = "x", lb: float | None = 0.0, ub: float | None = None) -> LPVariable:
    return LPVariable(name=name, lower_bound=lb, upper_bound=ub)


def make_constraint(
    name: str = "c1",
    coeffs: dict[str, float] | None = None,
    sense: str = "<=",
    rhs: float = 10.0,
) -> LinearConstraint:
    return LinearConstraint(
        name=name,
        coefficients=coeffs or {"x": 1.0, "y": 1.0},
        sense=sense,  # type: ignore[arg-type]
        rhs=rhs,
    )


def make_objective(sense: str = "maximize", coeffs: dict[str, float] | None = None) -> LinearObjective:
    return LinearObjective(sense=sense, coefficients=coeffs or {"x": 3.0, "y": 2.0})  # type: ignore[arg-type]


def make_simple_lp() -> LPModel:
    """Maximize 3x + 2y s.t. x+y<=10, x<=6, y<=8, x,y>=0  → optimal x=6, y=4, obj=26."""
    return LPModel(
        name="simple_lp",
        variables=[
            LPVariable(name="x", lower_bound=0.0, upper_bound=6.0),
            LPVariable(name="y", lower_bound=0.0, upper_bound=8.0),
        ],
        constraints=[
            LinearConstraint(name="sum_limit", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=10.0),
        ],
        objective=LinearObjective(sense="maximize", coefficients={"x": 3.0, "y": 2.0}),
    )


# ===========================================================================
# LPVariable
# ===========================================================================


class TestLPVariable:
    def test_defaults(self) -> None:
        v = LPVariable(name="x")
        assert v.lower_bound == 0.0
        assert v.upper_bound is None

    def test_free_variable(self) -> None:
        v = LPVariable(name="x", lower_bound=None, upper_bound=None)
        assert v.lower_bound is None
        assert v.upper_bound is None

    def test_negative_lower_bound(self) -> None:
        v = LPVariable(name="profit", lower_bound=-1000.0, upper_bound=1000.0)
        assert v.lower_bound == -1000.0

    def test_zero_bounds(self) -> None:
        v = LPVariable(name="x", lower_bound=0.0, upper_bound=0.0)
        assert v.lower_bound == 0.0
        assert v.upper_bound == 0.0

    def test_invalid_bounds_raises(self) -> None:
        with pytest.raises(ValidationError, match="lower_bound"):
            LPVariable(name="x", lower_bound=10.0, upper_bound=5.0)

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            LPVariable(name="")

    def test_serialization_round_trip(self) -> None:
        v = LPVariable(name="x", lower_bound=-5.0, upper_bound=10.0)
        data = v.model_dump()
        v2 = LPVariable.model_validate(data)
        assert v == v2

    def test_json_round_trip(self) -> None:
        v = LPVariable(name="y", lower_bound=0.0, upper_bound=None)
        v2 = LPVariable.model_validate_json(v.model_dump_json())
        assert v == v2


# ===========================================================================
# LinearConstraint
# ===========================================================================


class TestLinearConstraint:
    def test_valid_leq(self) -> None:
        c = make_constraint(sense="<=")
        assert c.sense == "<="

    def test_valid_geq(self) -> None:
        c = make_constraint(sense=">=")
        assert c.sense == ">="

    def test_valid_eq(self) -> None:
        c = make_constraint(sense="==")
        assert c.sense == "=="

    def test_invalid_sense_raises(self) -> None:
        with pytest.raises(ValidationError):
            LinearConstraint(name="c", coefficients={"x": 1.0}, sense="<", rhs=5.0)  # type: ignore[arg-type]

    def test_empty_coefficients_raises(self) -> None:
        with pytest.raises(ValidationError, match="coefficients must not be empty"):
            LinearConstraint(name="c", coefficients={}, sense="<=", rhs=5.0)

    def test_negative_coefficients(self) -> None:
        c = LinearConstraint(name="c", coefficients={"x": -2.5, "y": 3.0}, sense=">=", rhs=-10.0)
        assert c.coefficients["x"] == -2.5

    def test_serialization_round_trip(self) -> None:
        c = make_constraint()
        assert LinearConstraint.model_validate(c.model_dump()) == c


# ===========================================================================
# LinearObjective
# ===========================================================================


class TestLinearObjective:
    def test_minimize(self) -> None:
        obj = LinearObjective(sense="minimize", coefficients={"x": 1.0})
        assert obj.sense == "minimize"

    def test_maximize(self) -> None:
        obj = LinearObjective(sense="maximize", coefficients={"x": 1.0})
        assert obj.sense == "maximize"

    def test_invalid_sense_raises(self) -> None:
        with pytest.raises(ValidationError):
            LinearObjective(sense="max", coefficients={"x": 1.0})  # type: ignore[arg-type]

    def test_empty_coefficients_raises(self) -> None:
        with pytest.raises(ValidationError, match="coefficients must not be empty"):
            LinearObjective(sense="minimize", coefficients={})

    def test_multiple_variables(self) -> None:
        obj = LinearObjective(sense="maximize", coefficients={"x": 3.0, "y": 2.0, "z": -1.0})
        assert len(obj.coefficients) == 3


# ===========================================================================
# LPModel
# ===========================================================================


class TestLPModel:
    def test_simple_lp(self) -> None:
        model = make_simple_lp()
        assert model.name == "simple_lp"
        assert len(model.variables) == 2
        assert len(model.constraints) == 1

    def test_no_description(self) -> None:
        model = make_simple_lp()
        assert model.description is None

    def test_with_description(self) -> None:
        model = make_simple_lp()
        model2 = model.model_copy(update={"description": "A test LP"})
        assert model2.description == "A test LP"

    def test_empty_variables_raises(self) -> None:
        with pytest.raises(ValidationError):
            LPModel(
                name="bad",
                variables=[],
                constraints=[],
                objective=make_objective(),
            )

    def test_duplicate_variable_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate variable names"):
            LPModel(
                name="bad",
                variables=[LPVariable(name="x"), LPVariable(name="x")],
                constraints=[],
                objective=make_objective(coeffs={"x": 1.0}),
            )

    def test_duplicate_constraint_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate constraint names"):
            LPModel(
                name="bad",
                variables=[LPVariable(name="x")],
                constraints=[
                    make_constraint("c1", {"x": 1.0}),
                    make_constraint("c1", {"x": 2.0}),
                ],
                objective=make_objective(coeffs={"x": 1.0}),
            )

    def test_empty_constraints_allowed(self) -> None:
        """LP with no constraints (only variable bounds) should be valid."""
        model = LPModel(
            name="unconstrained",
            variables=[LPVariable(name="x", upper_bound=10.0)],
            constraints=[],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0}),
        )
        assert model.constraints == []

    def test_serialization_round_trip(self) -> None:
        model = make_simple_lp()
        model2 = LPModel.model_validate(model.model_dump())
        assert model == model2

    def test_json_round_trip(self) -> None:
        model = make_simple_lp()
        model2 = LPModel.model_validate_json(model.model_dump_json())
        assert model == model2


# ===========================================================================
# MIPVariable
# ===========================================================================


class TestMIPVariable:
    def test_continuous_default(self) -> None:
        v = MIPVariable(name="x")
        assert v.var_type == "continuous"

    def test_integer_type(self) -> None:
        v = MIPVariable(name="x", var_type="integer")
        assert v.var_type == "integer"

    def test_binary_type(self) -> None:
        v = MIPVariable(name="y", var_type="binary")
        assert v.var_type == "binary"
        assert v.lower_bound == 0.0
        assert v.upper_bound is None  # None is valid for binary (treated as 1)

    def test_binary_bad_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError, match="lower_bound must be 0"):
            MIPVariable(name="y", var_type="binary", lower_bound=0.5)

    def test_binary_bad_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError, match="upper_bound must be 1"):
            MIPVariable(name="y", var_type="binary", upper_bound=2.0)

    def test_invalid_bounds_raises(self) -> None:
        with pytest.raises(ValidationError, match="lower_bound"):
            MIPVariable(name="x", lower_bound=5.0, upper_bound=2.0)


# ===========================================================================
# MIPModel
# ===========================================================================


class TestMIPModel:
    def make_mip(self) -> MIPModel:
        return MIPModel(
            name="simple_mip",
            variables=[
                MIPVariable(name="x", var_type="integer", upper_bound=6.0),
                MIPVariable(name="y", var_type="integer", upper_bound=8.0),
            ],
            constraints=[
                LinearConstraint(name="sum_limit", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=10.0),
            ],
            objective=LinearObjective(sense="maximize", coefficients={"x": 3.0, "y": 2.0}),
        )

    def test_valid_mip(self) -> None:
        m = self.make_mip()
        assert m.name == "simple_mip"
        assert m.time_limit_seconds == 60.0
        assert m.mip_gap_tolerance == 0.0001

    def test_custom_time_limit(self) -> None:
        m = self.make_mip()
        m2 = m.model_copy(update={"time_limit_seconds": 300.0})
        assert m2.time_limit_seconds == 300.0

    def test_duplicate_variable_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate variable names"):
            MIPModel(
                name="bad",
                variables=[MIPVariable(name="x"), MIPVariable(name="x")],
                constraints=[],
                objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
            )

    def test_serialization_round_trip(self) -> None:
        m = self.make_mip()
        assert MIPModel.model_validate(m.model_dump()) == m


# ===========================================================================
# Portfolio schemas
# ===========================================================================


class TestAsset:
    def test_valid_asset(self) -> None:
        a = Asset(name="AAPL", expected_return=0.12, sector="Technology")
        assert a.name == "AAPL"
        assert a.sector == "Technology"

    def test_no_sector(self) -> None:
        a = Asset(name="BND", expected_return=0.03)
        assert a.sector is None

    def test_negative_return(self) -> None:
        a = Asset(name="SHORT", expected_return=-0.05)
        assert a.expected_return == -0.05


class TestPortfolioConstraints:
    def test_defaults(self) -> None:
        pc = PortfolioConstraints()
        assert pc.min_total_allocation == 1.0
        assert pc.max_total_allocation == 1.0
        assert pc.forbidden_assets is None

    def test_valid_constraints(self) -> None:
        pc = PortfolioConstraints(
            max_allocation_per_asset=0.20,
            min_allocation_per_asset=0.05,
            max_sector_allocation={"Tech": 0.40},
        )
        assert pc.max_allocation_per_asset == 0.20

    def test_min_gt_max_total_raises(self) -> None:
        with pytest.raises(ValidationError, match="min_total_allocation"):
            PortfolioConstraints(min_total_allocation=1.0, max_total_allocation=0.5)

    def test_min_gt_max_per_asset_raises(self) -> None:
        with pytest.raises(ValidationError, match="min_allocation_per_asset"):
            PortfolioConstraints(min_allocation_per_asset=0.30, max_allocation_per_asset=0.20)


class TestPortfolioModel:
    def make_2_asset_portfolio(self) -> PortfolioModel:
        return PortfolioModel(
            assets=[
                Asset(name="AAPL", expected_return=0.12, sector="Tech"),
                Asset(name="BND", expected_return=0.03, sector="Bonds"),
            ],
            covariance_matrix=[[0.04, 0.002], [0.002, 0.001]],
            risk_aversion=2.0,
        )

    def test_valid_portfolio(self) -> None:
        p = self.make_2_asset_portfolio()
        assert len(p.assets) == 2
        assert p.risk_aversion == 2.0

    def test_covariance_wrong_rows_raises(self) -> None:
        with pytest.raises(ValidationError, match="covariance_matrix has 1 rows"):
            PortfolioModel(
                assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
                covariance_matrix=[[0.04, 0.002]],  # only 1 row, need 2
            )

    def test_covariance_wrong_cols_raises(self) -> None:
        with pytest.raises(ValidationError, match="row 0"):
            PortfolioModel(
                assets=[Asset(name="A", expected_return=0.1), Asset(name="B", expected_return=0.05)],
                covariance_matrix=[[0.04], [0.002, 0.001]],  # row 0 has 1 col
            )

    def test_duplicate_asset_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate asset names"):
            PortfolioModel(
                assets=[
                    Asset(name="AAPL", expected_return=0.12),
                    Asset(name="AAPL", expected_return=0.08),
                ],
                covariance_matrix=[[0.04, 0.002], [0.002, 0.001]],
            )

    def test_single_asset(self) -> None:
        p = PortfolioModel(
            assets=[Asset(name="X", expected_return=0.10)],
            covariance_matrix=[[0.05]],
        )
        assert len(p.assets) == 1

    def test_serialization_round_trip(self) -> None:
        p = self.make_2_asset_portfolio()
        assert PortfolioModel.model_validate(p.model_dump()) == p


# ===========================================================================
# Scheduling schemas
# ===========================================================================


class TestWorker:
    def test_valid_worker(self) -> None:
        w = Worker(name="Alice", max_hours=40.0, skills=["ICU", "ER"])
        assert w.max_hours == 40.0
        assert "ICU" in (w.skills or [])

    def test_no_skills(self) -> None:
        w = Worker(name="Bob", max_hours=35.0)
        assert w.skills is None
        assert w.unavailable_shifts is None

    def test_zero_max_hours_raises(self) -> None:
        with pytest.raises(ValidationError):
            Worker(name="X", max_hours=0.0)

    def test_negative_max_hours_raises(self) -> None:
        with pytest.raises(ValidationError):
            Worker(name="X", max_hours=-8.0)


class TestShift:
    def test_valid_shift(self) -> None:
        s = Shift(name="morning", duration_hours=8.0, required_workers=2)
        assert s.required_workers == 2

    def test_zero_required_workers_raises(self) -> None:
        with pytest.raises(ValidationError):
            Shift(name="x", duration_hours=8.0, required_workers=0)

    def test_with_skills(self) -> None:
        s = Shift(name="night_ICU", duration_hours=12.0, required_workers=1, required_skills=["ICU"])
        assert s.required_skills == ["ICU"]


class TestSchedulingModel:
    def make_simple_schedule(self) -> SchedulingModel:
        return SchedulingModel(
            workers=[
                Worker(name="Alice", max_hours=40.0),
                Worker(name="Bob", max_hours=40.0),
            ],
            shifts=[
                Shift(name="morning", duration_hours=8.0, required_workers=1),
                Shift(name="evening", duration_hours=8.0, required_workers=1),
            ],
            planning_horizon_days=5,
        )

    def test_valid_schedule(self) -> None:
        s = self.make_simple_schedule()
        assert s.planning_horizon_days == 5
        assert s.max_consecutive_days == 5  # default
        assert s.min_rest_hours == 8.0  # default

    def test_duplicate_worker_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate worker names"):
            SchedulingModel(
                workers=[Worker(name="Alice", max_hours=40), Worker(name="Alice", max_hours=40)],
                shifts=[Shift(name="morning", duration_hours=8, required_workers=1)],
            )

    def test_duplicate_shift_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate shift names"):
            SchedulingModel(
                workers=[Worker(name="Alice", max_hours=40)],
                shifts=[
                    Shift(name="morning", duration_hours=8, required_workers=1),
                    Shift(name="morning", duration_hours=8, required_workers=1),
                ],
            )

    def test_serialization_round_trip(self) -> None:
        s = self.make_simple_schedule()
        assert SchedulingModel.model_validate(s.model_dump()) == s

    def test_no_max_consecutive_days(self) -> None:
        s = self.make_simple_schedule()
        s2 = s.model_copy(update={"max_consecutive_days": None})
        assert s2.max_consecutive_days is None


# ===========================================================================
# SolverInput
# ===========================================================================


class TestSolverInput:
    def make_minimal_solver_input(self) -> SolverInput:
        """1-variable, 1-constraint minimization (x >= 5, min x)."""
        return SolverInput(
            num_variables=1,
            num_constraints=1,
            variable_names=["x"],
            variable_lower_bounds=[0.0],
            variable_upper_bounds=[1e30],
            variable_types=["continuous"],
            constraint_names=["lb_constraint"],
            constraint_matrix=[[1.0]],
            constraint_senses=[">="],
            constraint_rhs=[5.0],
            objective_coefficients=[1.0],
            objective_sense="minimize",
        )

    def test_valid_input(self) -> None:
        si = self.make_minimal_solver_input()
        assert si.num_variables == 1
        assert si.num_constraints == 1

    def test_zero_constraints_allowed(self) -> None:
        si = SolverInput(
            num_variables=2,
            num_constraints=0,
            variable_names=["x", "y"],
            variable_lower_bounds=[0.0, 0.0],
            variable_upper_bounds=[10.0, 10.0],
            variable_types=["continuous", "continuous"],
            constraint_names=[],
            constraint_matrix=[],
            constraint_senses=[],
            constraint_rhs=[],
            objective_coefficients=[1.0, 1.0],
            objective_sense="maximize",
        )
        assert si.num_constraints == 0

    def test_wrong_variable_names_length_raises(self) -> None:
        with pytest.raises(ValidationError, match="variable_names"):
            SolverInput(
                num_variables=2,
                num_constraints=0,
                variable_names=["x"],  # wrong — should have 2
                variable_lower_bounds=[0.0, 0.0],
                variable_upper_bounds=[1e30, 1e30],
                variable_types=["continuous", "continuous"],
                constraint_names=[],
                constraint_matrix=[],
                constraint_senses=[],
                constraint_rhs=[],
                objective_coefficients=[1.0, 1.0],
                objective_sense="minimize",
            )

    def test_wrong_constraint_row_length_raises(self) -> None:
        with pytest.raises(ValidationError, match="constraint_matrix row 0"):
            SolverInput(
                num_variables=2,
                num_constraints=1,
                variable_names=["x", "y"],
                variable_lower_bounds=[0.0, 0.0],
                variable_upper_bounds=[1e30, 1e30],
                variable_types=["continuous", "continuous"],
                constraint_names=["c1"],
                constraint_matrix=[[1.0]],  # should have 2 columns
                constraint_senses=["<="],
                constraint_rhs=[10.0],
                objective_coefficients=[1.0, 1.0],
                objective_sense="minimize",
            )

    def test_quadratic_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValidationError, match="objective_quadratic"):
            SolverInput(
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
                objective_sense="minimize",
                objective_quadratic=[[1.0]],  # 1×1, should be 2×2
            )

    def test_valid_quadratic(self) -> None:
        si = SolverInput(
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
            objective_coefficients=[0.0, 0.0],
            objective_sense="minimize",
            objective_quadratic=[[2.0, 0.5], [0.5, 1.0]],
        )
        assert si.objective_quadratic is not None


# ===========================================================================
# IISResult
# ===========================================================================


class TestIISResult:
    def test_minimal_iis(self) -> None:
        iis = IISResult(
            conflicting_constraints=["c1", "c2"],
            explanation="c1 and c2 cannot both be satisfied simultaneously.",
        )
        assert len(iis.conflicting_constraints) == 2

    def test_empty_conflicts(self) -> None:
        iis = IISResult(explanation="No specific constraints identified.")
        assert iis.conflicting_constraints == []
        assert iis.conflicting_variable_bounds == []

    def test_with_variable_bounds(self) -> None:
        iis = IISResult(
            conflicting_constraints=["c1"],
            conflicting_variable_bounds=["x_upper"],
            explanation="x is bounded above but c1 requires it to be larger.",
        )
        assert "x_upper" in iis.conflicting_variable_bounds


# ===========================================================================
# SolverResult
# ===========================================================================


class TestSolverResult:
    def test_optimal_result(self) -> None:
        result = SolverResult(
            status="optimal",
            objective_value=26.0,
            solve_time_seconds=0.01,
            variable_values={"x": 6.0, "y": 4.0},
        )
        assert result.status == "optimal"
        assert result.objective_value == 26.0

    def test_optimal_missing_objective_raises(self) -> None:
        with pytest.raises(ValidationError, match="objective_value must be set"):
            SolverResult(
                status="optimal",
                solve_time_seconds=0.01,
                variable_values={"x": 1.0},
            )

    def test_optimal_missing_variable_values_raises(self) -> None:
        with pytest.raises(ValidationError, match="variable_values must be set"):
            SolverResult(
                status="optimal",
                objective_value=10.0,
                solve_time_seconds=0.01,
            )

    def test_infeasible_result(self) -> None:
        iis = IISResult(
            conflicting_constraints=["c1", "c2"],
            explanation="c1 and c2 conflict.",
        )
        result = SolverResult(
            status="infeasible",
            solve_time_seconds=0.05,
            iis=iis,
        )
        assert result.iis is not None
        assert len(result.iis.conflicting_constraints) == 2

    def test_iis_on_non_infeasible_raises(self) -> None:
        iis = IISResult(conflicting_constraints=["c1"], explanation="irrelevant")
        with pytest.raises(ValidationError, match="iis should only be set"):
            SolverResult(
                status="optimal",
                objective_value=5.0,
                solve_time_seconds=0.01,
                variable_values={"x": 1.0},
                iis=iis,
            )

    def test_unbounded_result(self) -> None:
        result = SolverResult(status="unbounded", solve_time_seconds=0.001)
        assert result.objective_value is None

    def test_time_limit_result(self) -> None:
        result = SolverResult(
            status="time_limit_reached",
            objective_value=42.0,
            bound=40.0,
            gap=0.048,
            solve_time_seconds=60.0,
            variable_values={"x": 5.0},
        )
        assert result.gap == pytest.approx(0.048)

    def test_sensitivity_fields(self) -> None:
        result = SolverResult(
            status="optimal",
            objective_value=26.0,
            solve_time_seconds=0.01,
            variable_values={"x": 6.0, "y": 4.0},
            shadow_prices={"sum_limit": 2.0},
            reduced_costs={"x": 0.0, "y": 0.0},
            constraint_slack={"sum_limit": 0.0},
            binding_constraints=["sum_limit"],
            objective_ranges={"x": (2.0, float("inf")), "y": (0.0, 3.0)},
            rhs_ranges={"sum_limit": (6.0, float("inf"))},
        )
        assert result.shadow_prices == {"sum_limit": 2.0}
        assert result.binding_constraints == ["sum_limit"]

    def test_serialization_round_trip(self) -> None:
        result = SolverResult(
            status="optimal",
            objective_value=26.0,
            solve_time_seconds=0.01,
            variable_values={"x": 6.0, "y": 4.0},
        )
        result2 = SolverResult.model_validate(result.model_dump())
        assert result2.status == result.status
        assert result2.objective_value == result.objective_value


# ===========================================================================
# RelaxationSuggestion
# ===========================================================================


class TestRelaxationSuggestion:
    def test_valid_suggestion(self) -> None:
        s = RelaxationSuggestion(
            constraint_name="max_allocation",
            current_value=0.20,
            suggested_value=0.25,
            relaxation_amount=0.05,
            relaxation_percent=25.0,
            new_objective_value=8.5,
            explanation="Increasing max allocation from 20% to 25% improves return by 0.5%.",
            priority=1,
        )
        assert s.priority == 1
        assert s.relaxation_percent == 25.0

    def test_no_new_objective(self) -> None:
        s = RelaxationSuggestion(
            constraint_name="c1",
            current_value=10.0,
            suggested_value=12.0,
            relaxation_amount=2.0,
            relaxation_percent=20.0,
            explanation="Relax c1 by 2 units.",
            priority=2,
        )
        assert s.new_objective_value is None

    def test_priority_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            RelaxationSuggestion(
                constraint_name="c1",
                current_value=10.0,
                suggested_value=12.0,
                relaxation_amount=2.0,
                relaxation_percent=20.0,
                explanation="Test",
                priority=0,
            )


# ===========================================================================
# Error hierarchy
# ===========================================================================


class TestErrorHierarchy:
    def test_sage_error_is_exception(self) -> None:
        err = SAGEError("something went wrong")
        assert isinstance(err, Exception)
        assert err.message == "something went wrong"
        assert err.details == {}
        assert err.suggestions == []

    def test_sage_error_with_details(self) -> None:
        err = SAGEError(
            "bad input",
            details={"field": "x", "value": -1},
            suggestions=["Make x non-negative"],
        )
        assert err.details["field"] == "x"
        assert len(err.suggestions) == 1

    def test_data_validation_error(self) -> None:
        err = DataValidationError(
            "Missing column 'expected_return'",
            details={"sheet": "Assets", "missing": ["expected_return"]},
            suggestions=["Add column 'expected_return' with decimal values"],
        )
        assert isinstance(err, SAGEError)
        assert isinstance(err, DataValidationError)

    def test_model_build_error(self) -> None:
        err = ModelBuildError("No variables defined")
        assert isinstance(err, SAGEError)

    def test_solver_error(self) -> None:
        err = SolverError("HiGHS returned code 5", details={"code": 5})
        assert isinstance(err, SAGEError)

    def test_file_io_error(self) -> None:
        err = FileIOError("Cannot open file", details={"path": "/tmp/missing.xlsx"})
        assert isinstance(err, SAGEError)

    def test_repr(self) -> None:
        err = SAGEError("test error")
        assert "SAGEError" in repr(err)
        assert "test error" in repr(err)


# ===========================================================================
# SAGEErrorResponse
# ===========================================================================


class TestSAGEErrorResponse:
    def test_from_exception(self) -> None:
        exc = DataValidationError(
            "Missing column",
            details={"sheet": "Assets"},
            suggestions=["Add the column"],
        )
        resp = SAGEErrorResponse.from_exception(exc)
        assert resp.error_type == "DataValidationError"
        assert resp.message == "Missing column"
        assert resp.details == {"sheet": "Assets"}
        assert resp.suggestions == ["Add the column"]

    def test_defaults(self) -> None:
        resp = SAGEErrorResponse(error_type="SAGEError", message="oops")
        assert resp.details == {}
        assert resp.suggestions == []

    def test_serialization(self) -> None:
        exc = SolverError("internal error", details={"code": 99})
        resp = SAGEErrorResponse.from_exception(exc)
        data = resp.model_dump()
        assert data["error_type"] == "SolverError"
        resp2 = SAGEErrorResponse.model_validate(data)
        assert resp == resp2
