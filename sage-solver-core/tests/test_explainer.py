"""Tests for sage_core.explainer — result narrator and infeasibility explainer.

Coverage:
- TestDetailLevels: brief/standard/detailed output length and content
- TestBindingConstraintMentioned: binding constraints appear in output
- TestDomainLanguage: portfolio vs scheduling vocabulary
- TestInfeasibilityExplanation: explain_infeasibility on nurse scheduling case
- TestNonOptimalStatuses: unbounded, time_limit, solver_error explanations
- TestIntegration: full pipeline explain at all three levels
"""

from __future__ import annotations

import pytest

from sage_solver_core.builder import (
    build_from_lp,
    build_from_mip,
    build_from_portfolio,
    build_from_scheduling,
)
from sage_solver_core.explainer import explain_infeasibility, explain_result
from sage_solver_core.models import (
    Asset,
    IISResult,
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
    SolverResult,
    Worker,
)
from sage_solver_core.solver import solve


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_lp_model() -> LPModel:
    """LP: max 5x1 + 4x2 s.t. 2x1+x2<=14, x1+2x2<=14. Optimal at x1=x2=14/3, obj=42."""
    return LPModel(
        name="production",
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
        objective=LinearObjective(sense="maximize", coefficients={"x1": 5.0, "x2": 4.0}),
    )


@pytest.fixture()
def simple_lp_result(simple_lp_model: LPModel) -> SolverResult:
    return solve(build_from_lp(simple_lp_model))


@pytest.fixture()
def portfolio_model() -> PortfolioModel:
    return PortfolioModel(
        assets=[
            Asset(name="Stocks", expected_return=0.12, sector="Equity"),
            Asset(name="Bonds", expected_return=0.05, sector="Fixed"),
            Asset(name="Gold", expected_return=0.08, sector="Commodity"),
        ],
        covariance_matrix=[
            [0.04, 0.002, 0.001],
            [0.002, 0.001, 0.0005],
            [0.001, 0.0005, 0.005],
        ],
        risk_aversion=1.0,
        constraints=PortfolioConstraints(
            min_total_allocation=1.0,
            max_total_allocation=1.0,
            min_allocation_per_asset=0.05,
            max_allocation_per_asset=0.70,
        ),
    )


@pytest.fixture()
def portfolio_result(portfolio_model: PortfolioModel) -> SolverResult:
    return solve(build_from_portfolio(portfolio_model))


@pytest.fixture()
def scheduling_model_feasible() -> SchedulingModel:
    return SchedulingModel(
        workers=[
            Worker(name="Alice", max_hours=40, skills=["ICU", "General"]),
            Worker(name="Bob", max_hours=40, skills=["ER", "General"]),
            Worker(name="Carol", max_hours=32, skills=["ICU", "ER"]),
        ],
        shifts=[
            Shift(name="Morning", duration_hours=8, required_workers=1, required_skills=["General"]),
            Shift(name="Night", duration_hours=8, required_workers=1),
        ],
        planning_horizon_days=3,
        max_consecutive_days=3,
    )


@pytest.fixture()
def scheduling_result_feasible(scheduling_model_feasible: SchedulingModel) -> SolverResult:
    return solve(build_from_scheduling(scheduling_model_feasible))


@pytest.fixture()
def infeasible_lp_model() -> LPModel:
    """LP with contradictory constraints: x >= 10 and x <= 5."""
    return LPModel(
        name="infeasible_lp",
        variables=[LPVariable(name="x", lower_bound=0.0)],
        constraints=[
            LinearConstraint(name="lower_x", coefficients={"x": 1.0}, sense=">=", rhs=10.0),
            LinearConstraint(name="upper_x", coefficients={"x": 1.0}, sense="<=", rhs=5.0),
        ],
        objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
    )


@pytest.fixture()
def infeasible_lp_result(infeasible_lp_model: LPModel) -> SolverResult:
    return solve(build_from_lp(infeasible_lp_model))


# ---------------------------------------------------------------------------
# TestDetailLevels: output length and key content at each level
# ---------------------------------------------------------------------------


