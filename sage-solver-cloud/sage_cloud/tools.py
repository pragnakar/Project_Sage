"""Sage Cloud core tool registry and 12 built-in tool implementations."""

import inspect
import json
import logging
import traceback
from typing import Any

from pydantic import BaseModel

from sage_cloud.artifact_store import ArtifactStore
from sage_cloud.models import (
    AppPageMeta,
    AppPageResult,
    AppResult,
    ArtifactSummary,
    BlobData,
    BlobMeta,
    BlobResult,
    SageCloudConfig,
    LogResult,
    PageMeta,
    PageResult,
    SchemaMeta,
    SchemaResult,
    SystemState,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)

# Mapping from Python types to JSON Schema types
_TYPE_MAP: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _build_parameters(fn) -> dict[str, Any]:
    """Build a JSON Schema parameters dict from a function signature, skipping 'store'."""
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "store":
            continue

        annotation = param.annotation
        json_type = _TYPE_MAP.get(annotation, "string")
        properties[param_name] = {"type": json_type}

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class ToolRegistry:
    """Registry for all Sage Cloud tools — core and domain-app tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        tool_fn,
        name: str | None = None,
        description: str | None = None,
        namespace: str = "core",
    ) -> None:
        """Register a callable as a named tool. Extracts metadata from type hints and docstring."""
        tool_name = name or tool_fn.__name__
        tool_description = description or (inspect.getdoc(tool_fn) or "")
        parameters = _build_parameters(tool_fn)

        self._tools[tool_name] = ToolDefinition(
            name=tool_name,
            description=tool_description,
            namespace=namespace,
            parameters=parameters,
            fn=tool_fn,
        )

    def get(self, name: str) -> ToolDefinition:
        """Get a registered tool by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name!r}")
        return self._tools[name]

    def list_tools(self, namespace: str | None = None) -> list[ToolDefinition]:
        """List all registered tools, optionally filtered by namespace."""
        tools = list(self._tools.values())
        if namespace is not None:
            tools = [t for t in tools if t.namespace == namespace]
        return tools

    def unregister_namespace(self, namespace: str) -> int:
        """Remove all tools belonging to a namespace. Returns count removed."""
        to_remove = [name for name, t in self._tools.items() if t.namespace == namespace]
        for name in to_remove:
            del self._tools[name]
        return len(to_remove)

    async def call(self, tool_name: str, store: ArtifactStore, **kwargs) -> BaseModel:
        """
        Call a tool by name with kwargs. Injects store as first arg.
        Returns the tool's Pydantic model result, or ToolError on failure.
        """
        try:
            tool = self.get(tool_name)
        except KeyError:
            return ToolError(error="not_found", detail=f"Tool not registered: {tool_name!r}", tool_name=tool_name)

        try:
            result = await tool.fn(store, **kwargs)
            return result
        except KeyError as e:
            return ToolError(error="not_found", detail=str(e), tool_name=tool_name)
        except ValueError as e:
            return ToolError(error="validation_error", detail=str(e), tool_name=tool_name)
        except Exception as e:
            logger.error("Tool %r raised unexpected exception: %s\n%s", tool_name, e, traceback.format_exc())
            return ToolError(error="internal_error", detail=str(e), tool_name=tool_name)


# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------

async def write_blob(store: ArtifactStore, key: str, data: str, content_type: str = "text/plain") -> BlobResult:
    """Write a blob to the artifact store. Key format: 'namespace/name'. Returns blob metadata and URL."""
    return await store.write_blob(key, data, content_type)


async def read_blob(store: ArtifactStore, key: str) -> BlobData:
    """Read a blob from the artifact store by key. Returns full data and metadata."""
    return await store.read_blob(key)


async def list_blobs(store: ArtifactStore, prefix: str = "") -> list[BlobMeta]:
    """List blobs in the artifact store, optionally filtered by key prefix."""
    return await store.list_blobs(prefix)


async def delete_blob(store: ArtifactStore, key: str) -> bool:
    """Delete a blob from the artifact store. Returns True if deleted, False if not found."""
    return await store.delete_blob(key)


# ---------------------------------------------------------------------------
# Page tools
# ---------------------------------------------------------------------------

async def create_page(store: ArtifactStore, name: str, jsx_code: str, description: str = "") -> PageResult:
    """Store a React JSX component and register it as a live route at /apps/{name}."""
    return await store.create_page(name, jsx_code, description)


async def update_page(store: ArtifactStore, name: str, jsx_code: str) -> PageResult:
    """Replace an existing page's JSX. Hot-updates the route."""
    return await store.update_page(name, jsx_code)


async def upsert_page(store: ArtifactStore, name: str, jsx_code: str, description: str = "") -> PageResult:
    """Create or update a page atomically. Safe to call whether or not the page exists."""
    return await store.upsert_page(name, jsx_code, description)


