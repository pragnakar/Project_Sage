"""Tests for sage_cloud/page_server.py — PageServer routes and static registration."""

import os
import tempfile
from pathlib import Path

import pytest

from sage_cloud.artifact_store import ArtifactStore
from sage_cloud.page_server import PageServer, _validate_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def ps():
    """Standalone PageServer backed by a temp ArtifactStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(db_path=os.path.join(tmpdir, "t.db"), artifact_dir=tmpdir)
        await store.init_db()
        yield PageServer(store)


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

def test_valid_names_pass():
    for name in ("dashboard", "my-page", "sage-result", "Page1", "a", "_example", "under_score"):
        _validate_name(name)  # must not raise


def test_invalid_names_raise():
    for name in ("-bad", "has space", "", "dot.name"):
        with pytest.raises(ValueError):
            _validate_name(name)


# ---------------------------------------------------------------------------
# GET /api/pages — list
# ---------------------------------------------------------------------------

def test_list_pages_returns_builtin_pages(client, auth_headers):
    # Built-in pages (sage-dashboard, sage-artifacts) are registered at startup
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "sage-dashboard" in names
    assert "sage-artifacts" in names


def test_list_pages_after_create(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "my-page", "jsx_code": "<div/>", "description": "test"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "my-page" in names


def test_list_pages_multiple(client, auth_headers):
    for name in ("alpha", "beta", "gamma"):
        client.post(
            "/api/tools/create_page",
            json={"name": name, "jsx_code": f"<div>{name}</div>"},
            headers=auth_headers,
        )
    resp = client.get("/api/pages")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "alpha" in names
    assert "beta" in names
    assert "gamma" in names


# ---------------------------------------------------------------------------
# GET /api/pages/{name}/source
# ---------------------------------------------------------------------------

def test_page_source_returns_jsx(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "src-test", "jsx_code": "<h1>Hello Sage Cloud</h1>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/src-test/source")
    assert resp.status_code == 200
    assert resp.text == "<h1>Hello Sage Cloud</h1>"


def test_page_source_content_type_is_text_plain(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "ct-test", "jsx_code": "<span/>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/ct-test/source")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


def test_page_source_404_for_missing(client):
    resp = client.get("/api/pages/nonexistent/source")
    assert resp.status_code == 404


def test_page_source_after_update(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "upd-test", "jsx_code": "<div>old</div>"},
        headers=auth_headers,
    )
    client.post(
        "/api/tools/update_page",
        json={"name": "upd-test", "jsx_code": "<div>new</div>"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/upd-test/source")
    assert resp.status_code == 200
    assert resp.text == "<div>new</div>"


# ---------------------------------------------------------------------------
# GET /api/pages/{name}/meta
# ---------------------------------------------------------------------------

def test_page_meta_returns_metadata(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "meta-test", "jsx_code": "<div/>", "description": "my desc"},
        headers=auth_headers,
    )
    resp = client.get("/api/pages/meta-test/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "meta-test"
    assert body["description"] == "my desc"
    assert "created_at" in body
    assert "updated_at" in body


def test_page_meta_404_for_missing(client):
    resp = client.get("/api/pages/ghost/meta")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# register_static
# ---------------------------------------------------------------------------

async def test_register_static_stores_jsx(ps):
    with tempfile.NamedTemporaryFile(suffix=".jsx", mode="w", delete=False) as f:
        f.write("<div>Static Page</div>")
        jsx_path = f.name
    try:
        await ps.register_static("home", jsx_path)
        source = await ps.store.get_page_source("home")
        assert source == "<div>Static Page</div>"
    finally:
        os.unlink(jsx_path)


async def test_register_static_with_app_prefix(ps):
    with tempfile.NamedTemporaryFile(suffix=".jsx", mode="w", delete=False) as f:
        f.write("<div>Sage Dashboard</div>")
        jsx_path = f.name
    try:
        await ps.register_static("dashboard", jsx_path, app_name="sage")
        source = await ps.store.get_page_source("sage-dashboard")
        assert source == "<div>Sage Dashboard</div>"
    finally:
        os.unlink(jsx_path)


async def test_register_static_upserts_on_repeat(ps):
    """Calling register_static twice for the same page updates rather than errors."""
    with tempfile.NamedTemporaryFile(suffix=".jsx", mode="w", delete=False) as f:
        f.write("<div>v1</div>")
        jsx_path = f.name
    try:
        await ps.register_static("repeated", jsx_path)
        # Overwrite file and re-register
        Path(jsx_path).write_text("<div>v2</div>")
        await ps.register_static("repeated", jsx_path)
        source = await ps.store.get_page_source("repeated")
        assert source == "<div>v2</div>"
    finally:
        os.unlink(jsx_path)


# ---------------------------------------------------------------------------
# No auth required for page server GET routes
# ---------------------------------------------------------------------------

def test_page_export_import_roundtrip(client, auth_headers):
    """Export a page as ZIP, delete it, re-import via /api/apps/import — page restored."""
    import io as _io
    client.post("/api/tools/create_page", json={"name": "roundtrip", "jsx_code": "<div>hello</div>", "description": "A test page"}, headers=auth_headers)

    zip_bytes = client.get("/api/pages/roundtrip/export").content
    client.post("/api/tools/delete_page", json={"name": "roundtrip"}, headers=auth_headers)
    assert client.get("/api/pages/roundtrip/source").status_code == 404

    resp = client.post(
        "/api/apps/import",
        files={"file": ("roundtrip.zip", _io.BytesIO(zip_bytes), "application/zip")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "roundtrip"
    assert data["pages_registered"] == 1
    assert client.get("/api/pages/roundtrip/source").text == "<div>hello</div>"


def test_page_routes_require_no_auth(client, auth_headers):
    client.post(
        "/api/tools/create_page",
        json={"name": "public-page", "jsx_code": "<p>public</p>"},
        headers=auth_headers,
    )
    # No auth header — should still succeed
    assert client.get("/api/pages").status_code == 200
    assert client.get("/api/pages/public-page/source").status_code == 200
    assert client.get("/api/pages/public-page/meta").status_code == 200


# ---------------------------------------------------------------------------
# Page store — GET/PUT /api/pages/{name}/store
# ---------------------------------------------------------------------------

def test_page_store_get_empty(client, auth_headers):
    """GET store for a page with no saved data returns empty object."""
    client.post("/api/tools/create_page", json={"name": "mystore", "jsx_code": "<div/>"}, headers=auth_headers)
    resp = client.get("/api/pages/mystore/store")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_page_store_put_and_get(client, auth_headers):
    """PUT saves JSON, GET retrieves it round-trip."""
    client.post("/api/tools/create_page", json={"name": "storetest", "jsx_code": "<div/>"}, headers=auth_headers)
    payload = {"count": 42, "items": ["a", "b"]}
    resp = client.put("/api/pages/storetest/store", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    resp2 = client.get("/api/pages/storetest/store")
    assert resp2.status_code == 200
    assert resp2.json() == payload


def test_page_store_put_no_auth_required(client, auth_headers):
    """PUT /store requires no API key — pages can write without /api/config."""
    client.post("/api/tools/create_page", json={"name": "noauth", "jsx_code": "<div/>"}, headers=auth_headers)
    # No auth header
    resp = client.put("/api/pages/noauth/store", json={"x": 1})
    assert resp.status_code == 200


def test_page_store_put_invalid_json(client, auth_headers):
    client.post("/api/tools/create_page", json={"name": "badjson", "jsx_code": "<div/>"}, headers=auth_headers)
    resp = client.put("/api/pages/badjson/store", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_page_store_scope_isolation(client, auth_headers):
    """Two pages have independent stores."""
    client.post("/api/tools/create_page", json={"name": "page-a", "jsx_code": "<div/>"}, headers=auth_headers)
    client.post("/api/tools/create_page", json={"name": "page-b", "jsx_code": "<div/>"}, headers=auth_headers)
    client.put("/api/pages/page-a/store", json={"owner": "a"})
    client.put("/api/pages/page-b/store", json={"owner": "b"})
    assert client.get("/api/pages/page-a/store").json() == {"owner": "a"}
    assert client.get("/api/pages/page-b/store").json() == {"owner": "b"}


# ---------------------------------------------------------------------------
# Public blob read — GET /blobs/{key:path}
# ---------------------------------------------------------------------------

def test_public_blob_read(client, auth_headers):
    """write_blob URL resolves and returns the raw content."""
    write_resp = client.post(
        "/api/tools/write_blob",
        json={"key": "ns/myblob", "data": '{"hello":"world"}', "content_type": "application/json"},
        headers=auth_headers,
    )
    assert write_resp.status_code == 200
    url = write_resp.json()["url"]          # e.g. /blobs/ns/myblob

    read_resp = client.get(url)             # no auth header
    assert read_resp.status_code == 200
    assert read_resp.json() == {"hello": "world"}


def test_public_blob_read_not_found(client):
    assert client.get("/blobs/missing/key").status_code == 404


# ---------------------------------------------------------------------------
# Dual export — new manifest format
# ---------------------------------------------------------------------------

def test_page_export_contains_manifest(client, auth_headers):
    """New export format: ZIP contains manifest.json + pages/{name}.jsx."""
    import io as _io
    import zipfile as _zf
    import json as _json

    client.post("/api/tools/create_page", json={"name": "mftest", "jsx_code": "<div>mf</div>", "description": "mf desc"}, headers=auth_headers)
    resp = client.get("/api/pages/mftest/export")
    assert resp.status_code == 200

    with _zf.ZipFile(_io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "pages/mftest.jsx" in names
        manifest = _json.loads(zf.read("manifest.json"))
        assert manifest["kind"] == "page"
        assert manifest["name"] == "mftest"
        assert manifest["description"] == "mf desc"
        assert manifest["pages"][0]["name"] == "mftest"
        assert manifest["blobs"] == []
        assert zf.read("pages/mftest.jsx").decode() == "<div>mf</div>"


def test_page_export_with_data_includes_blobs(client, auth_headers):
    """?include_data=true adds matching blobs to blobs/ directory."""
    import io as _io
    import zipfile as _zf
    import json as _json

    client.post("/api/tools/create_page", json={"name": "blobpage", "jsx_code": "<div/>"}, headers=auth_headers)
    client.post("/api/tools/write_blob", json={"key": "blobpage/mydata", "data": '{"x":1}', "content_type": "application/json"}, headers=auth_headers)

    resp = client.get("/api/pages/blobpage/export?include_data=true")
    assert resp.status_code == 200

    with _zf.ZipFile(_io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "blobs/blobpage/mydata" in names
        manifest = _json.loads(zf.read("manifest.json"))
        assert len(manifest["blobs"]) == 1
        assert manifest["blobs"][0]["key"] == "blobpage/mydata"
        assert zf.read("blobs/blobpage/mydata").decode() == '{"x":1}'


def test_page_export_with_data_roundtrip(client, auth_headers):
    """Export page + data, delete, re-import — page and blobs both restored."""
    import io as _io

    client.post("/api/tools/create_page", json={"name": "datapage", "jsx_code": "<div>data</div>"}, headers=auth_headers)
    client.post("/api/tools/write_blob", json={"key": "datapage/state", "data": '{"saved":true}', "content_type": "application/json"}, headers=auth_headers)

    zip_bytes = client.get("/api/pages/datapage/export?include_data=true").content
    client.post("/api/tools/delete_page", json={"name": "datapage"}, headers=auth_headers)
    client.post("/api/tools/write_blob", json={"key": "datapage/state", "data": '{"saved":false}', "content_type": "application/json"}, headers=auth_headers)  # overwrite blob

    resp = client.post(
        "/api/apps/import",
        files={"file": ("datapage.zip", _io.BytesIO(zip_bytes), "application/zip")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["pages_registered"] == 1
    assert client.get("/api/pages/datapage/source").text == "<div>data</div>"
    # Blob should be restored from the export
    assert client.get("/blobs/datapage/state").json() == {"saved": True}