class TestDetailLevels:
    def test_brief_is_short(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "brief")
        # Brief should be a single sentence / short paragraph — less than 300 chars
        # (includes SAGE attribution line appended to all explanations)
        assert len(text) < 300
        assert "Optimal" in text or "optimal" in text

    def test_standard_is_longer_than_brief(self, simple_lp_model, simple_lp_result):
        brief = explain_result(simple_lp_result, simple_lp_model, "brief")
        standard = explain_result(simple_lp_result, simple_lp_model, "standard")
        assert len(standard) > len(brief)

    def test_detailed_is_longer_than_standard(self, simple_lp_model, simple_lp_result):
        standard = explain_result(simple_lp_result, simple_lp_model, "standard")
        detailed = explain_result(simple_lp_result, simple_lp_model, "detailed")
        assert len(detailed) > len(standard)

    def test_brief_contains_objective_value(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "brief")
        # Objective is 42.00
        assert "42" in text

    def test_standard_contains_variable_values(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "standard")
        # Variables x1 and x2 should appear
        assert "x1" in text or "x2" in text

    def test_detailed_contains_shadow_price(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "detailed")
        # Should mention shadow price
        assert "shadow price" in text.lower() or "Shadow price" in text

    def test_detailed_contains_sensitivity(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "detailed")
        assert "sensitivity" in text.lower() or "Sensitivity" in text

    def test_default_level_is_standard(self, simple_lp_model, simple_lp_result):
        default = explain_result(simple_lp_result, simple_lp_model)
        standard = explain_result(simple_lp_result, simple_lp_model, "standard")
        assert default == standard

    def test_returns_string(self, simple_lp_model, simple_lp_result):
        for level in ("brief", "standard", "detailed"):
            result = explain_result(simple_lp_result, simple_lp_model, level)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# TestBindingConstraintMentioned
# ---------------------------------------------------------------------------


class TestBindingConstraintMentioned:
    def test_binding_constraints_in_standard(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "standard")
        # Both resource_A and resource_B are binding at the optimal solution
        assert "resource_A" in text or "resource_B" in text

    def test_binding_constraints_in_detailed(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "detailed")
        assert "resource_A" in text
        assert "resource_B" in text

    def test_shadow_prices_reported_for_binding(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "detailed")
        # resource_A shadow price ≈ 2.0
        assert "2.00" in text or "2.0" in text

    def test_binding_label_present(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "detailed")
        assert "binding" in text.lower()

    def test_non_binding_not_labeled_as_binding(self):
        """LP with one slack constraint should not call it binding."""
        model = LPModel(
            name="slack_test",
            variables=[LPVariable(name="x", lower_bound=0.0, upper_bound=5.0)],
            constraints=[
                LinearConstraint(name="loose", coefficients={"x": 1.0}, sense="<=", rhs=100.0),
            ],
            objective=LinearObjective(sense="maximize", coefficients={"x": 1.0}),
        )
        result = solve(build_from_lp(model))
        text = explain_result(result, model, "detailed")
        # "loose" should appear as non-binding
        if "loose" in text:
            assert "non-binding" in text.lower()


# ---------------------------------------------------------------------------
# TestDomainLanguage
# ---------------------------------------------------------------------------


class TestDomainLanguage:
    def test_portfolio_uses_allocation_language(self, portfolio_model, portfolio_result):
        text = explain_result(portfolio_result, portfolio_model, "standard")
        # Should use portfolio-specific words
        portfolio_words = {"allocation", "return", "portfolio", "asset", "Stocks", "Bonds", "Gold"}
        assert any(w.lower() in text.lower() for w in portfolio_words)

    def test_portfolio_brief_mentions_expected_return(self, portfolio_model, portfolio_result):
        text = explain_result(portfolio_result, portfolio_model, "brief")
        # Expected return should be reported as a percentage
        assert "%" in text or "return" in text.lower()

    def test_portfolio_standard_shows_asset_weights(self, portfolio_model, portfolio_result):
        text = explain_result(portfolio_result, portfolio_model, "standard")
        # Asset names should appear in the solution section
        assert "Stocks" in text or "Bonds" in text or "Gold" in text

    def test_portfolio_weights_shown_as_percentages(self, portfolio_model, portfolio_result):
        text = explain_result(portfolio_result, portfolio_model, "standard")
        # Asset values should be shown as % (e.g., "25.00%")
        assert "%" in text

    def test_scheduling_uses_shift_language(
        self, scheduling_model_feasible, scheduling_result_feasible
    ):
        text = explain_result(scheduling_result_feasible, scheduling_model_feasible, "standard")
        scheduling_words = {"shift", "schedule", "assignment", "worker", "coverage"}
        assert any(w.lower() in text.lower() for w in scheduling_words)

    def test_scheduling_mentions_assignments(
        self, scheduling_model_feasible, scheduling_result_feasible
    ):
        text = explain_result(scheduling_result_feasible, scheduling_model_feasible, "standard")
        assert "assign" in text.lower() or "shift" in text.lower()

    def test_lp_uses_generic_language(self, simple_lp_model, simple_lp_result):
        text = explain_result(simple_lp_result, simple_lp_model, "standard")
        # Generic words
        assert "objective" in text.lower() or "variable" in text.lower()

    def test_scheduling_no_markdown(
        self, scheduling_model_feasible, scheduling_result_feasible
    ):
        """Output must not contain Markdown formatting characters."""
        text = explain_result(scheduling_result_feasible, scheduling_model_feasible, "detailed")
        assert "**" not in text
        assert not text.lstrip().startswith("#")


