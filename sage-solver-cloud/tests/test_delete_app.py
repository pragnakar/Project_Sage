"""Tests for DELETE /api/apps/{name} endpoint (task 868hwpqxk)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sage_cloud.config import Settings, get_settings
from sage_cloud.server import app

TEST_API_KEY = "sage_sk_test_key"
AUTH = {"X-Sage-Key": TEST_API_KEY}


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
