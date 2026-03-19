"""Sage Cloud app discovery routes — GET /api/apps, /api/apps/{name}, /api/apps/{name}/health, DELETE /api/apps/{name}, GET /api/apps/{name}/export, POST /api/apps/import."""

import importlib
import io
import json
import logging
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from sage_cloud.auth import AuthContext, verify_api_key
from sage_cloud.models import AppDeleteResult, AppDetail, AppHealth, AppInfo, AppImportResult, AppsResponse, CoreInfo, PageMeta, ToolInfo

_SAGE_CLOUD_APPS_DIR = Path(__file__).parent.parent / "sage_cloud_apps"

logger = logging.getLogger(__name__)

_CORE_VERSION = "0.3.0"
_BUILTIN_PAGES = {"sage-dashboard", "sage-artifacts"}


def get_app_routes() -> APIRouter:
    """Return a router with all unauthenticated app discovery endpoints."""
    router = APIRouter()

    @router.get("/api/apps", response_model=AppsResponse)
    async def list_apps(request: Request):
        """List all loaded app modules with tool/page counts, plus core runtime summary."""
        registry = request.app.state.registry
        store = request.app.state.store
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})

        all_pages = await store.list_pages()
        core_page_count = sum(1 for p in all_pages if p.name in _BUILTIN_PAGES)
        core_tools = registry.list_tools(namespace="core")

        app_infos = []
        for name, entry in loaded_apps.items():
            meta = entry.get("meta", {})
            status = entry.get("status", "error")
            app_tools = registry.list_tools(namespace=name) if status == "loaded" else []
            app_pages = [p for p in all_pages if p.name.startswith(f"{name}-")]
            app_infos.append(AppInfo(
                name=name,
                namespace=name,
                tools_count=len(app_tools),
                pages_count=len(app_pages),
                status=status,
                description=meta.get("description", ""),
            ))

        return AppsResponse(
            apps=app_infos,
            core=CoreInfo(
                tools_count=len(core_tools),
                pages_count=core_page_count,
                version=_CORE_VERSION,
            ),
        )

    @router.get("/api/apps/{name}", response_model=AppDetail)
    async def get_app(name: str, request: Request):
        """Return full detail for a loaded app: tools with schemas, registered pages."""
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        if name not in loaded_apps:
            raise HTTPException(status_code=404, detail=f"App not found: {name!r}")

        entry = loaded_apps[name]
        status = entry.get("status", "error")
        registry = request.app.state.registry
        store = request.app.state.store

        app_tools = []
        app_pages: list[PageMeta] = []

        if status == "loaded":
            app_tools = [
                ToolInfo(name=t.name, description=t.description, parameters=t.parameters)
                for t in registry.list_tools(namespace=name)
            ]
            all_pages = await store.list_pages()
            app_pages = [p for p in all_pages if p.name.startswith(f"{name}-")]

        return AppDetail(
            name=name,
            namespace=name,
            tools=app_tools,
            pages=app_pages,
            status=status,
        )

    @router.get("/api/apps/{name}/health", response_model=AppHealth)
    async def app_health(name: str, request: Request):
        """Call the app's health_check() if it provides one, else return basic status."""
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        if name not in loaded_apps:
            raise HTTPException(status_code=404, detail=f"App not found: {name!r}")

        entry = loaded_apps[name]
        status = entry.get("status", "error")

        if status != "loaded":
            return AppHealth(name=name, status="error", checks={"error": entry.get("error", "load failed")})

        module = entry.get("module")
        health_fn = getattr(module, "health_check", None)
        if health_fn is None:
            return AppHealth(name=name, status="healthy", checks={})

        try:
            result = await health_fn()
            return AppHealth(
                name=name,
                status=result.get("status", "healthy"),
                checks=result.get("checks", {}),
            )
        except Exception as e:
            logger.warning("health_check() for app %r raised: %s", name, e)
            return AppHealth(name=name, status="error", checks={"exception": str(e)})

    @router.delete("/api/apps/{name}", response_model=AppDeleteResult)
    async def delete_app(
        name: str,
        request: Request,
        purge_data: bool = Query(default=False),
        force: bool = Query(default=False),
        auth: AuthContext = Depends(verify_api_key),
    ):
        """Unregister an app module and remove its pages. Requires auth.

        - purge_data=true: also delete blobs and schemas prefixed with the app name
        - force=true: required to delete a currently-loaded (running) app and remove its directory
        """
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        if name not in loaded_apps:
            raise HTTPException(status_code=404, detail=f"App not found: {name!r}")

        entry = loaded_apps[name]
        status = entry.get("status", "error")

        # Protection: loaded apps require force=true
        if status == "loaded" and not force:
            raise HTTPException(
                status_code=409,
                detail=f"App {name!r} is currently loaded. Use ?force=true to delete it.",
            )

        registry = request.app.state.registry
        store = request.app.state.store

        # 1. Unregister tools
        tools_removed = registry.unregister_namespace(name)

        # 2. Remove app pages (pages prefixed with "{name}-")
        all_pages = await store.list_pages()
        app_pages = [p.name for p in all_pages if p.name.startswith(f"{name}-")]
        for page_name in app_pages:
            await store.delete_page(page_name)

        # 3. Purge blobs and schemas if requested
        blobs_removed = 0
        schemas_removed = 0
        if purge_data:
            app_blobs = await store.list_blobs(prefix=f"{name}/")
            for blob in app_blobs:
                await store.delete_blob(blob.key)
                blobs_removed += 1

            all_schemas = await store.list_schemas()
            for schema in all_schemas:
                if schema.name.startswith(f"{name}/") or schema.name.startswith(f"{name}-"):
                    # ArtifactStore has no delete_schema — skip silently if absent
                    if hasattr(store, "delete_schema"):
                        await store.delete_schema(schema.name)
                        schemas_removed += 1

        # 4. Remove from loaded_apps registry
        del loaded_apps[name]

        # 5. Remove app directory from "sage_cloud_apps/ (only with force)
        directory_removed = False
        if force:
            app_dir = _SAGE_CLOUD_APPS_DIR / name
            if app_dir.exists() and app_dir.is_dir():
                shutil.rmtree(app_dir)
                directory_removed = True
                logger.info("Removed app directory: %s", app_dir)

        logger.info("Deleted app %r: tools=%d pages=%d blobs=%d schemas=%d dir=%s",
                    name, tools_removed, len(app_pages), blobs_removed, schemas_removed, directory_removed)

        return AppDeleteResult(
            name=name,
            tools_removed=tools_removed,
            pages_removed=len(app_pages),
            blobs_removed=blobs_removed,
            schemas_removed=schemas_removed,
            directory_removed=directory_removed,
        )

    @router.post("/api/apps/import", response_model=AppImportResult)
    async def import_app(
        request: Request,
        file: UploadFile = File(...),
        auth: AuthContext = Depends(verify_api_key),
    ):
        """Import an app module from a .zip archive and hot-load it into the runtime.

        The ZIP must contain a single top-level directory (the app name) with a
        valid Python package (__init__.py required). All paths must be within that
        directory — path traversal is rejected. Max upload size: 10 MB.
        """
        _MAX_BYTES = 10 * 1024 * 1024  # 10 MB

        # 1. Read and enforce size limit
        raw = await file.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="ZIP file exceeds 10 MB limit.")

        # 2. Validate it's a ZIP
        if not zipfile.is_zipfile(io.BytesIO(raw)):
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.")

        app_name: str = ""
        blobs_to_restore: list[tuple[str, str, str]] = []

        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            top_dirs = {n.split("/")[0] for n in names if "/" in n}
            bare_files = [n for n in names if "/" not in n]

            # --- PATH A: manifest.json at root → route by kind ---
            if "manifest.json" in bare_files:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                kind = manifest.get("kind", "")
                export_name = manifest.get("name", "")

                if kind == "page":
                    # Restore page JSX from pages/ directory
                    pages_list = manifest.get("pages", [])
                    if not pages_list:
                        raise HTTPException(status_code=400, detail="manifest.json has no pages listed.")
                    page_entry = pages_list[0]
                    page_name = page_entry.get("name") or export_name
                    jsx_path = page_entry.get("path", f"pages/{page_name}.jsx")
                    jsx_code = zf.read(jsx_path).decode("utf-8")
                    description = manifest.get("description", "")
                    store = request.app.state.store
                    try:
                        await store.create_page(page_name, jsx_code, description)
                    except ValueError:
                        await store.update_page(page_name, jsx_code)
                    # Restore blobs if present
                    for blob_entry in manifest.get("blobs", []):
                        k = blob_entry.get("key")
                        p = blob_entry.get("path")
                        ct = blob_entry.get("content_type", "application/json")
                        if k and p:
                            try:
                                await store.write_blob(k, zf.read(p).decode("utf-8"), ct)
                            except Exception:
                                pass
                    return AppImportResult(
                        name=page_name,
                        status="loaded",
                        tools_registered=0,
                        pages_registered=1,
                        message=f"Page {page_name!r} imported successfully.",
                    )

                elif kind == "module_app":
                    # Pre-read blobs before ZIP closes
                    for blob_entry in manifest.get("blobs", []):
                        k = blob_entry.get("key")
                        p = blob_entry.get("path")
                        ct = blob_entry.get("content_type", "application/json")
                        if k and p:
                            try:
                                blobs_to_restore.append((k, zf.read(p).decode("utf-8"), ct))
                            except Exception:
                                pass
                    # Identify app directory (skip manifest.json + blobs/)
                    non_meta_dirs = top_dirs - {"blobs"}
                    if len(non_meta_dirs) != 1:
                        raise HTTPException(
                            status_code=400,
                            detail=f"module_app ZIP must have exactly one app directory, found: {sorted(non_meta_dirs)}",
                        )
                    app_name = non_meta_dirs.pop()
                    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", app_name):
                        raise HTTPException(status_code=400, detail=f"App name {app_name!r} is not a valid Python identifier.")
                    # Validate path traversal (skip manifest.json and blobs/ entries)
                    for zip_entry in names:
                        if zip_entry == "manifest.json" or zip_entry.startswith("blobs/"):
                            continue
                        resolved = Path(zip_entry)
                        if resolved.is_absolute() or ".." in resolved.parts:
                            raise HTTPException(status_code=400, detail=f"Path traversal detected in ZIP entry: {zip_entry!r}")
                        if not zip_entry.startswith(f"{app_name}/"):
                            raise HTTPException(status_code=400, detail=f"ZIP entry {zip_entry!r} is outside the app directory.")
                    init_path = f"{app_name}/__init__.py"
                    if init_path not in names:
                        raise HTTPException(status_code=400, detail=f"ZIP must contain {init_path!r} to be a valid Python package.")
                    # Extract only app directory files
                    dest_dir = _SAGE_CLOUD_APPS_DIR / app_name
                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for zip_entry in names:
                        if zip_entry.startswith(f"{app_name}/"):
                            zf.extract(zip_entry, _SAGE_CLOUD_APPS_DIR)
                    logger.info("Extracted app %r to %s", app_name, dest_dir)

                else:
                    raise HTTPException(status_code=400, detail=f"Unknown manifest kind: {kind!r}")

            # --- PATH B: bare .jsx files → legacy page export ---
            elif bare_files and any(n.endswith(".jsx") for n in bare_files):
                jsx_files = [n for n in bare_files if n.endswith(".jsx")]
                if len(jsx_files) != 1:
                    raise HTTPException(status_code=400, detail=f"Page ZIP must contain exactly one .jsx file, found: {jsx_files}")
                page_name = jsx_files[0][:-4]
                jsx_code = zf.read(jsx_files[0]).decode("utf-8")
                description = ""
                meta_file = f"{page_name}_meta.json"
                if meta_file in bare_files:
                    try:
                        meta = json.loads(zf.read(meta_file).decode("utf-8"))
                        description = meta.get("description", "")
                    except Exception:
                        pass
                store = request.app.state.store
                try:
                    await store.create_page(page_name, jsx_code, description)
                except ValueError:
                    await store.update_page(page_name, jsx_code)
                return AppImportResult(
                    name=page_name,
                    status="loaded",
                    tools_registered=0,
                    pages_registered=1,
                    message=f"Page {page_name!r} imported successfully.",
                )

            # --- PATH C: unexpected bare files ---
            elif bare_files:
                raise HTTPException(
                    status_code=400,
                    detail=f"ZIP must have a single top-level directory. Found bare files: {bare_files[:3]}",
                )

            # --- PATH D: legacy module app (no manifest, no bare files) ---
            else:
                if len(top_dirs) != 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"ZIP must have exactly one top-level directory, found: {sorted(top_dirs)}",
                    )
                app_name = top_dirs.pop()
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", app_name):
                    raise HTTPException(status_code=400, detail=f"App name {app_name!r} is not a valid Python identifier.")
                for zip_entry in names:
                    resolved = Path(zip_entry)
                    if resolved.is_absolute() or ".." in resolved.parts:
                        raise HTTPException(status_code=400, detail=f"Path traversal detected in ZIP entry: {zip_entry!r}")
                    if not zip_entry.startswith(f"{app_name}/"):
                        raise HTTPException(status_code=400, detail=f"ZIP entry {zip_entry!r} is outside the app directory.")
                init_path = f"{app_name}/__init__.py"
                if init_path not in names:
                    raise HTTPException(status_code=400, detail=f"ZIP must contain {init_path!r} to be a valid Python package.")
                dest_dir = _SAGE_CLOUD_APPS_DIR / app_name
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                dest_dir.mkdir(parents=True, exist_ok=True)
                zf.extractall(_SAGE_CLOUD_APPS_DIR)
                logger.info("Extracted app %r to %s", app_name, dest_dir)

        # Hot-load for PATH A (module_app) and PATH D
        if not app_name:
            raise HTTPException(status_code=500, detail="Import routing error: app_name not set.")

        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        registry = request.app.state.registry
        page_server = request.app.state.page_server
        store = request.app.state.store

        module_path = f"sage_cloud_apps.{app_name}.loader"
        try:
            if module_path in sys.modules:
                module = importlib.reload(sys.modules[module_path])
            else:
                module = importlib.import_module(module_path)

            tools_before = len(registry.list_tools(namespace=app_name))
            pages_before = len([p for p in await store.list_pages() if p.name.startswith(f"{app_name}-")])

            await module.register(registry, page_server, store)

            tools_after = len(registry.list_tools(namespace=app_name))
            pages_after = len([p for p in await store.list_pages() if p.name.startswith(f"{app_name}-")])

            loaded_apps[app_name] = {
                "module": module,
                "meta": getattr(module, "APP_META", {}),
                "status": "loaded",
            }
            logger.info("Hot-loaded app %r: tools=%d pages=%d", app_name,
                        tools_after - tools_before, pages_after - pages_before)

            # Restore blobs from manifest-based exports
            for key, data, content_type in blobs_to_restore:
                await store.write_blob(key, data, content_type)

            return AppImportResult(
                name=app_name,
                status="loaded",
                tools_registered=tools_after - tools_before,
                pages_registered=pages_after - pages_before,
                message=f"App {app_name!r} imported and loaded successfully.",
            )

        except ModuleNotFoundError as e:
            loaded_apps[app_name] = {"status": "error", "error": str(e)}
            raise HTTPException(
                status_code=422,
                detail=f"App extracted but loader not found: {e}. Ensure loader.py exists in the ZIP.",
            )
        except Exception as e:
            loaded_apps[app_name] = {"status": "error", "error": str(e)}
            logger.warning("Failed to hot-load imported app %r: %s", app_name, e)
            raise HTTPException(
                status_code=422,
                detail=f"App extracted but failed to load: {e}",
            )

    @router.get("/api/apps/{name}/export")
    async def export_app(
        name: str,
        request: Request,
        include_data: bool = Query(default=False),
    ):
        """Export app module as a downloadable .zip archive.

        Packages "sage_cloud_apps/{name}/ into a ZIP. With ?include_data=true,
        also bundles the app's registered pages and blobs as JSON files.
        """
        loaded_apps: dict = getattr(request.app.state, "loaded_apps", {})
        if name not in loaded_apps:
            raise HTTPException(status_code=404, detail=f"App not found: {name!r}")

        blobs_exported = []
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Package the module directory
            app_dir = _SAGE_CLOUD_APPS_DIR / name
            if app_dir.exists() and app_dir.is_dir():
                for file_path in app_dir.rglob("*"):
                    if file_path.is_file() and "__pycache__" not in file_path.parts:
                        arcname = Path(name) / file_path.relative_to(app_dir)
                        zf.write(file_path, arcname)
            else:
                logger.warning("Export: app directory not found on disk for %r", name)

            # 2. Optionally bundle blobs into blobs/ directory
            if include_data:
                store = request.app.state.store
                app_blobs = await store.list_blobs(prefix=f"{name}/")
                for blob_item in app_blobs:
                    try:
                        blob_data = await store.read_blob(blob_item.key)
                        zf.writestr(f"blobs/{blob_item.key}", blob_data.data)
                        blobs_exported.append({
                            "key": blob_item.key,
                            "path": f"blobs/{blob_item.key}",
                            "content_type": blob_item.content_type,
                        })
                    except Exception:
                        pass

            # 3. Write manifest.json at ZIP root
            entry = loaded_apps[name]
            app_meta = entry.get("meta", {})
            manifest = {
                "sage_cloud_version": "0.3.0",
                "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "name": name,
                "description": app_meta.get("description", ""),
                "kind": "module_app",
                "pages": [],
                "blobs": blobs_exported,
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        buf.seek(0)
        filename = f"{name}.zip"
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
