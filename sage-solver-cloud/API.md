# API.md — sage-solver-cloud endpoint reference

> This is the contract that sage-solver-mcp will be built against.

All authenticated endpoints require the `X-Sage-Key` header. In development mode with no keys configured, auth is bypassed.

Base URL: `http://localhost:8000` (default)

---

## 1. Health & Config

### GET /health

Health check. No auth required.

**Response:**
```json
{"status": "ok", "version": "0.3.0"}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### GET /api/config

Runtime connection info. No auth required. Exposes the API key for local dashboard auto-population — do not expose externally.

**Response:**
```json
{
  "api_key": "sage_sk_...",
  "base_url": "http://localhost:8000",
  "dashboard_url": "http://localhost:8000/"
}
```

**Example:**
```bash
curl http://localhost:8000/api/config
```

---

## 2. Blob CRUD

The primary integration surface for sage-solver-mcp. Job state, notifications, and indexes are stored as blobs.

### POST /api/tools/write_blob

Write a blob to the artifact store. Auth required.

**Request body:**
```json
{
  "key": "sage-jobs/job-abc123",
  "data": "{\"status\": \"running\"}",
  "content_type": "application/json"
}
```

**Response:** `BlobResult`
```json
{
  "key": "sage-jobs/job-abc123",
  "size_bytes": 22,
  "content_type": "application/json",
  "created_at": "2026-03-19T12:00:00Z",
  "url": "/blobs/sage-jobs/job-abc123"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/write_blob \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"key":"sage-jobs/job-1","data":"{\"status\":\"queued\"}","content_type":"application/json"}'
