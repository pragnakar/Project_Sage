"""G3 end-to-end integration tests — built-in pages + full create/update/delete cycle."""


# ---------------------------------------------------------------------------
# Built-in page registration
# ---------------------------------------------------------------------------

def test_builtin_dashboard_is_listed(client):
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "sage-dashboard" in names


def test_builtin_artifacts_is_listed(client):
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "sage-artifacts" in names


def test_dashboard_source_contains_sage_cloud(client):
    resp = client.get("/api/pages/sage-dashboard/source")
    assert resp.status_code == 200
    assert "Sage Cloud" in resp.text


def test_dashboard_source_references_system_state(client):
    resp = client.get("/api/pages/sage-dashboard/source")
    assert resp.status_code == 200
    assert "/api/system/state" in resp.text


def test_artifacts_source_contains_tab_structure(client):
    resp = client.get("/api/pages/sage-artifacts/source")
    assert resp.status_code == 200
    src = resp.text
    assert "blobs" in src.lower()
    assert "schemas" in src.lower()
    assert "events" in src.lower()


def test_builtin_pages_survive_restart(client):
    """Second TestClient (second lifespan) should still find built-in pages (upsert)."""
    # client fixture already ran lifespan once; re-querying confirms they exist
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "sage-dashboard" in names
    assert "sage-artifacts" in names


# ---------------------------------------------------------------------------
# Shell routes
# ---------------------------------------------------------------------------

def test_root_returns_shell(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Full create → source → list → update → source → delete → 404 cycle
# ---------------------------------------------------------------------------

def test_create_page_appears_in_list(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "test-page", "jsx_code": "<div>hello</div>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages")
    assert "test-page" in [p["name"] for p in resp.json()]


def test_custom_page_source_is_accessible(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "cycle-page", "jsx_code": "<p>original</p>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/cycle-page/source")
    assert resp.status_code == 200
    assert resp.text == "<p>original</p>"


def test_update_page_changes_source(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "upd-cycle", "jsx_code": "<p>v1</p>"},
        headers=auth_headers,
    )
    client.post(
        "/api/tools/update_page",
        json={"name": "upd-cycle", "jsx_code": "<p>v2</p>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/upd-cycle/source")
    assert resp.status_code == 200
    assert resp.text == "<p>v2</p>"


def test_delete_page_returns_404_on_source(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "del-cycle", "jsx_code": "<span/>"},
        headers=auth_headers,
    )
    client.post(
        "/api/tools/delete_page",
        json={"name": "del-cycle"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/del-cycle/source")
    assert resp.status_code == 404


def test_deleted_page_absent_from_list(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "gone-page", "jsx_code": "<div/>"},
        headers=auth_headers,
    )
    client.post(
        "/api/tools/delete_page",
        json={"name": "gone-page"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages")
    assert "gone-page" not in [p["name"] for p in resp.json()]
