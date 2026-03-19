"""Tests for sage_solver_mcp.cloud — discovery-based cloud connection."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from sage_solver_mcp.cloud import (
    DISCOVERY_FILE,
    CloudConnection,
    _discover,
    find_cloud,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level cache before each test."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def tmp_discovery(tmp_path):
    """Provide a temp discovery file path and patch DISCOVERY_FILE."""
    test_file = tmp_path / "cloud.json"
    with patch("sage_solver_mcp.cloud.DISCOVERY_FILE", test_file):
        yield test_file


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that responds to /health."""

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging in tests


@pytest.fixture
def health_server():
    """Start a local HTTP server that responds to /health."""
    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


class TestFindCloudHappyPath:
    def test_returns_cloud_connection(self, tmp_discovery, health_server):
        """Happy path: valid cloud.json + healthy server returns CloudConnection."""
        port = health_server
        data = {
            "url": f"http://127.0.0.1:{port}",
            "port": port,
            "pid": 12345,
            "version": "0.3.0",
            "started_at": "2026-03-19T10:00:00Z",
        }
        tmp_discovery.write_text(json.dumps(data))

        result = find_cloud()
        assert result is not None
        assert isinstance(result, CloudConnection)
        assert result.url == f"http://127.0.0.1:{port}"
        assert result.version == "0.3.0"
        assert result.port == port


class TestFindCloudMissingFile:
    def test_returns_none_without_error(self, tmp_discovery):
        """Missing cloud.json returns None without raising."""
        assert not tmp_discovery.exists()
        result = find_cloud()
        assert result is None


class TestFindCloudDeadCloud:
    def test_returns_none_on_timeout(self, tmp_discovery):
        """cloud.json exists but health check fails returns None."""
        data = {
            "url": "http://127.0.0.1:1",  # Port 1 — will timeout/refuse
            "port": 1,
            "pid": 12345,
            "version": "0.3.0",
            "started_at": "2026-03-19T10:00:00Z",
        }
        tmp_discovery.write_text(json.dumps(data))

        result = find_cloud()
        assert result is None


class TestFindCloudCaching:
    def test_caches_for_30_seconds(self, tmp_discovery, health_server):
        """Two calls within 30s result in only one disk read + HTTP hit."""
        port = health_server
        data = {
            "url": f"http://127.0.0.1:{port}",
            "port": port,
            "pid": 12345,
            "version": "0.3.0",
            "started_at": "2026-03-19T10:00:00Z",
        }
        tmp_discovery.write_text(json.dumps(data))

        # First call — actually discovers
        result1 = find_cloud()
        assert result1 is not None

        # Delete the file — second call should still return cached result
        tmp_discovery.unlink()

        result2 = find_cloud()
        assert result2 is not None
        assert result2.url == result1.url

    def test_cache_expires(self, tmp_discovery, health_server):
        """Cache expires after 30 seconds, triggering re-discovery."""
        port = health_server
        data = {
            "url": f"http://127.0.0.1:{port}",
            "port": port,
            "pid": 12345,
            "version": "0.3.0",
            "started_at": "2026-03-19T10:00:00Z",
        }
        tmp_discovery.write_text(json.dumps(data))

        # First call
        result1 = find_cloud()
        assert result1 is not None

        # Simulate cache expiry by manipulating _cache
        import sage_solver_mcp.cloud as cloud_mod
        cloud_mod._cache = (time.monotonic() - 60.0, result1)

        # Delete the file — cache is expired, so re-discover will fail
        tmp_discovery.unlink()
        result2 = find_cloud()
        assert result2 is None


class TestDiscoverInternal:
    def test_malformed_json_returns_none(self, tmp_discovery):
        """Malformed cloud.json returns None."""
        tmp_discovery.write_text("not valid json{{{")
        result = _discover()
        assert result is None

    def test_missing_url_returns_none(self, tmp_discovery):
        """cloud.json without 'url' field returns None."""
        tmp_discovery.write_text(json.dumps({"port": 8000}))
        result = _discover()
        assert result is None
