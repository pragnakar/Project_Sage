"""Integration tests for sage_cloud/server.py — HTTP routes, auth, and end-to-end flows."""

import pytest


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["version"] == "0.3.0"


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

def test_write_blob_requires_auth(client):
    resp = client.post("/api/tools/write_blob", json={"key": "ns/x", "data": "hello"})
    assert resp.status_code == 401


def test_read_blob_requires_auth(client):
    resp = client.post("/api/tools/read_blob", json={"key": "ns/x"})
    assert resp.status_code == 401


def test_list_blobs_requires_auth(client):
    resp = client.post("/api/tools/list_blobs", json={})
    assert resp.status_code == 401


def test_system_state_requires_auth(client):
    resp = client.get("/api/system/state")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Critical end-to-end flow (G1 acceptance test)
# ---------------------------------------------------------------------------

def test_e2e_write_read_list_state(client, auth_headers):
    # 1. Write blob
    resp = client.post(
        "/api/tools/write_blob",
        json={"key": "test/hello", "data": "Hello, Sage Cloud!", "content_type": "text/plain"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "test/hello"
    assert body["url"] == "/blobs/test/hello"

    # 2. Read blob back
    resp = client.post("/api/tools/read_blob", json={"key": "test/hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == "Hello, Sage Cloud!"

    # 3. List blobs with prefix
    resp = client.post("/api/tools/list_blobs", json={"prefix": "test/"}, headers=auth_headers)
    assert resp.status_code == 200
    keys = [b["key"] for b in resp.json()]
    assert "test/hello" in keys

    # 4. System state reflects the write
    resp = client.get("/api/system/state", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["blob_count"] >= 1


# ---------------------------------------------------------------------------
# Blob routes
# ---------------------------------------------------------------------------

def test_delete_blob(client, auth_headers):
    client.post("/api/tools/write_blob", json={"key": "ns/del", "data": "bye"}, headers=auth_headers)
    resp = client.post("/api/tools/delete_blob", json={"key": "ns/del"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_read_nonexistent_blob_returns_400(client, auth_headers):
    resp = client.post("/api/tools/read_blob", json={"key": "ns/missing"}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "not_found"


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

def test_create_and_list_pages(client, auth_headers):
    resp = client.post(
        "/api/tools/create_page",
        json={"name": "dashboard", "jsx_code": "<div>hello</div>", "description": "main"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["url"].endswith("/apps/dashboard")

    resp = client.post("/api/tools/list_pages", headers=auth_headers)
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "dashboard" in names


def test_update_page(client, auth_headers):
    client.post("/api/tools/create_page", json={"name": "ui", "jsx_code": "<div>old</div>"}, headers=auth_headers)
    resp = client.post("/api/tools/update_page", json={"name": "ui", "jsx_code": "<div>new</div>"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "ui"


def test_upsert_page_create(client, auth_headers):
    resp = client.post("/api/tools/upsert_page", json={"name": "ups", "jsx_code": "<div>v1</div>"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "ups"


def test_upsert_page_update(client, auth_headers):
    client.post("/api/tools/upsert_page", json={"name": "ups2", "jsx_code": "<div>v1</div>"}, headers=auth_headers)
    resp = client.post("/api/tools/upsert_page", json={"name": "ups2", "jsx_code": "<div>v2</div>"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "ups2"


def test_list_web_apps(client, auth_headers):
    client.post("/api/tools/create_page", json={"name": "mypage", "jsx_code": "<div/>"}, headers=auth_headers)
    resp = client.get("/api/web-apps")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    names = [a["name"] for a in items]
    assert "mypage" in names
    page_item = next(a for a in items if a["name"] == "mypage")
    assert page_item["kind"] == "page"
    assert "url" in page_item


def test_web_apps_includes_bundles(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "webapp", "description": "Test"}, headers=auth_headers)
    resp = client.get("/api/web-apps")
    assert resp.status_code == 200
    items = resp.json()
    bundle = next((a for a in items if a["name"] == "webapp"), None)
    assert bundle is not None
    assert bundle["kind"] == "multi_page_bundle"


def test_delete_page(client, auth_headers):
    client.post("/api/tools/create_page", json={"name": "gone", "jsx_code": "<div/>"}, headers=auth_headers)
    resp = client.post("/api/tools/delete_page", json={"name": "gone"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_create_duplicate_page_returns_400(client, auth_headers):
    client.post("/api/tools/create_page", json={"name": "dup", "jsx_code": "<div/>"}, headers=auth_headers)
    resp = client.post("/api/tools/create_page", json={"name": "dup", "jsx_code": "<span/>"}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "validation_error"


# ---------------------------------------------------------------------------
# Schema routes
# ---------------------------------------------------------------------------

def test_define_and_get_schema(client, auth_headers):
    schema = {"type": "object", "properties": {"x": {"type": "number"}}}
    resp = client.post("/api/tools/define_schema", json={"name": "solve_input", "definition": schema}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "solve_input"

    resp = client.post("/api/tools/get_schema", json={"name": "solve_input"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["definition"] == schema


def test_list_schemas(client, auth_headers):
    client.post("/api/tools/define_schema", json={"name": "s1", "definition": {"type": "string"}}, headers=auth_headers)
    resp = client.post("/api/tools/list_schemas", headers=auth_headers)
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "s1" in names


# ---------------------------------------------------------------------------
# System routes
# ---------------------------------------------------------------------------

def test_log_event(client, auth_headers):
    resp = client.post("/api/tools/log_event", json={"message": "server test", "level": "info"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "server test"


def test_system_artifacts(client, auth_headers):
    client.post("/api/tools/write_blob", json={"key": "art/x", "data": "data"}, headers=auth_headers)
    resp = client.get("/api/system/artifacts", headers=auth_headers)
    assert resp.status_code == 200
    keys = [b["key"] for b in resp.json()["blobs"]]
    assert "art/x" in keys


# ---------------------------------------------------------------------------
# Generic tool call endpoint
# ---------------------------------------------------------------------------

def test_generic_call_write_blob(client, auth_headers):
    resp = client.post(
        "/api/tools/call",
        json={"tool": "write_blob", "arguments": {"key": "generic/test", "data": "via call"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "generic/test"


def test_generic_call_invalid_tool_returns_400(client, auth_headers):
    resp = client.post(
        "/api/tools/call",
        json={"tool": "nonexistent_tool", "arguments": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "not_found"


# ---------------------------------------------------------------------------
# Server starts with no app modules
# ---------------------------------------------------------------------------

def test_server_starts_with_no_apps(client, auth_headers):
    # client fixture already uses SAGE_CLOUD_APPS="" — server should be up
    resp = client.get("/health")
    assert resp.status_code == 200
