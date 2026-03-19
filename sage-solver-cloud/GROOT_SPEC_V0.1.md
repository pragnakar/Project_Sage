# Project Groot — Build Specification
# (living document — updated to reflect actual built state)

**Original draft:** 2026-03-13
**Author:** Claude (Cowork instance) — for Claude Code execution
**Repo:** `github.com/pragnakar/Project_Groot`
**Current version:** v0.3.0 (266 tests, SHA 01c7cd8)
**First Groot app:** Deferred — sage/ will integrate from its own repo (Project Sage)
**App module interface:** Generalized — any developer or AI can fork and build their own Groot app

---

## 1. What Groot Is

Groot is a **LLM runtime environment**. It gives any MCP-compatible LLM agent a persistent execution layer consisting of:

- A web server it can add pages and routes to
- A persistent artifact store it can read and write
- A validated tool interface it calls through
- A pluggable domain module system for domain-specific tools and pages

**The LLM is always external.** Claude, ChatGPT, or any MCP client calls Groot tools over MCP (stdio or SSE) or REST HTTP. Groot never embeds a model.

**The flywheel:** Every artifact the LLM creates (React components, pages, blobs, schemas) is stored in Groot's artifact store. Each session builds on the last. The runtime becomes more capable as artifacts accumulate.

**The in-chat design pattern:** Claude in Chat (claude.ai/Cowork) generates React components as artifacts for human review. Approved components are staged to Groot via `create_page`. Chat is the design surface and QA layer before artifacts enter the runtime.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LLM CLIENTS (external)                 │
│                                                          │
│  Claude Desktop  ChatGPT  Claude in Chat  Any MCP Client │
│  (MCP stdio)     (MCP SSE) (design surface) (HTTP)       │
└──────────────────────────┬──────────────────────────────┘
                           │ MCP / HTTP
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   GROOT RUNTIME (FastAPI)                 │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────┐              │
│  │  Tool Registry   │  │  MCP Transport   │              │
│  │  (pluggable)     │  │  (stdio + SSE)   │              │
│  └────────┬────────┘  └────────┬─────────┘              │
│           └──────────┬─────────┘                        │
│                      ▼                                   │
│           ┌──────────────────────┐                       │
│           │   Runtime Core       │                       │
│           │   validates · routes │                       │
│           │   sandboxes · auth   │                       │
│           └────┬──────────┬─────┘                       │
│                │          │                              │
│   ┌────────────▼──┐  ┌───▼────────────┐                 │
│   │ Artifact Store │  │  Page Server   │                 │
│   │ SQLite + fs    │  │  React shell   │                 │
│   │ blobs · pages  │  │  dynamic routes│                 │
│   │ schemas · apps │  │  /apps/:name   │                 │
│   │ app_pages      │  │  /apps/:name/  │                 │
│   └───────────────┘  └────────────────┘                 │
└──────────────────────────┬──────────────────────────────┘
                           │ imports · registers tools
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  GROOT APPS (domain modules)              │
│                                                          │
│  _example/        sage/           hermes/                │
│  (ships w/ Groot) (own repo)      (future)               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Repository Structure

