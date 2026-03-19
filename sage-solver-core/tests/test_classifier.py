"""Tests for sage_solver_core.classifier — Problem Classifier (Stage 9)."""

from __future__ import annotations

import time

import pytest

from sage_solver_core.classifier import ClassificationResult, classify
from sage_solver_core.models import (
    Asset,
    LPModel,
    LPVariable,
    LinearConstraint,
    LinearObjective,
    MIPModel,
    MIPVariable,
    PortfolioModel,
    SchedulingModel,
    Shift,
    Worker,
)


# ---------------------------------------------------------------------------
# Helpers — minimal model factories
# ---------------------------------------------------------------------------


def _make_lp(n_vars: int, n_constraints: int = 1) -> LPModel:
    """Build a minimal LP with *n_vars* variables and *n_constraints* constraints."""
    variables = [LPVariable(name=f"x{i}") for i in range(n_vars)]
    # Each constraint references the first variable to keep it simple
    constraints = [
        LinearConstraint(
            name=f"c{i}",
            coefficients={f"x{i % n_vars}": 1.0},
            sense="<=",
            rhs=100.0,
        )
        for i in range(n_constraints)
    ]
    objective = LinearObjective(
        sense="maximize",
        coefficients={f"x0": 1.0},
    )
    return LPModel(
        name="test_lp",
        variables=variables,
        constraints=constraints,
        objective=objective,
    )


def _make_mip(
    n_binary: int,
    n_continuous: int = 0,
    n_constraints: int = 1,
    time_limit: float | None = 60.0,
) -> MIPModel:
    """Build a minimal MIP with *n_binary* binary vars and *n_continuous* continuous vars."""
    variables: list[MIPVariable] = []
    for i in range(n_binary):
        variables.append(
            MIPVariable(name=f"b{i}", var_type="binary", lower_bound=0, upper_bound=1)
        )
    for i in range(n_continuous):
        variables.append(MIPVariable(name=f"c{i}", var_type="continuous"))

    n_total = n_binary + n_continuous
    constraints = [
        LinearConstraint(
            name=f"con{i}",
            coefficients={variables[i % n_total].name: 1.0},
            sense="<=",
            rhs=100.0,
        )
        for i in range(n_constraints)
    ]
    objective = LinearObjective(
        sense="maximize",
        coefficients={variables[0].name: 1.0},
    )
    return MIPModel(
        name="test_mip",
        variables=variables,
        constraints=constraints,
        objective=objective,
        time_limit_seconds=time_limit,
    )


def _make_portfolio(n_assets: int = 5) -> PortfolioModel:
    """Build a minimal portfolio model with *n_assets* assets."""
    assets = [
        Asset(name=f"ASSET{i}", expected_return=0.05 + i * 0.01)
        for i in range(n_assets)
    ]
    # Identity covariance matrix (simple PSD)
    cov = [[1.0 if i == j else 0.0 for j in range(n_assets)] for i in range(n_assets)]
    return PortfolioModel(
        assets=assets,
        covariance_matrix=cov,
        risk_aversion=1.0,
    )


