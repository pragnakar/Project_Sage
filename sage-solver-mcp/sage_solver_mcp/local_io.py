"""Local filesystem bridge for sage-mcp.

Provides path resolution, file reading, and file writing utilities
for the MCP server operating in the user's local environment.
All functions are synchronous — they are called from async tool
handlers via run_in_executor where needed.
"""

from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_path(filepath: str) -> Path:
    """Expand ~ and resolve relative paths; verify the file exists.

    Args:
        filepath: Raw path string (may be relative, may start with ~).

    Returns:
        Resolved absolute Path.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
    """
    path = Path(filepath).expanduser()
    if not path.is_absolute():
        # Resolve relative to cwd (the user's working directory when they
        # started the MCP server / invoked the tool).
        path = Path.cwd() / path
    # Check existence before resolving symlinks so the error message shows
    # the user-supplied path, not the macOS firmlink expansion
    # (e.g. /home → /System/Volumes/Data/home).
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}\n"
            f"Original path given: {filepath!r}\n"
            f"Working directory: {Path.cwd()}"
        )
    return path.resolve()


def ensure_output_dir(filepath: str | Path) -> Path:
    """Ensure the parent directory for an output file exists, creating it if needed.

    Args:
        filepath: Path to the intended output file.

    Returns:
        Resolved Path to the output file (parent is guaranteed to exist).
    """
    path = Path(filepath).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def read_file_bytes(filepath: str) -> bytes:
    """Read a file and return its raw bytes.

    Args:
        filepath: Path to the file (~ and relative paths are resolved).

    Returns:
        Raw bytes of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    path = resolve_path(filepath)
    return path.read_bytes()


def write_file_bytes(filepath: str | Path, content: bytes) -> Path:
    """Write bytes to a file, creating parent directories as needed.

    Args:
        filepath: Destination path (~ and relative paths are resolved).
        content:  Bytes to write.

    Returns:
        Resolved Path of the written file.

    Raises:
        OSError: If the file cannot be written.
    """
    path = ensure_output_dir(filepath)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# Derived-path helpers
# ---------------------------------------------------------------------------


def output_path_for(input_filepath: str, suffix: str = "_optimized") -> Path:
    """Compute the default output path adjacent to the input file.

    For example:
        input_filepath = "/home/user/data/portfolio.xlsx"
        suffix        = "_optimized"
        → /home/user/data/portfolio_optimized.xlsx

    Args:
        input_filepath: Path to the original input file.
        suffix:         String to append before the extension.

    Returns:
        Path for the output file (parent directory guaranteed to exist).
    """
    p = resolve_path(input_filepath)
    name = p.stem + suffix + p.suffix
    out = p.parent / name
    return ensure_output_dir(out)


def default_output_dir() -> Path:
    """Return a writable directory for output files.

    Falls back to the user's home directory when the current working directory
    is root or not writable (common when the MCP server is launched by a desktop
    app with CWD set to /).
    """
    cwd = Path.cwd().resolve()
    if str(cwd) == "/" or not os.access(cwd, os.W_OK):
        return Path.home().resolve()
    return cwd