```
Project_Groot/
├── README.md
├── GROOT_SPEC_V0.1.md         ← This document
├── pyproject.toml             ← groot-runtime package (v0.3.0)
├── claude_desktop_config.json ← MCP stdio config for Claude Desktop
│
├── groot/                     ← Core runtime (domain-agnostic)
│   ├── __init__.py            ← version = "0.3.0"
│   ├── __main__.py            ← Entry point: python -m groot [--mcp-stdio] [--http] [--port]
│   ├── server.py              ← FastAPI app, startup lifespan, all HTTP routes
│   ├── tools.py               ← Core tool definitions + registry (19 tools)
│   ├── artifact_store.py      ← SQLite + filesystem persistence (all CRUD)
│   ├── page_server.py         ← Page routes: source, meta, export, store endpoints
│   ├── app_routes.py          ← App module HTTP routes: CRUD, export/import ZIP
│   ├── app_interface.py       ← GrootAppModule Protocol (documentation-first)
│   ├── builtin_pages.py       ← groot-dashboard + groot-artifacts JSX (Python strings)
│   ├── auth.py                ← API key middleware (X-Groot-Key header + ?key= param)
│   ├── mcp_transport.py       ← MCP stdio + SSE transport (MCPBridge class)
│   ├── models.py              ← Pydantic schemas for all tool I/O
│   └── config.py              ← Settings (env vars, .env)
│
├── groot_apps/
│   └── _example/              ← Reference implementation (ships with Groot)
│       ├── __init__.py
│       ├── loader.py          ← register(): echo_tool + hello.jsx page
│       └── README.md          ← "Build Your First Groot App" guide
│
├── docs/
│   └── APP_MODULE_GUIDE.md    ← Developer guide: how to build a Groot app module
│
├── groot-shell/
│   └── index.html             ← Self-contained React shell (Babel CDN, no build step)
│                              ← Path-based router, DynamicPage + DynamicAppPage
│
└── tests/
    ├── test_tools.py
    ├── test_artifact_store.py
    ├── test_page_server.py
    ├── test_auth.py
    ├── test_app_interface.py
    ├── test_app_store.py
    ├── test_app_tools.py
    ├── test_app_page_routes.py
    ├── test_delete_app.py
    ├── test_export_app.py
    ├── test_import_app.py
    └── test_server.py
```

---

## 4. Core Tool Interface

Groot's built-in tools — available to any LLM agent, domain-agnostic. All return Pydantic models.

### 4.1 Storage Tools

```python
write_blob(key: str, data: str | bytes, content_type: str = "text/plain") -> BlobResult
# Writes a blob to the artifact store. Key format: "namespace/name"
# Returns: { key, size_bytes, created_at, url }

read_blob(key: str) -> BlobResult
# Reads a blob. Returns: { key, data, content_type, created_at }

list_blobs(prefix: str = "") -> list[BlobMeta]
# Lists blobs matching prefix. Returns: [{ key, size_bytes, created_at }]

delete_blob(key: str) -> bool
# Deletes a blob. Returns True if deleted.
```

### 4.2 Page Tools

```python
create_page(name: str, jsx_code: str, description: str = "") -> PageResult
# Stores a React component and registers it as a live route at /apps/{name}
# jsx_code: valid React JSX (functional component, default export)
# Returns: { name, url, created_at }

update_page(name: str, jsx_code: str) -> PageResult
# Replaces an existing page's JSX. Hot-updates the route.

upsert_page(name: str, jsx_code: str, description: str = "") -> PageResult
# Create-or-update: creates if absent, updates if present. Used by builtin startup.

list_pages() -> list[PageMeta]
# Lists all registered pages: [{ name, url, description, created_at, updated_at, last_opened_at }]

delete_page(name: str) -> bool
```

### 4.3 Schema Tools

```python
define_schema(name: str, schema: dict) -> SchemaResult
# Stores a JSON schema under a name. Used for structured data validation.

get_schema(name: str) -> SchemaResult

list_schemas() -> list[SchemaMeta]
```

### 4.4 System Tools

```python
log_event(message: str, level: str = "info", context: dict = {}) -> LogResult
# Appends a structured log entry. Returns: { id, timestamp, message, level }

get_system_state() -> SystemState
# Returns: { uptime, artifact_count, page_count, blob_count, registered_apps }

list_artifacts() -> ArtifactSummary
# Returns full inventory: pages, blobs, schemas, recent logs

get_groot_config() -> GrootConfig
# Returns: { api_key, host, port, base_url, dashboard_url }
# Tool #15 — lets Claude discover connection details via MCP without manual copy-paste
```

### 4.5 Multi-page App Tools

```python
create_app(name: str, description: str = "") -> AppResult
# Creates a multi-page app entry (DB-only, no Python module). Served at /apps/{name}/

create_app_page(app: str, page: str, jsx_code: str, description: str = "") -> AppPageResult
# Adds a page to a multi-page app. Served at /apps/{app}/{page}
# Use page="index" for the layout/nav component (wraps child pages via {children} prop)

update_app_page(app: str, page: str, jsx_code: str) -> AppPageResult
# Replaces a page's JSX in a multi-page app.

list_app_pages(app: str) -> list[AppPageMeta]
# Lists all pages in a multi-page app.
```

