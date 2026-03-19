"""Shared pytest fixtures for Groot tests."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from groot.config import Settings, get_settings
from groot.server import app

TEST_API_KEY = "groot_sk_test_key"


@pytest.fixture
def test_settings(tmp_path):
    """Settings using a temp DB and test API key."""
    return Settings(
        GROOT_API_KEYS=TEST_API_KEY,
        GROOT_DB_PATH=str(tmp_path / "test.db"),
        GROOT_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        GROOT_APPS="",  # no app modules in tests
        GROOT_ENV="development",
    )


@pytest.fixture
def client(test_settings):
    """Synchronous TestClient with settings overridden."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-Groot-Key": TEST_API_KEY}
