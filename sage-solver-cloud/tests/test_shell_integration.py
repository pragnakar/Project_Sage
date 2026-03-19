"""Tests for React shell static file serving (G3-2)."""


# ---------------------------------------------------------------------------
# SPA route tests
# ---------------------------------------------------------------------------

def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_root_contains_react_shell(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sage Cloud" in resp.content
    assert b"react" in resp.content.lower()


def test_artifacts_route_returns_shell(client):
    resp = client.get("/artifacts")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_apps_route_returns_shell(client):
    resp = client.get("/apps/my-page")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_apps_nested_route_returns_shell(client):
    resp = client.get("/apps/some-deeply/nested")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_api_routes_not_shadowed_by_shell(client):
    """API endpoints must remain accessible and not return HTML."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_pages_not_shadowed(client):
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


def test_shell_html_contains_babel_cdn(client):
    """Shell must include Babel standalone for client-side JSX transform."""
    resp = client.get("/")
    assert b"babel" in resp.content.lower()
