"""Sage Cloud FastAPI application — lifespan, tool routes, health check, app module loader."""

import importlib
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import json as _json

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

_SHELL_DIR = Path(__file__).parent / "sage_shell"

from sage_cloud.artifact_store import ArtifactStore
from sage_cloud.auth import AuthContext, verify_api_key
from sage_cloud.config import Settings, get_settings
from sage_cloud.models import (
    AppBundle,
    AppBundleImportResult,
    AppPageMeta,
    AppPageResult,
    AppResult,
    ArtifactSummary,
    BlobData,
    BlobMeta,
    BlobResult,
    CreateAppPageRequest,
    CreateAppRequest,
    CreatePageRequest,
    DefineSchemaRequest,
    ListAppPagesRequest,
    LogEventRequest,
    LogResult,
    PageMeta,
    PageResult,
    SchemaMeta,
    SchemaResult,
    SystemState,
    ToolError,
    UpdateAppPageRequest,
    UpdatePageRequest,
    UpsertPageRequest,
    WriteBlobRequest,
)
from sage_cloud.app_routes import get_app_routes
from sage_cloud.jobs_api import router as jobs_router
from sage_cloud.builtin_pages import register_builtin_pages
from sage_cloud.mcp_transport import mount_sse_transport
from sage_cloud.page_server import PageServer
from sage_cloud.tools import ToolRegistry, register_core_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline request models for simple endpoints
# ---------------------------------------------------------------------------

class ReadBlobRequest(BaseModel):
    key: str


class ListBlobsRequest(BaseModel):
    prefix: str = ""


class DeleteBlobRequest(BaseModel):
    key: str


class DeletePageRequest(BaseModel):
    name: str


class GetSchemaRequest(BaseModel):
    name: str


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Respect dependency_overrides so tests can inject test settings
    settings_fn = app.dependency_overrides.get(get_settings, get_settings)
    settings: Settings = settings_fn()

    store = ArtifactStore(
        db_path=settings.SAGE_CLOUD_DB_PATH,
        artifact_dir=settings.SAGE_CLOUD_ARTIFACT_DIR,
    )
    await store.init_db()

    registry = ToolRegistry()
    register_core_tools(registry, store)

    page_server = PageServer(store)
    await register_builtin_pages(store)

    # Load enabled app modules — graceful skip on missing
    loaded_apps: dict = {}
    for app_name in settings.apps_list():
        try:
            module = importlib.import_module(f"sage_cloud_apps.{app_name}.loader")
            await module.register(registry, page_server, store)
            loaded_apps[app_name] = {
                "module": module,
                "meta": getattr(module, "APP_META", {}),
                "status": "loaded",
            }
            logger.info("Loaded Sage Cloud app module: %s", app_name)
        except ModuleNotFoundError:
            logger.warning("Sage Cloud app module not found, skipping: %s", app_name)
        except Exception as e:
            loaded_apps[app_name] = {"status": "error", "error": str(e)}
            logger.warning("Failed to load Sage Cloud app module %s: %s", app_name, e)

    # Mount page server routes + app discovery routes (idempotent)
    _dynamic_paths = {
        "/api/pages", "/api/pages/{name}/source", "/api/pages/{name}/meta",
        "/api/pages/{name}/export", "/api/pages/{name}/store",
        "/api/apps", "/api/apps/{name}", "/api/apps/{name}/health",
        "/api/apps/import",
        "/api/app-pages/{app_name}/{page_name}/source",
        "/api/app-pages/{app_name}/layout/source",
    }
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in _dynamic_paths]
    app.include_router(page_server.get_routes())
    app.include_router(get_app_routes())

    mount_sse_transport(app, registry, store, settings)

    app.state.store = store
    app.state.registry = registry
    app.state.page_server = page_server
    app.state.loaded_apps = loaded_apps
    app.state.start_time = time.time()

    logger.info("Sage Cloud runtime started. Apps: %s", settings.apps_list())

    yield

    logger.info("Sage Cloud runtime shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sage Cloud",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError):
    return JSONResponse(
        status_code=404,
        content=ToolError(error="not_found", detail=str(exc)).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=422,
        content=ToolError(error="validation_error", detail=str(exc)).model_dump(),
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_store(request: Request) -> ArtifactStore:
    return request.app.state.store


def get_registry(request: Request) -> ToolRegistry:
    return request.app.state.registry


def get_uptime(request: Request) -> float:
    return time.time() - request.app.state.start_time


# ---------------------------------------------------------------------------
# Health + config discovery
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}


