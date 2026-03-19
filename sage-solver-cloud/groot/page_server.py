"""Groot page server — dynamic route registration and JSX source delivery."""

import io
import json as _json
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from groot.artifact_store import ArtifactStore
from groot.models import PageMeta, PageResult

logger = logging.getLogger(__name__)

# Page names: start with alphanumeric or underscore, then alphanumeric, hyphens, or underscores
_NAME_RE = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_\-]*$")


def _validate_name(name: str) -> None:
    """Raise ValueError if name is not URL-safe (alphanumeric, hyphens, underscores)."""
    if not _NAME_RE.match(name):
        raise ValueError(
            f"Page name must contain only alphanumeric characters and hyphens: {name!r}"
        )


class PageServer:
    """Serves JSX pages from the artifact store and handles static app-module registration."""

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    async def register_static(self, name: str, jsx_path: str, app_name: str = "") -> None:
        """Register a static JSX file from an app module's pages/ directory.

        Reads the file at jsx_path and upserts it into the artifact store.
        If app_name is provided, prefixes the page name: {app_name}-{name}.
        """
        full_name = f"{app_name}-{name}" if app_name else name
        _validate_name(full_name)
        jsx_code = Path(jsx_path).read_text(encoding="utf-8")
        try:
            await self.store.create_page(full_name, jsx_code)
        except ValueError:
            # Page already exists — update JSX to latest
            await self.store.update_page(full_name, jsx_code)
        logger.info("Registered static page: %s from %s", full_name, jsx_path)

    def get_routes(self) -> APIRouter:
        """Return a router with all page-serving endpoints (no auth required)."""
        router = APIRouter()
        store = self.store

        @router.get("/api/pages", response_model=list[PageMeta])
        async def list_pages():
            """List all registered pages."""
            return await store.list_pages()

        @router.get("/api/pages/{name}/source", response_class=PlainTextResponse)
        async def page_source(name: str):
            """Return raw JSX source as text/plain (for client-side Babel transform)."""
            try:
                jsx = await store.get_page_source(name)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"Page not found: {name!r}")
            return PlainTextResponse(jsx, media_type="text/plain")

        @router.get("/api/pages/{name}/meta", response_model=PageResult)
        async def page_meta(name: str):
            """Return page metadata (name, description, timestamps)."""
            try:
                return await store.get_page(name)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"Page not found: {name!r}")

        @router.get("/api/pages/{name}/export")
        async def page_export(name: str, include_data: bool = Query(default=False)):
            """Export a standalone page as a ZIP: manifest.json + pages/{name}.jsx + optional blobs/."""
            try:
                jsx = await store.get_page_source(name)
                meta = await store.get_page(name)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"Page not found: {name!r}")

            blobs_exported = []
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"pages/{name}.jsx", jsx)
                if include_data:
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
                manifest = {
                    "groot_version": "0.3.0",
                    "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "name": name,
                    "description": meta.description,
                    "kind": "page",
                    "pages": [{"name": name, "path": f"pages/{name}.jsx"}],
                    "blobs": blobs_exported,
                }
                zf.writestr("manifest.json", _json.dumps(manifest, indent=2))
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
            )

        # Layout route registered FIRST — more specific, must win over {page_name} wildcard
        @router.get("/api/app-pages/{app_name}/layout/source", response_class=PlainTextResponse)
        async def app_layout_source(app_name: str):
            """Return layout JSX for an app. Returns 204 No Content if no layout is set."""
            from fastapi.responses import Response
            layout = await store.get_app_layout(app_name)
            if not layout:
                return Response(status_code=204)
            return PlainTextResponse(layout, media_type="text/plain")

        @router.get("/api/app-pages/{app_name}/{page_name}/source", response_class=PlainTextResponse)
        async def app_page_source(app_name: str, page_name: str):
            """Return raw JSX for an app page (no auth — browser fetches this at runtime)."""
            try:
                jsx = await store.get_app_page_source(app_name, page_name)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"App page not found: {app_name}/{page_name}")
            return PlainTextResponse(jsx, media_type="text/plain")

        # Store routes registered BEFORE {name} wildcard to avoid shadowing
        _STORE_KEY_PREFIX = "_page_store/"

        @router.get("/api/pages/{name}/store")
        async def page_store_get(name: str):
            """Return this page's persistent JSON store. Returns {} on first use.

            Pages call this on mount to restore saved state. No API key required.
            """
            try:
                blob = await store.read_blob(_STORE_KEY_PREFIX + name)
                return JSONResponse(_json.loads(blob.data))
            except KeyError:
                return JSONResponse({})

        @router.put("/api/pages/{name}/store")
        async def page_store_put(name: str, request: Request):
            """Overwrite this page's persistent JSON store. No API key required.

            Pages call this whenever state changes. Body must be a JSON object.
            Scoped by page name — one page cannot overwrite another's store.
            """
            body = await request.body()
            try:
                data_str = body.decode("utf-8")
                _json.loads(data_str)  # validate JSON
            except Exception:
                raise HTTPException(status_code=400, detail="Request body must be valid JSON")
            await store.write_blob(_STORE_KEY_PREFIX + name, data_str, "application/json")
            return JSONResponse({"ok": True})

        return router
