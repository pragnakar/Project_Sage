"""Full pipeline integration tests: Stage 1 → Stage 2 → Stage 3.

Verifies end-to-end flows: domain model → SolverInput → SolverResult.
"""

from __future__ import annotations

import pytest

from sage_solver_core.models import (
    Asset,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    MIPModel,
    MIPVariable,
    PortfolioConstraints,
    PortfolioModel,
    SchedulingModel,
    Shift,
    Worker,
)
from sage_solver_core.builder import (
    build_from_lp,
    build_from_mip,
    build_from_portfolio,
    build_from_scheduling,
)
from sage_solver_core.solver import solve


def test_lp_full_pipeline() -> None:
    """LP: LPModel → build_from_lp → solve → SolverResult."""
    model = LPModel(
        name="prod_mix",
        variables=[
            LPVariable(name="x1", lower_bound=0.0),
            LPVariable(name="x2", lower_bound=0.0),
        ],
        constraints=[
            LinearConstraint(
                name="resource_A",
                coefficients={"x1": 2.0, "x2": 1.0},
                sense="<=",
                rhs=14.0,
            ),
            LinearConstraint(
                name="resource_B",
                coefficients={"x1": 1.0, "x2": 2.0},
                sense="<=",
                rhs=14.0,
            ),
        ],
        objective=LinearObjective(
            sense="maximize",
            coefficients={"x1": 5.0, "x2": 4.0},
        ),
    )

    solver_input = build_from_lp(model)
    result = solve(solver_input)

    assert result.status == "optimal"
    # Optimal: x1 = x2 = 14/3 ≈ 4.667, objective = 5*(14/3) + 4*(14/3) = 42
    assert result.objective_value == pytest.approx(42.0, abs=1e-4)
    assert result.variable_values is not None
    x1 = result.variable_values["x1"]
    x2 = result.variable_values["x2"]
    assert x1 == pytest.approx(14 / 3, abs=1e-4)
    assert x2 == pytest.approx(14 / 3, abs=1e-4)
    assert result.shadow_prices is not None
    assert result.shadow_prices["resource_A"] == pytest.approx(2.0, abs=0.01)
    assert result.shadow_prices["resource_B"] == pytest.approx(1.0, abs=0.01)


def test_mip_full_pipeline() -> None:
    """MIP: MIPModel → build_from_mip → solve → SolverResult."""
    model = MIPModel(
        name="knapsack",
        variables=[
            MIPVariable(name="item1", var_type="binary"),
            MIPVariable(name="item2", var_type="binary"),
            MIPVariable(name="item3", var_type="binary"),
        ],
        constraints=[
            LinearConstraint(
                name="weight_limit",
                coefficients={"item1": 3.0, "item2": 4.0, "item3": 5.0},
                sense="<=",
                rhs=8.0,
            ),
        ],
        objective=LinearObjective(
            sense="maximize",
            coefficients={"item1": 4.0, "item2": 5.0, "item3": 6.0},
        ),
    )

    solver_input = build_from_mip(model)
    result = solve(solver_input)

    assert result.status == "optimal"
    assert result.objective_value == pytest.approx(10.0, abs=1e-4)
    assert result.variable_values is not None
    # item2 + item3 weights = 9 > 8; item1 + item2 = 7 ≤ 8, value = 9
    # item1 + item3 = 8 ≤ 8, value = 10 ← optimal
    assert result.variable_values["item1"] == pytest.approx(1.0, abs=1e-4)
    assert result.variable_values["item2"] == pytest.approx(0.0, abs=1e-4)
    assert result.variable_values["item3"] == pytest.approx(1.0, abs=1e-4)


