"""Tests for Stage 12 — cloud integration in the MCP server.

Covers:
1. Instant tier solves inline
2. Background tier submits to cloud
3. Fallback when cloud absent
4. explain_solution with task_id
5. pause_job succeeds
6. pause_job no cloud
7. resume_job succeeds with gap info
8. get_job_progress narration
9. check_notifications with pending
10. check_notifications empty
11. All original tools still work
12. Tool count is 12
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch, MagicMock

import pytest

import sage_solver_mcp.server as _srv


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


def _reset_state() -> None:
    _srv._state.last_result = None
    _srv._state.last_model = None
    _srv._state.last_solver_input = None
    _srv._state.last_iis = None
    _srv._state.cloud_url = None
    _srv._state.cloud_api_key = None
    _srv._state.last_task_id = None


@pytest.fixture(autouse=True)
def reset_state():
    _reset_state()
    yield
    _reset_state()


# ---------------------------------------------------------------------------
# Test 1: Instant tier solves inline
# ---------------------------------------------------------------------------


class TestInstantTierInline:
    def test_simple_lp_solves_inline(self):
        """Small LP classifies as instant and solves inline."""
        result = run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        text = result[0].text
        assert "[tier: instant]" in text
        assert "optimal" in text.lower() or "28" in text

    def test_no_cloud_calls_for_instant(self):
        """Instant tier should not attempt cloud submission."""
        with patch.object(_srv, "_cloud_post", wraps=_srv._cloud_post) as mock_post:
            run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
            # _cloud_post should only be called for persist (best-effort),
            # not for job submission. Since cloud_url is None, it returns None immediately.
            # No /api/jobs call should happen.
            for call in mock_post.call_args_list:
                assert "/api/jobs" not in call.args[0]


# ---------------------------------------------------------------------------
# Test 2: Background tier submits to cloud
# ---------------------------------------------------------------------------


class TestBackgroundSubmitsToCloud:
    def test_background_tier_submits_to_cloud(self):
        """When cloud is available and tier is background, job is submitted."""
        _srv._state.cloud_url = "http://localhost:8765"

        # Mock the classifier to return background
        mock_classification = MagicMock()
        mock_classification.tier = "background"

        # Mock cloud POST to return a task_id
        cloud_response = {"task_id": "sage-test123", "status": "queued"}

        with patch("sage_solver_core.classifier.classify", return_value=mock_classification), \
             patch.object(_srv, "_cloud_post", return_value=cloud_response) as mock_post:
            result = run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))

        text = result[0].text
        assert "sage-test123" in text
        assert "background" in text.lower()
        # Verify cloud was called with /api/jobs
        called_paths = [call.args[0] for call in mock_post.call_args_list]
        assert "/api/jobs" in called_paths


# ---------------------------------------------------------------------------
# Test 3: Fallback when cloud absent
# ---------------------------------------------------------------------------


class TestFallbackNoCloud:
    def test_no_cloud_solve_works_inline(self):
        """With no cloud URL, even background-tier problems solve inline."""
        assert _srv._state.cloud_url is None

        # Mock classifier to return background
        mock_classification = MagicMock()
        mock_classification.tier = "background"

        with patch("sage_solver_core.classifier.classify", return_value=mock_classification):
            result = run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))

        text = result[0].text
        # Should solve inline and include a note about cloud not available
        assert "[Sage MCP]" in text
        assert "28" in text or "optimal" in text.lower()


# ---------------------------------------------------------------------------
# Test 4: explain_solution with task_id
# ---------------------------------------------------------------------------


class TestExplainWithTaskId:
    def test_explain_falls_back_to_local_state(self):
        """explain_solution uses local state when cloud is not available."""
        run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        result = run(_srv._handle_explain_solution({"detail_level": "brief"}))
        text = result[0].text
        assert len(text) > 0
        assert "[Sage MCP]" in text

    def test_explain_with_task_id_and_cloud(self):
        """explain_solution with task_id attempts cloud fetch, falls back to local."""
        run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        _srv._state.cloud_url = "http://localhost:8765"

        # Mock cloud GET to return None (blob not found)
        with patch.object(_srv, "_cloud_get", return_value=None):
            result = run(_srv._handle_explain_solution({
                "task_id": "sage-test123",
                "detail_level": "standard",
            }))

        text = result[0].text
        assert len(text) > 0  # Falls back to local state


# ---------------------------------------------------------------------------
# Test 5: pause_job succeeds
# ---------------------------------------------------------------------------


class TestPauseJob:
    def test_pause_job_success(self):
        """pause_job returns success when cloud responds."""
        _srv._state.cloud_url = "http://localhost:8765"

        with patch.object(_srv, "_cloud_post", return_value={"status": "pausing"}):
            result = run(_srv._handle_pause_job({"task_id": "sage-abc123"}))

        text = result[0].text
        assert "sage-abc123" in text
        assert "pause" in text.lower()
        assert "checkpoint" in text.lower()


# ---------------------------------------------------------------------------
# Test 6: pause_job no cloud
# ---------------------------------------------------------------------------


class TestPauseJobNoCloud:
    def test_pause_job_no_cloud_returns_error(self):
        """pause_job returns error when cloud is not running."""
        assert _srv._state.cloud_url is None

        result = run(_srv._handle_pause_job({"task_id": "sage-abc123"}))
        text = result[0].text
        assert "not running" in text.lower() or "error" in text.lower()


# ---------------------------------------------------------------------------
# Test 7: resume_job succeeds with gap info
# ---------------------------------------------------------------------------


class TestResumeJob:
    def test_resume_job_with_gap_info(self):
        """resume_job returns success with gap percentage."""
        _srv._state.cloud_url = "http://localhost:8765"

        job_info = {"status": "paused", "gap_pct": 12.5}
        resume_resp = {"status": "running"}

        with patch.object(_srv, "_cloud_get", return_value=job_info), \
             patch.object(_srv, "_cloud_post", return_value=resume_resp):
            result = run(_srv._handle_resume_job({"task_id": "sage-abc123"}))

        text = result[0].text
        assert "sage-abc123" in text
        assert "resumed" in text.lower()
        assert "12.5%" in text
        assert "warm-start" in text.lower()

    def test_resume_job_no_cloud(self):
        """resume_job returns error when cloud is not running."""
        result = run(_srv._handle_resume_job({"task_id": "sage-abc123"}))
        text = result[0].text
        assert "not running" in text.lower() or "error" in text.lower()


# ---------------------------------------------------------------------------
# Test 8: get_job_progress narration
# ---------------------------------------------------------------------------


class TestGetJobProgress:
    def test_progress_narration(self):
        """get_job_progress returns plain-language progress."""
        _srv._state.cloud_url = "http://localhost:8765"

        progress_data = {
            "status": "running",
            "elapsed_seconds": 3720,  # 1h 2m
            "gap_pct": 5.3,
            "best_incumbent": 1234.5678,
            "best_bound": 1300.0,
            "stall_detected": False,
        }

        with patch.object(_srv, "_cloud_get", return_value=progress_data):
            result = run(_srv._handle_get_job_progress({"task_id": "sage-xyz"}))

        text = result[0].text
        assert "sage-xyz" in text
        assert "running" in text.lower()
        assert "1h 2m" in text
        assert "5.3%" in text
        assert "1234.5678" in text
        assert "1300.0" in text

    def test_progress_with_stall(self):
        """get_job_progress includes stall warning when detected."""
        _srv._state.cloud_url = "http://localhost:8765"

        progress_data = {
            "status": "running",
            "elapsed_seconds": 600,
            "stall_detected": True,
        }

        with patch.object(_srv, "_cloud_get", return_value=progress_data):
            result = run(_srv._handle_get_job_progress({"task_id": "sage-xyz"}))

        text = result[0].text
        assert "stall" in text.lower()

    def test_progress_no_cloud(self):
        """get_job_progress returns error when cloud is not running."""
        result = run(_srv._handle_get_job_progress({"task_id": "sage-xyz"}))
        text = result[0].text
        assert "not running" in text.lower() or "error" in text.lower()


# ---------------------------------------------------------------------------
# Test 9: check_notifications with pending
# ---------------------------------------------------------------------------


class TestCheckNotificationsWithPending:
    def test_notifications_with_pending_jobs(self):
        """check_notifications returns completed job summaries."""
        _srv._state.cloud_url = "http://localhost:8765"

        notif_data = {
            "schema_version": "2.0",
            "pending": [
                {"task_id": "sage-001", "problem_name": "Portfolio Q1", "status": "optimal"},
                {"task_id": "sage-002", "problem_name": "Scheduling March", "status": "optimal"},
            ],
        }

        post_calls = []

        def mock_post(path, body):
            post_calls.append((path, body))
            return {"status": "ok"}

        with patch.object(_srv, "_cloud_get", return_value=notif_data), \
             patch.object(_srv, "_cloud_post", side_effect=mock_post):
            result = run(_srv._handle_check_notifications({}))

        text = result[0].text
        assert "2 job(s)" in text
        assert "sage-001" in text
        assert "Portfolio Q1" in text
        assert "sage-002" in text
        # Verify notifications were cleared
        assert any("/api/tools/write_blob" in call[0] for call in post_calls)


# ---------------------------------------------------------------------------
# Test 10: check_notifications empty
# ---------------------------------------------------------------------------


class TestCheckNotificationsEmpty:
    def test_no_pending_notifications(self):
        """check_notifications with no pending jobs."""
        _srv._state.cloud_url = "http://localhost:8765"

        with patch.object(_srv, "_cloud_get", return_value=None):
            result = run(_srv._handle_check_notifications({}))

        text = result[0].text
        assert "no pending" in text.lower()

    def test_empty_pending_list(self):
        """check_notifications with empty pending list."""
        _srv._state.cloud_url = "http://localhost:8765"

        with patch.object(_srv, "_cloud_get", return_value={"pending": []}):
            result = run(_srv._handle_check_notifications({}))

        text = result[0].text
        assert "no pending" in text.lower()


# ---------------------------------------------------------------------------
# Test 11: All original tools still work
# ---------------------------------------------------------------------------


class TestOriginalToolsStillWork:
    def test_solve_optimization_still_works(self):
        """solve_optimization with simple LP still returns correct result."""
        result = run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        text = result[0].text
        assert "[Sage MCP]" in text
        assert "26" in text  # objective value (3*6 + 2*4 = 26)

    def test_state_still_populated(self):
        """Server state is populated after solve for explain/suggest follow-ups."""
        run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        assert _srv._state.last_result is not None
        assert _srv._state.last_result.status == "optimal"
        assert _srv._state.last_model is not None
        assert _srv._state.last_solver_input is not None
        assert _srv._state.last_task_id is not None

    def test_explain_after_solve_still_works(self):
        """explain_solution after solve still works."""
        run(_srv._handle_solve_optimization(SIMPLE_LP_ARGS))
        result = run(_srv._handle_explain_solution({"detail_level": "brief"}))
        text = result[0].text
        assert len(text) > 0

    def test_infeasible_stores_iis(self):
        """Infeasible solve still stores IIS in state."""
        run(_srv._handle_solve_optimization(INFEASIBLE_LP_ARGS))
        assert _srv._state.last_iis is not None

    def test_suggest_relaxations_after_infeasible(self):
        """suggest_relaxations still works after infeasible solve."""
        run(_srv._handle_solve_optimization(INFEASIBLE_LP_ARGS))
        result = run(_srv._handle_suggest_relaxations({}))
        text = result[0].text
        assert "relaxation" in text.lower() or "constraint" in text.lower()


# ---------------------------------------------------------------------------
# Test 12: Tool count is 12
# ---------------------------------------------------------------------------


class TestToolCount:
    def test_tool_count_is_twelve(self):
        """list_tools() returns exactly 12 tools."""
        tools = run(_srv.list_tools())
        assert len(tools) == 12

    def test_new_tools_registered(self):
        """All 4 new tools are registered."""
        tools = run(_srv.list_tools())
        names = {t.name for t in tools}
        new_tools = {"pause_job", "resume_job", "get_job_progress", "check_notifications"}
        assert new_tools.issubset(names)

    def test_all_tools_in_handler_map(self):
        """Every registered tool has a handler."""
        tools = run(_srv.list_tools())
        for tool in tools:
            assert tool.name in _srv._TOOL_HANDLERS, f"Tool {tool.name!r} has no handler"