*Total core tools: 19 (tools 1-14 original, 15 = get_groot_config, 16-19 = multi-page app tools)*

---

## 5. Artifact Store — Data Model

SQLite database at `groot.db`.

```sql
-- Blobs: arbitrary data keyed by namespace/name
CREATE TABLE blobs (
    key          TEXT PRIMARY KEY,
    data         BLOB NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text/plain',
    size_bytes   INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- Pages: standalone React components registered as routes at /apps/{name}
CREATE TABLE pages (
    name          TEXT PRIMARY KEY,
    jsx_code      TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    last_opened_at TEXT              -- UTC ISO; touched on every GET /apps/{name}
);

-- Schemas: named JSON schemas
CREATE TABLE schemas (
    name        TEXT PRIMARY KEY,
    schema_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Event log: structured history
CREATE TABLE events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    level        TEXT NOT NULL DEFAULT 'info',
    message      TEXT NOT NULL,
    context_json TEXT NOT NULL DEFAULT '{}'
);

-- Multi-page apps: DB-only app registry (no Python module required)
CREATE TABLE apps (
    name          TEXT PRIMARY KEY,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    last_opened_at TEXT              -- UTC ISO; touched on every GET /apps/{name}/
);

-- Multi-page app pages: belong to an app, ON DELETE CASCADE
CREATE TABLE app_pages (
    app           TEXT NOT NULL,
    page          TEXT NOT NULL,
    jsx_code      TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (app, page),
    FOREIGN KEY (app) REFERENCES apps(name) ON DELETE CASCADE
);
```

**Schema migrations** are idempotent — new columns added via `ALTER TABLE ... ADD COLUMN` wrapped in try/except, so existing databases upgrade automatically on server start.

---

## 6. Page Server — React Shell

Groot serves a single React shell application that dynamically loads registered pages.

**How it works:**
1. LLM calls `create_page("my-dashboard", jsx_code)`
2. Groot stores the JSX in the artifact store
3. Page server exposes `GET /api/pages/my-dashboard/source` → returns the JSX
4. React shell fetches and renders it at `/apps/my-dashboard`

**Shell routing (path-based, no hash):**
```
/                      ← Groot dashboard (built-in)
/artifacts             ← Artifact browser (built-in)
/apps/{name}           ← Standalone page (pages table)
/apps/{name}/          ← Multi-page app root (apps + app_pages tables)
/apps/{name}/{page}    ← Multi-page app sub-page
/docs                  ← FastAPI auto-docs
/health                ← Health check
```

**JSX delivery:**
The shell fetches raw JSX from `/api/pages/{name}/source` (or `/api/app-pages/{app}/{page}/source`), transforms it with Babel standalone (CDN), and renders it. No build step required.

Before eval, the shell:
- Strips `import` / `export` statements (invalid in browser eval context)
- Captures the exported component name if it differs from `Page`
- Injects all 9 common React hooks as named variables into the eval scope

**Multi-page app rendering:**
`DynamicAppPage` fetches the layout JSX (`page=index`) and the current page JSX in parallel. The layout receives `children` prop; the current page renders inside the layout.

**Page server HTTP endpoints (unauthenticated — browser-facing):**
```
GET  /api/pages                         → list all pages (PageMeta[])
GET  /api/pages/{name}/source           → raw JSX string
GET  /api/pages/{name}/meta             → PageMeta JSON
GET  /api/pages/{name}/export           → ZIP download (manifest-based, see §8)
GET  /api/pages/{name}/store            → list blobs in page's namespace
PUT  /api/pages/{name}/store            → write a blob in page's namespace
GET  /api/app-pages/{app}/layout/source → layout JSX (204 if no layout)
GET  /api/app-pages/{app}/{page}/source → page JSX
```

---

## 7. App Module Interface

Domain apps register themselves with Groot at startup via a standardized protocol. **Groot ships domain-agnostic** — any developer or AI agent can fork the repo, create `groot_apps/{name}/loader.py`, and have a working app module.

### 7.1 The Protocol