def test_portfolio_full_pipeline() -> None:
    """Portfolio QP: PortfolioModel → build_from_portfolio → solve → SolverResult.

    Verifies:
    - Weights sum to 1.0
    - Risk-aversion effect: higher lambda shifts weight to lower-variance asset
    - All weights within [min_alloc, max_alloc]
    """
    assets = [
        Asset(name="Stocks", expected_return=0.12, sector="Equity"),
        Asset(name="Bonds", expected_return=0.05, sector="Fixed"),
        Asset(name="Gold", expected_return=0.08, sector="Commodity"),
    ]
    cov = [
        [0.04, 0.002, 0.001],
        [0.002, 0.001, 0.0005],
        [0.001, 0.0005, 0.005],
    ]

    def solve_portfolio(lam: float) -> dict[str, float]:
        model = PortfolioModel(
            assets=assets,
            covariance_matrix=cov,
            risk_aversion=lam,
            constraints=PortfolioConstraints(
                min_total_allocation=1.0,
                max_total_allocation=1.0,
                min_allocation_per_asset=0.05,
                max_allocation_per_asset=0.70,
            ),
        )
        si = build_from_portfolio(model)
        result = solve(si)
        assert result.status == "optimal"
        assert result.variable_values is not None
        return result.variable_values

    w_aggressive = solve_portfolio(lam=0.1)
    w_conservative = solve_portfolio(lam=5.0)

    # Weights must sum to ~1.0
    assert sum(w_aggressive.values()) == pytest.approx(1.0, abs=1e-4)
    assert sum(w_conservative.values()) == pytest.approx(1.0, abs=1e-4)

    # All weights in [0.05, 0.70]
    for w in w_aggressive.values():
        assert 0.05 - 1e-4 <= w <= 0.70 + 1e-4
    for w in w_conservative.values():
        assert 0.05 - 1e-4 <= w <= 0.70 + 1e-4

    # Higher risk aversion → more weight to Bonds (lowest variance)
    assert w_conservative["Bonds"] > w_aggressive["Bonds"]


def test_scheduling_full_pipeline() -> None:
    """Scheduling MIP: SchedulingModel → build_from_scheduling → solve → SolverResult.

    Verifies:
    - All shifts covered every day
    - Skill restrictions respected (Carol cannot do Morning — no General skill)
    - Max hours not exceeded
    """
    model = SchedulingModel(
        workers=[
            Worker(name="Alice", max_hours=40, skills=["ICU", "General"]),
            Worker(name="Bob", max_hours=40, skills=["ER", "General"]),
            Worker(name="Carol", max_hours=32, skills=["ICU", "ER"]),
        ],
        shifts=[
            Shift(
                name="Morning",
                duration_hours=8,
                required_workers=1,
                required_skills=["General"],
            ),
            Shift(name="Night", duration_hours=8, required_workers=1),
        ],
        planning_horizon_days=3,
        max_consecutive_days=3,
    )

    si = build_from_scheduling(model)
    result = solve(si)

    assert result.status == "optimal"
    assert result.variable_values is not None

    assigned = {k: v for k, v in result.variable_values.items() if v > 0.5}

    # Skill restriction: Carol must not be assigned to Morning
    carol_morning = [k for k in assigned if "Carol" in k and "Morning" in k]
    assert carol_morning == [], f"Carol assigned to Morning: {carol_morning}"

    # Coverage: every shift must be covered every day
    from collections import defaultdict

    coverage: dict[tuple[str, int], int] = defaultdict(int)
    for k in assigned:
        parts = k.split("_")  # x_{worker}_{shift}_d{day}
        shift_name = parts[2]
        day = int(parts[3][1:])
        coverage[(shift_name, day)] += 1

    for shift_name in ["Morning", "Night"]:
        for day in range(3):
            assert coverage[(shift_name, day)] >= 1, (
                f"Shift {shift_name} day {day} not covered"
            )

    # Max hours: Alice and Bob ≤ 40h, Carol ≤ 32h
    hours: dict[str, float] = defaultdict(float)
    for k in assigned:
        parts = k.split("_")
        worker_name = parts[1]
        hours[worker_name] += 8  # each shift is 8 hours

    assert hours.get("Alice", 0) <= 40.0 + 1e-6
    assert hours.get("Bob", 0) <= 40.0 + 1e-6
    assert hours.get("Carol", 0) <= 32.0 + 1e-6
