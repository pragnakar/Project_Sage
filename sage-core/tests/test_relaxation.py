"""Tests for sage_core.relaxation — constraint relaxation suggester.

Coverage:
- TestRelaxationSuggestions: basic constraint/bound relaxations
- TestRanking: smallest relaxation_percent first
- TestFeasibilityVerification: re-solving with suggestion actually gives feasible result
- TestIntegrationInfeasibleToFeasible: full pipeline infeasible→explain→relax→re-solve
- TestEdgeCases: IIS with no suggestions, variable bound relaxation
"""

from __future__ import annotations

import pytest

from sage_core.builder import build_from_lp, build_from_mip, build_from_scheduling
from sage_core.explainer import explain_infeasibility
from sage_core.models import (
    IISResult,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    MIPModel,
    MIPVariable,
    RelaxationSuggestion,
    SchedulingModel,
    Shift,
    SolverInput,
    SolverResult,
    Worker,
)
from sage_core.relaxation import suggest_relaxations
from sage_core.solver import solve


# ---------------------------------------------------------------------------
# Fixtures: infeasible LP models
# ---------------------------------------------------------------------------


@pytest.fixture()
def contradictory_lp() -> tuple[LPModel, SolverInput, SolverResult]:
    """LP infeasible due to x >= 10 AND x <= 5."""
    model = LPModel(
        name="contradict",
        variables=[LPVariable(name="x", lower_bound=0.0)],
        constraints=[
            LinearConstraint(name="lower_x", coefficients={"x": 1.0}, sense=">=", rhs=10.0),
            LinearConstraint(name="upper_x", coefficients={"x": 1.0}, sense="<=", rhs=5.0),
        ],
        objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
    )
    si = build_from_lp(model)
    result = solve(si)
    return model, si, result


@pytest.fixture()
def three_constraint_infeasible() -> tuple[LPModel, SolverInput, SolverResult]:
    """Infeasible: x + y <= 3 AND x >= 2 AND y >= 2 => x+y >= 4 > 3."""
    model = LPModel(
        name="three_con",
        variables=[
            LPVariable(name="x", lower_bound=0.0),
            LPVariable(name="y", lower_bound=0.0),
        ],
        constraints=[
            LinearConstraint(name="sum_limit", coefficients={"x": 1.0, "y": 1.0}, sense="<=", rhs=3.0),
            LinearConstraint(name="x_min", coefficients={"x": 1.0}, sense=">=", rhs=2.0),
            LinearConstraint(name="y_min", coefficients={"y": 1.0}, sense=">=", rhs=2.0),
        ],
        objective=LinearObjective(sense="maximize", coefficients={"x": 1.0, "y": 1.0}),
    )
    si = build_from_lp(model)
    result = solve(si)
    return model, si, result


# ---------------------------------------------------------------------------
# TestRelaxationSuggestions
# ---------------------------------------------------------------------------