# ---------------------------------------------------------------------------
# TestInfeasibilityExplanation
# ---------------------------------------------------------------------------


class TestInfeasibilityExplanation:
    def test_infeasible_lp_result_delegates_to_explain_infeasibility(
        self, infeasible_lp_model, infeasible_lp_result
    ):
        text = explain_result(infeasible_lp_result, infeasible_lp_model, "standard")
        assert "infeasible" in text.lower()

    def test_infeasibility_mentions_conflicting_constraints(
        self, infeasible_lp_model, infeasible_lp_result
    ):
        text = explain_result(infeasible_lp_result, infeasible_lp_model, "standard")
        assert "lower_x" in text or "upper_x" in text

    def test_infeasibility_standalone_function(self, infeasible_lp_result, infeasible_lp_model):
        assert infeasible_lp_result.iis is not None
        text = explain_infeasibility(infeasible_lp_result.iis, infeasible_lp_model)
        assert isinstance(text, str)
        assert "infeasible" in text.lower()

    def test_scheduling_infeasibility_nurse_case(self):
        """Nurse scheduling infeasibility: 5 nurses × 5 max shifts < 42 required."""
        model = SchedulingModel(
            workers=[Worker(name=f"Nurse{i}", max_hours=40) for i in range(5)],
            shifts=[
                Shift(name="Day", duration_hours=8, required_workers=2),
                Shift(name="Night", duration_hours=8, required_workers=2),
            ],
            planning_horizon_days=7,
            max_consecutive_days=5,
        )
        si = build_from_scheduling(model)
        result = solve(si)
        assert result.status == "infeasible"
        assert result.iis is not None
        text = explain_infeasibility(result.iis, model)
        assert "infeasible" in text.lower()
        # Should mention coverage demand and available capacity
        assert "coverage" in text.lower() or "assignment" in text.lower() or "demand" in text.lower()

    def test_scheduling_infeasibility_quantitative(self):
        """The scheduling explanation should include a numeric argument."""
        model = SchedulingModel(
            workers=[Worker(name=f"N{i}", max_hours=40) for i in range(3)],
            shifts=[Shift(name="S1", duration_hours=8, required_workers=3)],
            planning_horizon_days=7,
            max_consecutive_days=5,
        )
        si = build_from_scheduling(model)
        result = solve(si)
        assert result.status == "infeasible"
        text = explain_infeasibility(result.iis, model)  # type: ignore[arg-type]
        # Should mention some numbers related to demand vs capacity
        import re
        numbers = re.findall(r"\d+", text)
        assert len(numbers) >= 2, f"Expected numeric content in: {text}"

    def test_portfolio_infeasibility_explains_allocation_conflict(self):
        """Portfolio where min_alloc * n_assets > max_total is infeasible."""
        model = PortfolioModel(
            assets=[
                Asset(name=f"A{i}", expected_return=0.1) for i in range(5)
            ],
            covariance_matrix=[[0.01 if i == j else 0.0 for j in range(5)] for i in range(5)],
            risk_aversion=1.0,
            constraints=PortfolioConstraints(
                min_allocation_per_asset=0.25,  # 5 * 0.25 = 1.25 > 1.0
                max_total_allocation=1.0,
            ),
        )
        si = build_from_portfolio(model)
        result = solve(si)
        assert result.status == "infeasible"
        text = explain_infeasibility(result.iis, model)  # type: ignore[arg-type]
        assert "infeasible" in text.lower()
        assert "allocation" in text.lower()

    def test_infeasibility_ends_with_actionable_suggestion(
        self, infeasible_lp_model, infeasible_lp_result
    ):
        text = explain_infeasibility(infeasible_lp_result.iis, infeasible_lp_model)  # type: ignore[arg-type]
        # Should contain "relax" or "remove" or "options"
        assert any(w in text.lower() for w in ["relax", "remove", "option", "restore"])


