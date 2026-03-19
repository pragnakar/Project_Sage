"""Unit tests for ArtifactStore multi-page app methods."""

import pytest
from groot.artifact_store import ArtifactStore


@pytest.fixture
async def store(tmp_path):
    s = ArtifactStore(
        db_path=str(tmp_path / "test.db"),
        artifact_dir=str(tmp_path / "artifacts"),
    )
    await s.init_db()
    return s


async def test_create_app_returns_base_url(store):
    result = await store.create_app("myapp", description="My app")
    assert result.name == "myapp"
    assert result.description == "My app"
    assert result.base_url.endswith("/apps/myapp/")
    assert result.created_at
    assert result.updated_at


async def test_create_app_duplicate_raises_value_error(store):
    await store.create_app("myapp")
    with pytest.raises(ValueError, match="already exists"):
        await store.create_app("myapp")


async def test_create_app_page_returns_url(store):
    await store.create_app("myapp")
    result = await store.create_app_page("myapp", "clock", "<h1>Clock</h1>", "A clock")
    assert result.app == "myapp"
    assert result.page == "clock"
    assert result.url.endswith("/apps/myapp/clock")
    assert result.description == "A clock"
    assert result.created_at


async def test_create_app_page_index_url_is_app_root(store):
    await store.create_app("myapp")
    result = await store.create_app_page("myapp", "index", "<h1>Home</h1>")
    assert result.url.endswith("/apps/myapp/")


async def test_create_app_page_missing_app_raises_key_error(store):
    with pytest.raises(KeyError, match="not found"):
        await store.create_app_page("noapp", "clock", "<h1>Clock</h1>")


async def test_create_app_page_duplicate_raises_value_error(store):
    await store.create_app("myapp")
    await store.create_app_page("myapp", "clock", "<h1>v1</h1>")
    with pytest.raises(ValueError, match="already exists"):
        await store.create_app_page("myapp", "clock", "<h1>v2</h1>")


async def test_update_app_page_replaces_jsx(store):
    await store.create_app("myapp")
    await store.create_app_page("myapp", "clock", "<h1>v1</h1>")
    result = await store.update_app_page("myapp", "clock", "<h1>v2</h1>")
    assert result.app == "myapp"
    assert result.page == "clock"
    source = await store.get_app_page_source("myapp", "clock")
    assert source == "<h1>v2</h1>"


async def test_update_app_page_missing_raises_key_error(store):
    await store.create_app("myapp")
    with pytest.raises(KeyError):
        await store.update_app_page("myapp", "missing", "<h1>x</h1>")


async def test_list_app_pages_returns_all_pages(store):
    await store.create_app("myapp")
    await store.create_app_page("myapp", "clock", "<h1>Clock</h1>")
    await store.create_app_page("myapp", "todos", "<h1>Todos</h1>")
    pages = await store.list_app_pages("myapp")
    assert len(pages) == 2
    names = {p.page for p in pages}
    assert names == {"clock", "todos"}


async def test_list_app_pages_missing_app_raises_key_error(store):
    with pytest.raises(KeyError):
        await store.list_app_pages("noapp")


async def test_get_app_layout_returns_empty_when_no_layout(store):
    await store.create_app("myapp")
    layout = await store.get_app_layout("myapp")
    assert layout == ""


async def test_get_app_layout_returns_jsx_when_set(store):
    await store.create_app("myapp", layout_jsx="function Layout({children}){return <div>{children}</div>;}")
    layout = await store.get_app_layout("myapp")
    assert "Layout" in layout


async def test_get_app_page_source_returns_jsx(store):
    await store.create_app("myapp")
    await store.create_app_page("myapp", "clock", "function Page(){return <h1>Clock</h1>;}")
    source = await store.get_app_page_source("myapp", "clock")
    assert "Clock" in source


async def test_get_app_page_source_missing_raises_key_error(store):
    await store.create_app("myapp")
    with pytest.raises(KeyError):
        await store.get_app_page_source("myapp", "missing")