async def list_pages(store: ArtifactStore) -> list[PageMeta]:
    """List all registered pages with their URLs and metadata."""
    return await store.list_pages()


async def delete_page(store: ArtifactStore, name: str) -> bool:
    """Delete a registered page. Returns True if deleted, False if not found."""
    return await store.delete_page(name)


# ---------------------------------------------------------------------------
# Schema tools
# ---------------------------------------------------------------------------

async def define_schema(store: ArtifactStore, name: str, schema: dict) -> SchemaResult:
    """Store a named JSON schema for structured data validation."""
    try:
        json.dumps(schema)
    except (TypeError, ValueError) as e:
        raise ValueError(f"schema is not JSON-serializable: {e}") from e
    return await store.define_schema(name, schema)


async def get_schema(store: ArtifactStore, name: str) -> SchemaResult:
    """Retrieve a stored JSON schema by name."""
    return await store.get_schema(name)


async def list_schemas(store: ArtifactStore) -> list[SchemaMeta]:
    """List all stored schema names and metadata."""
    return await store.list_schemas()


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------

async def log_event(store: ArtifactStore, message: str, level: str = "info", context: dict = {}) -> LogResult:
    """Append a structured log event to the artifact store event log."""
    return await store.log_event(message, level, context)


async def get_system_state(store: ArtifactStore, uptime_seconds: float) -> SystemState:
    """Return Sage Cloud runtime state: uptime, artifact counts, registered apps."""
    return await store.get_system_state(uptime_seconds)


async def list_artifacts(store: ArtifactStore) -> ArtifactSummary:
    """Return a full inventory of all artifacts: pages, blobs, schemas, recent events."""
    return await store.list_artifacts()


async def get_sage_cloud_config(store: ArtifactStore) -> SageCloudConfig:
    """Return Sage Cloud's runtime connection info: API key, host, port, and URLs.

    Use this to discover the API key and base URL needed for direct HTTP calls.
    The api_key value goes in the X-Sage-Key header for authenticated endpoints.
    """
    import os
    from sage_cloud.config import get_settings
    settings = get_settings()
    host = settings.SAGE_CLOUD_HOST if settings.SAGE_CLOUD_HOST != "0.0.0.0" else "localhost"
    port = settings.SAGE_CLOUD_PORT
    base_url = f"http://{host}:{port}"
    keys = os.environ.get("SAGE_CLOUD_API_KEYS", "").strip()
    api_key = keys.split(",")[0].strip() if keys else "sage_sk_dev_key_01"
    return SageCloudConfig(
        api_key=api_key,
        host=host,
        port=port,
        base_url=base_url,
        dashboard_url=f"{base_url}/",
    )


# ---------------------------------------------------------------------------
# Multi-page app tools
# ---------------------------------------------------------------------------

async def create_app(store: ArtifactStore, name: str, description: str = "", layout_jsx: str = "") -> AppResult:
    """Register a new multi-page app namespace. Returns base_url for the app root.

    Use create_app_page to add pages. Navigate between pages with plain <a href> links.
    layout_jsx is optional JSX for a shared wrapper rendered around every page in the app.
    """
    return await store.create_app(name, description, layout_jsx)


async def create_app_page(store: ArtifactStore, app_name: str, page_name: str, jsx_code: str, description: str = "") -> AppPageResult:
    """Add a React JSX page to an existing app namespace.

    page_name='index' is served at /apps/{app}/ (the app root).
    Any other page_name is served at /apps/{app}/{page_name}.
    Navigation between pages uses plain anchor tags: <a href="/apps/myapp/clock">Clock</a>
    """
    return await store.create_app_page(app_name, page_name, jsx_code, description)


async def update_app_page(store: ArtifactStore, app_name: str, page_name: str, jsx_code: str) -> AppPageResult:
    """Hot-swap the JSX for an existing app page without restarting the server."""
    return await store.update_app_page(app_name, page_name, jsx_code)


async def list_app_pages(store: ArtifactStore, app_name: str) -> list[AppPageMeta]:
    """List all pages registered under an app namespace."""
    return await store.list_app_pages(app_name)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_core_tools(registry: ToolRegistry, store: ArtifactStore) -> None:
    """Register all 20 core tools with the registry."""
    for fn in [
        write_blob, read_blob, list_blobs, delete_blob,
        create_page, update_page, upsert_page, list_pages, delete_page,
        define_schema, get_schema, list_schemas,
        log_event, get_system_state, list_artifacts,
        get_sage_cloud_config,
        create_app, create_app_page, update_app_page, list_app_pages,
    ]:
        registry.register(fn, namespace="core")