```python
# groot/app_interface.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class GrootAppModule(Protocol):
    """Every Groot app module must expose a loader that satisfies this protocol."""

    async def register(
        self,
        tool_registry: "ToolRegistry",
        page_server: "PageServer",
        store: "ArtifactStore"
    ) -> None:
        """Called by Groot runtime at startup. Register tools, pages, and any
        artifacts your app needs. Groot passes in the shared runtime services."""
        ...

    async def health_check(self) -> dict:
        """Optional. Return { status: "ok"|"error", ... }"""
        ...
```

### 7.2 Example App (ships with Groot)

```python
# groot_apps/_example/loader.py

APP_META = {
    "name": "_example",
    "version": "0.1.0",
    "description": "Reference scaffold — one echo tool and one hello page",
}

async def register(tool_registry, page_server, store):
    @tool_registry.tool(name="example.echo", description="Echoes a message")
    async def echo(message: str) -> EchoResult:
        return EchoResult(echo=message)

    await page_server.upsert_page("_example-hello", HELLO_JSX, "Hello world demo page")
```

### 7.3 Groot Startup

```python
# groot/server.py (simplified)

ENABLED_APPS = os.getenv("GROOT_APPS", "_example").split(",")

@asynccontextmanager
async def lifespan(app):
    store = ArtifactStore(...)
    await store.init_db()
    for app_name in ENABLED_APPS:
        try:
            module = importlib.import_module(f"groot_apps.{app_name}.loader")
            await module.register(tool_registry, page_server, store)
            loaded_apps[app_name] = {"module": module, "meta": module.APP_META, "status": "loaded"}
        except ModuleNotFoundError:
            pass  # app not installed — silently skipped
        except Exception as e:
            loaded_apps[app_name] = {"module": None, "meta": {}, "status": "error", "error": str(e)}
    yield
```

### 7.4 App Module HTTP API (authenticated)

```
GET    /api/apps                  → list loaded apps (name, status, tools, pages)
GET    /api/apps/{name}           → app detail: tools, pages, health
GET    /api/apps/{name}/health    → delegates to module.health_check()
DELETE /api/apps/{name}           → unload app; ?purge_data=true deletes blobs+schemas+pages;
                                    ?force=true also removes directory from disk
GET    /api/apps/{name}/export    → ZIP download (manifest-based, see §8)
POST   /api/apps/import           → multipart ZIP upload → extract → hot-load
```

### 7.5 Convention

| Item | Convention |
|---|---|
| Directory | `groot_apps/{app_name}/loader.py` |
| Entry point | `async register(tool_registry, page_server, store)` |
| Tool namespace | `{app_name}.{tool_name}` (e.g., `sage.solve_optimization`) |
| Page namespace | `{app_name}-{page_name}` (e.g., `sage-dashboard`) |
| Config | App reads its own env vars; Groot passes shared services only |
| Metadata | `APP_META` dict in loader.py: name, version, description |

---

## 8. Export / Import — ZIP Bundle Format

Groot uses a unified manifest-based ZIP format for both standalone page exports and module app exports.

### 8.1 ZIP Structure

```
# Standalone page export  (GET /api/pages/{name}/export)
manifest.json
pages/{name}.jsx
blobs/{key}              ← only when ?include_data=true

# Module app export  (GET /api/apps/{name}/export)
manifest.json
{name}/                  ← full Python app directory
  __init__.py
  loader.py
  ...
blobs/{key}              ← only when ?include_data=true
```

### 8.2 Manifest Schema

```json
{
  "groot_version": "0.3.0",
  "exported_at": "2026-03-18T18:00:00Z",
  "name": "my-page",
  "description": "...",
  "kind": "page",          // "page" | "module_app"
  "pages": [
    { "name": "my-page", "path": "pages/my-page.jsx" }
  ],
  "blobs": [
    { "key": "my-page/data", "path": "blobs/my-page/data", "content_type": "application/json" }
  ]
}
```

### 8.3 Import Routing (POST /api/apps/import)

