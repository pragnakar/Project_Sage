"""Tests for sage_cloud/auth.py — API key validation, header/query param, dev bypass."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sage_cloud.auth import verify_api_key
from sage_cloud.config import Settings, get_settings


def make_app(settings: Settings) -> FastAPI:
    """Build a minimal test FastAPI app using the given settings."""
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protected")
    async def protected(auth=pytest.approx(None)):
        from sage_cloud.auth import verify_api_key
        from fastapi import Depends
        return {"ok": True}

    return app


def _app_with_key(key: str, env: str = "development") -> tuple[FastAPI, TestClient]:
    """Return a test FastAPI app + client configured with a single API key."""
    app = FastAPI()
    settings = Settings(SAGE_CLOUD_API_KEYS=key, SAGE_CLOUD_ENV=env)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protected")
    async def protected(auth=pytest.approx(None)):
        pass

    from fastapi import Depends
    from sage_cloud.auth import verify_api_key

    @app.get("/secure")
    async def secure(auth=Depends(verify_api_key)):
        return {"key": auth.key}

    return app, TestClient(app, raise_server_exceptions=False)


def _app_no_keys(env: str = "development") -> tuple[FastAPI, TestClient]:
    """Return a test app with no API keys configured."""
    app = FastAPI()
    settings = Settings(SAGE_CLOUD_API_KEYS="", SAGE_CLOUD_ENV=env)
    app.dependency_overrides[get_settings] = lambda: settings

    from fastapi import Depends
    from sage_cloud.auth import verify_api_key

    @app.get("/secure")
    async def secure(auth=Depends(verify_api_key)):
        return {"key": auth.key}

    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Valid key tests
# ---------------------------------------------------------------------------

def test_valid_key_in_header():
    _, client = _app_with_key("sage_sk_testkey")
    resp = client.get("/secure", headers={"X-Sage-Key": "sage_sk_testkey"})
    assert resp.status_code == 200
    assert resp.json()["key"] == "sage_sk_testkey"


def test_valid_key_in_query_param():
    _, client = _app_with_key("sage_sk_testkey")
    resp = client.get("/secure", params={"key": "sage_sk_testkey"})
    assert resp.status_code == 200
    assert resp.json()["key"] == "sage_sk_testkey"


def test_header_takes_precedence_over_query_param():
    _, client = _app_with_key("sage_sk_real")
    # header is valid, query param is wrong — header should win
    resp = client.get(
        "/secure",
        headers={"X-Sage-Key": "sage_sk_real"},
        params={"key": "sage_sk_wrong"},
    )
    assert resp.status_code == 200


def test_multiple_valid_keys_all_accepted():
    app = FastAPI()
    settings = Settings(SAGE_CLOUD_API_KEYS="key_one,key_two,key_three", SAGE_CLOUD_ENV="development")
    app.dependency_overrides[get_settings] = lambda: settings

    from fastapi import Depends
    from sage_cloud.auth import verify_api_key

    @app.get("/secure")
    async def secure(auth=Depends(verify_api_key)):
        return {"key": auth.key}

    client = TestClient(app, raise_server_exceptions=False)

    for k in ["key_one", "key_two", "key_three"]:
        resp = client.get("/secure", headers={"X-Sage-Key": k})
        assert resp.status_code == 200, f"Key {k!r} should be accepted"


# ---------------------------------------------------------------------------
# Missing / invalid key
# ---------------------------------------------------------------------------

def test_missing_key_returns_401():
    _, client = _app_with_key("sage_sk_testkey")
    resp = client.get("/secure")
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["error"] == "unauthorized"


def test_invalid_key_returns_403():
    _, client = _app_with_key("sage_sk_real")
    resp = client.get("/secure", headers={"X-Sage-Key": "sage_sk_wrong"})
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"] == "forbidden"


def test_error_response_is_tool_error_shape():
    _, client = _app_with_key("sage_sk_real")
    resp = client.get("/secure")
    detail = resp.json()["detail"]
    assert "error" in detail
    assert "detail" in detail
    assert "tool_name" in detail


# ---------------------------------------------------------------------------
# Development bypass
# ---------------------------------------------------------------------------

def test_dev_bypass_no_keys_allows_request():
    _, client = _app_no_keys(env="development")
    resp = client.get("/secure")
    assert resp.status_code == 200
    assert resp.json()["key"] == "dev-bypass"


# ---------------------------------------------------------------------------
# Production guard
# ---------------------------------------------------------------------------

def test_production_empty_keys_returns_500():
    _, client = _app_no_keys(env="production")
    resp = client.get("/secure")
    assert resp.status_code == 500
