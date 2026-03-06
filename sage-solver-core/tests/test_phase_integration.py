"""Phase 1 + Phase 2 cross-phase integration tests.

Verifies that Phase 1 schemas (LPModel, LinearConstraint, …) and Phase 2
solver (solve(), compute_iis()) work together without data loss, and that
SolverResult round-trips cleanly through JSON serialization.
"""

from __future__ import annotations

import json

import pytest

from sage_solver_core.models import (
    IISResult,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    SolverInput,
    SolverResult,
)
from sage_solver_core.solver import solve


# ---------------------------------------------------------------------------
# Minimal Phase-3 preview: LPModel → SolverInput conversion
# ---------------------------------------------------------------------------


def _lp_model_to_solver_input(model: LPModel) -> SolverInput:
    """Convert a Phase 1 LPModel to a Phase 2 SolverInput.

    This mirrors what builder.build_from_lp() will do in Phase 3.
    It exists here solely to enable cross-phase integration testing.
    """
    var_names = [v.name for v in model.variables]
    var_map = {v.name: i for i, v in enumerate(model.variables)}
    n = len(var_names)

    constraint_matrix: list[list[float]] = []
    for c in model.constraints:
        row = [0.0] * n
        for vname, coef in c.coefficients.items():
            row[var_map[vname]] = coef
        constraint_matrix.append(row)

    return SolverInput(
        num_variables=n,
        num_constraints=len(model.constraints),
        variable_names=var_names,
        variable_lower_bounds=[
            v.lower_bound if v.lower_bound is not None else 0.0
            for v in model.variables
        ],
        variable_upper_bounds=[
            v.upper_bound if v.upper_bound is not None else 1e30
            for v in model.variables
        ],
        variable_types=["continuous"] * n,
        constraint_names=[c.name for c in model.constraints],
        constraint_matrix=constraint_matrix,
        constraint_senses=[c.sense for c in model.constraints],
        constraint_rhs=[c.rhs for c in model.constraints],
        objective_coefficients=[
            model.objective.coefficients.get(v.name, 0.0) for v in model.variables
        ],
        objective_sense=model.objective.sense,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_lp_model_to_solver_roundtrip() -> None:
    """Phase 1 LPModel → SolverInput → solve() → SolverResult round-trip.

    Uses the canonical LP from CLAUDE.md:
        max 3x + 2y  s.t.  x+y ≤ 10,  x ≤ 6,  y ≤ 8,  x,y ≥ 0
        Optimal: x=6, y=4, objective=26
    """
    # Variables have no upper bound — the constraints enforce the limits.
    # This matches CLAUDE.md known test values: shadow_prices x_limit = 1.0.
    # (If upper_bound=6 were set on the variable directly, x_limit would be
    # redundant and its shadow price would be 0.)
    model = LPModel(
        name="simple_lp",
        variables=[
            LPVariable(name="x", lower_bound=0.0),
            LPVariable(name="y", lower_bound=0.0),
        ],
        constraints=[
            LinearConstraint(
                name="sum_limit",
                coefficients={"x": 1.0, "y": 1.0},
                sense="<=",
                rhs=10.0,
            ),
            LinearConstraint(
                name="x_limit",
                coefficients={"x": 1.0},
                sense="<=",
                rhs=6.0,
            ),
            LinearConstraint(
                name="y_limit",
                coefficients={"y": 1.0},
                sense="<=",
                rhs=8.0,
            ),
        ],
        objective=LinearObjective(
            sense="maximize",
            coefficients={"x": 3.0, "y": 2.0},
        ),
    )

    solver_input = _lp_model_to_solver_input(model)

    # Verify SolverInput was built correctly from LPModel
    assert solver_input.num_variables == 2
    assert solver_input.num_constraints == 3
    assert solver_input.variable_names == ["x", "y"]
    assert solver_input.objective_sense == "maximize"
    assert solver_input.objective_coefficients == [3.0, 2.0]

    result = solve(solver_input)

    assert result.status == "optimal"
    assert result.objective_value == pytest.approx(26.0, abs=1e-6)
    assert result.variable_values is not None
    assert result.variable_values["x"] == pytest.approx(6.0, abs=1e-6)
    assert result.variable_values["y"] == pytest.approx(4.0, abs=1e-6)

    # Sensitivity must be populated for LP
    assert result.shadow_prices is not None
    assert result.reduced_costs is not None
    assert result.constraint_slack is not None
    assert result.binding_constraints is not None

    # Shadow prices — cross-phase values from CLAUDE.md known test values
    assert result.shadow_prices["sum_limit"] == pytest.approx(2.0, abs=1e-6)
    assert result.shadow_prices["x_limit"] == pytest.approx(1.0, abs=1e-6)
    assert result.shadow_prices["y_limit"] == pytest.approx(0.0, abs=1e-6)

    # Binding constraints
    assert "sum_limit" in result.binding_constraints
    assert "x_limit" in result.binding_constraints
    assert "y_limit" not in result.binding_constraints

    # IIS must NOT be present for an optimal result
    assert result.iis is None


def test_infeasible_model_iis() -> None:
    """Infeasible LPModel produces IISResult with correct conflicting constraints.

    Uses the canonical infeasible LP from CLAUDE.md:
        x + y ≤ 5  AND  x + y ≥ 10,  x,y ≥ 0
        Both constraints are in the IIS.
    """
    model = LPModel(
        name="infeasible_lp",
        variables=[
            LPVariable(name="x", lower_bound=0.0),
            LPVariable(name="y", lower_bound=0.0),
        ],
        constraints=[
            LinearConstraint(
                name="upper_sum",
                coefficients={"x": 1.0, "y": 1.0},
                sense="<=",
                rhs=5.0,
            ),
            LinearConstraint(
                name="lower_sum",
                coefficients={"x": 1.0, "y": 1.0},
                sense=">=",
                rhs=10.0,
            ),
        ],
        objective=LinearObjective(
            sense="minimize",
            coefficients={"x": 1.0, "y": 1.0},
        ),
    )

    solver_input = _lp_model_to_solver_input(model)
    result = solve(solver_input)

    assert result.status == "infeasible"
    assert result.objective_value is None
    assert result.variable_values is None

    # IIS populated
    assert result.iis is not None
    assert isinstance(result.iis, IISResult)
    assert "upper_sum" in result.iis.conflicting_constraints
    assert "lower_sum" in result.iis.conflicting_constraints
    assert len(result.iis.conflicting_constraints) == 2
    assert result.iis.explanation != ""


def test_solver_result_json_completeness() -> None:
    """SolverResult serializes to/from JSON without data loss.

    Verifies:
    - All sensitivity fields are present and non-null
    - float('inf') ranging bounds are serialized as null (not crashing)
    - Round-trip deserialization restores identical values
    """
    solver_input = SolverInput(
        num_variables=2,
        num_constraints=3,
        variable_names=["x", "y"],
        variable_lower_bounds=[0.0, 0.0],
        variable_upper_bounds=[6.0, 8.0],
        variable_types=["continuous", "continuous"],
        constraint_names=["sum_limit", "x_limit", "y_limit"],
        constraint_matrix=[[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]],
        constraint_senses=["<=", "<=", "<="],
        constraint_rhs=[10.0, 6.0, 8.0],
        objective_coefficients=[3.0, 2.0],
        objective_sense="maximize",
    )

    result = solve(solver_input)
    assert result.status == "optimal"

    # ---- Serialize to JSON ------------------------------------------------
    json_str = result.model_dump_json()
    data = json.loads(json_str)

    # Core solution fields
    assert data["status"] == "optimal"
    assert data["objective_value"] == pytest.approx(26.0)
    assert data["variable_values"]["x"] == pytest.approx(6.0)
    assert data["variable_values"]["y"] == pytest.approx(4.0)

    # Sensitivity fields must be present (not null)
    assert data["shadow_prices"] is not None
    assert data["reduced_costs"] is not None
    assert data["constraint_slack"] is not None
    assert data["binding_constraints"] is not None
    assert data["objective_ranges"] is not None
    assert data["rhs_ranges"] is not None

    # Ranging entries must be lists (tuples serialize as JSON arrays)
    for name, rng in data["objective_ranges"].items():
        assert isinstance(rng, list), f"objective_ranges[{name!r}] should be a list"
        assert len(rng) == 2, f"objective_ranges[{name!r}] should have 2 elements"
        # Each bound is either a number or null (unbounded)
        for bound in rng:
            assert bound is None or isinstance(
                bound, (int, float)
            ), f"Unexpected bound type in objective_ranges[{name!r}]: {type(bound)}"

    for name, rng in data["rhs_ranges"].items():
        assert isinstance(rng, list)
        assert len(rng) == 2
        for bound in rng:
            assert bound is None or isinstance(bound, (int, float))

    # ---- Round-trip deserialization ---------------------------------------
    result2 = SolverResult.model_validate_json(json_str)
    assert result2.status == result.status
    assert result2.objective_value == pytest.approx(result.objective_value)
    assert result2.variable_values == pytest.approx(result.variable_values)
    assert result2.shadow_prices == pytest.approx(result.shadow_prices)
    assert result2.binding_constraints == result.binding_constraints
    # Ranging round-trips (None values preserved)
    assert result2.objective_ranges is not None
    assert result2.rhs_ranges is not None
    for name in result2.objective_ranges:
        assert result2.objective_ranges[name] == result.objective_ranges[name]
    for name in result2.rhs_ranges:
        assert result2.rhs_ranges[name] == result.rhs_ranges[name]
