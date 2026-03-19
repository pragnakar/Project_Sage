"""Groot MCP transport — bridges ToolRegistry to MCP protocol (stdio + SSE transports)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError

from groot.artifact_store import ArtifactStore
from groot.models import ToolError
from groot.tools import ToolRegistry

if TYPE_CHECKING:
    from fastapi import FastAPI
    from groot.config import Settings

logger = logging.getLogger(__name__)

_ERROR_CODES = {
    "not_found": types.METHOD_NOT_FOUND,
    "validation_error": types.INVALID_PARAMS,
    "internal_error": types.INTERNAL_ERROR,
}


class MCPBridge:
    """Bridges ToolRegistry to MCP protocol — testable without any transport."""

    def __init__(self, registry: ToolRegistry, store: ArtifactStore) -> None:
        self._registry = registry
        self._store = store

    async def list_tools(self) -> list[types.Tool]:
        """Return all registered tools as MCP Tool objects."""
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.parameters,
            )
            for t in self._registry.list_tools()
        ]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Route an MCP tool call to the registry. Returns serialized result dict."""
        result = await self._registry.call(name, store=self._store, **arguments)
        if isinstance(result, ToolError):
            raise McpError(
                types.ErrorData(
                    code=_ERROR_CODES.get(result.error, types.INTERNAL_ERROR),
                    message=result.detail or result.error,
                    data=result.model_dump(),
                )
            )
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, list):
            return {"result": [item.model_dump() if hasattr(item, "model_dump") else item for item in result]}
        return {"result": result}


def register_tools_with_mcp(
    mcp_server: Server,
    registry: ToolRegistry,
    store: ArtifactStore,
) -> MCPBridge:
    """Register all tools from the ToolRegistry as MCP tools. Returns the bridge."""
    bridge = MCPBridge(registry, store)

    @mcp_server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return await bridge.list_tools()

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict) -> dict:
        return await bridge.call_tool(name, arguments)

    return bridge


async def run_stdio(store: ArtifactStore, registry: ToolRegistry) -> None:
    """Start the MCP server in stdio mode (blocking until stdin closes)."""
    server = Server("groot")
    register_tools_with_mcp(server, registry, store)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def mount_sse_transport(
    app: FastAPI,
    registry: ToolRegistry,
    store: ArtifactStore,
    settings: Settings,
) -> None:
    """Mount SSE MCP transport on the FastAPI app at /mcp/sse and /mcp/messages.

    - GET  /mcp/sse       — establishes SSE stream; auth via ?key= query param
    - POST /mcp/messages  — receives MCP JSON-RPC messages for an existing session
    """
    from mcp.server.sse import SseServerTransport
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response as StarletteResponse
    from starlette.routing import Mount, Route

    sse_transport = SseServerTransport("/mcp/messages")
    mcp_server = Server("groot-sse")
    register_tools_with_mcp(mcp_server, registry, store)

    async def _connect_sse(scope, receive, send):  # pragma: no cover
        async with sse_transport.connect_sse(scope, receive, send) as (rs, ws):
            await mcp_server.run(rs, ws, mcp_server.create_initialization_options())

    async def sse_endpoint(request: StarletteRequest) -> StarletteResponse:
        key = request.query_params.get("key")
        valid_keys = settings.api_keys_list()

        if settings.GROOT_ENV == "production" and not valid_keys:
            return StarletteResponse("Server misconfiguration", status_code=500)

        if valid_keys and key not in valid_keys:
            return StarletteResponse("Unauthorized", status_code=401)

        return await _connect_sse(  # type: ignore[return-value]
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        )

    # Replace existing /mcp routes on every lifespan restart (idempotent for tests)
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in ("/mcp/sse", "/mcp/messages")
    ]
    app.router.routes.append(Route("/mcp/sse", endpoint=sse_endpoint, methods=["GET"]))
    app.router.routes.append(Mount("/mcp/messages", app=sse_transport.handle_post_message))
