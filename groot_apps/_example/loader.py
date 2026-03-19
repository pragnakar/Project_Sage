"""Example Groot app module loader — reference implementation.

Copy this directory to groot_apps/myapp/ and adapt to build your own app.
Enable with GROOT_APPS=_example in your .env file.
"""

from pathlib import Path

from groot.artifact_store import ArtifactStore
from groot.page_server import PageServer
from groot.tools import ToolRegistry
from groot_apps._example.tools import echo_tool

APP_META = {
    "description": "Minimal reference app — one tool, one page",
    "version": "0.1.0",
}

_PAGES_DIR = Path(__file__).parent / "pages"


async def register(
    tool_registry: ToolRegistry,
    page_server: PageServer,
    store: ArtifactStore,
) -> None:
    """Register example tools and pages into the Groot runtime."""
    tool_registry.register(echo_tool, namespace="_example")
    await page_server.register_static("hello", str(_PAGES_DIR / "hello.jsx"), app_name="_example")


async def health_check() -> dict:
    """Return example app health status."""
    return {"status": "healthy", "checks": {"echo_tool": "available"}}
