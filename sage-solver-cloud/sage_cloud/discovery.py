"""Port discovery file management for sage-solver-cloud.

On startup, writes ``~/.sage/cloud.json`` so that sage-solver-mcp (and other
consumers) can discover a running cloud instance without subprocess tricks.

On shutdown (atexit + SIGTERM/SIGINT), the file is deleted.

The file format:
{
    "url": "http://localhost:{port}",
    "port": {port},
    "pid": {pid},
    "version": "0.3.0",
    "started_at": "ISO datetime"
}
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DISCOVERY_DIR = Path.home() / ".sage"
DISCOVERY_FILE = DISCOVERY_DIR / "cloud.json"


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        return False


def write_discovery_file(port: int, version: str = "0.3.0") -> None:
    """Write ~/.sage/cloud.json for the current process.

    If the file already exists with a different PID:
    - If that PID is dead, overwrite.
    - If that PID is alive, log a warning and overwrite anyway (last writer wins).
    """
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

    pid = os.getpid()

    # Check for stale file
    if DISCOVERY_FILE.exists():
        try:
            existing = json.loads(DISCOVERY_FILE.read_text())
            existing_pid = existing.get("pid", 0)
            if existing_pid != pid:
                if _is_pid_alive(existing_pid):
                    logger.warning(
                        "Overwriting discovery file owned by live PID %d "
                        "(this instance PID %d will take over)",
                        existing_pid,
                        pid,
                    )
                else:
                    logger.info(
                        "Overwriting stale discovery file (PID %d is dead)",
                        existing_pid,
                    )
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.info("Overwriting malformed discovery file")

    data = {
        "url": f"http://localhost:{port}",
        "port": port,
        "pid": pid,
        "version": version,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    DISCOVERY_FILE.write_text(json.dumps(data, indent=2))
    logger.info("Discovery file written: %s (port=%d, pid=%d)", DISCOVERY_FILE, port, pid)


def delete_discovery_file() -> None:
    """Delete ~/.sage/cloud.json if it belongs to the current process."""
    if not DISCOVERY_FILE.exists():
        return
    try:
        data = json.loads(DISCOVERY_FILE.read_text())
        if data.get("pid") != os.getpid():
            # File belongs to another process — don't delete it
            return
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    try:
        DISCOVERY_FILE.unlink()
        logger.info("Discovery file deleted: %s", DISCOVERY_FILE)
    except OSError as exc:
        logger.warning("Failed to delete discovery file: %s", exc)


def register_cleanup() -> None:
    """Register atexit + signal handlers to clean up the discovery file."""
    atexit.register(delete_discovery_file)

    def _signal_handler(signum: int, frame: object) -> None:
        delete_discovery_file()
        sys.exit(0)

    # Only register signal handlers if we're in the main thread
    import threading
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
