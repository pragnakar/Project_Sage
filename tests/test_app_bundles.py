"""Tests for app bundle export/import endpoints."""

import pytest


@pytest.fixture
def bundle_app(client, auth_headers):
    """Create a test app with two pages and return its name."""
    name = "testbundle"
    client.post("/api/tools/create_app", json={"name": name, "description": "Test bundle app"}, headers=auth_headers)
    client.post("/api/tools/create_app_page", json={"app": name, "page": "index", "jsx_code": "<div>Home</div>"}, headers=auth_headers)
    client.post("/api/tools/create_app_page", json={"app": name, "page": "about", "jsx_code": "<div>About</div>"}, headers=auth_headers)
    return name


def test_list_app_bundles_empty(client):
    resp = client.get("/api/app-bundles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_app_bundles(client, auth_headers, bundle_app):
    resp = client.get("/api/app-bundles")
    assert resp.status_code == 200
    apps = resp.json()
    assert any(a["name"] == bundle_app for a in apps)
    app = next(a for a in apps if a["name"] == bundle_app)
    assert app["page_count"] == 2
    assert app["description"] == "Test bundle app"


def test_export_app_bundle(client, auth_headers, bundle_app):
    resp = client.get(f"/api/app-bundles/{bundle_app}")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert f'filename="{bundle_app}-bundle.json"' in resp.headers["content-disposition"]
    data = resp.json()
    assert data["name"] == bundle_app
    assert data["description"] == "Test bundle app"
    assert len(data["pages"]) == 2
    pages = {p["page"]: p["jsx_code"] for p in data["pages"]}
    assert pages["index"] == "<div>Home</div>"
    assert pages["about"] == "<div>About</div>"


def test_export_app_bundle_not_found(client):
    resp = client.get("/api/app-bundles/nonexistent")
    assert resp.status_code == 404


def test_import_app_bundle_new(client, auth_headers):
    bundle = {
        "name": "imported",
        "description": "Imported app",
        "layout_jsx": "",
        "pages": [
            {"page": "index", "jsx_code": "<div>Imported home</div>", "description": ""},
            {"page": "docs", "jsx_code": "<div>Docs</div>", "description": "Documentation"},
        ],
    }
    resp = client.post("/api/app-bundles", json=bundle, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "imported"
    assert data["pages_imported"] == 2
    assert "/apps/imported/" in data["url"]


def test_import_app_bundle_requires_auth(client):
    bundle = {"name": "nope", "pages": []}
    resp = client.post("/api/app-bundles", json=bundle)
    assert resp.status_code in (401, 403)


def test_import_app_bundle_idempotent(client, auth_headers, bundle_app):
    """Re-importing an existing app updates its pages without error."""
    export = client.get(f"/api/app-bundles/{bundle_app}").json()
    # pages are alphabetical: about, index — update the index page explicitly
    for p in export["pages"]:
        if p["page"] == "index":
            p["jsx_code"] = "<div>Updated Home</div>"
    resp = client.post("/api/app-bundles", json=export, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["pages_imported"] == 2
    # Verify page was updated
    src = client.get(f"/api/app-pages/{bundle_app}/index/source").text
    assert src == "<div>Updated Home</div>"


def test_roundtrip_export_import(client, auth_headers, bundle_app):
    """Export then import to a new name produces identical pages."""
    export = client.get(f"/api/app-bundles/{bundle_app}").json()
    export["name"] = "roundtrip"
    resp = client.post("/api/app-bundles", json=export, headers=auth_headers)
    assert resp.status_code == 200

    new_export = client.get("/api/app-bundles/roundtrip").json()
    orig_pages = {p["page"]: p["jsx_code"] for p in export["pages"]}
    new_pages = {p["page"]: p["jsx_code"] for p in new_export["pages"]}
    assert orig_pages == new_pages
