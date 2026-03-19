# Project Groot

Domain-agnostic LLM runtime environment.

Groot gives any MCP-compatible LLM agent a persistent execution layer: a SQLite artifact store, a validated tool interface (19 core tools), a React page server with multi-page app support, and a pluggable domain module system. The LLM is always external — Groot never embeds a model.

---

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Run HTTP server (REST API + dashboard at http://localhost:8000)
python -m groot

# Custom port
python -m groot --port 8001

# Run tests
pytest
```

A new API key is printed to the terminal on every startup. Use it in the dashboard or as `X-Groot-Key` header in API calls.

---

## Transport modes

| Mode | Command | Description |
|---|---|---|
| HTTP + SSE | `python -m groot` | REST API, dashboard, and MCP SSE on port 8000 (default) |
| stdio only | `python -m groot --mcp-stdio` | MCP stdio for Claude Desktop — **no HTTP server** |
| stdio + HTTP | `python -m groot --mcp-stdio --http` | stdio for Claude Desktop **and** HTTP server on port 8000 |

> **Important:** `--mcp-stdio` alone does not start an HTTP server. To open groot pages in a browser while Claude Desktop is connected, you must use `--mcp-stdio --http` (see Claude Desktop setup below).

---

## API

All tool routes require authentication via `X-Groot-Key` header or `?key=` query param.

| Route | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | No | Health check |
| `/` | GET | No | React shell (groot-dashboard) |
| `/artifacts` | GET | No | React shell (groot-artifacts) |
| `/apps/{name}` | GET | No | React shell (standalone page) |
| `/apps/{app}/` | GET | No | React shell (multi-page app root / index) |
| `/apps/{app}/{page}` | GET | No | React shell (multi-page app sub-page) |
| `/api/config` | GET | No | Runtime connection info (api_key, base_url) |
| `/api/pages` | GET | No | List all registered standalone pages |
| `/api/pages/{name}/source` | GET | No | Raw JSX source for a page |
| `/api/pages/{name}/meta` | GET | No | Page metadata |
| `/api/tools/write_blob` | POST | Yes | Write a blob to the artifact store |
| `/api/tools/read_blob` | POST | Yes | Read a blob by key |
| `/api/tools/list_blobs` | POST | Yes | List blobs with optional prefix filter |
| `/api/tools/delete_blob` | POST | Yes | Delete a blob |
| `/api/tools/create_page` | POST | Yes | Store a React JSX page |
| `/api/tools/update_page` | POST | Yes | Update an existing page |
| `/api/tools/list_pages` | POST | Yes | List all registered pages |
| `/api/tools/delete_page` | POST | Yes | Delete a page |
| `/api/tools/define_schema` | POST | Yes | Store a named JSON schema |
| `/api/tools/get_schema` | POST | Yes | Retrieve a schema by name |
| `/api/tools/list_schemas` | POST | Yes | List all schemas |
| `/api/tools/log_event` | POST | Yes | Append a structured log event |
| `/api/tools/call` | POST | Yes | Generic tool call endpoint |
| `/api/system/state` | GET | Yes | Runtime state (uptime, counts) |
| `/api/system/artifacts` | GET | Yes | Full artifact inventory |
| `/api/apps` | GET | No | List loaded app modules |
| `/api/apps/{name}` | GET | No | App detail (tools, pages, status) |
| `/api/apps/{name}/health` | GET | No | App health check |
| `/api/apps/{name}` | DELETE | Yes | Unregister app, remove pages/tools; `?purge_data=true` deletes blobs+schemas; `?force=true` required for loaded apps + removes directory |
| `/api/apps/import` | POST | Yes | Upload `.zip` to install + hot-load an app module |
| `/api/apps/{name}/export` | GET | No | Download app as `.zip`; `?include_data=true` bundles pages + blobs |
| `/api/tools/create_app` | POST | Yes | Register a multi-page app namespace |
| `/api/tools/create_app_page` | POST | Yes | Add a page to an app; `page=index` → app root |
| `/api/tools/update_app_page` | POST | Yes | Hot-swap JSX for an existing app page |
| `/api/tools/list_app_pages` | POST | Yes | List all pages under an app |
| `/api/app-pages/{app}/layout/source` | GET | No | App layout JSX (204 if none set) |
| `/api/app-pages/{app}/{page}/source` | GET | No | App page JSX (browser fetches at runtime) |
| `/mcp/sse` | GET | `?key=` | MCP SSE transport |
| `/mcp/messages` | POST | — | MCP SSE message relay |

---

## MCP integration

### Claude Desktop (stdio + HTTP)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "groot": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "groot", "--mcp-stdio", "--http"]
    }
  }
}
```

That's it. No env vars needed — Groot resolves all paths (database, artifacts, host, port) automatically from its install location.

**The only thing you need:** the absolute path to the Python binary where Groot is installed. Find it with `which python` (or `which python3`).

Restart Claude Desktop. The hammer icon in the toolbar confirms Groot tools are connected.

**Test it:** ask Claude to `create a Groot page called hello with a live clock`. Then open `http://localhost:8000/apps/hello` in your browser. The dashboard is at `http://localhost:8000/`.

> **Optional overrides:** if you need a custom database path, port, or API key, you can still set env vars (`GROOT_DB_PATH`, `GROOT_PORT`, etc.) in the config — see [Configuration](#configuration) below. But the defaults work out of the box.

---

### Standalone HTTP server (no Claude Desktop)

```bash
python -m groot
```

Groot prints the API key and dashboard URL to the terminal on startup. Open `http://localhost:8000/` in your browser.

---

### Remote SSE clients

Connect to `http://localhost:8000/mcp/sse?key=<api-key>` from any SSE-capable MCP client.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GROOT_API_KEYS` | *(auto-generated)* | Comma-separated API keys. If unset, a random key is generated and printed at startup. |
| `GROOT_DB_PATH` | `~/.groot/groot.db` | SQLite database path. Auto-created on first run. |
| `GROOT_ARTIFACT_DIR` | `~/.groot/artifacts` | Blob storage directory. Auto-created on first run. |
| `GROOT_APPS` | `_example` | Comma-separated app modules to auto-load from `groot_apps/` |
| `GROOT_HOST` | `0.0.0.0` | HTTP server bind address. Use `127.0.0.1` for local-only access. |
| `GROOT_PORT` | `8000` | HTTP server port |
| `GROOT_ENV` | `development` | `development` or `production` |

In `development` mode with no keys configured, auth is bypassed (dev convenience).
In `production` mode, empty `GROOT_API_KEYS` raises a 500 on startup.

---

## Project structure

```
groot/
  config.py          — Settings (pydantic-settings, .env)
  models.py          — Pydantic request/response models
  artifact_store.py  — Async SQLite CRUD (blobs, pages, schemas, events)
  auth.py            — API key middleware (FastAPI Depends)
  tools.py           — ToolRegistry + 19 core tools
  server.py          — FastAPI app, lifespan, all HTTP routes
  mcp_transport.py   — MCPBridge, stdio transport, SSE transport
  page_server.py     — PageServer: JSX delivery routes + static registration
  builtin_pages.py   — Built-in page JSX (groot-dashboard, groot-artifacts)
  __main__.py        — Entry point (python -m groot)

groot_apps/
  _example/          — Example app scaffold (ships with Groot)
    loader.py        — Minimal register() — one demo tool + one demo page
    README.md        — "Build Your First Groot App" guide

docs/
  APP_MODULE_GUIDE.md — Developer guide: how to build a Groot app module

groot-shell/
  index.html         — Self-contained React 18 shell (hash router, DynamicPage, Babel CDN)

groot/builtin_pages.py — Built-in pages registered at startup (dashboard + artifact browser)

tests/
  conftest.py        — Shared fixtures (TestClient, temp DB, auth headers)
  test_models.py     — Pydantic model tests (31)
  test_artifact_store.py — SQLite CRUD tests (24)
  test_auth.py       — Auth middleware tests (9)
  test_tools.py      — ToolRegistry + core tool tests (22)
  test_server.py     — HTTP route integration tests (19)
  test_mcp_transport.py — MCPBridge + stdio tests (12)
  test_mcp_sse.py    — SSE route tests (8)
  test_page_server.py   — Page server route tests (15)
  test_shell_integration.py — React shell + SPA route tests (8)
  test_g3_integration.py    — Full G3 integration tests (12)
```

---

## Build phases

| Phase | Description | Status | Tests |
|---|---|---|---|
| G1 | Runtime core: FastAPI + SQLite + 14 tools + auth | **Complete** | 105 |
| G2 | MCP transport: stdio + SSE | **Complete** | 125 total |
| G3 | Page server + React shell + built-in pages | **Complete** | 160 total |
| G-APP | Generalized app module interface + example scaffold + docs | **Complete** | — |
| Delete App | `DELETE /api/apps/{name}` with purge_data + force flags | **Complete** | 184 total |
| Export App | `GET /api/apps/{name}/export` — ZIP download with optional data bundle | **Complete** | 197 total |
| Import App | `POST /api/apps/import` — ZIP upload, validate, extract, hot-load | **Complete** | 211 total |
| Dashboard v0.3.0 | Full UI overhaul — custom dropdowns, API key validation, search, toasts, source viewer modal, compact view, nav links, clickable stats, uptime format | **Complete** | 211 total |
| Multi-page Apps | `create_app` / `create_app_page` / `update_app_page` / `list_app_pages` — real URL routing, optional shared layout, SPA navigation via plain `<a href>` | **Complete** | 243 total |
| ~~G4~~ | ~~Sage app module~~ | **Deferred** | — |

> **G4 note:** Sage is a domain-specific optimization engine with its own lifecycle. It was deferred to [Project Sage](https://github.com/pragnakar/Project_Sage) and will integrate with Groot as an external app module via the `register()` protocol. This keeps Groot clean, forkable, and domain-agnostic.

## Building your own Groot app

Groot ships with a generalized app module interface. Any developer or AI agent can build a Groot app:

1. Create `groot_apps/{your_app}/loader.py`
2. Implement `async def register(tool_registry, page_server, store)`
3. Register your tools and pages
4. Set `GROOT_APPS=your_app` in `.env`
5. Run `python -m groot`

See `docs/APP_MODULE_GUIDE.md` for the full guide, or copy `groot_apps/_example/` as a starting point.

---

## JSX page compatibility

The React shell handles all common LLM-generated JSX patterns automatically:

| Pattern | Handled |
|---|---|
| `function Page() { ... }` | Native |
| `export default function AnyName() { ... }` | Name captured, resolved |
| Bare JSX expression | Wrapped automatically |
| `import React from 'react'` | Stripped before transform |
| Destructured hooks (`useState`, `useEffect`, etc.) | Injected as named vars |
| `React.useState` style | Works natively |

No special prompt engineering needed — just ask Claude to build a page.

---

## Architecture

See `GROOT_SPEC_V0.1.md` for the full spec and `groot_architecture.jsx` for the architecture diagram.