```

---

### POST /api/tools/read_blob

Read a blob by key. Auth required.

**Request body:**
```json
{"key": "sage-jobs/job-abc123"}
```

**Response:** `BlobData`
```json
{
  "key": "sage-jobs/job-abc123",
  "data": "{\"status\": \"running\"}",
  "content_type": "application/json",
  "created_at": "2026-03-19T12:00:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/read_blob \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"key":"sage-jobs/job-1"}'
```

---

### POST /api/tools/list_blobs

List blobs with optional prefix filter. Auth required.

**Request body:**
```json
{"prefix": "sage-jobs/"}
```

**Response:** `list[BlobMeta]`
```json
[
  {
    "key": "sage-jobs/job-abc123",
    "size_bytes": 22,
    "content_type": "application/json",
    "created_at": "2026-03-19T12:00:00Z"
  }
]
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/list_blobs \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"prefix":"sage-jobs/"}'
```

---

### POST /api/tools/delete_blob

Delete a blob by key. Auth required.

**Request body:**
```json
{"key": "sage-jobs/job-abc123"}
```

**Response:**
```json
{"deleted": true}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/delete_blob \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"key":"sage-jobs/job-1"}'
```

---

### GET /blobs/{key}

Public blob read. No auth required. Returns raw blob content with its stored Content-Type. This is the URL returned in `BlobResult.url`.

**Response:** Raw content with stored Content-Type header.

**Example:**
```bash
curl http://localhost:8000/blobs/sage-jobs/job-1
```

---

## 3. Page CRUD

### POST /api/tools/create_page

Create a new React JSX page. Auth required.

**Request body:**
```json
{
  "name": "my-page",
  "jsx_code": "function Page() { return <h1>Hello</h1>; }",
  "description": "A test page"
}
```

**Response:** `PageResult`
```json
{
  "name": "my-page",
  "url": "/apps/my-page",
  "description": "A test page",
  "created_at": "2026-03-19T12:00:00Z",
  "updated_at": "2026-03-19T12:00:00Z",
  "last_opened_at": null
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/create_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-page","jsx_code":"function Page() { return <h1>Hello</h1>; }"}'
```

---

### POST /api/tools/update_page

Update an existing page's JSX. Auth required.

**Request body:**
```json
{
  "name": "my-page",
  "jsx_code": "function Page() { return <h1>Updated</h1>; }"
}
```

**Response:** `PageResult`

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/update_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-page","jsx_code":"function Page() { return <h1>Updated</h1>; }"}'
```

---

### POST /api/tools/upsert_page

Create or update a page (idempotent). Auth required.

**Request body:**
```json
{
  "name": "my-page",
  "jsx_code": "function Page() { return <h1>Hello</h1>; }",
  "description": "optional"
}
```

**Response:** `PageResult`

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/upsert_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-page","jsx_code":"function Page() { return <h1>Hello</h1>; }"}'
```

---

### POST /api/tools/list_pages

List all registered pages. Auth required.

**Request body:** (none)

**Response:** `list[PageMeta]`
```json
[
  {
    "name": "my-page",
    "url": "/apps/my-page",
    "description": "",
    "created_at": "2026-03-19T12:00:00Z",
    "updated_at": "2026-03-19T12:00:00Z",
    "last_opened_at": null
  }
]
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/list_pages \
  -H "X-Sage-Key: $KEY"
```

---

### POST /api/tools/delete_page

Delete a page by name. Auth required.

**Request body:**
```json
{"name": "my-page"}
```

**Response:**
```json
{"deleted": true}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/delete_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-page"}'
```

---

### GET /api/pages

List all registered pages. No auth required.

**Response:** `list[PageMeta]`

**Example:**
```bash
curl http://localhost:8000/api/pages
```

---

### GET /api/pages/{name}/source

Raw JSX source for a page. No auth required. Returns `text/plain`.

**Example:**
```bash
curl http://localhost:8000/api/pages/my-page/source
```

---

### GET /api/pages/{name}/meta

Page metadata (name, description, timestamps). No auth required.

**Response:** `PageResult`

**Example:**
```bash
curl http://localhost:8000/api/pages/my-page/meta
```

---

### GET /api/pages/{name}/export

Export a standalone page as a ZIP archive. No auth required. Optional `?include_data=true` bundles associated blobs.

**Response:** `application/zip` download.

**Example:**
```bash
curl -o my-page.zip http://localhost:8000/api/pages/my-page/export
```

---

### GET /api/pages/{name}/store

Read a page's persistent JSON store. No auth required. Returns `{}` on first use.

**Example:**
```bash
curl http://localhost:8000/api/pages/my-page/store
```

---

### PUT /api/pages/{name}/store

Overwrite a page's persistent JSON store. No auth required. Body must be valid JSON.

**Example:**
```bash
curl -X PUT http://localhost:8000/api/pages/my-page/store \
  -H "Content-Type: application/json" \
  -d '{"counter": 42}'
```

---

## 4. App Management

### GET /api/apps

List all loaded app modules with tool/page counts and core runtime summary. No auth required.

**Response:** `AppsResponse`
```json
{
  "apps": [
    {
      "name": "_example",
      "namespace": "_example",
      "tools_count": 1,
      "pages_count": 1,
      "status": "loaded",
      "description": ""
    }
  ],
  "core": {
    "tools_count": 19,
    "pages_count": 2,
    "version": "0.3.0"
  }
}
```

**Example:**
```bash
curl http://localhost:8000/api/apps
```

---

### GET /api/apps/{name}

Full detail for a loaded app module: tools with schemas, registered pages. No auth required.

**Response:** `AppDetail`
```json
{
  "name": "_example",
  "namespace": "_example",
  "tools": [{"name": "example_tool", "description": "...", "parameters": {}}],
  "pages": [],
  "status": "loaded"
}
```

**Example:**
```bash
curl http://localhost:8000/api/apps/_example
```

---

### GET /api/apps/{name}/health

App health check. Calls the app's `health_check()` if it provides one. No auth required.

**Response:** `AppHealth`
```json
{"name": "_example", "status": "healthy", "checks": {}}
```

**Example:**
```bash
curl http://localhost:8000/api/apps/_example/health
```

---

### DELETE /api/apps/{name}

Unregister an app module and remove its pages. Auth required.

Query params:
- `purge_data=true` — also delete blobs and schemas prefixed with the app name
- `force=true` — required for currently-loaded apps; also removes the app directory from disk

**Response:** `AppDeleteResult`
```json
{
  "name": "_example",
  "tools_removed": 1,
  "pages_removed": 1,
  "blobs_removed": 0,
  "schemas_removed": 0,
  "directory_removed": true
}
```

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/apps/_example?force=true&purge_data=true" \
  -H "X-Sage-Key: $KEY"
```

---

### POST /api/apps/import

Upload a `.zip` archive to install and hot-load an app module. Auth required. Max upload: 10 MB.

The ZIP must contain either:
- A manifest.json with `kind: "module_app"` and a single app directory
- A manifest.json with `kind: "page"` and a `pages/` directory
- A single bare `.jsx` file (legacy page import)
- A single top-level directory with `__init__.py` (legacy module import)

**Request:** `multipart/form-data` with `file` field.

**Response:** `AppImportResult`
```json
{
  "name": "my_app",
  "status": "loaded",
  "tools_registered": 2,
  "pages_registered": 1,
  "message": "App 'my_app' imported and loaded successfully."
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/apps/import \
  -H "X-Sage-Key: $KEY" \
  -F file=@my_app.zip
```

---

### GET /api/apps/{name}/export

Download an app module as a `.zip` archive. No auth required. Optional `?include_data=true` bundles the app's blobs.

**Response:** `application/zip` download with `manifest.json`.

**Example:**
```bash
curl -o my_app.zip http://localhost:8000/api/apps/_example/export
```

---

### GET /api/web-apps

Unified list of all web apps: module apps (`kind: "app_bundle"`), DB multi-page apps (`kind: "multi_page_bundle"`), and individual pages (`kind: "page"`). No auth required.

**Response:** `list[dict]` — each entry has `kind`, `name`, `description`, `url`, `status`, `tools_count`, `page_count`, `created_at`, `updated_at`, `last_opened_at`.

**Example:**
```bash
curl http://localhost:8000/api/web-apps
```

---

### POST /api/tools/create_app

Register a multi-page app namespace. Auth required.

**Request body:**
```json
{
  "name": "dashboard",
  "description": "Main dashboard app",
  "layout_jsx": "function Layout({children}) { return <div>{children}</div>; }"
}
```

**Response:** `AppResult`
```json
{
  "name": "dashboard",
  "description": "Main dashboard app",
  "base_url": "http://localhost:8000/apps/dashboard/",
  "created_at": "2026-03-19T12:00:00Z",
  "updated_at": "2026-03-19T12:00:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/create_app \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"dashboard","description":"Main dashboard"}'
```

---

### POST /api/tools/create_app_page

Add a page to a multi-page app. `page: "index"` becomes the app root. Auth required.

**Request body:**
```json
{
  "app": "dashboard",
  "page": "overview",
  "jsx_code": "function Page() { return <h1>Overview</h1>; }",
  "description": "Overview page"
}
```

**Response:** `AppPageResult`
```json
{
  "app": "dashboard",
  "page": "overview",
  "url": "http://localhost:8000/apps/dashboard/overview",
  "description": "Overview page",
  "created_at": "2026-03-19T12:00:00Z",
  "updated_at": "2026-03-19T12:00:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/create_app_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"app":"dashboard","page":"overview","jsx_code":"function Page() { return <h1>Overview</h1>; }"}'
```

---

### POST /api/tools/update_app_page

Hot-swap JSX for an existing app page. Auth required.

**Request body:**
```json
{
  "app": "dashboard",
  "page": "overview",
  "jsx_code": "function Page() { return <h1>Updated</h1>; }"
}
```

**Response:** `AppPageResult`

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/update_app_page \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"app":"dashboard","page":"overview","jsx_code":"function Page() { return <h1>Updated</h1>; }"}'
```

---

### POST /api/tools/list_app_pages

List all pages under a multi-page app. Auth required.

**Request body:**
```json
{"app": "dashboard"}
```

**Response:** `list[AppPageMeta]`
```json
[
  {
    "app": "dashboard",
    "page": "overview",
    "url": "http://localhost:8000/apps/dashboard/overview",
    "description": "Overview page",
    "created_at": "2026-03-19T12:00:00Z",
    "updated_at": "2026-03-19T12:00:00Z"
  }
]
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/list_app_pages \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"app":"dashboard"}'
```

---

### GET /api/app-pages/{app}/layout/source

App layout JSX. No auth required. Returns `text/plain` or 204 if no layout is set.

**Example:**
```bash
curl http://localhost:8000/api/app-pages/dashboard/layout/source
```

---

### GET /api/app-pages/{app}/{page}/source

App page JSX source. No auth required. Returns `text/plain`.

**Example:**
```bash
curl http://localhost:8000/api/app-pages/dashboard/overview/source
```

---

## 5. Schema CRUD

### POST /api/tools/define_schema

Store a named JSON schema. Auth required.

**Request body:**
```json
{
  "name": "sage-jobs/job",
  "definition": {"type": "object", "properties": {"status": {"type": "string"}}}
}
```

**Response:** `SchemaResult`
```json
{
  "name": "sage-jobs/job",
  "definition": {"type": "object", "properties": {"status": {"type": "string"}}},
  "created_at": "2026-03-19T12:00:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/define_schema \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"sage-jobs/job","definition":{"type":"object"}}'
```

---

### POST /api/tools/get_schema

Retrieve a schema by name. Auth required.

**Request body:**
```json
{"name": "sage-jobs/job"}
```

**Response:** `SchemaResult`

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/get_schema \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"sage-jobs/job"}'
```

---

### POST /api/tools/list_schemas

List all stored schemas. Auth required.

**Request body:** (none)

**Response:** `list[SchemaMeta]`
```json
[{"name": "sage-jobs/job", "created_at": "2026-03-19T12:00:00Z"}]
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/list_schemas \
  -H "X-Sage-Key: $KEY"
```

---

## 6. System

### GET /api/system/state

Runtime state: uptime, artifact counts. Auth required.

**Response:** `SystemState`
```json
{
  "uptime_seconds": 3600.5,
  "artifact_count": 12,
  "page_count": 3,
  "blob_count": 8,
  "schema_count": 1,
  "registered_apps": ["_example"]
}
```

**Example:**
```bash
curl http://localhost:8000/api/system/state \
  -H "X-Sage-Key: $KEY"
```

---

### GET /api/system/artifacts

Full artifact inventory: all pages, blobs, schemas, and recent events. Auth required.

**Response:** `ArtifactSummary`
```json
{
  "pages": [],
  "blobs": [],
  "schemas": [],
  "recent_events": []
}
```

**Example:**
```bash
curl http://localhost:8000/api/system/artifacts \
  -H "X-Sage-Key: $KEY"
```

---

### POST /api/tools/log_event

Append a structured log event. Auth required.

**Request body:**
```json
{
  "message": "Job completed",
  "level": "info",
  "context": {"job_id": "abc123"}
}
```

**Response:** `LogResult`
```json
{
  "id": 1,
  "timestamp": "2026-03-19T12:00:00Z",
  "message": "Job completed",
  "level": "info"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/log_event \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Job completed","level":"info"}'
```

---

### POST /api/tools/call

Generic tool call endpoint. Routes to any registered tool by name. Auth required.

**Request body:**
```json
{
  "tool": "write_blob",
  "arguments": {"key": "test", "data": "hello"}
}
```

**Response:** Varies by tool.

**Example:**
```bash
curl -X POST http://localhost:8000/api/tools/call \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool":"list_blobs","arguments":{"prefix":"sage-jobs/"}}'
```

---

## 7. App Bundle CRUD (DB multi-page apps)

### GET /api/app-bundles

List all DB-registered multi-page apps. No auth required.

**Response:** `list[dict]`

**Example:**
```bash
curl http://localhost:8000/api/app-bundles
```

---

### GET /api/app-bundles/{name}

Export a DB multi-page app as a JSON bundle download. No auth required.

**Response:** `application/json` attachment with `name`, `description`, `layout_jsx`, `pages[]`.

**Example:**
```bash
curl -o dashboard-bundle.json http://localhost:8000/api/app-bundles/dashboard
```

---

### POST /api/app-bundles

Import a JSON bundle, creating or updating the app and all its pages. Auth required.

**Request body:** `AppBundle`
```json
{
  "name": "dashboard",
  "description": "Main dashboard",
  "layout_jsx": "",
  "pages": [
    {"page": "index", "jsx_code": "function Page() { return <h1>Home</h1>; }", "description": ""}
  ]
}
```

**Response:** `AppBundleImportResult`
```json
{
  "name": "dashboard",
  "pages_imported": 1,
  "url": "http://localhost:8000/apps/dashboard/"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/app-bundles \
  -H "X-Sage-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"dashboard","pages":[{"page":"index","jsx_code":"function Page() { return <h1>Home</h1>; }"}]}'
```

---

## 8. MCP Transport

### GET /mcp/sse?key={api_key}

MCP Server-Sent Events transport. Auth via `key` query param.

**Example:**
```bash
curl -N "http://localhost:8000/mcp/sse?key=$KEY"
```

---

### POST /mcp/messages

MCP SSE message relay. Used internally by the SSE transport to receive client messages.

---

## 9. SPA Shell Routes

These routes serve the React shell (`index.html`) for client-side routing. No auth required.

| Route | Description |
|---|---|
| GET `/` | Dashboard (sage-dashboard) |
| GET `/artifacts` | Artifact browser (sage-artifacts) |
| GET `/apps/{path}` | Standalone page or multi-page app |
