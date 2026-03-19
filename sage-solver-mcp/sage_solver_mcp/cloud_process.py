"""Manage the sage-solver-cloud subprocess lifecycle.

Starts sage-solver-cloud on a dynamic port when sage-solver-mcp boots,
captures the assigned port and API key, and tears it down on exit.

Usage:
    cloud = CloudProcess()
    cloud.start()          # spawns subprocess, blocks until ready
    cloud.base_url         # "http://localhost:53821"
    cloud.api_key          # "sage_sk_..."
    cloud.stop()           # kills subprocess
"""

from __future__ import annotations

import atexit
import logging
import os
import re
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

_PORT_RE = re.compile(r"Uvicorn running on http://[\d.]+:(\d+)")
_KEY_RE = re.compile(r"API Key\s*:\s*(sage_sk_\w+)")


class CloudProcess:
    """Manages a sage-solver-cloud subprocess."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.port: int | None = None
        self.api_key: str | None = None
        self.base_url: str | None = None

    def start(self, timeout: float = 15.0) -> None:
        """Spawn sage-solver-cloud on a dynamic port and wait until ready."""
        if self.process is not None:
            return  # already running

        import secrets

        # Generate API key here and pass it to the subprocess via env
        self.api_key = "sage_sk_" + secrets.token_hex(16)

        env = os.environ.copy()
        env["SAGE_CLOUD_PORT"] = "0"  # dynamic port
        env["SAGE_CLOUD_API_KEYS"] = self.api_key

        self.process = subprocess.Popen(
            [sys.executable, "-m", "sage_cloud"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )

        atexit.register(self.stop)

        # Read output lines until we find the port
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                remaining = self.process.stdout.read() if self.process.stdout else ""
                logger.error("sage-solver-cloud exited early: %s", remaining)
                raise RuntimeError(f"sage-solver-cloud exited with code {self.process.returncode}")

            line = self.process.stdout.readline() if self.process.stdout else ""
            if not line:
                time.sleep(0.1)
                continue

            line = line.strip()
            logger.debug("cloud: %s", line)

            port_match = _PORT_RE.search(line)
            if port_match:
                self.port = int(port_match.group(1))
                self.base_url = f"http://localhost:{self.port}"
                logger.info(
                    "sage-solver-cloud ready at %s",
                    self.base_url,
                )
                return

        # Timeout
        self.stop()
        raise RuntimeError(
            f"sage-solver-cloud did not become ready within {timeout}s"
        )

    def stop(self) -> None:
        """Terminate the subprocess."""
        if self.process is not None and self.process.poll() is None:
            logger.info("Stopping sage-solver-cloud (pid=%d)", self.process.pid)
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# Module-level singleton
_cloud: CloudProcess | None = None


def get_cloud() -> CloudProcess:
    """Get or start the cloud process singleton."""
    global _cloud
    if _cloud is None or not _cloud.is_running:
        _cloud = CloudProcess()
        _cloud.start()
    return _cloud
