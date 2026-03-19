"""Tests for sage_cloud/tools.py — ToolRegistry and all 12 core tools."""

import os
import tempfile

import pytest

from sage_cloud.artifact_store import ArtifactStore
from sage_cloud.models import (
    ArtifactSummary,
    BlobData,
    BlobResult,
    LogResult,
    PageResult,
    SchemaResult,
    SystemState,
    ToolError,
)
from sage_cloud.tools import ToolRegistry, register_core_tools


@pytest.fixture
async def registry_and_store():
    """Temporary ArtifactStore + ToolRegistry with all core tools registered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = ArtifactStore(db_path=db_path, artifact_dir=tmpdir)
        await store.init_db()
        registry = ToolRegistry()
        register_core_tools(registry, store)
        yield registry, store


# ---------------------------------------------------------------------------
# Registry introspection
# ---------------------------------------------------------------------------

async def test_list_tools_returns_all_14(registry_and_store):
    registry, _ = registry_and_store
    tools = registry.list_tools()
    assert len(tools) == 20  # 4 storage + 5 page + 3 schema + 3 system + 1 config + 4 app


async def test_list_tools_namespace_filter(registry_and_store):
    registry, _ = registry_and_store
    core_tools = registry.list_tools(namespace="core")
    assert len(core_tools) == 20
    assert all(t.namespace == "core" for t in core_tools)


async def test_tool_metadata_has_required_fields(registry_and_store):
    registry, _ = registry_and_store
    for tool in registry.list_tools():
        assert tool.name
        assert tool.description
        assert isinstance(tool.parameters, dict)
        assert "properties" in tool.parameters


async def test_get_registered_tool(registry_and_store):
    registry, _ = registry_and_store
    tool = registry.get("write_blob")
    assert tool.name == "write_blob"


async def test_get_nonexistent_tool_raises(registry_and_store):
    registry, _ = registry_and_store
    with pytest.raises(KeyError):
        registry.get("nonexistent_tool")


async def test_call_nonexistent_tool_returns_tool_error(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("ghost_tool", store=store)
    assert isinstance(result, ToolError)
    assert result.error == "not_found"


# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------

async def test_write_blob(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("write_blob", store=store, key="ns/test.txt", data="hello", content_type="text/plain")
    assert isinstance(result, BlobResult)
    assert result.key == "ns/test.txt"
    assert result.size_bytes == len("hello".encode())
    assert result.url == "/blobs/ns/test.txt"


async def test_read_blob_after_write(registry_and_store):
    registry, store = registry_and_store
    await registry.call("write_blob", store=store, key="ns/r.txt", data="world")
    result = await registry.call("read_blob", store=store, key="ns/r.txt")
    assert isinstance(result, BlobData)
    assert result.data == "world"


async def test_list_blobs_with_prefix(registry_and_store):
    registry, store = registry_and_store
    await registry.call("write_blob", store=store, key="sage/a.json", data="{}")
    await registry.call("write_blob", store=store, key="sage_cloud/b.txt", data="x")
    result = await registry.call("list_blobs", store=store, prefix="sage/")
    assert isinstance(result, list)
    assert all(b.key.startswith("sage/") for b in result)
    assert len(result) == 1


async def test_delete_blob(registry_and_store):
    registry, store = registry_and_store
    await registry.call("write_blob", store=store, key="ns/del.txt", data="bye")
    deleted = await registry.call("delete_blob", store=store, key="ns/del.txt")
    assert deleted is True
    result = await registry.call("read_blob", store=store, key="ns/del.txt")
    assert isinstance(result, ToolError)
    assert result.error == "not_found"


# ---------------------------------------------------------------------------
# Page tools
# ---------------------------------------------------------------------------

async def test_create_page(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("create_page", store=store, name="dashboard", jsx_code="<div/>", description="main")
    assert isinstance(result, PageResult)
    assert result.url.endswith("/apps/dashboard")
    assert result.description == "main"


async def test_update_page(registry_and_store):
    registry, store = registry_and_store
    await registry.call("create_page", store=store, name="ui", jsx_code="<div>old</div>")
    result = await registry.call("update_page", store=store, name="ui", jsx_code="<div>new</div>")
    assert isinstance(result, PageResult)
    assert result.name == "ui"


async def test_list_pages(registry_and_store):
    registry, store = registry_and_store
    await registry.call("create_page", store=store, name="p1", jsx_code="<div/>")
    await registry.call("create_page", store=store, name="p2", jsx_code="<span/>")
    result = await registry.call("list_pages", store=store)
    assert isinstance(result, list)
    names = [p.name for p in result]
    assert "p1" in names and "p2" in names


async def test_delete_page(registry_and_store):
    registry, store = registry_and_store
    await registry.call("create_page", store=store, name="gone", jsx_code="<div/>")
    deleted = await registry.call("delete_page", store=store, name="gone")
    assert deleted is True
    pages = await registry.call("list_pages", store=store)
    assert not any(p.name == "gone" for p in pages)


# ---------------------------------------------------------------------------
# Schema tools
# ---------------------------------------------------------------------------

async def test_define_and_get_schema(registry_and_store):
    registry, store = registry_and_store
    schema = {"type": "object", "properties": {"x": {"type": "number"}}}
    result = await registry.call("define_schema", store=store, name="solve_input", schema=schema)
    assert isinstance(result, SchemaResult)
    assert result.definition == schema

    fetched = await registry.call("get_schema", store=store, name="solve_input")
    assert isinstance(fetched, SchemaResult)
    assert fetched.definition == schema


async def test_list_schemas(registry_and_store):
    registry, store = registry_and_store
    await registry.call("define_schema", store=store, name="s1", schema={"type": "string"})
    await registry.call("define_schema", store=store, name="s2", schema={"type": "number"})
    result = await registry.call("list_schemas", store=store)
    assert isinstance(result, list)
    names = [s.name for s in result]
    assert "s1" in names and "s2" in names


async def test_get_nonexistent_schema_returns_tool_error(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("get_schema", store=store, name="missing")
    assert isinstance(result, ToolError)
    assert result.error == "not_found"


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------

async def test_log_event(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("log_event", store=store, message="test started", level="info")
    assert isinstance(result, LogResult)
    assert result.message == "test started"
    assert result.id is not None


async def test_get_system_state(registry_and_store):
    registry, store = registry_and_store
    await registry.call("write_blob", store=store, key="k/1", data="a")
    await registry.call("create_page", store=store, name="p1", jsx_code="<div/>")
    result = await registry.call("get_system_state", store=store, uptime_seconds=10.0)
    assert isinstance(result, SystemState)
    assert result.blob_count == 1
    assert result.page_count == 1
    assert result.uptime_seconds == 10.0


async def test_list_artifacts(registry_and_store):
    registry, store = registry_and_store
    await registry.call("write_blob", store=store, key="ns/x", data="data")
    await registry.call("create_page", store=store, name="mypage", jsx_code="<div/>")
    await registry.call("log_event", store=store, message="artifact test")
    result = await registry.call("list_artifacts", store=store)
    assert isinstance(result, ArtifactSummary)
    assert any(b.key == "ns/x" for b in result.blobs)
    assert any(p.name == "mypage" for p in result.pages)
    assert any(e.message == "artifact test" for e in result.recent_events)


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------

async def test_create_page_duplicate_returns_tool_error(registry_and_store):
    registry, store = registry_and_store
    await registry.call("create_page", store=store, name="dup", jsx_code="<div/>")
    result = await registry.call("create_page", store=store, name="dup", jsx_code="<span/>")
    assert isinstance(result, ToolError)
    assert result.error == "validation_error"
    assert result.tool_name == "create_page"


async def test_update_nonexistent_page_returns_tool_error(registry_and_store):
    registry, store = registry_and_store
    result = await registry.call("update_page", store=store, name="ghost", jsx_code="<div/>")
    assert isinstance(result, ToolError)
    assert result.error == "not_found"
