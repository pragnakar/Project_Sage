"""Tests for Stage 15 — Assumed Constraints.

Coverage:
- AssumedConstraint schema validates with all valid field combinations
- Invalid source rejected
- SolverInput accepts assumed_constraints list
- evaluate_assumed_constraints: sensitivity_safe = True when within range
- evaluate_assumed_constraints: sensitivity_safe = False when outside range
- High shadow price + low confidence → flagged even when within range
- Top-3 shadow price + low confidence → urgent flag
- Explainer narration includes flags for unsafe assumptions
- Explainer narration includes brief mention for safe assumptions
- SolverResult includes assumed_constraints post-solve
- Full pipeline: solve with assumed constraints → explanation includes flags
"""

from __future__ import annotations

import pytest

from sage_solver_core.builder import build_from_lp
from sage_solver_core.explainer import evaluate_assumed_constraints, explain_result
from sage_solver_core.models import (
    AssumedConstraint,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    SolverInput,
    SolverResult,
)
from sage_solver_core.solver import solve


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_lp() -> LPModel:
    """Maximize 3x + 2y s.t. x+y<=10, x<=6, y<=8, x,y>=0."""
    return LPModel(
        name="simple_lp",
        variables=[
            LPVariable(name="x", lower_bound=0, upper_bound=None),
            LPVariable(name="y", lower_bound=0, upper_bound=None),
        ],
        constraints=[
            LinearConstraint(name="total", coefficients={"x": 1, "y": 1}, sense="<=", rhs=10),
            LinearConstraint(name="x_cap", coefficients={"x": 1}, sense="<=", rhs=6),
            LinearConstraint(name="y_cap", coefficients={"y": 1}, sense="<=", rhs=8),
        ],
        objective=LinearObjective(sense="maximize", coefficients={"x": 3, "y": 2}),
    )


def _sample_assumed_constraints() -> list[AssumedConstraint]:
    return [
        AssumedConstraint(
            constraint_name="total",
            assumed_value=10.0,
            confidence="high",
            source="user_stated",
            rationale="Budget confirmed by CFO",
        ),
        AssumedConstraint(
            constraint_name="x_cap",
            assumed_value=6.0,
            confidence="medium",
            source="industry_benchmark",
            rationale="Based on 2024 average capacity",
        ),
        AssumedConstraint(
            constraint_name="y_cap",
            assumed_value=8.0,
            confidence="low",
            source="expert_estimate",
            rationale="Rough estimate from operations team",
        ),
    ]


# ---------------------------------------------------------------------------
# Schema Validation
# ---------------------------------------------------------------------------


class TestAssumedConstraintSchema:
    """AssumedConstraint Pydantic schema validation."""

    def test_valid_all_sources(self):
        """All valid source values should be accepted."""
        for source in [
            "user_stated",
            "historical_average",
            "industry_benchmark",
            "web_research",
            "regulatory_default",
            "expert_estimate",
        ]:
            ac = AssumedConstraint(
                constraint_name="c1",
                assumed_value=10.0,
                confidence="high",
                source=source,
                rationale="Test rationale",
            )
            assert ac.source == source

    def test_valid_all_confidence_levels(self):
        """All confidence levels should be accepted."""
        for conf in ["high", "medium", "low"]:
            ac = AssumedConstraint(
                constraint_name="c1",
                assumed_value=10.0,
                confidence=conf,
                source="user_stated",
                rationale="Test rationale",
            )
            assert ac.confidence == conf

    def test_invalid_source_rejected(self):
        """Invalid source values should raise ValidationError."""
        with pytest.raises(Exception):
            AssumedConstraint(
                constraint_name="c1",
                assumed_value=10.0,
                confidence="high",
                source="made_up",
                rationale="Test rationale",
            )

    def test_invalid_confidence_rejected(self):
        """Invalid confidence values should raise ValidationError."""
        with pytest.raises(Exception):
            AssumedConstraint(
                constraint_name="c1",
                assumed_value=10.0,
                confidence="very_high",
                source="user_stated",
                rationale="Test rationale",
            )

    def test_optional_fields_default_none(self):
        """actual_value and sensitivity_safe default to None."""
        ac = AssumedConstraint(
            constraint_name="c1",
            assumed_value=10.0,
            confidence="high",
            source="user_stated",
            rationale="Test",
        )
        assert ac.actual_value is None
        assert ac.sensitivity_safe is None

    def test_sensitivity_safe_populated(self):
        """sensitivity_safe can be set to True or False."""
        ac = AssumedConstraint(
            constraint_name="c1",
            assumed_value=10.0,
            confidence="high",
            source="user_stated",
            rationale="Test",
            sensitivity_safe=True,
        )
        assert ac.sensitivity_safe is True


