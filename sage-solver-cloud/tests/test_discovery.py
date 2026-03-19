"""Tests for sage_cloud.discovery — port discovery file write/delete."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sage_cloud.discovery import (
    DISCOVERY_FILE,
    _is_pid_alive,
    delete_discovery_file,
    write_discovery_file,
)


@pytest.fixture(autouse=True)
def _clean_discovery_file(tmp_path):
    """Redirect DISCOVERY_FILE to a temp path for test isolation."""
    test_file = tmp_path / "cloud.json"
    test_dir = tmp_path
    with (
        patch("sage_cloud.discovery.DISCOVERY_FILE", test_file),
        patch("sage_cloud.discovery.DISCOVERY_DIR", test_dir),
    ):
        yield test_file
    # Cleanup
    if test_file.exists():
        test_file.unlink()


class TestWriteDiscoveryFile:
    def test_writes_valid_json(self, _clean_discovery_file):
        """Discovery file is written with correct structure on startup."""
        test_file = _clean_discovery_file
        write_discovery_file(port=8001)
        assert test_file.exists()

        data = json.loads(test_file.read_text())
        assert data["url"] == "http://localhost:8001"
        assert data["port"] == 8001
        assert data["pid"] == os.getpid()
        assert data["version"] == "0.3.0"
        assert "started_at" in data
        # Validate ISO format
        from datetime import datetime
        datetime.fromisoformat(data["started_at"])

    def test_creates_directory(self, tmp_path):
        """Creates the ~/.sage/ directory if it doesn't exist."""
        nested = tmp_path / "nested" / "sage"
        test_file = nested / "cloud.json"
        with (
            patch("sage_cloud.discovery.DISCOVERY_FILE", test_file),
            patch("sage_cloud.discovery.DISCOVERY_DIR", nested),
        ):
            write_discovery_file(port=9000)
            assert test_file.exists()

    def test_custom_version(self, _clean_discovery_file):
        test_file = _clean_discovery_file
        write_discovery_file(port=8001, version="1.0.0")
        data = json.loads(test_file.read_text())
        assert data["version"] == "1.0.0"


class TestDeleteDiscoveryFile:
    def test_deletes_own_file(self, _clean_discovery_file):
        """File is deleted on shutdown if it belongs to current process."""
        test_file = _clean_discovery_file
        write_discovery_file(port=8001)
        assert test_file.exists()
        delete_discovery_file()
        assert not test_file.exists()

    def test_does_not_delete_other_pid(self, _clean_discovery_file):
        """File is NOT deleted if PID doesn't match (another instance owns it)."""
        test_file = _clean_discovery_file
        # Write a file with a different PID
        data = {
            "url": "http://localhost:8001",
            "port": 8001,
            "pid": os.getpid() + 99999,
            "version": "0.3.0",
            "started_at": "2026-01-01T00:00:00Z",
        }
        test_file.write_text(json.dumps(data))
        delete_discovery_file()
        # File should still exist
        assert test_file.exists()

    def test_noop_when_no_file(self, _clean_discovery_file):
        """No error when discovery file doesn't exist."""
        test_file = _clean_discovery_file
        assert not test_file.exists()
        delete_discovery_file()  # Should not raise


class TestStalePIDOverwrite:
    def test_overwrites_dead_pid(self, _clean_discovery_file):
        """Overwrites discovery file if existing PID is dead."""
        test_file = _clean_discovery_file
        # Write a file with a PID that's definitely dead (use a very high PID)
        stale_data = {
            "url": "http://localhost:9999",
            "port": 9999,
            "pid": 999999999,  # Almost certainly not running
            "version": "0.2.0",
            "started_at": "2025-01-01T00:00:00Z",
        }
        test_file.write_text(json.dumps(stale_data))

        # Now write new discovery
        write_discovery_file(port=8001)
        data = json.loads(test_file.read_text())
        assert data["port"] == 8001
        assert data["pid"] == os.getpid()
        assert data["version"] == "0.3.0"

    def test_overwrites_live_pid_with_warning(self, _clean_discovery_file, caplog):
        """Overwrites discovery file even if existing PID is alive, but logs warning."""
        test_file = _clean_discovery_file
        import logging
        # Use current PID + 1 but mock it as alive
        other_pid = os.getpid() + 1
        stale_data = {
            "url": "http://localhost:9999",
            "port": 9999,
            "pid": other_pid,
            "version": "0.2.0",
            "started_at": "2025-01-01T00:00:00Z",
        }
        test_file.write_text(json.dumps(stale_data))

        with patch("sage_cloud.discovery._is_pid_alive", return_value=True):
            with caplog.at_level(logging.WARNING, logger="sage_cloud.discovery"):
                write_discovery_file(port=8001)

        data = json.loads(test_file.read_text())
        assert data["port"] == 8001
        assert data["pid"] == os.getpid()
        assert any("Overwriting discovery file owned by live PID" in r.message for r in caplog.records)


class TestIsPidAlive:
    def test_current_pid_is_alive(self):
        assert _is_pid_alive(os.getpid()) is True

    def test_zero_pid_is_dead(self):
        assert _is_pid_alive(0) is False

    def test_negative_pid_is_dead(self):
        assert _is_pid_alive(-1) is False

    def test_nonexistent_pid(self):
        # Very high PID that almost certainly doesn't exist
        assert _is_pid_alive(999999999) is False
