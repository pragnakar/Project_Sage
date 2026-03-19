# Fork and Integrate Project Groot

**Who this is for:** Coding agents and developers who want to use Groot as the
runtime layer for their own LLM-powered project. This document walks you through
every decision from first clone to a running integration.

---

## What Groot Gives You

When you integrate Groot, your LLM agent gets a persistent execution environment
it can call over MCP or HTTP:

| What you get | How it works |
|---|---|
| Persistent storage | Blobs, pages, schemas — all keyed and queryable |
| Live React pages | LLM calls `create_page` → page is instantly live at `/apps/{name}` |
| MCP tool interface | Claude Desktop (stdio) or any MCP client (SSE) connects directly |
| REST API | Every tool callable as `POST /api/tools/call` — no MCP client needed |
| Domain tool slots | Your code registers tools that appear alongside Groot's core tools |
| Dashboard | Built-in web UI for managing pages, blobs, exports, and imports |

**The LLM is always external.** Groot never embeds a model. It is the runtime
your model calls into.

---

## Two Integration Paths

### Path A — Fork and extend (recommended for most projects)

Clone Groot, add your domain logic as an app module inside `groot_apps/`, and
run Groot as your project's server. Your app is part of the same process.

**Use this when:**
- Your project needs custom MCP tools alongside Groot's core tools
- You want your pages and blobs stored in Groot's artifact store
- You want a single `python -m groot` command to start everything

### Path B — Groot as a sidecar runtime

Run Groot unmodified as a background service. Your project talks to it entirely
over HTTP (`POST /api/tools/call`). No Python-level integration required.

**Use this when:**
- Your project is in a different language or framework
- You want Groot upgradeable independently of your project
- You only need storage and page hosting, not custom tools

---

## Path A: Fork and Extend

### 1. Fork the repo

```bash
# On GitHub: fork github.com/pragnakar/Project_Groot to your account
# Then clone your fork
git clone https://github.com/YOUR_ORG/YOUR_PROJECT_NAME.git
cd YOUR_PROJECT_NAME
```

Rename the remote if you want to pull upstream Groot updates later:

```bash
git remote rename origin mine
git remote add upstream https://github.com/pragnakar/Project_Groot.git
```

### 2. Install

```bash
pip install -e .
```

Verify:

```bash
python -c "import groot; print(groot.__version__)"
# 0.3.0
```

### 3. Configure

Create a `.env` file at the project root:

```bash
# .env

# Your app module name (directory under groot_apps/)
GROOT_APPS=myapp

# Optional: set a fixed API key (auto-generated on first run if not set)
GROOT_API_KEYS=your_secret_key_here

# Optional: host and port (defaults: 0.0.0.0, 8000)
GROOT_HOST=0.0.0.0
GROOT_PORT=8000

# Optional: custom DB and artifact paths
GROOT_DB_PATH=groot.db
GROOT_ARTIFACT_DIR=artifacts/
```

### 4. Create your app module

```
groot_apps/
└── myapp/
    ├── __init__.py      ← empty
    ├── loader.py        ← required: register() function
    ├── tools.py         ← your domain tools
    └── models.py        ← Pydantic return types for your tools
```

Minimal `loader.py`:

```python
from groot.tools import ToolRegistry
from groot.page_server import PageServer
from groot.artifact_store import ArtifactStore
from groot_apps.myapp.tools import my_tool

APP_META = {
    "description": "My project's domain tools",
    "version": "0.1.0",
}

async def register(
    tool_registry: ToolRegistry,
    page_server: PageServer,
    store: ArtifactStore,
) -> None:
    tool_registry.register(my_tool, namespace="myapp")
```

Minimal tool in `tools.py`:

```python
from pydantic import BaseModel
from groot.artifact_store import ArtifactStore

class MyResult(BaseModel):
    message: str

async def my_tool(store: ArtifactStore, input: str) -> MyResult:
    """Does something useful. Appears as an MCP tool."""
    await store.write_blob(f"myapp/last_input", input)
    return MyResult(message=f"Processed: {input}")
```

> See `docs/APP_MODULE_GUIDE.md` for the full contract: tool signatures,
> page registration, health checks, testing patterns, and FAQ.

### 5. Start Groot

```bash
# HTTP only (browser + REST API)
python -m groot

# HTTP + MCP stdio (for Claude Desktop)
python -m groot --mcp-stdio --http

# Custom port
python -m groot --port 9000
```

On first start, Groot prints the generated API key to stdout:

```
[GROOT] API key: groot_sk_xxxxxxxxxxxxxxxxxxxx
[GROOT] Dashboard: http://localhost:8000
```

### 6. Verify your app loaded

```bash
curl http://localhost:8000/api/apps
# {"apps": [{"name": "myapp", "status": "loaded", ...}]}

curl http://localhost:8000/api/apps/myapp
# {"name": "myapp", "tools": [{"name": "my_tool", ...}], "pages": [...]}
```

---

## Path B: Groot as a Sidecar

### 1. Run Groot (no fork needed)

```bash
pip install git+https://github.com/pragnakar/Project_Groot.git
GROOT_API_KEYS=my-key python -m groot
```

Or with Docker (if a `Dockerfile` is available in the repo).

### 2. Call tools from your project

```python
import httpx

GROOT_URL = "http://localhost:8000"
GROOT_KEY = "my-key"

def call_tool(tool: str, arguments: dict) -> dict:
    resp = httpx.post(
        f"{GROOT_URL}/api/tools/call",
        json={"tool": tool, "arguments": arguments},
        headers={"X-Groot-Key": GROOT_KEY},
    )
    resp.raise_for_status()
    return resp.json()

# Store a blob
call_tool("write_blob", {"key": "myproject/result", "data": "hello"})

# Create a live page
call_tool("create_page", {
    "name": "myproject-dashboard",
    "jsx_code": "function Page() { return <h1>Hello from my project</h1>; }",
    "description": "My project dashboard",
})
```

### 3. Read back from any client

```bash
# Page is live immediately
curl http://localhost:8000/apps/myproject-dashboard

# List all pages
curl http://localhost:8000/api/pages
```

---

## Connecting an LLM Agent via MCP

Groot supports two MCP transports.

### MCP stdio (Claude Desktop, Claude Code)

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "groot": {
      "command": "python",
      "args": ["-m", "groot", "--mcp-stdio", "--http"],
      "env": {
        "GROOT_API_KEYS": "your-key",
        "GROOT_HOST": "0.0.0.0",
        "GROOT_PORT": "8000"
      }
    }
  }
}
```

After connecting, the agent can call `get_groot_config` to discover the API key
and base URL without manual configuration.

### MCP SSE (remote / ChatGPT / any SSE client)

```
GET http://localhost:8000/mcp/sse?key=your-key
POST http://localhost:8000/mcp/messages?key=your-key
```

---

## Core Tools Available to Your Agent

These are always available — no app module required.

| Tool | What it does |
|---|---|
| `write_blob(key, data, content_type)` | Persist arbitrary data |
| `read_blob(key)` | Read back a blob |
| `list_blobs(prefix)` | List blobs by namespace prefix |
| `create_page(name, jsx_code, description)` | Create a live React page |
| `update_page(name, jsx_code)` | Update an existing page |
| `list_pages()` | List all registered pages |
| `delete_page(name)` | Remove a page |
| `define_schema(name, schema)` | Store a JSON schema |
| `get_schema(name)` | Retrieve a schema |
| `log_event(message, level, context)` | Append to the event log |
| `get_system_state()` | Uptime, counts, registered apps |
| `list_artifacts()` | Full inventory: pages, blobs, schemas, events |
| `get_groot_config()` | API key, host, port, dashboard URL |
| `create_app(name)` | Create a multi-page app namespace |
| `create_app_page(app, page, jsx_code)` | Add a page to a multi-page app |
| `update_app_page(app, page, jsx_code)` | Update a multi-page app page |
| `list_app_pages(app)` | List pages in a multi-page app |

Your app module's tools appear in this same list under your namespace.

---

## Making It Your Own

### Rename and rebrand

The dashboard and shell display "Groot" in the header. To rebrand:

1. **Dashboard title** — edit `groot/builtin_pages.py`, find `'Groot' Dashboard` in `_DASHBOARD_JSX`
2. **Package name** — update `pyproject.toml` (`name = "your-project-runtime"`)
3. **Version** — update `groot/__init__.py` and `pyproject.toml`
4. **Dashboard default URL** — controlled by `GROOT_HOST` / `GROOT_PORT` env vars

### Add your own built-in pages

Built-in pages (like the dashboard) are registered at startup from
`groot/builtin_pages.py`. You can add your own by calling `upsert_page` in
the `register_builtin_pages` function, or from your app module's `register()`.

### Customize the shell nav

The navigation bar is in `groot-shell/index.html`. Search for the `Nav`
component. Add links to your pages here — no build step, just edit and restart.

### Add your own REST routes

Add a `FastAPI` `APIRouter` in your app module and mount it in `server.py`'s
lifespan alongside the existing routers:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/myapp/custom")
async def my_custom_endpoint():
    return {"hello": "world"}

# In register(), make the router accessible:
page_server._app.include_router(router)
```