@app.get("/api/config")
async def get_config():
    """Return runtime connection info for the dashboard (no auth required).

    Exposes the API key so the browser dashboard can auto-populate the key
    field and make authenticated requests without manual copy-paste.
    Safe for local/on-prem use — do not expose this endpoint externally.
    """
    import os
    settings = get_settings()
    host = settings.SAGE_CLOUD_HOST if settings.SAGE_CLOUD_HOST != "0.0.0.0" else "localhost"
    port = settings.SAGE_CLOUD_PORT
    keys = os.environ.get("SAGE_CLOUD_API_KEYS", "").strip()
    api_key = keys.split(",")[0].strip() if keys else "sage_sk_dev_key_01"
    return {
        "api_key": api_key,
        "base_url": f"http://{host}:{port}",
        "dashboard_url": f"http://{host}:{port}/",
    }


# ---------------------------------------------------------------------------
# React shell — SPA routes (must come after API routes so they don't shadow)
# ---------------------------------------------------------------------------

@app.get("/")
async def shell_root():
    return FileResponse(_SHELL_DIR / "index.html")


@app.get("/artifacts")
async def shell_artifacts():
    return FileResponse(_SHELL_DIR / "index.html")


@app.get("/apps/{path:path}")
async def shell_apps(path: str, request: Request, store: ArtifactStore = Depends(get_store)):
    from datetime import datetime, timezone
    primary = path.split("/")[0]
    if primary:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        if primary in loaded_apps:
            # Module app — track in-memory (no DB row for module apps)
            loaded_apps[primary]["last_opened_at"] = now
        elif "/" in path:
            # Sub-path present → multi-page app; touch the app DB row
            await store.touch_app(primary)
        else:
            # Standalone page or multi-page app root without trailing slash
            if not await store.touch_page(primary):
                await store.touch_app(primary)
    return FileResponse(_SHELL_DIR / "index.html")


# ---------------------------------------------------------------------------
# Tool routes — Storage
# ---------------------------------------------------------------------------

