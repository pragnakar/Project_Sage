"""Tests for sage_cloud/artifact_store.py — CRUD, edge cases, and system ops."""

import os
import tempfile

import pytest

from sage_cloud.artifact_store import ArtifactStore


@pytest.fixture
async def store():
    """Temporary ArtifactStore with isolated DB for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        s = ArtifactStore(db_path=db_path, artifact_dir=tmpdir)
        await s.init_db()
        yield s


# ---------------------------------------------------------------------------
# Blob CRUD
# ---------------------------------------------------------------------------

async def test_write_and_read_blob(store):
    result = await store.write_blob("ns/hello.txt", "hello world", "text/plain")
    assert result.key == "ns/hello.txt"
    assert result.size_bytes == len("hello world".encode())
    assert result.url == "/blobs/ns/hello.txt"

    blob = await store.read_blob("ns/hello.txt")
    assert blob.data == "hello world"
    assert blob.content_type == "text/plain"


async def test_blob_upsert_updates_data(store):
    await store.write_blob("ns/x", "v1", "text/plain")
    r1 = await store.read_blob("ns/x")

    await store.write_blob("ns/x", "v2", "text/plain")
    r2 = await store.read_blob("ns/x")

    assert r2.data == "v2"
    assert r1.created_at == r2.created_at  # created_at preserved on upsert


async def test_blob_upsert_preserves_created_at(store):
    result1 = await store.write_blob("ns/y", "original", "text/plain")
    result2 = await store.write_blob("ns/y", "updated", "text/plain")
    assert result1.created_at == result2.created_at


async def test_list_blobs_all(store):
    await store.write_blob("a/1", "data", "text/plain")
    await store.write_blob("b/2", "data", "text/plain")
    blobs = await store.list_blobs()
    keys = [b.key for b in blobs]
    assert "a/1" in keys
    assert "b/2" in keys


async def test_list_blobs_prefix(store):
    await store.write_blob("sage/result.json", "{}", "application/json")
    await store.write_blob("sage_cloud/state.txt", "ok", "text/plain")
    blobs = await store.list_blobs("sage/")
    assert all(b.key.startswith("sage/") for b in blobs)
    assert len(blobs) == 1


async def test_list_blobs_empty_prefix_returns_all(store):
    await store.write_blob("x/1", "a", "text/plain")
    await store.write_blob("y/2", "b", "text/plain")
    blobs = await store.list_blobs("")
    assert len(blobs) == 2


async def test_delete_blob(store):
    await store.write_blob("ns/del", "bye", "text/plain")
    deleted = await store.delete_blob("ns/del")
    assert deleted is True
    with pytest.raises(KeyError):
        await store.read_blob("ns/del")


async def test_delete_nonexistent_blob(store):
    result = await store.delete_blob("ns/ghost")
    assert result is False


async def test_read_nonexistent_blob_raises(store):
    with pytest.raises(KeyError):
        await store.read_blob("ns/missing")


# ---------------------------------------------------------------------------
# Page CRUD
# ---------------------------------------------------------------------------

async def test_create_and_get_page(store):
    result = await store.create_page("dashboard", "<div>hello</div>", "main dash")
    assert result.name == "dashboard"
    assert result.url.endswith("/apps/dashboard")
    assert result.description == "main dash"


async def test_create_page_duplicate_raises(store):
    await store.create_page("dash", "<div/>")
    with pytest.raises(ValueError):
        await store.create_page("dash", "<span/>")


async def test_update_page(store):
    await store.create_page("ui", "<div>old</div>")
    result = await store.update_page("ui", "<div>new</div>")
    assert result.name == "ui"
    page = await store.get_page("ui")
    assert page.updated_at == result.updated_at


async def test_update_nonexistent_page_raises(store):
    with pytest.raises(KeyError):
        await store.update_page("ghost", "<div/>")


async def test_list_pages(store):
    await store.create_page("p1", "<div/>")
    await store.create_page("p2", "<span/>")
    pages = await store.list_pages()
    names = [p.name for p in pages]
    assert "p1" in names and "p2" in names


async def test_delete_page(store):
    await store.create_page("del_me", "<div/>")
    deleted = await store.delete_page("del_me")
    assert deleted is True
    pages = await store.list_pages()
    assert not any(p.name == "del_me" for p in pages)


async def test_delete_nonexistent_page(store):
    assert await store.delete_page("ghost") is False


# ---------------------------------------------------------------------------
# Schema CRUD
# ---------------------------------------------------------------------------

async def test_define_and_get_schema(store):
    schema = {"type": "object", "properties": {"x": {"type": "number"}}}
    result = await store.define_schema("solve_input", schema)
    assert result.name == "solve_input"
    assert result.definition == schema


async def test_schema_upsert(store):
    await store.define_schema("s1", {"type": "string"})
    updated = await store.define_schema("s1", {"type": "number"})
    fetched = await store.get_schema("s1")
    assert fetched.definition == {"type": "number"}
    assert fetched.created_at == updated.created_at  # preserved


async def test_get_nonexistent_schema_raises(store):
    with pytest.raises(KeyError):
        await store.get_schema("missing")


async def test_list_schemas(store):
    await store.define_schema("s1", {"type": "string"})
    await store.define_schema("s2", {"type": "number"})
    schemas = await store.list_schemas()
    names = [s.name for s in schemas]
    assert "s1" in names and "s2" in names


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

async def test_log_and_list_events(store):
    for i in range(5):
        await store.log_event(f"event {i}", level="info")
    events = await store.list_events()
    assert len(events) == 5
    # Most recent first
    assert events[0].message == "event 4"
    assert events[-1].message == "event 0"


async def test_log_event_returns_correct_model(store):
    result = await store.log_event("started", level="info", context={"app": "sage"})
    assert result.id is not None
    assert result.message == "started"
    assert result.level == "info"


# ---------------------------------------------------------------------------
# System operations
# ---------------------------------------------------------------------------

async def test_get_system_state(store):
    await store.write_blob("k/1", "a", "text/plain")
    await store.write_blob("k/2", "b", "text/plain")
    await store.create_page("p1", "<div/>")
    await store.define_schema("s1", {"type": "object"})

    state = await store.get_system_state(uptime_seconds=42.0)
    assert state.blob_count == 2
    assert state.page_count == 1
    assert state.schema_count == 1
    assert state.artifact_count == 4
    assert state.uptime_seconds == 42.0


async def test_list_artifacts(store):
    await store.write_blob("ns/a", "data", "text/plain")
    await store.create_page("mypage", "<div/>")
    await store.define_schema("myschema", {"type": "object"})
    await store.log_event("test event")

    summary = await store.list_artifacts()
    assert any(b.key == "ns/a" for b in summary.blobs)
    assert any(p.name == "mypage" for p in summary.pages)
    assert any(s.name == "myschema" for s in summary.schemas)
    assert any(e.message == "test event" for e in summary.recent_events)
