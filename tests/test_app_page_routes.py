"""HTTP integration tests for multi-page app routes."""

import pytest


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------

def test_create_app_requires_auth(client):
    resp = client.post("/api/tools/create_app", json={"name": "myapp"})
    assert resp.status_code in (401, 403)


def test_create_app_returns_200_and_base_url(client, auth_headers):
    resp = client.post("/api/tools/create_app",
                       json={"name": "myapp", "description": "Test app"},
                       headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "myapp"
    assert body["base_url"].endswith("/apps/myapp/")


def test_create_app_duplicate_returns_400(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    resp = client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# create_app_page
# ---------------------------------------------------------------------------

def test_create_app_page_requires_auth(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    resp = client.post("/api/tools/create_app_page",
                       json={"app": "myapp", "page": "clock", "jsx_code": "<h1>Clock</h1>"})
    assert resp.status_code in (401, 403)


def test_create_app_page_returns_200_and_url(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    resp = client.post("/api/tools/create_app_page",
                       json={"app": "myapp", "page": "clock",
                             "jsx_code": "function Page(){return <h1>Clock</h1>;}"},
                       headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "myapp"
    assert body["page"] == "clock"
    assert body["url"].endswith("/apps/myapp/clock")


def test_create_app_page_index_url_is_app_root(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    resp = client.post("/api/tools/create_app_page",
                       json={"app": "myapp", "page": "index",
                             "jsx_code": "function Page(){return <h1>Home</h1>;}"},
                       headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["url"].endswith("/apps/myapp/")


def test_create_app_page_missing_app_returns_400(client, auth_headers):
    resp = client.post("/api/tools/create_app_page",
                       json={"app": "noapp", "page": "clock", "jsx_code": "<h1>x</h1>"},
                       headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# update_app_page
# ---------------------------------------------------------------------------

def test_update_app_page_returns_200(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    client.post("/api/tools/create_app_page",
                json={"app": "myapp", "page": "clock", "jsx_code": "<h1>v1</h1>"},
                headers=auth_headers)
    resp = client.post("/api/tools/update_app_page",
                       json={"app": "myapp", "page": "clock", "jsx_code": "<h1>v2</h1>"},
                       headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["page"] == "clock"


# ---------------------------------------------------------------------------
# list_app_pages
# ---------------------------------------------------------------------------

def test_list_app_pages_returns_list(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    client.post("/api/tools/create_app_page",
                json={"app": "myapp", "page": "clock", "jsx_code": "<h1>Clock</h1>"},
                headers=auth_headers)
    client.post("/api/tools/create_app_page",
                json={"app": "myapp", "page": "todos", "jsx_code": "<h1>Todos</h1>"},
                headers=auth_headers)
    resp = client.post("/api/tools/list_app_pages", json={"app": "myapp"}, headers=auth_headers)
    assert resp.status_code == 200
    pages = resp.json()
    assert len(pages) == 2
    names = {p["page"] for p in pages}
    assert names == {"clock", "todos"}


# ---------------------------------------------------------------------------
# Source delivery endpoints (no auth)
# ---------------------------------------------------------------------------

def test_app_page_source_no_auth_required(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    client.post("/api/tools/create_app_page",
                json={"app": "myapp", "page": "clock",
                      "jsx_code": "function Page(){return <h1>Clock</h1>;}"},
                headers=auth_headers)
    resp = client.get("/api/app-pages/myapp/clock/source")
    assert resp.status_code == 200
    assert "Clock" in resp.text


def test_app_page_source_missing_returns_404(client):
    resp = client.get("/api/app-pages/noapp/nopage/source")
    assert resp.status_code == 404


def test_app_layout_source_no_layout_returns_204(client, auth_headers):
    client.post("/api/tools/create_app", json={"name": "myapp"}, headers=auth_headers)
    resp = client.get("/api/app-pages/myapp/layout/source")
    assert resp.status_code == 204


def test_app_layout_source_returns_jsx(client, auth_headers):
    client.post("/api/tools/create_app",
                json={"name": "myapp",
                      "layout_jsx": "function Layout({children}){return <div>{children}</div>;}"},
                headers=auth_headers)
    resp = client.get("/api/app-pages/myapp/layout/source")
    assert resp.status_code == 200
    assert "Layout" in resp.text


def test_apps_path_serves_shell_html(client):
    resp = client.get("/apps/myapp/clock")
    assert resp.status_code == 200
    assert b"<div id=" in resp.content
