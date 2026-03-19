"""Shared pytest fixtures for Sage Cloud tests."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from sage_cloud.config import Settings, get_settings
from sage_cloud.server import app

TEST_API_KEY = "sage_sk_test_key"


@pytest.fixture
def test_settings(tmp_path):
    """Settings using a temp DB and test API key."""
    return Settings(
        SAGE_CLOUD_API_KEYS=TEST_API_KEY,
        SAGE_CLOUD_DB_PATH=str(tmp_path / "test.db"),
        SAGE_CLOUD_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        SAGE_CLOUD_APPS="",  # no app modules in tests
        SAGE_CLOUD_ENV="development",
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
    return {"X-Sage-Key": TEST_API_KEY}
