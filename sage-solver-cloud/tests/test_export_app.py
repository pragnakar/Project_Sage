"""Tests for GET /api/apps/{name}/export endpoint (task 868hwpquk)."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from sage_cloud.config import Settings, get_settings
from sage_cloud.server import app

TEST_API_KEY = "sage_sk_test_key"
AUTH = {"X-Sage-Key": TEST_API_KEY}


def _open_zip(response) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(response.content))


# ---------------------------------------------------------------------------
# 404 for unknown app
# ---------------------------------------------------------------------------

def test_export_missing_app_returns_404(client):
    resp = client.get("/api/apps/nonexistent/export")
    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]
