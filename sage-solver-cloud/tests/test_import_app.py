"""Tests for POST /api/apps/import endpoint (task 868hwpqf3)."""

import io
import zipfile
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from groot.config import Settings, get_settings
from groot.server import app

TEST_API_KEY = "groot_sk_test_key"
AUTH = {"X-Groot-Key": TEST_API_KEY}

# ---------------------------------------------------------------------------
# Helpers — build ZIP bytes in memory
# ---------------------------------------------------------------------------

def _make_zip(files: dict[str, str]) -> bytes:
    """Build a ZIP from a {arcname: content} dict and return bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _minimal_app_zip(app_name: str, extra: dict[str, str] | None = None) -> bytes:
    """Create a minimal valid app ZIP with __init__.py and a no-op loader."""
    files = {
        f"{app_name}/__init__.py": "",
        f"{app_name}/loader.py": (
            "APP_META = {'description': 'test import app'}\n\n"
            "async def register(tool_registry, page_server, store):\n"
            "    pass\n"
        ),
    }
    if extra:
        files.update(extra)
    return _make_zip(files)


@pytest.fixture
def client_no_apps(tmp_path):
    settings = Settings(
        GROOT_API_KEYS=TEST_API_KEY,
        GROOT_DB_PATH=str(tmp_path / "test.db"),
        GROOT_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        GROOT_APPS="",
        GROOT_ENV="development",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _upload(client, zip_bytes: bytes, filename: str = "app.zip"):
    return client.post(
        "/api/apps/import",
        files={"file": (filename, io.BytesIO(zip_bytes), "application/zip")},
        headers=AUTH,
    )


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_import_requires_auth(client_no_apps):
    zip_bytes = _minimal_app_zip("testapp")
    resp = client_no_apps.post(
        "/api/apps/import",
        files={"file": ("app.zip", io.BytesIO(zip_bytes), "application/zip")},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation — malformed uploads
# ---------------------------------------------------------------------------

def test_import_rejects_non_zip(client_no_apps):
    resp = client_no_apps.post(
        "/api/apps/import",
        files={"file": ("bad.txt", io.BytesIO(b"not a zip"), "text/plain")},
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "not a valid ZIP" in resp.json()["detail"]


def test_import_rejects_missing_init(client_no_apps):
    zip_bytes = _make_zip({"myapp/loader.py": "async def register(*a): pass\n"})
    resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 400
    assert "__init__.py" in resp.json()["detail"]


def test_import_rejects_bare_files(client_no_apps):
    zip_bytes = _make_zip({
        "bare.py": "x=1",
        "myapp/__init__.py": "",
        "myapp/loader.py": "async def register(*a): pass\n",
    })
    resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 400
    assert "bare files" in resp.json()["detail"]


def test_import_rejects_multiple_top_dirs(client_no_apps):
    zip_bytes = _make_zip({
        "app_a/__init__.py": "",
        "app_b/__init__.py": "",
    })
    resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 400
    assert "exactly one top-level directory" in resp.json()["detail"]


def test_import_rejects_invalid_app_name(client_no_apps):
    zip_bytes = _make_zip({
        "bad-name/__init__.py": "",
        "bad-name/loader.py": "async def register(*a): pass\n",
    })
    resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 400
    assert "valid Python identifier" in resp.json()["detail"]


def test_import_rejects_path_traversal(client_no_apps):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("myapp/__init__.py", "")
        zf.writestr("myapp/loader.py", "async def register(*a): pass\n")
        zf.writestr("myapp/../../../etc/passwd", "evil")
    resp = _upload(client_no_apps, buf.getvalue())
    assert resp.status_code == 400
    assert "traversal" in resp.json()["detail"].lower() or "outside" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Happy path — valid import with mock extraction
# ---------------------------------------------------------------------------

def _mock_loader():
    """Return a mock loader module with a no-op async register()."""
    mod = ModuleType("mock_loader")
    mod.APP_META = {"description": "mocked import app"}
    mod.register = AsyncMock()
    return mod


def test_import_valid_app_returns_200(client_no_apps, tmp_path):
    zip_bytes = _minimal_app_zip("newapp")
    with patch("groot.app_routes._GROOT_APPS_DIR", tmp_path / "groot_apps"), \
         patch("groot.app_routes.importlib.import_module", return_value=_mock_loader()):
        resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "newapp"
    assert body["status"] == "loaded"


def test_import_result_has_correct_fields(client_no_apps, tmp_path):
    zip_bytes = _minimal_app_zip("myapp2")
    with patch("groot.app_routes._GROOT_APPS_DIR", tmp_path / "groot_apps"), \
         patch("groot.app_routes.importlib.import_module", return_value=_mock_loader()):
        resp = _upload(client_no_apps, zip_bytes)
    body = resp.json()
    assert "tools_registered" in body
    assert "pages_registered" in body
    assert "message" in body
    assert "myapp2" in body["message"]


def test_import_app_appears_in_list(client_no_apps, tmp_path):
    zip_bytes = _minimal_app_zip("listapp")
    with patch("groot.app_routes._GROOT_APPS_DIR", tmp_path / "groot_apps"), \
         patch("groot.app_routes.importlib.import_module", return_value=_mock_loader()):
        _upload(client_no_apps, zip_bytes)
        resp = client_no_apps.get("/api/apps")
    names = [a["name"] for a in resp.json()["apps"]]
    assert "listapp" in names


def test_import_app_status_is_loaded(client_no_apps, tmp_path):
    zip_bytes = _minimal_app_zip("statusapp")
    with patch("groot.app_routes._GROOT_APPS_DIR", tmp_path / "groot_apps"), \
         patch("groot.app_routes.importlib.import_module", return_value=_mock_loader()):
        _upload(client_no_apps, zip_bytes)
        resp = client_no_apps.get("/api/apps")
    apps = {a["name"]: a for a in resp.json()["apps"]}
    assert apps["statusapp"]["status"] == "loaded"


def test_import_extracts_files_to_disk(client_no_apps, tmp_path):
    zip_bytes = _minimal_app_zip("diskapp")
    fake_groot_apps = tmp_path / "groot_apps"
    with patch("groot.app_routes._GROOT_APPS_DIR", fake_groot_apps):
        _upload(client_no_apps, zip_bytes)
    assert (fake_groot_apps / "diskapp" / "__init__.py").exists()
    assert (fake_groot_apps / "diskapp" / "loader.py").exists()


# ---------------------------------------------------------------------------
# 413 — size limit
# ---------------------------------------------------------------------------

def test_import_rejects_oversized_file(client_no_apps):
    # Build a zip with a file just over 10MB
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("bigapp/__init__.py", "")
        zf.writestr("bigapp/loader.py", "async def register(*a): pass\n")
        zf.writestr("bigapp/data.bin", b"\x00" * (10 * 1024 * 1024 + 1))
    resp = _upload(client_no_apps, buf.getvalue())
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Loader missing — extracted but load fails
# ---------------------------------------------------------------------------

def test_import_loader_missing_returns_422(client_no_apps, tmp_path):
    zip_bytes = _make_zip({"noloader/__init__.py": ""})
    with patch("groot.app_routes._GROOT_APPS_DIR", tmp_path / "groot_apps"):
        resp = _upload(client_no_apps, zip_bytes)
    assert resp.status_code == 422
    assert "loader" in resp.json()["detail"].lower()