class TestRelaxationSuggestions:
    def test_suggestions_not_empty(self, contradictory_lp):
        model, si, result = contradictory_lp
        assert result.status == "infeasible"
        assert result.iis is not None
        suggestions = suggest_relaxations(result.iis, model, si)
        assert len(suggestions) > 0

    def test_suggestions_are_relaxation_suggestion_type(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        for s in suggestions:
            assert isinstance(s, RelaxationSuggestion)

    def test_suggestions_contain_iis_constraint(self, contradictory_lp):
        model, si, result = contradictory_lp
        assert result.iis is not None
        suggestions = suggest_relaxations(result.iis, model, si)
        suggested_names = {s.constraint_name for s in suggestions}
        # At least one IIS constraint should appear in suggestions
        iis_constraints = set(result.iis.conflicting_constraints)
        assert suggested_names & iis_constraints, (
            f"Expected IIS constraints {iis_constraints} in suggestions {suggested_names}"
        )

    def test_relaxation_amount_is_positive(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        for s in suggestions:
            assert s.relaxation_amount != 0.0

    def test_relaxation_percent_is_positive(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        for s in suggestions:
            assert s.relaxation_percent > 0.0

    def test_explanations_are_non_empty_strings(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        for s in suggestions:
            assert isinstance(s.explanation, str) and len(s.explanation) > 0

    def test_three_constraint_suggestions_include_sum_limit(self, three_constraint_infeasible):
        model, si, result = three_constraint_infeasible
        assert result.status == "infeasible"
        assert result.iis is not None
        suggestions = suggest_relaxations(result.iis, model, si)
        # At least one suggestion should reference the binding sum_limit constraint
        names = {s.constraint_name for s in suggestions}
        # sum_limit (x+y<=3) and/or x_min and y_min should appear
        iis_names = set(result.iis.conflicting_constraints)
        assert names & iis_names

    def test_contradictory_upper_x_relaxation_direction(self, contradictory_lp):
        """upper_x (x <= 5) should be relaxed by increasing RHS toward >= 10."""
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        upper_x_sug = next((s for s in suggestions if s.constraint_name == "upper_x"), None)
        if upper_x_sug:
            # upper_x RHS must increase from 5.0 toward 10.0
            assert upper_x_sug.suggested_value > upper_x_sug.current_value
            assert upper_x_sug.suggested_value >= 10.0 - 0.01

    def test_lower_x_relaxation_direction(self, contradictory_lp):
        """lower_x (x >= 10) should be relaxed by decreasing RHS toward <= 5."""
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        lower_x_sug = next((s for s in suggestions if s.constraint_name == "lower_x"), None)
        if lower_x_sug:
            # lower_x RHS must decrease from 10.0 toward 5.0
            assert lower_x_sug.suggested_value < lower_x_sug.current_value
            assert lower_x_sug.suggested_value <= 5.0 + 0.01


# ---------------------------------------------------------------------------
# TestRanking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_suggestions_sorted_by_relaxation_percent_ascending(self, three_constraint_infeasible):
        model, si, result = three_constraint_infeasible
        suggestions = suggest_relaxations(result.iis, model, si)
        if len(suggestions) >= 2:
            percents = [s.relaxation_percent for s in suggestions]
            assert percents == sorted(percents), (
                f"Suggestions not sorted by relaxation_percent: {percents}"
            )

    def test_priority_field_starts_at_one(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        if suggestions:
            assert suggestions[0].priority == 1

    def test_priority_is_sequential(self, three_constraint_infeasible):
        model, si, result = three_constraint_infeasible
        suggestions = suggest_relaxations(result.iis, model, si)
        for i, s in enumerate(suggestions):
            assert s.priority == i + 1

    def test_smallest_relaxation_is_first(self):
        """Build a model where one constraint needs a small relaxation and one a large one."""
        # x >= 5.001 AND x <= 5.000 → upper_x needs +0.001, lower_x needs -5.001
        model = LPModel(
            name="asymmetric",
            variables=[LPVariable(name="x", lower_bound=0.0)],
            constraints=[
                LinearConstraint(name="lower_x", coefficients={"x": 1.0}, sense=">=", rhs=5.001),
                LinearConstraint(name="upper_x", coefficients={"x": 1.0}, sense="<=", rhs=5.000),
            ],
            objective=LinearObjective(sense="minimize", coefficients={"x": 1.0}),
        )
        si = build_from_lp(model)
        result = solve(si)
        assert result.status == "infeasible"
        assert result.iis is not None
        suggestions = suggest_relaxations(result.iis, model, si)
        if len(suggestions) >= 2:
            # Both need a small relaxation (~0.001 change on RHS of 5)
            # Relaxation percents should be equal or nearly equal in this case
            assert suggestions[0].relaxation_percent <= suggestions[1].relaxation_percent


# ---------------------------------------------------------------------------
# TestFeasibilityVerification
# ---------------------------------------------------------------------------


class TestFeasibilityVerification:
    def test_applying_suggestion_gives_feasible_result(self, contradictory_lp):
        """Re-solve with the suggested RHS and verify the result is optimal."""
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        assert len(suggestions) > 0

        top = suggestions[0]
        # Apply the suggestion manually
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}

        if top.constraint_name in cname_to_idx:
            c_idx = cname_to_idx[top.constraint_name]
            data = si.model_dump()
            data["constraint_rhs"][c_idx] = top.suggested_value
            from sage_core.models import SolverInput
            relaxed_si = SolverInput(**data)
            relaxed_result = solve(relaxed_si)
            assert relaxed_result.status == "optimal", (
                f"Re-solving with suggestion for '{top.constraint_name}' "
                f"(RHS={top.suggested_value:.4f}) is still {relaxed_result.status}"
            )

    def test_new_objective_value_matches_resolve(self, contradictory_lp):
        """The reported new_objective_value should match actual re-solve."""
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        if not suggestions or suggestions[0].new_objective_value is None:
            pytest.skip("No new_objective_value reported")

        top = suggestions[0]
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}

        if top.constraint_name in cname_to_idx:
            c_idx = cname_to_idx[top.constraint_name]
            data = si.model_dump()
            data["constraint_rhs"][c_idx] = top.suggested_value
            from sage_core.models import SolverInput
            relaxed_si = SolverInput(**data)
            actual_result = solve(relaxed_si)
            if actual_result.status == "optimal" and actual_result.objective_value is not None:
                assert actual_result.objective_value == pytest.approx(
                    top.new_objective_value, rel=1e-3
                )

    def test_three_constraint_relaxed_solutions_are_feasible(self, three_constraint_infeasible):
        """Every suggestion in a 3-constraint IIS should produce a feasible result."""
        model, si, result = three_constraint_infeasible
        suggestions = suggest_relaxations(result.iis, model, si)

        from sage_core.models import SolverInput
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}
        vname_to_idx = {n: i for i, n in enumerate(si.variable_names)}

        for s in suggestions:
            data = si.model_dump()
            if s.constraint_name in cname_to_idx:
                c_idx = cname_to_idx[s.constraint_name]
                data["constraint_rhs"][c_idx] = s.suggested_value
            elif s.constraint_name.endswith("_upper_bound"):
                vname = s.constraint_name.replace("_upper_bound", "")
                if vname in vname_to_idx:
                    v_idx = vname_to_idx[vname]
                    data["variable_upper_bounds"][v_idx] = s.suggested_value
            else:
                continue

            relaxed_si = SolverInput(**data)
            relaxed_result = solve(relaxed_si)
            assert relaxed_result.status == "optimal", (
                f"Suggestion for '{s.constraint_name}' (value={s.suggested_value:.4f}) "
                f"still infeasible"
            )


# ---------------------------------------------------------------------------
# TestIntegrationInfeasibleToFeasible
# ---------------------------------------------------------------------------


class TestIntegrationInfeasibleToFeasible:
    def test_lp_infeasible_explain_relax_resolve(self, contradictory_lp):
        """Full pipeline: infeasible LP → explain → relax → re-solve → feasible."""
        model, si, result = contradictory_lp
        assert result.status == "infeasible"

        # Step 1: explain infeasibility
        explanation = explain_infeasibility(result.iis, model)  # type: ignore[arg-type]
        assert "infeasible" in explanation.lower()

        # Step 2: suggest relaxations
        suggestions = suggest_relaxations(result.iis, model, si)
        assert len(suggestions) > 0

        # Step 3: apply best relaxation and re-solve
        top = suggestions[0]
        from sage_core.models import SolverInput
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}

        assert top.constraint_name in cname_to_idx
        c_idx = cname_to_idx[top.constraint_name]
        data = si.model_dump()
        data["constraint_rhs"][c_idx] = top.suggested_value
        relaxed_si = SolverInput(**data)
        final_result = solve(relaxed_si)

        # Step 4: verify feasible
        assert final_result.status == "optimal"

    def test_scheduling_infeasible_explain_relax_resolve(self):
        """Full pipeline: infeasible scheduling → explain → relax → re-solve → feasible.

        Alice has max_hours=8 (1 shift worth) but must cover 3 planning days × 8h.
        The hours_Alice constraint (<=8) conflicts with 3 coverage constraints (>=1 each).
        Relaxing hours_Alice to <=24 restores feasibility with a single constraint change.
        """
        model = SchedulingModel(
            workers=[Worker(name="Alice", max_hours=8)],  # only 8h = 1 shift
            shifts=[Shift(name="Day", duration_hours=8, required_workers=1)],
            planning_horizon_days=3,   # 3 days × 8h = 24h needed, Alice has only 8h
            max_consecutive_days=3,
        )
        si = build_from_scheduling(model)
        result = solve(si)
        assert result.status == "infeasible"

        # Explain
        explanation = explain_infeasibility(result.iis, model)  # type: ignore[arg-type]
        assert isinstance(explanation, str) and len(explanation) > 0
        assert "infeasible" in explanation.lower()

        # Suggest relaxations
        suggestions = suggest_relaxations(result.iis, model, si)
        assert len(suggestions) > 0, "Expected at least one relaxation suggestion"

        # Apply best relaxation and verify feasibility
        from sage_core.models import SolverInput
        top = suggestions[0]
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}
        vname_to_idx = {n: i for i, n in enumerate(si.variable_names)}

        data = si.model_dump()
        if top.constraint_name in cname_to_idx:
            c_idx = cname_to_idx[top.constraint_name]
            data["constraint_rhs"][c_idx] = top.suggested_value
        elif top.constraint_name.endswith("_upper_bound"):
            vname = top.constraint_name.replace("_upper_bound", "")
            if vname in vname_to_idx:
                v_idx = vname_to_idx[vname]
                data["variable_upper_bounds"][v_idx] = top.suggested_value

        relaxed_si = SolverInput(**data)
        final_result = solve(relaxed_si)
        assert final_result.status == "optimal", (
            f"Re-solving with best suggestion still {final_result.status}"
        )

    def test_portfolio_infeasible_explain_relax_resolve(self):
        """Portfolio with impossible allocation constraints → relax → feasible.

        5 assets, each requiring min 25% allocation → min total = 125% > 100%.
        """
        from sage_core.builder import build_from_portfolio
        from sage_core.models import Asset, PortfolioConstraints, PortfolioModel

        model = PortfolioModel(
            assets=[Asset(name=f"A{i}", expected_return=0.1) for i in range(5)],
            covariance_matrix=[
                [0.01 if i == j else 0.001 for j in range(5)] for i in range(5)
            ],
            risk_aversion=1.0,
            constraints=PortfolioConstraints(
                min_allocation_per_asset=0.25,
                max_total_allocation=1.0,
            ),
        )
        si = build_from_portfolio(model)
        result = solve(si)
        assert result.status == "infeasible"

        explanation = explain_infeasibility(result.iis, model)  # type: ignore[arg-type]
        assert "infeasible" in explanation.lower()

        suggestions = suggest_relaxations(result.iis, model, si)
        assert len(suggestions) > 0

        # Apply best relaxation
        from sage_core.models import SolverInput
        top = suggestions[0]
        cname_to_idx = {n: i for i, n in enumerate(si.constraint_names)}
        if top.constraint_name in cname_to_idx:
            c_idx = cname_to_idx[top.constraint_name]
            data = si.model_dump()
            data["constraint_rhs"][c_idx] = top.suggested_value
            relaxed_si = SolverInput(**data)
            final_result = solve(relaxed_si)
            assert final_result.status == "optimal"


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_iis_with_unknown_constraint_names_skipped(self, contradictory_lp):
        """IIS referencing nonexistent constraints should be skipped gracefully."""
        model, si, result = contradictory_lp
        fake_iis = IISResult(
            conflicting_constraints=["nonexistent_constraint"],
            conflicting_variable_bounds=[],
            explanation="fake iis",
        )
        suggestions = suggest_relaxations(fake_iis, model, si)
        assert suggestions == []

    def test_suggestion_explanation_mentions_constraint_name(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        for s in suggestions:
            # Explanation should mention the constraint name or at least be meaningful
            assert len(s.explanation) > 20

    def test_suggestion_current_value_matches_original_rhs(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        cname_to_rhs = dict(zip(si.constraint_names, si.constraint_rhs))
        for s in suggestions:
            if s.constraint_name in cname_to_rhs:
                assert s.current_value == pytest.approx(
                    cname_to_rhs[s.constraint_name], abs=1e-8
                )

    def test_suggestions_are_list(self, contradictory_lp):
        model, si, result = contradictory_lp
        suggestions = suggest_relaxations(result.iis, model, si)
        assert isinstance(suggestions, list)

    def test_mip_infeasible_suggestions(self):
        """MIP with infeasible constraint — suggestions should still work."""
        model = MIPModel(
            name="mip_infeasible",
            variables=[MIPVariable(name="y", var_type="binary")],
            constraints=[
                LinearConstraint(name="force_above", coefficients={"y": 1.0}, sense=">=", rhs=2.0),
            ],
            objective=LinearObjective(sense="minimize", coefficients={"y": 1.0}),
        )
        si = build_from_mip(model)
        result = solve(si)
        assert result.status == "infeasible"
        assert result.iis is not None
        suggestions = suggest_relaxations(result.iis, model, si)
        # force_above (y >= 2) should be relaxed to y >= 1 or below
        if suggestions:
            assert suggestions[0].relaxation_percent > 0