---

## Key Conventions to Respect

These keep the runtime domain-agnostic and your module portable:

1. **No domain logic in `groot/`** — all project-specific code lives in `groot_apps/{name}/`
2. **No LLM API calls from inside Groot** — the LLM is always external
3. **No module-level mutable state** — tools receive `store` per-call; don't use globals
4. **No bare dicts from tools** — return Pydantic models
5. **No secrets hardcoded** — read from env vars in your `loader.py`
6. **Tool namespace = your app name** — `tool_registry.register(fn, namespace="myapp")`
7. **Page names prefixed** — `myapp-dashboard`, `myapp-results` (prevents collisions)
8. **Blob keys namespaced** — `myapp/result_001`, `myapp/config` (prefix = your app name)

---

## Export / Import (moving apps between instances)

Groot supports ZIP-based export and import for both pages and module apps.

```bash
# Export a module app (Python code + optional blobs)
GET /api/apps/myapp/export?include_data=true
# → myapp.zip containing manifest.json + groot_apps/myapp/ + blobs/

# Import on another instance
POST /api/apps/import
Content-Type: multipart/form-data
file=@myapp.zip
```

The ZIP manifest (`manifest.json`) identifies the kind, version, and contents.
Same format works for standalone pages:

```bash
GET /api/pages/myapp-dashboard/export
# → myapp-dashboard.zip containing manifest.json + pages/myapp-dashboard.jsx
```

---

## API Reference Cheat Sheet

| Endpoint | Auth | Description |
|---|---|---|
| `GET /` | No | Groot dashboard |
| `GET /apps/{name}` | No | Render a standalone page |
| `GET /apps/{name}/` | No | Render a multi-page app root |
| `GET /api/config` | No | API key + base URL (browser bootstrap) |
| `GET /api/pages` | No | List all pages |
| `GET /api/pages/{name}/source` | No | Raw JSX for a page |
| `GET /api/web-apps` | No | All web apps (pages + app bundles + module apps) |
| `GET /api/apps` | No | Loaded app modules |
| `GET /api/apps/{name}` | No | App tools, pages, status |
| `GET /api/apps/{name}/health` | No | App health check |
| `POST /api/tools/call` | Yes | Call any tool by name |
| `DELETE /api/apps/{name}` | Yes | Unload + optionally purge app |
| `GET /api/apps/{name}/export` | Yes | Download app as ZIP |
| `POST /api/apps/import` | Yes | Upload ZIP to install app |
| `GET /health` | No | `{"status":"ok","version":"..."}` |
| `GET /docs` | No | Interactive API docs (Swagger UI) |

Auth: `X-Groot-Key: your-key` header, or `?key=your-key` query param for SSE.

---

## Checklist for Coding Agents

Work through this in order on a fresh fork:

```
[ ] 1. Clone and install:  pip install -e .
[ ] 2. Start Groot:        python -m groot
[ ] 3. Note the API key from startup output
[ ] 4. Open dashboard:     http://localhost:8000
[ ] 5. Call get_groot_config via MCP to verify connection
[ ] 6. Create a test page: create_page("hello", "function Page(){return <h1>Hi</h1>;}")
[ ] 7. Verify page live:   http://localhost:8000/apps/hello
[ ] 8. Create groot_apps/myapp/__init__.py  (empty)
[ ] 9. Create groot_apps/myapp/loader.py   (APP_META + register())
[ ] 10. Add GROOT_APPS=myapp to .env
[ ] 11. Restart Groot and verify: GET /api/apps/myapp shows status "loaded"
[ ] 12. Register your first tool in loader.py, call it via MCP
[ ] 13. Write a test:  pytest tests/ (all 266 core tests should still pass)
[ ] 14. Create your first page from your tool's output
[ ] 15. Export the app as a ZIP: GET /api/apps/myapp/export
```

---

## Further Reading

- `docs/APP_MODULE_GUIDE.md` — full app module contract, tool/page patterns, testing
- `GROOT_SPEC_V0.1.md` — architecture, data model, design decisions, build history
- `groot_apps/_example/` — minimal working reference implementation
- `groot/builtin_pages.py` — dashboard and artifact browser source (real-world JSX examples)

---

*Project Groot is maintained at github.com/pragnakar/Project_Groot.*
*Fork it, build on it, make it yours.*
