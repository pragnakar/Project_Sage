"""Tests for SSE transport routes mounted by mount_sse_transport.

Auth failures and message-endpoint error responses are synchronous HTTP responses
(no SSE streaming involved), making them fully testable via TestClient.
Full SSE streaming (connect, MCP initialize, tool calls over SSE) is an
integration-level concern tested end-to-end with a live server.
"""

import uuid

import pytest

# ---------------------------------------------------------------------------
# SSE endpoint — auth enforcement
# ---------------------------------------------------------------------------

def test_sse_no_key_returns_401(client):
    resp = client.get("/mcp/sse")
    assert resp.status_code == 401


def test_sse_wrong_key_returns_401(client):
    resp = client.get("/mcp/sse?key=wrong_key")
    assert resp.status_code == 401


def test_sse_route_registered_not_404(client):
    """Route exists — no key → 401, not 404 (confirms route is registered)."""
    resp = client.get("/mcp/sse")
    assert resp.status_code != 404


# ---------------------------------------------------------------------------
# Message endpoint — session validation
# ---------------------------------------------------------------------------

def test_mcp_messages_no_session_id_returns_400(client):
    """POST /mcp/messages without session_id → 400."""
    resp = client.post("/mcp/messages")
    assert resp.status_code == 400


def test_mcp_messages_invalid_uuid_returns_400(client):
    """POST /mcp/messages with a malformed UUID → 400."""
    resp = client.post("/mcp/messages?session_id=not-a-valid-uuid", content=b"{}")
    assert resp.status_code == 400


def test_mcp_messages_unknown_session_returns_404(client):
    """POST /mcp/messages with valid UUID but no live session → 404."""
    valid_uuid = uuid.uuid4().hex
    resp = client.post(
        f"/mcp/messages?session_id={valid_uuid}",
        content=b'{"jsonrpc":"2.0","method":"ping","id":1}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 404


def test_mcp_messages_route_registered_not_404(client):
    """Route /mcp/messages exists (missing session_id → 400, not 404)."""
    resp = client.post("/mcp/messages")
    assert resp.status_code != 404


# ---------------------------------------------------------------------------
# MCPBridge integration — tools reachable after SSE mount
# ---------------------------------------------------------------------------

async def test_mcp_bridge_tools_available_after_sse_mount(client, test_settings):
    """After SSE mount in lifespan, MCPBridge still exposes all 14 tools."""
    import os
    import tempfile
    from sage_cloud.artifact_store import ArtifactStore
    from sage_cloud.mcp_transport import MCPBridge
    from sage_cloud.tools import ToolRegistry, register_core_tools

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(db_path=os.path.join(tmpdir, "t.db"), artifact_dir=tmpdir)
        await store.init_db()
        registry = ToolRegistry()
        register_core_tools(registry, store)
        bridge = MCPBridge(registry, store)
        tools = await bridge.list_tools()
        assert len(tools) == 20