@app.post("/api/tools/write_blob", response_model=BlobResult)
async def write_blob(
    body: WriteBlobRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("write_blob", store=store, key=body.key, data=body.data, content_type=body.content_type)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/read_blob", response_model=BlobData)
async def read_blob(
    body: ReadBlobRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("read_blob", store=store, key=body.key)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/list_blobs")
async def list_blobs(
    body: ListBlobsRequest = ListBlobsRequest(),
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
) -> list[BlobMeta]:
    return await registry.call("list_blobs", store=store, prefix=body.prefix)


@app.post("/api/tools/delete_blob")
async def delete_blob(
    body: DeleteBlobRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("delete_blob", store=store, key=body.key)
    return {"deleted": result}


# ---------------------------------------------------------------------------
# Tool routes — Pages
# ---------------------------------------------------------------------------

@app.post("/api/tools/create_page", response_model=PageResult)
async def create_page(
    body: CreatePageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("create_page", store=store, name=body.name, jsx_code=body.jsx_code, description=body.description)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/update_page", response_model=PageResult)
async def update_page(
    body: UpdatePageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("update_page", store=store, name=body.name, jsx_code=body.jsx_code)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/upsert_page", response_model=PageResult)
async def upsert_page(
    body: UpsertPageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("upsert_page", store=store, name=body.name, jsx_code=body.jsx_code, description=body.description)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/list_pages")
async def list_pages(
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
) -> list[PageMeta]:
    return await registry.call("list_pages", store=store)


@app.post("/api/tools/delete_page")
async def delete_page(
    body: DeletePageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("delete_page", store=store, name=body.name)
    return {"deleted": result}


# ---------------------------------------------------------------------------
# Tool routes — Multi-page apps
# ---------------------------------------------------------------------------

@app.post("/api/tools/create_app", response_model=AppResult)
async def create_app_route(
    body: CreateAppRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("create_app", store=store,
                                 name=body.name, description=body.description, layout_jsx=body.layout_jsx)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/create_app_page", response_model=AppPageResult)
async def create_app_page_route(
    body: CreateAppPageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("create_app_page", store=store,
                                 app_name=body.app, page_name=body.page,
                                 jsx_code=body.jsx_code, description=body.description)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/update_app_page", response_model=AppPageResult)
async def update_app_page_route(
    body: UpdateAppPageRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("update_app_page", store=store,
                                 app_name=body.app, page_name=body.page, jsx_code=body.jsx_code)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/list_app_pages")
async def list_app_pages_route(
    body: ListAppPagesRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
) -> list[AppPageMeta]:
    result = await registry.call("list_app_pages", store=store, app_name=body.app)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


# ---------------------------------------------------------------------------
# Tool routes — Schemas
# ---------------------------------------------------------------------------

@app.post("/api/tools/define_schema", response_model=SchemaResult)
async def define_schema(
    body: DefineSchemaRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("define_schema", store=store, name=body.name, schema=body.definition)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/get_schema", response_model=SchemaResult)
async def get_schema(
    body: GetSchemaRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call("get_schema", store=store, name=body.name)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@app.post("/api/tools/list_schemas")
async def list_schemas(
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
) -> list[SchemaMeta]:
    return await registry.call("list_schemas", store=store)


# ---------------------------------------------------------------------------
# Tool routes — System
# ---------------------------------------------------------------------------

@app.post("/api/tools/log_event", response_model=LogResult)
async def log_event(
    body: LogEventRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    return await registry.call("log_event", store=store, message=body.message, level=body.level, context=body.context)


@app.get("/api/system/state", response_model=SystemState)
async def system_state(
    request: Request,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    uptime = get_uptime(request)
    return await registry.call("get_system_state", store=store, uptime_seconds=uptime)


@app.get("/api/system/artifacts", response_model=ArtifactSummary)
async def system_artifacts(
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    return await registry.call("list_artifacts", store=store)


# ---------------------------------------------------------------------------
# App bundle routes — export / import DB-registered multi-page apps
# ---------------------------------------------------------------------------

@app.get("/api/app-bundles")
async def list_app_bundles(store: ArtifactStore = Depends(get_store)) -> list[dict]:
    """List all multi-page apps registered via create_app (no auth required)."""
    return await store.list_apps()


@app.get("/api/app-bundles/{name}")
async def export_app_bundle(name: str, store: ArtifactStore = Depends(get_store)):
    """Export a multi-page app as a downloadable JSON bundle (no auth required)."""
    try:
        info = await store.get_app_info(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"App not found: {name!r}")

    pages_meta = await store.list_app_pages(name)
    pages = []
    for pm in pages_meta:
        try:
            jsx = await store.get_app_page_source(name, pm.page)
            pages.append({"page": pm.page, "jsx_code": jsx, "description": pm.description or ""})
        except KeyError:
            pass

    bundle = {
        "name": info["name"],
        "description": info["description"],
        "layout_jsx": info["layout_jsx"],
        "pages": pages,
    }
    return Response(
        content=_json.dumps(bundle, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}-bundle.json"'},
    )


@app.post("/api/app-bundles", response_model=AppBundleImportResult)
async def import_app_bundle(
    body: AppBundle,
    store: ArtifactStore = Depends(get_store),
    auth: AuthContext = Depends(verify_api_key),
):
    """Import a JSON bundle, creating or updating the app and all its pages."""
    try:
        await store.create_app(body.name, body.description, body.layout_jsx)
    except ValueError:
        pass  # app already exists — pages will be upserted below

    for p in body.pages:
        try:
            await store.create_app_page(body.name, p.page, p.jsx_code, p.description)
        except ValueError:
            await store.update_app_page(body.name, p.page, p.jsx_code)

    settings = get_settings()
    host = settings.SAGE_CLOUD_HOST if settings.SAGE_CLOUD_HOST != "0.0.0.0" else "localhost"
    url = f"http://{host}:{settings.SAGE_CLOUD_PORT}/apps/{body.name}/"
    return AppBundleImportResult(name=body.name, pages_imported=len(body.pages), url=url)


# ---------------------------------------------------------------------------
# Public blob read — makes the URL returned by write_blob actually resolve
# ---------------------------------------------------------------------------

@app.get("/blobs/{key:path}")
async def read_blob_public(key: str, store: ArtifactStore = Depends(get_store)):
    """Return raw blob content with its stored Content-Type.

    Reads are unauthenticated — pages can fetch their own data without needing
    /api/config. Writes still require X-Sage-Key.
    """
    try:
        blob = await store.read_blob(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Blob not found: {key!r}")
    return Response(content=blob.data, media_type=blob.content_type)


# ---------------------------------------------------------------------------
# Unified web-apps list — merges module apps, DB bundles, and pages
# ---------------------------------------------------------------------------

@app.get("/api/web-apps")
async def list_web_apps(request: Request, store: ArtifactStore = Depends(get_store)) -> list[dict]:
    """Unified list of all web apps: module apps, DB app bundles, and individual pages.

    Returns entries with a `kind` field:
      'app_bundle'       — loaded Python module app (has tools)
      'multi_page_bundle' — DB-registered multi-page app (pages only, no tools)
      'page'             — individual registered page

    Pages whose name-prefix matches a loaded module app are excluded from the
    'page' list; they are implicitly grouped under their app_bundle entry.
    """
    loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
    registry = request.app.state.registry
    all_pages = await store.list_pages()
    app_name_set = set(loaded_apps.keys())

    result = []

    # 1. Module apps (kind: app_bundle)
    for name, entry in loaded_apps.items():
        meta = entry.get("meta", {})
        status = entry.get("status", "error")
        app_tools = registry.list_tools(namespace=name) if status == "loaded" else []
        app_pages = [p for p in all_pages if p.name.startswith(f"{name}-")]
        # Derive timestamps from associated pages (module apps have no DB row)
        if app_pages:
            created_at = min(p.created_at for p in app_pages)
            updated_at = max(p.updated_at for p in app_pages)
        else:
            created_at = ""
            updated_at = ""
        result.append({
            "kind": "app_bundle",
            "name": name,
            "description": meta.get("description", ""),
            "url": f"/apps/{name}/",
            "status": status,
            "tools_count": len(app_tools),
            "page_count": len(app_pages),
            "created_at": created_at,
            "updated_at": updated_at,
            "last_opened_at": entry.get("last_opened_at", None),
        })

    # 2. DB multi-page apps (kind: multi_page_bundle)
    db_apps = await store.list_apps()
    for a in db_apps:
        result.append({
            "kind": "multi_page_bundle",
            "name": a["name"],
            "description": a.get("description", ""),
            "url": "/apps/" + a["name"] + "/",
            "status": "",
            "tools_count": 0,
            "page_count": a.get("page_count", 0),
            "created_at": a.get("created_at", ""),
            "updated_at": a.get("updated_at", ""),
            "last_opened_at": a.get("last_opened_at", None),
        })

    # 3. Individual pages — exclude those owned by loaded module apps
    for p in all_pages:
        idx = p.name.find("-")
        if idx >= 0 and p.name[:idx] in app_name_set:
            continue  # owned by a module app — already represented above
        result.append({
            "kind": "page",
            "name": p.name,
            "description": p.description or "",
            "url": f"/apps/{p.name}",
            "status": "",
            "tools_count": 0,
            "page_count": 1,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "last_opened_at": p.last_opened_at,
        })

    return result


# ---------------------------------------------------------------------------
# Generic tool call endpoint (MCP-to-HTTP bridge for G2)
# ---------------------------------------------------------------------------

@app.post("/api/tools/call")
async def tool_call(
    body: ToolCallRequest,
    store: ArtifactStore = Depends(get_store),
    registry: ToolRegistry = Depends(get_registry),
    auth: AuthContext = Depends(verify_api_key),
):
    result = await registry.call(body.tool, store=store, **body.arguments)
    if isinstance(result, ToolError):
        raise HTTPException(status_code=400, detail=result.model_dump())
    # Return serializable result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import uvicorn
    settings = get_settings()
    uvicorn.run("sage_cloud.server:app", host=settings.SAGE_CLOUD_HOST, port=settings.SAGE_CLOUD_PORT, reload=True)
