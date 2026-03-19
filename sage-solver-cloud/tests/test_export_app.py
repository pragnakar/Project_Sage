"""Tests for GET /api/apps/{name}/export endpoint (task 868hwpquk)."""

import io
import json
import zipfile

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
    app.dependency_overrides[get_settings] = lambda: example_settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _open_zip(response) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(response.content))


# ---------------------------------------------------------------------------
# 404 for unknown app
# ---------------------------------------------------------------------------

def test_export_missing_app_returns_404(client):
    resp = client.get("/api/apps/nonexistent/export")
    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Basic export
# ---------------------------------------------------------------------------

def test_export_returns_zip_content_type(example_client):
    resp = example_client.get("/api/apps/_example/export")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]


def test_export_returns_attachment_disposition(example_client):
    resp = example_client.get("/api/apps/_example/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert "_example.zip" in resp.headers["content-disposition"]


def test_export_zip_is_valid(example_client):
    resp = example_client.get("/api/apps/_example/export")
    assert resp.status_code == 200
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert len(names) > 0


def test_export_zip_contains_loader(example_client):
    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert "_example/loader.py" in names


def test_export_zip_contains_init(example_client):
    """ZIP contains __init__.py — valid Python package that can be re-imported."""
    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert "_example/__init__.py" in names


def test_export_zip_excludes_pycache(example_client):
    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert not any("__pycache__" in n for n in names)


def test_export_zip_contains_metadata(example_client):
    """New format: manifest.json at ZIP root with kind=module_app."""
    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["name"] == "_example"
    assert manifest["kind"] == "module_app"


# ---------------------------------------------------------------------------
# include_data=true — blobs bundled in blobs/ directory
# ---------------------------------------------------------------------------

def test_export_include_data_contains_no_pages_json(example_client):
    """New format does not produce _export_pages.json — pages live in module."""
    resp = example_client.get("/api/apps/_example/export?include_data=true")
    assert resp.status_code == 200
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert "_example/_export_pages.json" not in names


def test_export_include_data_manifest_present(example_client):
    """manifest.json is always present with correct kind."""
    resp = example_client.get("/api/apps/_example/export?include_data=true")
    with _open_zip(resp) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["kind"] == "module_app"


def test_export_no_include_data_omits_blobs_dir(example_client):
    """Without include_data, blobs/ directory should not appear."""
    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        names = zf.namelist()
    assert not any(n.startswith("blobs/") for n in names)


def test_export_include_data_with_blobs(example_client):
    """Blobs prefixed with the app name appear in blobs/ with include_data=true."""
    example_client.post(
        "/api/tools/write_blob",
        json={"key": "_example/test.txt", "data": "hello from blob"},
        headers=AUTH,
    )
    resp = example_client.get("/api/apps/_example/export?include_data=true")
    assert resp.status_code == 200
    with _open_zip(resp) as zf:
        names = zf.namelist()
        assert "blobs/_example/test.txt" in names
        assert zf.read("blobs/_example/test.txt").decode() == "hello from blob"
        manifest = json.loads(zf.read("manifest.json"))
    keys = [b["key"] for b in manifest["blobs"]]
    assert "_example/test.txt" in keys


# ---------------------------------------------------------------------------
# Roundtrip: exported ZIP contains re-importable source
# ---------------------------------------------------------------------------

def test_export_roundtrip_loader_source_matches(example_client):
    """Source of loader.py in ZIP matches the file on disk."""
    from pathlib import Path
    disk_path = Path("groot_apps/_example/loader.py")
    if not disk_path.exists():
        pytest.skip("_example loader not on disk")
    disk_source = disk_path.read_text()

    resp = example_client.get("/api/apps/_example/export")
    with _open_zip(resp) as zf:
        zip_source = zf.read("_example/loader.py").decode()

    assert zip_source == disk_source