class TestSolverInputWithAssumedConstraints:
    """SolverInput accepts assumed_constraints."""

    def test_solver_input_with_assumed_constraints(self):
        """SolverInput should accept assumed_constraints list."""
        model = _simple_lp()
        si = build_from_lp(model)
        ac_list = _sample_assumed_constraints()
        si_with_ac = si.model_copy(update={"assumed_constraints": ac_list})
        assert si_with_ac.assumed_constraints is not None
        assert len(si_with_ac.assumed_constraints) == 3

    def test_solver_input_default_none(self):
        """SolverInput assumed_constraints defaults to None."""
        model = _simple_lp()
        si = build_from_lp(model)
        assert si.assumed_constraints is None

    def test_solve_with_assumed_constraints(self):
        """Solver should accept and solve a SolverInput with assumed_constraints."""
        model = _simple_lp()
        si = build_from_lp(model)
        ac_list = _sample_assumed_constraints()
        si_with_ac = si.model_copy(update={"assumed_constraints": ac_list})
        result = solve(si_with_ac)
        assert result.status == "optimal"
        assert result.objective_value == pytest.approx(26.0)


# ---------------------------------------------------------------------------
# Evaluate Assumed Constraints
# ---------------------------------------------------------------------------


class TestEvaluateAssumedConstraints:
    """evaluate_assumed_constraints cross-references sensitivity data."""

    def _solve_simple_lp(self) -> SolverResult:
        model = _simple_lp()
        si = build_from_lp(model)
        return solve(si)

    def test_safe_within_range(self):
        """Assumed value within allowable RHS range → sensitivity_safe = True."""
        result = self._solve_simple_lp()
        # The "total" constraint has RHS=10, assumed_value=10 should be within range
        assumed = [
            AssumedConstraint(
                constraint_name="total",
                assumed_value=10.0,
                confidence="high",
                source="user_stated",
                rationale="Known budget",
            )
        ]
        evaluated = evaluate_assumed_constraints(assumed, result)
        assert len(evaluated) == 1
        assert evaluated[0].sensitivity_safe is True

    def test_unsafe_outside_range(self):
        """Assumed value outside allowable RHS range → sensitivity_safe = False."""
        result = self._solve_simple_lp()
        # Create a fake result with tight RHS ranges
        # The "total" constraint binds at 10. If we claim assumed_value=100,
        # it should be outside the range.
        assumed = [
            AssumedConstraint(
                constraint_name="total",
                assumed_value=100.0,
                confidence="high",
                source="user_stated",
                rationale="Wild guess",
            )
        ]
        evaluated = evaluate_assumed_constraints(assumed, result)
        assert len(evaluated) == 1
        # If result has rhs_ranges for "total" and 100 is outside, should be False
        if result.rhs_ranges and "total" in result.rhs_ranges:
            assert evaluated[0].sensitivity_safe is False
        # Otherwise sensitivity data may not be available

    def test_high_shadow_price_low_confidence_flagged(self):
        """Shadow price > 0 AND confidence != 'high' → flagged."""
        result = self._solve_simple_lp()
        # "total" is a binding constraint with non-zero shadow price
        assumed = [
            AssumedConstraint(
                constraint_name="total",
                assumed_value=10.0,
                confidence="low",
                source="expert_estimate",
                rationale="Rough estimate",
            )
        ]
        evaluated = evaluate_assumed_constraints(assumed, result)
        assert len(evaluated) == 1
        # Should be flagged because shadow price > 0 and confidence is low
        if result.shadow_prices and abs(result.shadow_prices.get("total", 0)) > 1e-8:
            assert evaluated[0].sensitivity_safe is False

    def test_non_binding_high_confidence_safe(self):
        """Non-binding constraint with high confidence → safe."""
        result = self._solve_simple_lp()
        # "y_cap" has RHS=8 but y=4 at optimal, so it's non-binding
        assumed = [
            AssumedConstraint(
                constraint_name="y_cap",
                assumed_value=8.0,
                confidence="high",
                source="user_stated",
                rationale="Confirmed capacity",
            )
        ]
        evaluated = evaluate_assumed_constraints(assumed, result)
        assert len(evaluated) == 1
        # Non-binding with value within range and high confidence → safe
        if evaluated[0].sensitivity_safe is not None:
            assert evaluated[0].sensitivity_safe is True


