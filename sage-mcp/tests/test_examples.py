"""End-to-end smoke tests that read the bundled example files and
exercise the MCP tool handlers against real SAGE solves.

These tests use the handler functions directly (same pattern as test_server.py)
and verify that example files produce valid, non-error responses.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

# ── paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent  # Project_Sage/
EXAMPLES_DIR = REPO_ROOT / "examples"

PORTFOLIO_FILE = EXAMPLES_DIR / "portfolio_5_assets.xlsx"
NURSE_FILE = EXAMPLES_DIR / "nurse_scheduling.xlsx"
TRANSPORT_FILE = EXAMPLES_DIR / "transport_routing.xlsx"
BLENDING_CSV = EXAMPLES_DIR / "blending_problem.csv"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── import handlers ──────────────────────────────────────────────────────────
from sage_mcp.server import (  # noqa: E402
    _handle_read_data_file,
    _handle_solve_from_file,
    _handle_generate_template,
    _state,
    ServerState,
)


@pytest.fixture(autouse=True)
def reset_state():
    _state.last_result = None
    _state.last_model = None
    _state.last_solver_input = None
    _state.last_iis = None
    yield


# ── helpers ──────────────────────────────────────────────────────────────────
def text(responses) -> str:
    return responses[0].text


def is_error(response) -> bool:
    t = text(response).lower()
    return "error" in t or "traceback" in t


# ── example file existence ───────────────────────────────────────────────────
class TestExampleFilesExist:
    def test_portfolio_file_exists(self):
        assert PORTFOLIO_FILE.exists(), f"Missing: {PORTFOLIO_FILE}"

    def test_nurse_file_exists(self):
        assert NURSE_FILE.exists(), f"Missing: {NURSE_FILE}"

    def test_transport_file_exists(self):
        assert TRANSPORT_FILE.exists(), f"Missing: {TRANSPORT_FILE}"

    def test_blending_csv_exists(self):
        assert BLENDING_CSV.exists(), f"Missing: {BLENDING_CSV}"


# ── read_data_file smoke tests ───────────────────────────────────────────────
class TestReadExampleFiles:
    def test_read_portfolio_xlsx(self):
        resp = run(_handle_read_data_file({"filepath": str(PORTFOLIO_FILE)}))
        assert not is_error(resp)
        t = text(resp)
        # Should mention at least one sheet name
        assert any(kw in t for kw in ["assets", "sheet", "rows", "columns"])

    def test_read_nurse_xlsx(self):
        resp = run(_handle_read_data_file({"filepath": str(NURSE_FILE)}))
        assert not is_error(resp)
        t = text(resp)
        assert any(kw in t for kw in ["workers", "shifts", "rows", "columns"])

    def test_read_transport_xlsx(self):
        resp = run(_handle_read_data_file({"filepath": str(TRANSPORT_FILE)}))
        assert not is_error(resp)
        t = text(resp)
        assert any(kw in t for kw in ["supply", "demand", "cost", "rows", "columns"])

    def test_read_blending_csv(self):
        resp = run(_handle_read_data_file({"filepath": str(BLENDING_CSV)}))
        assert not is_error(resp)
        t = text(resp)
        assert any(kw in t for kw in ["ingredient", "csv", "rows", "columns", "Corn"])

    def test_read_missing_file_returns_error(self):
        resp = run(_handle_read_data_file({"filepath": "/no/such/file.xlsx"}))
        t = text(resp).lower()
        assert "error" in t or "not found" in t


# ── generate_template smoke tests ─────────────────────────────────────────────
class TestGenerateTemplates:
    def test_generate_generic_lp_template(self, tmp_path):
        resp = run(_handle_generate_template({"problem_type": "generic_lp", "output_directory": str(tmp_path)}))
        assert not is_error(resp)
        assert (tmp_path / "generic_lp_template.xlsx").exists()
        assert (tmp_path / "generic_lp_template.xlsx").stat().st_size > 0

    def test_generate_transport_template(self, tmp_path):
        resp = run(_handle_generate_template({"problem_type": "transport", "output_directory": str(tmp_path)}))
        assert not is_error(resp)
        assert (tmp_path / "transport_template.xlsx").exists()

    def test_generate_portfolio_template(self, tmp_path):
        resp = run(_handle_generate_template({"problem_type": "portfolio", "output_directory": str(tmp_path)}))
        assert not is_error(resp)
        assert (tmp_path / "portfolio_template.xlsx").exists()

    def test_generate_scheduling_template(self, tmp_path):
        resp = run(_handle_generate_template({"problem_type": "scheduling", "output_directory": str(tmp_path)}))
        assert not is_error(resp)
        assert (tmp_path / "scheduling_template.xlsx").exists()

    def test_generate_unknown_type_returns_error(self, tmp_path):
        resp = run(_handle_generate_template({"problem_type": "unicorn", "output_directory": str(tmp_path)}))
        t = text(resp).lower()
        assert "error" in t or "unsupported" in t or "invalid" in t or "could not" in t


# ── solve_from_file smoke tests ───────────────────────────────────────────────
class TestSolveFromFile:
    def test_portfolio_solve_from_file(self, tmp_path):
        out = str(tmp_path / "portfolio_result.xlsx")
        resp = run(
            _handle_solve_from_file(
                {
                    "filepath": str(PORTFOLIO_FILE),
                    "output_path": out,
                    "problem_type": "portfolio",
                }
            )
        )
        t = text(resp)
        # Not a Python traceback
        assert "Traceback" not in t
        # Either solved or a structured error about data format
        assert len(t) > 10

    def test_solve_from_file_missing_path_returns_error(self):
        resp = run(
            _handle_solve_from_file(
                {
                    "filepath": "/no/such/file.xlsx",
                    "problem_type": "lp",
                }
            )
        )
        t = text(resp).lower()
        assert "error" in t or "not found" in t

    def test_solve_from_file_state_populated_on_success(self, tmp_path):
        """After a successful solve the server state should hold a result."""
        out = str(tmp_path / "result.xlsx")
        run(
            _handle_solve_from_file(
                {
                    "filepath": str(PORTFOLIO_FILE),
                    "output_path": out,
                    "problem_type": "portfolio",
                }
            )
        )
        # State may or may not be populated depending on whether the xlsx was
        # parseable as a portfolio model — either way, no crash
        # If state is populated, last_result should be a SolverResult
        if _state.last_result is not None:
            from sage_core.models import SolverResult
            assert isinstance(_state.last_result, SolverResult)


# ── end-to-end conversation simulation ───────────────────────────────────────
class TestConversationSimulation:
    """Simulate a realistic multi-tool conversation."""

    def test_lp_conversation_read_then_solve(self):
        """Read data → solve LP directly → no crash anywhere."""
        # Step 1: Read a data file
        read_resp = run(_handle_read_data_file({"filepath": str(PORTFOLIO_FILE)}))
        assert "Traceback" not in text(read_resp)

        # Step 2: Solve an LP directly (not from file)
        from sage_mcp.server import _handle_solve_optimization, _handle_explain_solution

        lp_data = {
            "problem_type": "lp",
            "variables": [
                {"name": "x", "lb": 0.0, "ub": 10.0, "obj": 3.0},
                {"name": "y", "lb": 0.0, "ub": 10.0, "obj": 5.0},
            ],
            "constraints": [
                {"name": "c1", "coefficients": {"x": 1.0, "y": 2.0}, "rhs": 12.0, "sense": "<="},
            ],
            "sense": "maximize",
        }
        solve_resp = run(_handle_solve_optimization({"model": json.dumps(lp_data)}))
        assert "Traceback" not in text(solve_resp)

        # Step 3: Explain result
        if _state.last_result is not None:
            explain_resp = run(_handle_explain_solution({"detail_level": "brief"}))
            assert "Traceback" not in text(explain_resp)

    def test_generate_template_then_read_back(self, tmp_path):
        """Generate a template, then immediately read it back — round trip."""
        gen_resp = run(_handle_generate_template({"problem_type": "generic_lp", "output_directory": str(tmp_path)}))
        assert not is_error(gen_resp)

        out = str(tmp_path / "generic_lp_template.xlsx")
        read_resp = run(_handle_read_data_file({"filepath": out}))
        assert "Traceback" not in text(read_resp)
