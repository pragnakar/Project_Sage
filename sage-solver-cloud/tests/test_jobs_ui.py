"""Tests for the Sage Jobs UI page (Stage 13)."""

import json

import pytest


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

TEST_SOLVER_INPUT = {
    "num_variables": 2,
    "num_constraints": 1,
    "variable_names": ["x", "y"],
    "variable_lower_bounds": [0.0, 0.0],
    "variable_upper_bounds": [10.0, 10.0],
    "variable_types": ["continuous", "continuous"],
    "constraint_names": ["c1"],
    "constraint_matrix": [[1.0, 1.0]],
    "constraint_senses": ["<="],
    "constraint_rhs": [10.0],
    "objective_coefficients": [3.0, 2.0],
    "objective_sense": "maximize",
}


def _submit_job(client, auth_headers, **overrides):
    """Helper to submit a job and return the response."""
    body = {
        "solver_input": TEST_SOLVER_INPUT,
        "problem_name": "test-problem",
    }
    body.update(overrides)
    return client.post("/api/jobs", json=body, headers=auth_headers)


# ---------------------------------------------------------------------------
# 1. Page source returns valid JSX with function Page
# ---------------------------------------------------------------------------

def test_page_source_returns_valid_jsx(client, auth_headers):
    """GET /api/pages/sage-jobs/source returns 200 and contains function Page."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "function Page" in text


# ---------------------------------------------------------------------------
# 2. Page renders at /apps/sage-jobs
# ---------------------------------------------------------------------------

def test_page_renders_at_apps_route(client, auth_headers):
    """GET /apps/sage-jobs returns 200."""
    resp = client.get("/apps/sage-jobs")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 3. Jobs API integration — create job, verify list returns it
# ---------------------------------------------------------------------------

def test_create_and_list_job(client, auth_headers):
    """Submit a job via POST /api/jobs, then verify GET /api/jobs includes it."""
    r = _submit_job(client, auth_headers, problem_name="ui-test-job")
    assert r.status_code == 201
    task_id = r.json()["task_id"]

    resp = client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    jobs = resp.json()
    task_ids = [j["task_id"] for j in jobs]
    assert task_id in task_ids


# ---------------------------------------------------------------------------
# 4. Page source contains key UI elements
# ---------------------------------------------------------------------------

def test_page_contains_filter_buttons(client, auth_headers):
    """Page JSX source contains status and type filter text."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    # Status filters
    assert "Running" in text or "running" in text
    assert "Paused" in text or "paused" in text
    assert "Complete" in text or "complete" in text
    assert "Failed" in text or "failed" in text
    # Type filters
    assert "LP" in text
    assert "MIP" in text
    assert "Portfolio" in text
    assert "Scheduling" in text


def test_page_contains_empty_state(client, auth_headers):
    """Page JSX source contains the empty state message."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "No optimization jobs yet" in text


def test_page_contains_status_colors(client, auth_headers):
    """Page JSX source contains the defined status color codes."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    # Key color values from the spec
    assert "#3b82f6" in text  # blue accent
    assert "#34d399" in text  # green
    assert "#fbbf24" in text  # yellow
    assert "#f87171" in text  # red
    assert "#0d1117" in text  # dark bg
    assert "#161b22" in text  # surface


def test_page_contains_api_endpoints(client, auth_headers):
    """Page JSX source references the Jobs API endpoints."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "/api/jobs" in text
    assert "/progress" in text
    assert "/pause" in text
    assert "/resume" in text


def test_page_contains_hint_bar(client, auth_headers):
    """Page JSX source contains the bottom hint bar text."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "check task" in text


def test_page_contains_chart_js_loading(client, auth_headers):
    """Page JSX source contains Chart.js CDN loading logic."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "chart.umd.min.js" in text or "Chart.js" in text or "window.Chart" in text


def test_page_contains_delete_confirm(client, auth_headers):
    """Page JSX source has delete confirmation dialog."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "Delete job" in text or "confirmDelete" in text


def test_page_contains_webhook_section(client, auth_headers):
    """Page JSX source has webhook configuration."""
    resp = client.get("/api/pages/sage-jobs/source")
    assert resp.status_code == 200
    text = resp.text
    assert "Webhook" in text or "webhook" in text
