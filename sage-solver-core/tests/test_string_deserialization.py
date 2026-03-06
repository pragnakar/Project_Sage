"""Regression tests: MCP transport may serialize nested JSON objects as strings.

When the tool schema uses ``additionalProperties: true`` with no explicit field
types, some MCP clients serialize nested arrays/objects as JSON strings rather
than native Python types.  The model validators on LPModel, MIPModel,
PortfolioModel, and SchedulingModel must parse these strings transparently.
"""

from __future__ import annotations

import json

import pytest

from sage_solver_core.models import (
    LPModel,
    LinearConstraint,
    LinearObjective,
    LPVariable,
    MIPModel,
    MIPVariable,
)
from sage_solver_core.solver import solve
from sage_solver_core.builder import build_from_lp


# ---------------------------------------------------------------------------
# Field alias tests
# ---------------------------------------------------------------------------


def test_lp_variable_lb_ub_aliases():
    v = LPVariable(name="x", lb=2.0, ub=10.0)
    assert v.lower_bound == 2.0
    assert v.upper_bound == 10.0


def test_mip_variable_lb_ub_aliases():
    v = MIPVariable(name="x", lb=0.0, ub=5.0, var_type="integer")
    assert v.lower_bound == 0.0
    assert v.upper_bound == 5.0


def test_linear_constraint_operator_alias():
    c = LinearConstraint(
        name="c1",
        coefficients={"x": 1.0},
        operator="<=",
        rhs=10.0,
    )
    assert c.sense == "<="


def test_linear_constraint_expression_alias():
    c = LinearConstraint(
        name="c1",
        expression={"x": 3.0, "y": 2.0},
        sense=">=",
        rhs=5.0,
    )
    assert c.coefficients == {"x": 3.0, "y": 2.0}


def test_linear_objective_direction_alias():
    obj = LinearObjective(direction="maximize", coefficients={"x": 5.0})
    assert obj.sense == "maximize"


# ---------------------------------------------------------------------------
# String-encoded field deserialization (the MCP transport regression)
# ---------------------------------------------------------------------------


_VARIABLES = [
    {"name": "x1", "lower_bound": 0},
    {"name": "x2", "lower_bound": 0},
    {"name": "x3", "lower_bound": 0},
    {"name": "x4", "lower_bound": 0},
    {"name": "x5", "lower_bound": 0},
]

_CONSTRAINTS = [
    {"name": "c1", "coefficients": {"x1": 5, "x2": 7, "x3": 9, "x4": 2, "x5": 1}, "sense": "<=", "rhs": 250},
    {"name": "c2", "coefficients": {"x1": 18, "x2": 4, "x3": 8, "x4": 10, "x5": 15}, "sense": "<=", "rhs": 285},
    {"name": "c3", "coefficients": {"x1": 4, "x2": 2, "x3": 6, "x4": 7, "x5": 3}, "sense": "<=", "rhs": 211},
    {"name": "c4", "coefficients": {"x1": 5, "x2": 9, "x3": 3, "x4": 1, "x5": 12}, "sense": "<=", "rhs": 315},
]

_OBJECTIVE = {"sense": "maximize", "coefficients": {"x1": 7, "x2": 8, "x3": 2, "x4": 9, "x5": 6}}


def test_lp_model_string_encoded_fields():
    """LPModel must accept variables/constraints/objective as JSON strings."""
    payload = {
        "name": "LP_5var",
        "problem_type": "lp",
        "variables": json.dumps(_VARIABLES),
        "constraints": json.dumps(_CONSTRAINTS),
        "objective": json.dumps(_OBJECTIVE),
    }
    model = LPModel(**payload)
    assert len(model.variables) == 5
    assert len(model.constraints) == 4
    assert model.objective.sense == "maximize"


def test_lp_model_native_fields():
    """LPModel must also accept native Python lists/dicts (no regression)."""
    model = LPModel(
        name="LP_5var",
        variables=_VARIABLES,
        constraints=_CONSTRAINTS,
        objective=_OBJECTIVE,
    )
    assert len(model.variables) == 5


def test_mip_model_string_encoded_fields():
    mip_vars = [{"name": "x", "lower_bound": 0, "var_type": "integer"}]
    mip_obj = {"sense": "maximize", "coefficients": {"x": 3}}
    mip_con = [{"name": "c1", "coefficients": {"x": 1}, "sense": "<=", "rhs": 5}]

    model = MIPModel(
        name="mip_test",
        variables=json.dumps(mip_vars),
        constraints=json.dumps(mip_con),
        objective=json.dumps(mip_obj),
    )
    assert len(model.variables) == 1
    assert model.variables[0].var_type == "integer"


# ---------------------------------------------------------------------------
# End-to-end solve verification
# ---------------------------------------------------------------------------


def test_solve_lp_5var_correct_solution():
    """Solve the 5-variable LP and verify optimal value ≈ 393.47."""
    model = LPModel(
        name="LP_5var",
        variables=_VARIABLES,
        constraints=_CONSTRAINTS,
        objective=_OBJECTIVE,
    )
    si = build_from_lp(model)
    result = solve(si)

    assert result.status == "optimal"
    assert result.objective_value is not None
    assert abs(result.objective_value - 393.4677) < 0.01

    vals = result.variable_values
    assert vals is not None
    assert abs(vals["x2"] - 31.129) < 0.01
    assert abs(vals["x4"] - 16.048) < 0.01
    assert vals["x1"] < 0.001
    assert vals["x3"] < 0.001
    assert vals["x5"] < 0.001


def test_solve_lp_5var_string_encoded_end_to_end():
    """Same LP via string-encoded fields must produce the same solution."""
    model = LPModel(
        name="LP_5var",
        variables=json.dumps(_VARIABLES),
        constraints=json.dumps(_CONSTRAINTS),
        objective=json.dumps(_OBJECTIVE),
    )
    si = build_from_lp(model)
    result = solve(si)

    assert result.status == "optimal"
    assert result.objective_value is not None
    assert abs(result.objective_value - 393.4677) < 0.01


def test_solve_lp_with_lb_ub_aliases():
    """Variables specified with lb/ub aliases must solve correctly."""
    model = LPModel(
        name="simple_lp",
        variables=[
            {"name": "x", "lb": 0, "ub": 6},
            {"name": "y", "lb": 0, "ub": 8},
        ],
        constraints=[
            {"name": "total", "coefficients": {"x": 1, "y": 1}, "sense": "<=", "rhs": 10},
        ],
        objective={"sense": "maximize", "coefficients": {"x": 3, "y": 2}},
    )
    si = build_from_lp(model)
    result = solve(si)

    assert result.status == "optimal"
    assert result.objective_value is not None
    assert abs(result.objective_value - 26.0) < 0.001
