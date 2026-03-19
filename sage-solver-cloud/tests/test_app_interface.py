"""Tests for app discovery API (G-APP)."""

import pytest
from fastapi.testclient import TestClient

from sage_cloud.config import Settings, get_settings
from sage_cloud.server import app

TEST_API_KEY = "sage_sk_test_key"


# ---------------------------------------------------------------------------
# GET /api/apps — no apps loaded (default test fixture has SAGE_CLOUD_APPS="")
# ---------------------------------------------------------------------------

def test_list_apps_no_apps(client):
    resp = client.get("/api/apps")
    assert resp.status_code == 200
    body = resp.json()
    assert "apps" in body
    assert "core" in body
    assert body["apps"] == []
    assert body["core"]["tools_count"] == 20
    assert body["core"]["version"] == "0.3.0"


def test_list_apps_core_page_count(client):
    resp = client.get("/api/apps")
    assert resp.status_code == 200
    # Built-in pages: sage-dashboard + sage-artifacts
    assert resp.json()["core"]["pages_count"] == 2


# ---------------------------------------------------------------------------
# GET /api/apps/{name}
# ---------------------------------------------------------------------------

def test_get_app_detail_404_for_missing(client):
    resp = client.get("/api/apps/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/apps/{name}/health
# ---------------------------------------------------------------------------

def test_app_health_404_for_missing(client):
    resp = client.get("/api/apps/nonexistent/health")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Graceful degradation — broken loader
# ---------------------------------------------------------------------------

def test_broken_app_recorded_as_error(tmp_path):
    broken_settings = Settings(
        SAGE_CLOUD_API_KEYS=TEST_API_KEY,
        SAGE_CLOUD_DB_PATH=str(tmp_path / "test.db"),
        SAGE_CLOUD_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        SAGE_CLOUD_APPS="nonexistent_app_xyz",
        SAGE_CLOUD_ENV="development",
    )
    app.dependency_overrides[get_settings] = lambda: broken_settings
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/apps")
        assert resp.status_code == 200
        # App that failed to load (ModuleNotFoundError) is simply absent from the list
        names = [a["name"] for a in resp.json()["apps"]]
        assert "nonexistent_app_xyz" not in names
    finally:
        app.dependency_overrides.clear()
