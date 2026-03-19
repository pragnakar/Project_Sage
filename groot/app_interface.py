"""
Groot App Module Interface
==========================

Every Groot app module must:

1. Live in ``groot_apps/{name}/``
2. Provide a ``loader.py`` with an async ``register()`` function
3. Optionally declare ``APP_META`` and ``health_check()``

Minimal ``loader.py``::

    from groot.tools import ToolRegistry
    from groot.page_server import PageServer
    from groot.artifact_store import ArtifactStore

    async def register(
        tool_registry: ToolRegistry,
        page_server: PageServer,
        store: ArtifactStore,
    ) -> None:
        tool_registry.register(my_tool, namespace="myapp")
        await page_server.register_static("dashboard", jsx_path, app_name="myapp")

    async def health_check() -> dict:
        # Optional — surfaced by GET /api/apps/{name}/health
        return {"status": "healthy", "checks": {}}

    APP_META = {
        "description": "My custom Groot app",
        "version": "0.1.0",
    }

The ``GrootAppModule`` Protocol below is documentation-first.
It is NOT enforced at runtime — use it for type checking and reference.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from groot.artifact_store import ArtifactStore
    from groot.page_server import PageServer
    from groot.tools import ToolRegistry


@runtime_checkable
class GrootAppModule(Protocol):
    """Protocol that Groot app loader modules should satisfy.

    Only ``register`` is strictly required. ``APP_META`` and
    ``health_check`` are optional extensions.
    """

    async def register(
        self,
        tool_registry: "ToolRegistry",
        page_server: "PageServer",
        store: "ArtifactStore",
    ) -> None:
        """Register tools and pages into the Groot runtime."""
        ...

    # Optional attributes — presence is checked at runtime, not enforced
    APP_META: dict
    """Module-level metadata dict: description, version, etc."""

    async def health_check(self) -> dict:
        """Return app health status. Called by GET /api/apps/{name}/health."""
        ...
