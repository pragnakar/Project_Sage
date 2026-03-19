# Building a Groot App Module

Groot is domain-agnostic. The runtime provides storage, tools, transport (HTTP + MCP), auth, and a React shell. Domain-specific logic lives in app modules under `groot_apps/{name}/`. This guide is everything you need to build one.

---

## What is a Groot App?

A Groot app is a Python package that registers domain-specific tools and React pages into the runtime at startup. Once registered:

- Tools are callable via HTTP (`POST /api/tools/call`) and MCP
- Pages are served by the shell at `#/apps/{name}`
- The app appears in `GET /api/apps` for introspection

The runtime never changes — your app provides the domain logic.

---

## Quick Start

**1. Create your app directory:**

```
groot_apps/myapp/
├── __init__.py
├── loader.py        ← required
├── tools.py
├── models.py
└── pages/
    └── dashboard.jsx
```

**2. Implement `loader.py`:**

```python
from pathlib import Path
from groot.artifact_store import ArtifactStore
from groot.page_server import PageServer
from groot.tools import ToolRegistry
from groot_apps.myapp.tools import my_tool

APP_META = {
    "description": "My Groot app",
    "version": "0.1.0",
}

_PAGES_DIR = Path(__file__).parent / "pages"

async def register(
    tool_registry: ToolRegistry,
    page_server: PageServer,
    store: ArtifactStore,
) -> None:
    tool_registry.register(my_tool, namespace="myapp")
    await page_server.register_static("dashboard", str(_PAGES_DIR / "dashboard.jsx"), app_name="myapp")

async def health_check() -> dict:
    return {"status": "healthy", "checks": {"my_dependency": "ok"}}
```

**3. Enable your app:**

```bash
# .env
GROOT_APPS=myapp
```

Multiple apps: `GROOT_APPS=myapp,otherapp`

**4. Start Groot:**

```bash
python -m groot
```

**5. Verify:**

```bash
GET /api/apps           # your app appears
GET /api/apps/myapp     # lists tools and pages
```

---

## The App Module Contract

### Required: `async register(tool_registry, page_server, store)`

Called once at startup. Register all tools and pages here.

```python
async def register(
    tool_registry: ToolRegistry,
    page_server: PageServer,
    store: ArtifactStore,
) -> None:
    ...
```

### Optional: `APP_META`

Module-level dict with metadata used by `GET /api/apps`.

```python
APP_META = {
    "description": "Human-readable description",
    "version": "0.1.0",
}
```

### Optional: `async health_check() -> dict`

Called by `GET /api/apps/{name}/health`. Return a dict with `status` and `checks`.

```python
async def health_check() -> dict:
    return {
        "status": "healthy",      # or "degraded" / "error"
        "checks": {
            "database": "ok",
            "external_api": "ok",
        }
    }
```

If not provided, the health endpoint returns `{"status": "healthy", "checks": {}}`.

---

## Registering Tools

### Tool function signature

```python
from groot.artifact_store import ArtifactStore
from groot_apps.myapp.models import MyResult

async def my_tool(store: ArtifactStore, param1: str, param2: int = 0) -> MyResult:
    """What this tool does — used as the MCP tool description."""
    result = await store.write_blob(f"myapp/{param1}", str(param2))
    return MyResult(key=result.key, value=param2)
```

Rules:
- First parameter must be `store: ArtifactStore` — injected automatically
- All other parameters become tool arguments (visible in MCP and `/api/tools/call`)
- Return a Pydantic `BaseModel` — never a bare dict
- Raise exceptions on failure — the registry wraps them as `ToolError`

### Naming conventions

- Tool names: `snake_case`, descriptive (e.g. `solve_optimization`, not `solve`)
- Namespace: your app name — passed when registering

```python
tool_registry.register(my_tool, namespace="myapp")
# Tool callable as "my_tool" in namespace "myapp"
```

### Calling tools from HTTP

```bash
POST /api/tools/call
X-Groot-Key: your-key

{"tool": "my_tool", "arguments": {"param1": "hello", "param2": 42}}
```

---

## Registering Pages

### Static pages (shipped with your app)

```python
_PAGES_DIR = Path(__file__).parent / "pages"

await page_server.register_static(
    "dashboard",                          # page name suffix
    str(_PAGES_DIR / "dashboard.jsx"),   # absolute path to JSX file
    app_name="myapp",                    # prefix — final name: "myapp-dashboard"
)
```

The page is upserted at startup. Accessible at `#/apps/myapp-dashboard` in the shell.

### Dynamic pages (created at runtime by LLM)

```python
# Via HTTP tool
POST /api/tools/create_page
{"name": "myapp-results", "jsx_code": "...", "description": "Results view"}
```

The shell fetches JSX from `/api/pages/{name}/source` and renders it client-side with Babel.

### Page JSX conventions