# ---------------------------------------------------------------------------
# TestNonOptimalStatuses
# ---------------------------------------------------------------------------


class TestNonOptimalStatuses:
    def test_infeasible_without_iis(self, simple_lp_model):
        """If status=infeasible but iis=None, explain_result handles gracefully."""
        result = SolverResult(
            status="infeasible",
            solve_time_seconds=0.01,
            iis=None,
        )
        text = explain_result(result, simple_lp_model, "standard")
        assert "infeasible" in text.lower()

    def test_unbounded_explanation(self, simple_lp_model):
        result = SolverResult(
            status="unbounded",
            solve_time_seconds=0.01,
        )
        text = explain_result(result, simple_lp_model, "standard")
        assert "unbounded" in text.lower()

    def test_time_limit_explanation(self, simple_lp_model):
        result = SolverResult(
            status="time_limit_reached",
            solve_time_seconds=60.0,
            objective_value=100.0,
            variable_values={"x1": 1.0},
        )
        text = explain_result(result, simple_lp_model, "standard")
        assert "time" in text.lower()

    def test_solver_error_explanation(self, simple_lp_model):
        result = SolverResult(
            status="solver_error",
            solve_time_seconds=0.0,
        )
        text = explain_result(result, simple_lp_model, "standard")
        assert "error" in text.lower()


# ---------------------------------------------------------------------------
# TestIntegration: full pipeline at all three levels
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_lp_all_three_levels_pipeline(self, simple_lp_model, simple_lp_result):
        """Full pipeline: build → solve → explain at all three levels."""
        assert simple_lp_result.status == "optimal"
        assert simple_lp_result.objective_value == pytest.approx(42.0, abs=1e-3)

        brief = explain_result(simple_lp_result, simple_lp_model, "brief")
        standard = explain_result(simple_lp_result, simple_lp_model, "standard")
        detailed = explain_result(simple_lp_result, simple_lp_model, "detailed")

        # All three are non-empty strings
        assert all(isinstance(t, str) and len(t) > 0 for t in [brief, standard, detailed])

        # Length ordering
        assert len(brief) < len(standard) < len(detailed)

        # All mention the model being optimal
        for text in [brief, standard, detailed]:
            assert "optimal" in text.lower() or "Optimal" in text

    def test_portfolio_all_three_levels_pipeline(self, portfolio_model, portfolio_result):
        assert portfolio_result.status == "optimal"
        for level in ("brief", "standard", "detailed"):
            text = explain_result(portfolio_result, portfolio_model, level)
            assert isinstance(text, str) and len(text) > 0

    def test_mip_explain_brief(self):
        """MIP knapsack — brief explanation."""
        model = MIPModel(
            name="knapsack",
            variables=[
                MIPVariable(name=f"item{i}", var_type="binary") for i in range(3)
            ],
            constraints=[
                LinearConstraint(
                    name="weight",
                    coefficients={"item0": 3.0, "item1": 4.0, "item2": 5.0},
                    sense="<=",
                    rhs=8.0,
                )
            ],
            objective=LinearObjective(
                sense="maximize",
                coefficients={"item0": 4.0, "item1": 5.0, "item2": 6.0},
            ),
        )
        result = solve(build_from_mip(model))
        assert result.status == "optimal"
        text = explain_result(result, model, "brief")
        assert "optimal" in text.lower() or "Optimal" in text

    def test_mip_sensitivity_not_available_message(self):
        """MIP detailed explanation should note sensitivity is not available."""
        model = MIPModel(
            name="mip_test",
            variables=[MIPVariable(name="y", var_type="binary")],
            constraints=[
                LinearConstraint(name="c1", coefficients={"y": 1.0}, sense="<=", rhs=1.0)
            ],
            objective=LinearObjective(sense="maximize", coefficients={"y": 1.0}),
        )
        result = solve(build_from_mip(model))
        text = explain_result(result, model, "detailed")
        # MIP result has no shadow_prices, so sensitivity section should say so
        if result.shadow_prices is None:
            assert "not available" in text.lower() or "sensitivity" in text.lower()

    def test_output_is_plain_text_no_markdown(self, simple_lp_model, simple_lp_result):
        for level in ("brief", "standard", "detailed"):
            text = explain_result(simple_lp_result, simple_lp_model, level)
            assert "**" not in text
            assert "##" not in text
            assert not text.lstrip().startswith("#")
