"""Unit tests for the four new multi-page app tool functions."""

import pytest
from sage_cloud.artifact_store import ArtifactStore
from sage_cloud.tools import create_app, create_app_page, list_app_pages, update_app_page
from sage_cloud.models import AppPageMeta, AppPageResult, AppResult


@pytest.fixture
async def store(tmp_path):
    s = ArtifactStore(
        db_path=str(tmp_path / "test.db"),
        artifact_dir=str(tmp_path / "artifacts"),
    )
    await s.init_db()
    return s


async def test_create_app_tool_returns_app_result(store):
    result = await create_app(store, name="dashboard", description="My dashboard")
    assert isinstance(result, AppResult)
    assert result.name == "dashboard"
    assert result.base_url.endswith("/apps/dashboard/")


async def test_create_app_page_tool_returns_app_page_result(store):
    await create_app(store, name="dashboard")
    result = await create_app_page(store, app_name="dashboard", page_name="clock",
                                   jsx_code="function Page(){return <h1>Clock</h1>;}")
    assert isinstance(result, AppPageResult)
    assert result.app == "dashboard"
    assert result.page == "clock"
    assert result.url.endswith("/apps/dashboard/clock")


async def test_update_app_page_tool_updates_jsx(store):
    await create_app(store, name="dashboard")
    await create_app_page(store, app_name="dashboard", page_name="clock",
                          jsx_code="function Page(){return <h1>v1</h1>;}")
    result = await update_app_page(store, app_name="dashboard", page_name="clock",
                                   jsx_code="function Page(){return <h1>v2</h1>;}")
    assert isinstance(result, AppPageResult)
    source = await store.get_app_page_source("dashboard", "clock")
    assert "v2" in source


async def test_list_app_pages_tool_returns_list(store):
    await create_app(store, name="dashboard")
    await create_app_page(store, app_name="dashboard", page_name="clock",
                          jsx_code="function Page(){return <h1>Clock</h1>;}")
    await create_app_page(store, app_name="dashboard", page_name="todos",
                          jsx_code="function Page(){return <h1>Todos</h1>;}")
    result = await list_app_pages(store, app_name="dashboard")
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(p, AppPageMeta) for p in result)