Pages are transformed and evaluated in the browser. Rules:

- **No imports** — React is globally available as `React`
- **Named `Page` component** — the shell looks for `function Page()` or wraps bare JSX
- **Fetch data via Groot API** — use relative URLs, e.g. `fetch('/api/system/artifacts')`
- **Auth**: read-only endpoints (`/api/pages`, `/api/apps`, `/api/system/state`) are unauthenticated and work from the browser. Tool calls (`/api/tools/call`) require a key.

```jsx
function Page() {
  const [data, setData] = React.useState(null);

  React.useEffect(() => {
    fetch('/api/apps').then(r => r.json()).then(setData);
  }, []);

  if (!data) return <div>Loading…</div>;
  return <div>{JSON.stringify(data)}</div>;
}
```

**Color palette** (matches Groot shell):

```js
const colors = {
  bg:      '#0d1117',
  surface: '#161b22',
  border:  '#30363d',
  accent:  '#4ade80',   // green
  accent2: '#6366f1',   // indigo
  text:    '#e2e8f0',
  muted:   '#8b949e',
  error:   '#ff6b6b',
  warn:    '#f0a854',
};
```

---

## Testing Your App

### Unit test a tool

```python
import pytest
from groot.artifact_store import ArtifactStore
from groot_apps.myapp.tools import my_tool

@pytest.fixture
async def store(tmp_path):
    s = ArtifactStore(db_path=str(tmp_path / "t.db"), artifact_dir=str(tmp_path))
    await s.init_db()
    return s

async def test_my_tool(store):
    result = await my_tool(store, param1="test", param2=5)
    assert result.value == 5
```

### Integration test via HTTP

Use the standard `client` fixture from `conftest.py` but override `GROOT_APPS`:

```python
from groot.config import Settings, get_settings
from groot.server import app

@pytest.fixture
def myapp_client(tmp_path):
    settings = Settings(
        GROOT_API_KEYS="test-key",
        GROOT_DB_PATH=str(tmp_path / "t.db"),
        GROOT_ARTIFACT_DIR=str(tmp_path),
        GROOT_APPS="myapp",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_tool_via_http(myapp_client):
    resp = myapp_client.post(
        "/api/tools/call",
        json={"tool": "my_tool", "arguments": {"param1": "hello"}},
        headers={"X-Groot-Key": "test-key"},
    )
    assert resp.status_code == 200
```

### Verify app is listed

```python
def test_app_is_discoverable(myapp_client):
    resp = myapp_client.get("/api/apps")
    names = [a["name"] for a in resp.json()["apps"]]
    assert "myapp" in names
```

---

## Reference: `groot_apps/example/`

A complete working example is in `groot_apps/example/`:

```
groot_apps/example/
├── __init__.py
├── loader.py      — registers echo_tool + example-hello page
├── tools.py       — echo_tool(store, message) -> EchoResult
├── models.py      — EchoResult(message, echo)
└── pages/
    └── hello.jsx  — "Hello from Example App" page
```

Enable with `GROOT_APPS=example` and verify:

```bash
GET /api/apps/example
# {"name": "example", "tools": [{"name": "echo_tool", ...}], "pages": [...]}

POST /api/tools/call
{"tool": "echo_tool", "arguments": {"message": "hi"}}
# {"message": "hi", "echo": "Echo: hi"}
```

---

## Groot API Reference (for pages)

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/system/state` | No (dev) / Yes (prod) | Uptime, artifact counts |
| `GET /api/system/artifacts` | No (dev) / Yes (prod) | Full artifact inventory |
| `GET /api/pages` | No | List all registered pages |
| `GET /api/pages/{name}/source` | No | Raw JSX for a page |
| `GET /api/apps` | No | Loaded app modules |
| `GET /api/apps/{name}` | No | App tools and pages |
| `POST /api/tools/call` | Yes | Call any tool |

In `development` mode with no `GROOT_API_KEYS` set, all endpoints allow unauthenticated access.

---

## FAQ

**How do I add dependencies?**
Add an optional dependency group in `pyproject.toml`:
```toml
[project.optional-dependencies]
myapp = ["my-library>=1.0"]
```
Install with `pip install -e ".[myapp]"`.

**Can I access the database directly?**
No. Use `ArtifactStore` methods via your tool's `store` parameter. Never import `aiosqlite` in your app.

**Can two apps share a namespace?**
No. Each app must use a unique namespace matching its directory name.

**How do I pass the API key from a page to tool calls?**
In development mode, auth is bypassed. For production, the recommended pattern is to proxy tool calls through a dedicated unauthenticated endpoint you add to your app, or embed the key via a server-side config endpoint.

**What if my app fails to load?**
The runtime logs a warning and continues. The failing app is recorded with `status: "error"` in `GET /api/apps`. Other apps are unaffected.