def _make_scheduling(
    n_workers: int = 5,
    n_shifts: int = 3,
    horizon: int = 7,
) -> SchedulingModel:
    """Build a minimal scheduling model."""
    workers = [
        Worker(name=f"W{i}", max_hours=40.0) for i in range(n_workers)
    ]
    shifts = [
        Shift(name=f"S{i}", duration_hours=8.0, required_workers=1)
        for i in range(n_shifts)
    ]
    return SchedulingModel(
        workers=workers,
        shifts=shifts,
        planning_horizon_days=horizon,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassifier:
    """Classifier tier assignment tests."""

    def test_pure_lp_instant(self) -> None:
        """Test 1: Pure LP with 10 vars, 5 constraints -> instant."""
        model = _make_lp(n_vars=10, n_constraints=5)
        result = classify(model)
        assert result.tier == "instant"
        assert result.signals["problem_type"] == "lp"
        assert result.signals["n_vars"] == 10
        assert result.signals["n_binary"] == 0

    def test_small_mip_instant(self) -> None:
        """Test 2: Small MIP with 50 binary vars, 200 total -> instant."""
        model = _make_mip(n_binary=50, n_continuous=150, n_constraints=10)
        result = classify(model)
        assert result.tier == "instant"
        assert result.signals["n_binary"] == 50

    def test_medium_mip_fast(self) -> None:
        """Test 3: Medium MIP with 150 binary vars -> fast."""
        model = _make_mip(n_binary=150, n_constraints=5)
        result = classify(model)
        assert result.tier == "fast"

    def test_large_mip_background(self) -> None:
        """Test 4: Large MIP with 600 binary vars -> background."""
        model = _make_mip(n_binary=600, n_constraints=5)
        result = classify(model)
        assert result.tier == "background"

    def test_large_var_count_background(self) -> None:
        """Test 5: LP with 60,000 vars -> background."""
        model = _make_lp(n_vars=60_000, n_constraints=1)
        result = classify(model)
        assert result.tier == "background"
        assert result.signals["n_vars"] == 60_000

    def test_portfolio_instant(self) -> None:
        """Test 6: Portfolio problem -> instant regardless of size."""
        model = _make_portfolio(n_assets=50)
        result = classify(model)
        assert result.tier == "instant"
        assert result.signals["problem_type"] == "portfolio"

    def test_scheduling_fast(self) -> None:
        """Test 7: Moderate scheduling -> fast."""
        # 5 workers * 3 shifts * 7 days = 105 binary -> caught by rule 2 (n_binary > 100)
        # Use smaller dimensions: 3 workers * 2 shifts * 7 days = 42 binary
        model = _make_scheduling(n_workers=3, n_shifts=2, horizon=7)
        result = classify(model)
        assert result.tier == "fast"
        assert result.signals["problem_type"] == "scheduling"

    def test_large_scheduling_background(self) -> None:
        """Test 8: Large scheduling -> background (n_binary > 500)."""
        # 10 workers * 5 shifts * 14 days = 700 binary -> background
        model = _make_scheduling(n_workers=10, n_shifts=5, horizon=14)
        result = classify(model)
        assert result.tier == "background"
        assert result.signals["n_binary"] == 700

    def test_explicit_time_limit_fast(self) -> None:
        """Test 9: MIP with time_limit_seconds=120 -> at least fast."""
        model = _make_mip(n_binary=10, n_constraints=2, time_limit=120.0)
        result = classify(model)
        assert result.tier in ("fast", "background")
        assert result.signals["has_time_limit"] is True
        assert result.signals["time_limit"] == 120.0

    def test_probe_completes_quickly(self) -> None:
        """Test 10: Ambiguous MIP (80 binary) — classify completes within 200ms."""
        model = _make_mip(n_binary=80, n_continuous=20, n_constraints=5)
        t0 = time.perf_counter()
        result = classify(model)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # Should complete within 200ms total (probe is capped at 50ms)
        assert elapsed_ms < 200, f"classify took {elapsed_ms:.0f}ms, expected < 200ms"
        # Tier should be instant or fast depending on probe outcome
        assert result.tier in ("instant", "fast")

    def test_classification_result_has_reasoning(self) -> None:
        """Test 11: Every ClassificationResult has a non-empty reasoning string."""
        models = [
            _make_lp(10, 5),
            _make_mip(30, 10),
            _make_portfolio(5),
            _make_scheduling(3, 2, 7),
        ]
        for model in models:
            result = classify(model)
            assert isinstance(result.reasoning, str)
            assert len(result.reasoning) > 0

    def test_pure_function_no_side_effects(self) -> None:
        """Test 12: classify() is pure — same input gives same output twice."""
        model = _make_lp(n_vars=10, n_constraints=5)
        result1 = classify(model)
        result2 = classify(model)
        assert result1.tier == result2.tier
        assert result1.reasoning == result2.reasoning
        assert result1.estimated_seconds == result2.estimated_seconds
        assert result1.signals == result2.signals
