"""Tests for the status messaging, retry, and fallback chain (Parts 2-3).

Covers:
- Successful solve → [Sage MCP] ✓ header
- Infeasible problem → [Sage MCP] ✓ info header (NOT a fallback trigger)
- Technical error on first call, success on retry
- Technical error on both calls, fallback to scipy/PuLP
- All solvers failing
- MCP response schema validation
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock

import pytest

import sage_solver_mcp.server as _srv
from sage_solver_core.models import SolverResult


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_LP_ARGS = {
    "problem_type": "lp",
    "name": "test_lp",
    "variables": [
        {"name": "x", "lower_bound": 0.0, "upper_bound": 6.0},
        {"name": "y", "lower_bound": 0.0, "upper_bound": 8.0},
    ],
    "constraints": [
        {
            "name": "c1",
            "coefficients": {"x": 1.0, "y": 1.0},
            "sense": "<=",
            "rhs": 10.0,
        }
    ],
    "objective": {
        "coefficients": {"x": 3.0, "y": 2.0},
        "sense": "maximize",
    },
}

INFEASIBLE_LP_ARGS = {
    "problem_type": "lp",
    "name": "infeasible_lp",
    "variables": [
        {"name": "x", "lower_bound": 0.0},
        {"name": "y", "lower_bound": 0.0},
    ],
    "constraints": [
        {
            "name": "upper",
            "coefficients": {"x": 1.0, "y": 1.0},
            "sense": "<=",
            "rhs": 5.0,
        },
        {
            "name": "lower",
            "coefficients": {"x": 1.0, "y": 1.0},
            "sense": ">=",
            "rhs": 10.0,
        },
    ],
    "objective": {
        "coefficients": {"x": 1.0, "y": 1.0},
        "sense": "maximize",
    },
}


# ---------------------------------------------------------------------------
# Part 2: Status messaging
# ---------------------------------------------------------------------------


class TestStatusHeaders:
    """Verify the [Sage MCP] ✓ / ✗ headers appear correctly."""

    def test_successful_solve_has_success_header(self):
        result = run(_srv.call_tool("solve_optimization", SIMPLE_LP_ARGS))
        text = result[0].text
        assert text.startswith("[Sage MCP] \u2713 Solved using sage:solve_optimization")

    def test_infeasible_has_info_header_not_error(self):
        result = run(_srv.call_tool("solve_optimization", INFEASIBLE_LP_ARGS))
        text = result[0].text
        assert "[Sage MCP] \u2713" in text
        assert "completed" in text
        assert "infeasible/unbounded" in text
        # Must NOT contain error marker
        assert "\u2717" not in text

    def test_check_feasibility_feasible_has_success_header(self):
        result = run(_srv.call_tool("check_feasibility", SIMPLE_LP_ARGS))
        text = result[0].text
        assert "[Sage MCP] \u2713 Solved using sage:check_feasibility" in text

    def test_check_feasibility_infeasible_has_info_header(self):
        result = run(_srv.call_tool("check_feasibility", INFEASIBLE_LP_ARGS))
        text = result[0].text
        assert "[Sage MCP] \u2713" in text
        assert "infeasible/unbounded" in text

    def test_suggest_relaxations_has_success_header(self):
        # First make an infeasible solve to populate state
        run(_srv.call_tool("solve_optimization", INFEASIBLE_LP_ARGS))
        result = run(_srv.call_tool("suggest_relaxations", {}))
        text = result[0].text
        assert "[Sage MCP]" in text

    def test_validation_error_has_sage_error_header(self):
        bad_args = {"problem_type": "lp", "variables": "not_a_list"}
        result = run(_srv.call_tool("solve_optimization", bad_args))
        text = result[0].text
        assert "[Sage MCP]" in text
        assert "error" in text.lower()


# ---------------------------------------------------------------------------
# Part 2: MCP response schema validation
# ---------------------------------------------------------------------------


class TestMCPResponseSchema:
    """Verify every response matches { content: [{ type: "text", text: "..." }] }"""

    def test_success_response_schema(self):
        result = run(_srv.call_tool("solve_optimization", SIMPLE_LP_ARGS))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].type == "text"
        assert isinstance(result[0].text, str)
        assert result[0].text.startswith("[Sage MCP]")

    def test_infeasible_response_schema(self):
        result = run(_srv.call_tool("solve_optimization", INFEASIBLE_LP_ARGS))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].type == "text"
        assert isinstance(result[0].text, str)

    def test_error_response_schema(self):
        result = run(_srv.call_tool("solve_optimization", {"bad": "input"}))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].type == "text"


# ---------------------------------------------------------------------------
# Part 3: Retry and fallback chain
# ---------------------------------------------------------------------------


class TestRetryAndFallback:
    """Test the technical error → retry → fallback → graceful failure chain."""

    def test_tech_error_first_call_success_on_retry(self):
        """First call raises, retry succeeds."""
        call_count = {"n": 0}
        original_solve = _srv.solve

        def flaky_solve(si):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Transient HiGHS crash")
            return original_solve(si)

        with patch.object(_srv, "solve", side_effect=flaky_solve):
            result = run(_srv.call_tool("solve_optimization", SIMPLE_LP_ARGS))

        text = result[0].text
        # Retry succeeded — should have success header
        assert "[Sage MCP]" in text
        assert call_count["n"] == 2  # called twice

    def test_tech_error_both_calls_fallback_to_scipy(self):
        """Both primary calls fail, scipy/PuLP fallback succeeds."""
        def always_fail(si):
            raise RuntimeError("HiGHS unavailable")

        fake_result = SolverResult(
            status="optimal",
            objective_value=26.0,
            bound=26.0,
            gap=0.0,
            solve_time_seconds=0.001,
            variable_values={"x": 6.0, "y": 4.0},
            shadow_prices=None,
            reduced_costs=None,
            constraint_slack=None,
            binding_constraints=None,
            objective_ranges=None,
            rhs_ranges=None,
            iis=None,
        )

        with patch.object(_srv, "solve", side_effect=always_fail), \
             patch("sage_solver_mcp.server.fallback_solve", return_value=(fake_result, "scipy")):
            result = run(_srv.call_tool("solve_optimization", SIMPLE_LP_ARGS))

        text = result[0].text
        assert "Sage unavailable" in text or "Falling back" in text
        assert "scipy" in text

    def test_all_solvers_fail_graceful_message(self):
        """Primary, retry, and fallback all fail."""
        def always_fail(si):
            raise RuntimeError("HiGHS unavailable")

        def fallback_fail(si):
            raise RuntimeError("scipy also unavailable")

        with patch.object(_srv, "solve", side_effect=always_fail), \
             patch("sage_solver_mcp.server.fallback_solve", side_effect=fallback_fail):
            result = run(_srv.call_tool("solve_optimization", SIMPLE_LP_ARGS))

        text = result[0].text
        assert "[Sage MCP] \u2717 All solvers failed" in text
        assert "Suggestions" in text

    def test_infeasible_does_NOT_trigger_fallback(self):
        """Infeasible is a valid result — must NOT retry or fallback."""
        solve_count = {"n": 0}
        original_solve = _srv.solve

        def counting_solve(si):
            solve_count["n"] += 1
            return original_solve(si)

        with patch.object(_srv, "solve", side_effect=counting_solve):
            result = run(_srv.call_tool("solve_optimization", INFEASIBLE_LP_ARGS))

        assert solve_count["n"] == 1  # called exactly once, no retry
        text = result[0].text
        assert "infeasible" in text.lower()
        assert "Falling back" not in text

    def test_non_solve_tool_no_retry(self):
        """Non-solve tools with technical errors should NOT retry or fallback."""
        # Patch resolve_path to succeed but read_data to fail with a RuntimeError
        with patch.object(_srv, "resolve_path", return_value="/tmp/test.xlsx"), \
             patch.object(_srv, "read_data", side_effect=RuntimeError("disk error")):
            result = run(_srv.call_tool("read_data_file", {"filepath": "/tmp/test.xlsx"}))

        text = result[0].text
        assert "[Sage MCP] \u2717" in text
        assert "technical error" in text.lower()
