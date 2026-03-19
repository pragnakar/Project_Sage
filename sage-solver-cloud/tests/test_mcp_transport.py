"""Tests for groot/mcp_transport.py — MCPBridge and MCP tool registration."""

import os
import tempfile

import pytest
from mcp import types
from mcp.server import Server
from mcp.shared.exceptions import McpError

from groot.artifact_store import ArtifactStore
from groot.mcp_transport import MCPBridge, register_tools_with_mcp
from groot.tools import ToolRegistry, register_core_tools


@pytest.fixture
async def bridge():
    """MCPBridge backed by a temp ArtifactStore with all 14 core tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = ArtifactStore(db_path=db_path, artifact_dir=tmpdir)
        await store.init_db()
        registry = ToolRegistry()
        register_core_tools(registry, store)
        yield MCPBridge(registry, store)


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------

async def test_list_tools_count(bridge):
    tools = await bridge.list_tools()
    assert len(tools) == 20  # spec §4: 4 storage + 5 page + 3 schema + 3 system + 1 config


async def test_list_tools_are_mcp_tool_objects(bridge):
    tools = await bridge.list_tools()
    assert all(isinstance(t, types.Tool) for t in tools)


async def test_list_tools_have_required_fields(bridge):
    tools = await bridge.list_tools()
    for t in tools:
        assert t.name
        assert t.description
        assert isinstance(t.inputSchema, dict)
        assert "properties" in t.inputSchema


async def test_tool_schema_matches_python_hints(bridge):
    """write_blob schema must reflect its actual type-hint-derived parameter spec."""
    tools = await bridge.list_tools()
    tool_map = {t.name: t for t in tools}
    wb = tool_map["write_blob"]
    assert wb.inputSchema["properties"]["key"]["type"] == "string"
    assert wb.inputSchema["properties"]["data"]["type"] == "string"
    assert "key" in wb.inputSchema.get("required", [])
    assert "data" in wb.inputSchema.get("required", [])
    # content_type has a default — must NOT be required
    assert "content_type" not in wb.inputSchema.get("required", [])


async def test_all_tool_names_present(bridge):
    tools = await bridge.list_tools()
    names = {t.name for t in tools}
    for expected in [
        "write_blob", "read_blob", "list_blobs", "delete_blob",
        "create_page", "update_page", "list_pages", "delete_page",
        "define_schema", "get_schema", "list_schemas",
        "log_event", "get_system_state", "list_artifacts",
    ]:
        assert expected in names, f"Missing tool: {expected}"


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------

async def test_call_write_blob(bridge):
    result = await bridge.call_tool("write_blob", {"key": "mcp/test", "data": "hello mcp"})
    assert isinstance(result, dict)
    assert result["key"] == "mcp/test"
    assert result["url"] == "/blobs/mcp/test"


async def test_call_read_blob_after_write(bridge):
    await bridge.call_tool("write_blob", {"key": "mcp/round", "data": "round trip"})
    result = await bridge.call_tool("read_blob", {"key": "mcp/round"})
    assert result["data"] == "round trip"


async def test_call_list_blobs(bridge):
    await bridge.call_tool("write_blob", {"key": "ns/a", "data": "1"})
    await bridge.call_tool("write_blob", {"key": "ns/b", "data": "2"})
    result = await bridge.call_tool("list_blobs", {"prefix": "ns/"})
    assert isinstance(result, dict)
    keys = [b["key"] for b in result["result"]]

    assert "ns/a" in keys and "ns/b" in keys


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_call_nonexistent_tool_raises_mcp_error(bridge):
    with pytest.raises(McpError) as exc_info:
        await bridge.call_tool("nonexistent_tool", {})
    assert exc_info.value.error.code == types.METHOD_NOT_FOUND


async def test_call_with_missing_required_param_raises_mcp_error(bridge):
    """Calling write_blob without required key/data should raise McpError."""
    with pytest.raises(McpError):
        await bridge.call_tool("write_blob", {})


async def test_call_read_nonexistent_blob_raises_mcp_error(bridge):
    with pytest.raises(McpError) as exc_info:
        await bridge.call_tool("read_blob", {"key": "missing/blob"})
    assert exc_info.value.error.code == types.METHOD_NOT_FOUND


# ---------------------------------------------------------------------------
# Server registration
# ---------------------------------------------------------------------------

async def test_register_tools_with_mcp_server():
    """register_tools_with_mcp attaches list_tools + call_tool handlers to Server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "reg.db")
        store = ArtifactStore(db_path=db_path, artifact_dir=tmpdir)
        await store.init_db()
        registry = ToolRegistry()
        register_core_tools(registry, store)

        server = Server("test-groot")
        bridge = register_tools_with_mcp(server, registry, store)

        assert bridge is not None
        assert isinstance(bridge, MCPBridge)
        assert types.ListToolsRequest in server.request_handlers
        assert types.CallToolRequest in server.request_handlers