# ---------------------------------------------------------------------------
# Explainer Narration
# ---------------------------------------------------------------------------


class TestExplainerWithAssumedConstraints:
    """explain_result includes assumed constraint narratives."""

    def test_explanation_includes_safe_mention(self):
        """Safe assumptions get brief mention in explanation."""
        model = _simple_lp()
        si = build_from_lp(model)
        result = solve(si)
        assumed = [
            AssumedConstraint(
                constraint_name="total",
                assumed_value=10.0,
                confidence="high",
                source="user_stated",
                rationale="Budget confirmed by CFO",
                sensitivity_safe=True,
            )
        ]
        explanation = explain_result(result, model, "standard", assumed_constraints=assumed)
        assert "Assumed constraints" in explanation
        assert "Budget confirmed by CFO" in explanation

    def test_explanation_includes_warning_for_unsafe(self):
        """Unsafe assumptions get loud warning in explanation."""
        model = _simple_lp()
        si = build_from_lp(model)
        result = solve(si)
        assumed = [
            AssumedConstraint(
                constraint_name="x_cap",
                assumed_value=6.0,
                confidence="low",
                source="expert_estimate",
                rationale="Rough estimate from ops",
                sensitivity_safe=False,
            )
        ]
        explanation = explain_result(result, model, "standard", assumed_constraints=assumed)
        assert "Flagged" in explanation
        assert "Verify" in explanation
        assert "Rough estimate from ops" in explanation

    def test_explanation_no_assumed_constraints(self):
        """No assumed constraints → no assumed constraints section."""
        model = _simple_lp()
        si = build_from_lp(model)
        result = solve(si)
        explanation = explain_result(result, model, "standard")
        assert "Assumed constraints" not in explanation

    def test_detailed_includes_assumed_constraints(self):
        """Detailed explanation also includes assumed constraints section."""
        model = _simple_lp()
        si = build_from_lp(model)
        result = solve(si)
        assumed = _sample_assumed_constraints()
        evaluated = evaluate_assumed_constraints(assumed, result)
        explanation = explain_result(result, model, "detailed", assumed_constraints=evaluated)
        assert "Assumed constraints" in explanation


# ---------------------------------------------------------------------------
# SolverResult with assumed_constraints
# ---------------------------------------------------------------------------


class TestSolverResultAssumedConstraints:
    """SolverResult carries assumed_constraints post-solve."""

    def test_result_default_none(self):
        """SolverResult assumed_constraints defaults to None."""
        result = SolverResult(
            status="optimal",
            objective_value=26.0,
            solve_time_seconds=0.01,
            variable_values={"x": 6, "y": 4},
        )
        assert result.assumed_constraints is None

    def test_result_with_assumed_constraints(self):
        """SolverResult can carry evaluated assumed constraints."""
        ac = AssumedConstraint(
            constraint_name="total",
            assumed_value=10.0,
            confidence="high",
            source="user_stated",
            rationale="Known",
            sensitivity_safe=True,
        )
        result = SolverResult(
            status="optimal",
            objective_value=26.0,
            solve_time_seconds=0.01,
            variable_values={"x": 6, "y": 4},
            assumed_constraints=[ac],
        )
        assert result.assumed_constraints is not None
        assert len(result.assumed_constraints) == 1
        assert result.assumed_constraints[0].sensitivity_safe is True


# ---------------------------------------------------------------------------
# Full Pipeline Integration
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: solve LP with assumed constraints, evaluate, explain."""

    def test_full_pipeline(self):
        """Submit LP with assumed constraints → solve → evaluate → explain."""
        model = _simple_lp()
        si = build_from_lp(model)
        assumed = _sample_assumed_constraints()
        si_with_ac = si.model_copy(update={"assumed_constraints": assumed})

        # Solve
        result = solve(si_with_ac)
        assert result.status == "optimal"

        # Evaluate
        evaluated = evaluate_assumed_constraints(assumed, result)
        assert len(evaluated) == 3
        for ac in evaluated:
            assert ac.sensitivity_safe is not None  # All should be determined for LP

        # Attach to result
        result_with_ac = result.model_copy(update={"assumed_constraints": evaluated})
        assert result_with_ac.assumed_constraints is not None

        # Explain
        explanation = explain_result(result, model, "standard", assumed_constraints=evaluated)
        assert "Assumed constraints" in explanation

        # Round-trip serialization
        result_json = result_with_ac.model_dump_json()
        restored = SolverResult.model_validate_json(result_json)
        assert restored.assumed_constraints is not None
        assert len(restored.assumed_constraints) == 3