```
PATH A — manifest.json present at ZIP root:
    kind = "page"        → restore page JSX + blobs → return immediately
    kind = "module_app"  → pre-read blobs, extract app dir, fall through to hot-load
    kind = unknown       → 400

PATH B — no manifest, bare .jsx files present → legacy page import

PATH C — no manifest, other bare files → 400 (unrecognized format)

PATH D — no manifest, no bare files → legacy module app (single top-level dir)

Hot-load (PATH A module_app + PATH D):
    importlib.import_module() or reload() if already in sys.modules
    blob restore executes after successful hot-load
```

---

## 9. Multi-page App Bundles

Multi-page apps are **DB-only** — no Python module required. The LLM creates an app record and its pages purely through tool calls or REST.

```
POST /api/app-bundles          → create multi-page app from JSON bundle
GET  /api/app-bundles/{name}   → export multi-page app as JSON bundle
```

**Bundle JSON format:**
```json
{
  "name": "my-app",
  "description": "...",
  "pages": [
    { "page": "index", "jsx_code": "...", "description": "Layout/nav" },
    { "page": "home",  "jsx_code": "...", "description": "Home page" }
  ]
}
```

**Routing:**
- `/apps/my-app/` → renders `index` layout + `home` (default)
- `/apps/my-app/clock` → renders `index` layout + `clock` sub-page
- Layout receives `{children}` prop; sub-pages render inside it

---

## 10. Unified Web Apps API

`GET /api/web-apps` returns all three kinds of hosted content in a single list, for the dashboard and any client that wants to enumerate what's running.

```json
[
  {
    "name": "todo-app",
    "kind": "page",              // "page" | "app_bundle" | "module_app"
    "description": "...",
    "url": "http://localhost:8000/apps/todo-app",
    "created_at": "2026-03-18T10:00:00Z",
    "updated_at": "2026-03-18T10:05:00Z",
    "last_opened_at": "2026-03-18T18:30:00Z"   // null if never opened
  }
]
```

**`last_opened_at` tracking:**
- Standalone pages: updated in the `pages` table on every `GET /apps/{name}`
- Multi-page apps: updated in the `apps` table on every `GET /apps/{name}/`
- Module apps: stored in `loaded_apps[name]` dict in memory (resets on restart)
- Module app `created_at`/`updated_at` derived from min/max of associated `{name}-*` pages

---

## 11. Built-in Pages

Both built-in pages are stored as Python triple-quoted JSX strings in `groot/builtin_pages.py` and upserted to the pages table on every server start. They are served by the same page server as any user-created page.

### 11.1 Groot Dashboard (`/`)

- **API key field:** debounced validation against `/api/system/state`, color dot indicator; synced from `/api/config` on load (prevents stale key after restart)
- **Available Web Apps:** lists all three kinds with three-column timestamp display (Created / Modified / Opened), search/filter, per-row action dropdowns
- **Actions per kind:**
  - `page`: View · Edit source · Export App · Export App + Data · Delete
  - `app_bundle`: View · Export App · Export App + Data · Delete
  - `multi_page_bundle`: View · Export Bundle · Delete
- **Export App + Data**: confirmation modal before download; loading toast during fetch
- **Import ZIP**: spinner, success/error toast, inline message banner
- **System stats grid**: Pages / Blobs / Schemas / Artifacts — each card clickable, navigates to the corresponding Artifact Browser tab
- **Uptime**: formatted as "Xm Ys" / "Xh Ym" (not raw seconds)

### 11.2 Artifact Browser (`/artifacts`)

- Tabs: Pages · Blobs · Schemas · Events
- Fetches `/api/config` on mount to obtain API key; passes `X-Groot-Key` on all authenticated calls
- Pages tab: search/filter, compact/table view toggle, source modal viewer
- Blobs tab: key, size, content type, timestamp, inline Inspect (read content)
- Schemas tab: name, timestamp, field count, inline Inspect
- Initial tab from `?tab=` query param (deep-linkable from dashboard stat cards)

---

## 12. Authentication

**v0.1 MVP:** API key middleware only.

```python
# Header: X-Groot-Key: groot_sk_xxxxxxxxxxxx
# Query param (for MCP SSE): ?key=groot_sk_xxxxxxxxxxxx
# Keys stored in GROOT_API_KEYS env var (comma-separated)
# GET /api/config (unauthenticated): returns api_key for browser-side auto-discovery
# Dev bypass: GROOT_DEV_BYPASS=true skips key check (never enable in production)
```

