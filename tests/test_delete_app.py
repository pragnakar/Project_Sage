"""Tests for DELETE /api/apps/{name} endpoint (task 868hwpqxk)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from groot.config import Settings, get_settings
from groot.server import app

TEST_API_KEY = "groot_sk_test_key"
AUTH = {"X-Groot-Key": TEST_API_KEY}


@pytest.fixture
def example_settings(tmp_path):
    return Settings(
        GROOT_API_KEYS=TEST_API_KEY,
        GROOT_DB_PATH=str(tmp_path / "test.db"),
        GROOT_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        GROOT_APPS="_example",
        GROOT_ENV="development",
    )


@pytest.fixture
def example_client(example_settings):
    """Client with _example app loaded (status=loaded)."""
    app.dependency_overrides[get_settings] = lambda: example_settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_delete_requires_auth(example_client):
    resp = example_client.delete("/api/apps/_example?force=true")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 404 — app not found
# ---------------------------------------------------------------------------

def test_delete_missing_app_returns_404(example_client):
    resp = example_client.delete("/api/apps/nonexistent", headers=AUTH)
    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 409 — loaded app requires force
# ---------------------------------------------------------------------------

def test_delete_loaded_app_without_force_returns_409(example_client):
    resp = example_client.delete("/api/apps/_example", headers=AUTH)
    assert resp.status_code == 409
    assert "force=true" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Error-state app — can be deleted without force
# ---------------------------------------------------------------------------

def test_delete_error_app_without_force_succeeds(client, auth_headers):
    """An app in error state does not require force=true to delete."""
    # Inject a fake error-state app directly into the running lifespan state
    app.state.loaded_apps["broken_app"] = {"status": "error", "error": "import failed"}

    resp = client.delete("/api/apps/broken_app", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "broken_app"
    assert body["tools_removed"] == 0  # no tools were registered
    assert body["pages_removed"] == 0
    assert body["blobs_removed"] == 0
    assert body["schemas_removed"] == 0
    assert body["directory_removed"] is False


def test_delete_error_app_removes_from_list(client, auth_headers):
    app.state.loaded_apps["broken_app"] = {"status": "error", "error": "import failed"}

    client.delete("/api/apps/broken_app", headers=auth_headers)

    resp = client.get("/api/apps")
    names = [a["name"] for a in resp.json()["apps"]]
    assert "broken_app" not in names


# ---------------------------------------------------------------------------
# Successful delete with force=true
# ---------------------------------------------------------------------------

def test_delete_loaded_app_with_force_succeeds(example_client):
    with patch("groot.app_routes.shutil.rmtree") as mock_rm:
        resp = example_client.delete("/api/apps/_example?force=true", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "_example"
    assert body["tools_removed"] == 1   # echo_tool
    assert body["pages_removed"] == 1   # _example-hello
    assert body["directory_removed"] is True
    mock_rm.assert_called_once()


def test_delete_removes_app_from_list(example_client):
    with patch("groot.app_routes.shutil.rmtree"):
        example_client.delete("/api/apps/_example?force=true", headers=AUTH)

    resp = example_client.get("/api/apps")
    names = [a["name"] for a in resp.json()["apps"]]
    assert "_example" not in names


def test_delete_removes_app_pages(example_client):
    """After deleting _example, its pages are gone from /api/pages."""
    before = example_client.get("/api/pages")
    page_names_before = [p["name"] for p in before.json()]
    assert "_example-hello" in page_names_before

    with patch("groot.app_routes.shutil.rmtree"):
        example_client.delete("/api/apps/_example?force=true", headers=AUTH)

    after = example_client.get("/api/pages")
    page_names_after = [p["name"] for p in after.json()]
    assert "_example-hello" not in page_names_after


def test_delete_removes_app_tools(example_client):
    """After deleting _example with force, its tools are gone from the registry."""
    resp_before = example_client.post(
        "/api/tools/call",
        json={"tool": "echo_tool", "arguments": {"message": "ping"}},
        headers=AUTH,
    )
    assert resp_before.status_code == 200

    with patch("groot.app_routes.shutil.rmtree"):
        example_client.delete("/api/apps/_example?force=true", headers=AUTH)

    # echo_tool should now return 400 (tool not found)
    resp_after = example_client.post(
        "/api/tools/call",
        json={"tool": "echo_tool", "arguments": {"message": "ping"}},
        headers=AUTH,
    )
    assert resp_after.status_code == 400
    assert resp_after.json()["detail"]["error"] == "not_found"


# ---------------------------------------------------------------------------
# purge_data=true — blobs and schemas removed
# ---------------------------------------------------------------------------

def test_purge_data_removes_blobs(client, auth_headers):
    """purge_data=true deletes blobs prefixed with the app name."""
    # Register a fake loaded app
    app.state.loaded_apps["myapp"] = {"status": "error", "error": "intentional"}

    # Write blobs under the app prefix
    client.post("/api/tools/write_blob", json={"key": "myapp/data.txt", "data": "hello"}, headers=auth_headers)
    client.post("/api/tools/write_blob", json={"key": "myapp/other.txt", "data": "world"}, headers=auth_headers)
    client.post("/api/tools/write_blob", json={"key": "otherapp/keep.txt", "data": "keep"}, headers=auth_headers)

    resp = client.delete("/api/apps/myapp?purge_data=true", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["blobs_removed"] == 2

    # otherapp blob still exists
    blobs = client.post("/api/tools/list_blobs", json={}, headers=auth_headers).json()
    keys = [b["key"] for b in blobs]
    assert "otherapp/keep.txt" in keys
    assert "myapp/data.txt" not in keys
    assert "myapp/other.txt" not in keys


def test_purge_data_false_keeps_blobs(client, auth_headers):
    """Without purge_data, blobs are retained after app delete."""
    app.state.loaded_apps["keepapp"] = {"status": "error", "error": "intentional"}

    client.post("/api/tools/write_blob", json={"key": "keepapp/data.txt", "data": "hi"}, headers=auth_headers)

    client.delete("/api/apps/keepapp?purge_data=false", headers=auth_headers)

    blobs = client.post("/api/tools/list_blobs", json={}, headers=auth_headers).json()
    keys = [b["key"] for b in blobs]
    assert "keepapp/data.txt" in keys


def test_purge_data_removes_schemas(client, auth_headers):
    """purge_data=true deletes schemas prefixed with the app name."""
    app.state.loaded_apps["schemaapp"] = {"status": "error", "error": "intentional"}

    client.post("/api/tools/define_schema",
                json={"name": "schemaapp/MySchema", "definition": {"type": "object"}},
                headers=auth_headers)
    client.post("/api/tools/define_schema",
                json={"name": "schemaapp-OtherSchema", "definition": {"type": "string"}},
                headers=auth_headers)
    client.post("/api/tools/define_schema",
                json={"name": "keepschema/Safe", "definition": {"type": "null"}},
                headers=auth_headers)

    resp = client.delete("/api/apps/schemaapp?purge_data=true", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["schemas_removed"] == 2
