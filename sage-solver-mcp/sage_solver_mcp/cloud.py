"""Discovery-based cloud connection for sage-solver-mcp.

Reads ``~/.sage/cloud.json`` written by sage-solver-cloud to discover a
running instance, then validates with a health check. Results are cached
for 30 seconds to avoid repeated disk reads and HTTP calls.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DISCOVERY_FILE = Path.home() / ".sage" / "cloud.json"


@dataclass
class CloudConnection:
    url: str
    version: str
    port: int
    api_key: str | None = None


_cache: tuple[float, CloudConnection | None] = (0.0, None)


def find_cloud() -> CloudConnection | None:
    """Find a running sage-solver-cloud instance via discovery file.

    Reads ~/.sage/cloud.json, validates with a health check.
    Results cached for 30 seconds.
    """
    global _cache
    now = time.monotonic()
    if now - _cache[0] < 30.0:
        return _cache[1]

    result = _discover()
    _cache = (now, result)
    return result


def _discover() -> CloudConnection | None:
    if not DISCOVERY_FILE.exists():
        return None

    try:
        data = json.loads(DISCOVERY_FILE.read_text())
        url = data["url"]

        # Health check with 2s timeout
        req = urllib.request.Request(f"{url}/health")
        resp = urllib.request.urlopen(req, timeout=2)
        health = json.loads(resp.read())

        if health.get("status") == "ok":
            return CloudConnection(
                url=url,
                version=data.get("version", "unknown"),
                port=data.get("port", 0),
                api_key=data.get("api_key"),
            )
    except Exception as exc:
        logger.warning("sage-solver-cloud discovery failed: %s", exc)

    return None


def invalidate_cache() -> None:
    """Reset the discovery cache (useful for testing)."""
    global _cache
    _cache = (0.0, None)