**Key auto-generation:** On startup, if `GROOT_API_KEYS` is not set, a random key is generated and printed to stdout. If it is set, the env var is respected.

---

## 13. Build Phases — Actual Status

| Phase | Description | Status | SHA | Tests |
|---|---|---|---|---|
| G1 | Runtime core (tools, store, auth, server) | ✅ Complete | 79ac953 | 105 |
| G2 | MCP transport (stdio + SSE) | ✅ Complete | 87a5845 | 125 |
| G3 | Page server + React shell | ✅ Complete | d1ed76c | 160 |
| G-APP | Generalized app module interface | ✅ Complete | 22986a5 | 172 |
| Shell hotfixes | JSX import/export strip, hook injection | ✅ Complete | ed91b20 | 172 |
| Delete App | DELETE /api/apps/{name} + purge | ✅ Complete | fed4ea9 | 184 |
| Export App | GET /api/apps/{name}/export ZIP | ✅ Complete | 406322a | 197 |
| Import App | POST /api/apps/import ZIP hot-load | ✅ Complete | merged | 211 |
| Dashboard v0.3.0 | UI overhaul (two review rounds) | ✅ Complete | 0fdc443 | 211 |
| v0.3.0-session-2 | Config tool, multi-page apps, URL fixes | ✅ Complete | 7f638fa | 243→266 |
| v0.3.0-session-3 | Dual export, last_opened_at, web-apps, UX | ✅ Complete | 01c7cd8 | 266 |

**v0.3.0-session-2 highlights:**
- MCP stdio + HTTP combined mode: uvicorn logs redirected to stderr (prevents MCP JSON stream corruption)
- `/api/config` endpoint: browser-discoverable api_key, base_url, dashboard_url
- `get_groot_config()` tool #15: Claude discovers connection details via MCP
- Multi-page app support: `apps` + `app_pages` DB tables; tools 16-19; `DynamicAppPage` shell component; path-based routing replaces hash-based
- Multi-page JSON bundle import/export (`/api/app-bundles`)
- Dashboard: 5-bug fix round (hash links, shell chrome, upsert_page, stat-card nav, artifact tab routing)

**v0.3.0-session-3 highlights:**
- Manifest-based ZIP export for both pages and module apps (unified `manifest.json` format)
- 4-path import routing (manifest page / manifest module_app / bare .jsx / legacy module app)
- `last_opened_at` column on pages + apps; `touch_page()` / `touch_app()` helpers
- `GET /api/web-apps`: unified endpoint — all three kinds with timestamps
- Dashboard: three-column timestamp display (Created / Modified / Opened)
- Dashboard: Export App + Data confirmation modal, loading toast, filename from Content-Disposition
- Page store endpoints: `GET/PUT /api/pages/{name}/store`

---

## 14. Key Design Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | LLM topology | External client | LLM calls Groot via MCP/HTTP. Never embedded. |
| 2 | UI framework | React | LLM codegen quality for JSX >> Flutter/Dart. Component reuse maps to artifact accumulation. |
| 3 | JSX delivery | Babel standalone eval | No build step. Fast to ship. LLM-generated JSX stripped of import/export before eval; hooks injected into scope. |
| 4 | Storage | SQLite (no filesystem) | Zero-dependency for MVP. Upgrade path to Postgres. |
| 5 | MCP transport | stdio + SSE | Both. stdio for Claude Desktop, SSE for remote clients. |
| 6 | App modules | Import at startup | Simple, no service discovery overhead for MVP. |
| 7 | State isolation | Per-request (no module-level state) | Multi-app from day one. Learned from sage-mcp's ServerState limitation. |
| 8 | In-chat design flow | Claude chat → approve → create_page | Chat is Groot's design surface. Every page reviewed before entering artifact store. |
| 9 | App module scope | Generalized, not sage-specific | G4 (sage) deferred to own repo. Groot ships domain-agnostic with example scaffold. |
| 10 | App module protocol | Python Protocol class | Documentation-first; runtime_checkable but not enforced — avoids isinstance overhead on app authors. |
| 11 | Multi-page apps | DB-only (no Python module needed) | LLM can build multi-page apps purely through tool calls; no file system access required. |
| 12 | Export format | Manifest-based ZIP | Single format for both page and module app exports; manifest.json describes kind and content; blobs optional with ?include_data=true. |
| 13 | Import routing | 4-path router on manifest presence | Backwards-compatible: old bare-JSX ZIPs still work; new manifest ZIPs take priority. |
| 14 | last_opened_at | DB column (pages/apps); in-memory (module apps) | Module apps have no DB row — session-level tracking is sufficient; page/app_bundle tracking is durable. |
| 15 | /api/config | Unauthenticated | Browser needs the API key to authenticate subsequent calls — chicken-and-egg requires at least one unauthenticated endpoint. |
| 16 | Unified /api/web-apps | Single endpoint, three kinds | Dashboard needs one list; kinds are distinct enough to warrant a unified view over separate endpoints. |

---

## 15. Design Rules (non-negotiable)

1. **Groot runtime never contains domain logic.** It knows nothing about optimization, translation, or governance. It provides a runtime. Apps provide domain tools.
2. **All LLM interactions go through validated tool calls.** No raw code execution in the runtime.
3. **Artifact store is append-friendly.** Prefer update operations over deletes. The flywheel depends on accumulation.
4. **State is per-request.** No module-level mutable state. Learned from sage-mcp v0.1.
5. **React shell has no build step.** Babel standalone CDN only. Ship fast; optimize later.
6. **Every tool returns structured Pydantic models.** Never bare dicts or exceptions.
7. **No secrets hardcoded.** All credentials via env vars.

---

## 16. What Groot Unlocks

| Without Groot | With Groot |
|---|---|
| Every LLM project builds its own FastAPI server | Fork Groot, add `groot_apps/{name}/loader.py`, ship |
| Each project reinvents storage | One artifact store, accumulated across all apps |
| No standard LLM tool interface | Validated tool registry with Pydantic models and MCP transport |
| No live UI without a build step | React shell + Babel CDN — LLM creates pages, they render instantly |
| No design review layer | Claude in Chat generates pages; human approves before they enter Groot |
| Apps are one-off deployments | Export/import any app (or page) as a ZIP bundle; share across instances |
| No usage tracking | last_opened_at on every page and app; unified /api/web-apps dashboard |
| sage-cloud is a one-off app | sage integrates from its own repo as a Groot app module |
| New AI agents start from scratch | Any AI agent can fork Groot and have a runtime in minutes |

---

## 17. Resume Checklist (for Claude Code)

```
[x] 1. Read this file (GROOT_SPEC_V0.1.md)
[x] 2. Read .build/AGENT.md, .build/SPEC.md, .build/BUILD_LOG.md
[x] 3. Check ClickUp Claude Code Queue (901113364003) for pending tasks
[x] 4. Phase G1: artifact_store + tools + server + auth — 105 tests
[x] 5. Phase G2: mcp_transport stdio + SSE — 125 tests
[x] 6. Phase G3: page_server + React shell — 160 tests
[x] 7. Phase G-APP: app_interface + _example scaffold + APP_MODULE_GUIDE.md — 172 tests
[x] 8. Shell hotfixes: JSX import strip, component name capture, hook injection
[x] 9. Delete App (purge_data + force) — 184 tests
[x] 10. Export App ZIP — 197 tests
[x] 11. Import App ZIP hot-load — 211 tests
[x] 12. Dashboard v0.3.0 UI overhaul — 211 tests, tag groot-v0.1.0
[x] 13. v0.3.0-session-2: config tool, multi-page apps, URL fixes, bundle import/export
[x] 14. v0.3.0-session-3: dual export (manifest ZIP), last_opened_at, /api/web-apps, dashboard UX
[ ] 15. Next: check ClickUp queue for new tasks
```

---

*Original spec authored by Claude (Cowork) on 2026-03-13 based on Peter's groot_spec.md and session discussion.*
*G4 deferred to Project Sage on 2026-03-13. G-APP added same day.*
*Updated 2026-03-18 to reflect v0.3.0 built state (SHA 01c7cd8, 266 tests).*
*Architecture diagram available as groot_architecture.jsx (first Groot artifact, generated in-chat).*
