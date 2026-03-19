# BUILD_LOG.md — Build History
# Project: Sage Cloud
# Started: 2026-03-13

---

## Log Entry Format

```
[DATE] | [PHASE] | [ACTION]
---
Context: [What state the build was in before this entry]
Work:    [What was done in this session]
Result:  [What changed — files created, decisions made, problems encountered]
Next:    [What comes next — the immediate next action]
Evidence: [Test output, verification results, checksums, or links]
```

---

## Log

2026-03-13 | phase-0 | initialized
---
Context: New project. SAGE_CLOUD_SPEC.md and sage_cloud_architecture.jsx already authored by claude.ai Cowork instance. ClickUp coordination file in place. Git repo initialized on main branch.
Work:    Bootstrap protocol executed. Read BOOTSTRAP.md, LLM_NATIVE_SOFTWARE_ENGINEERING.md, Testing_Strategy.md. Created .build/ control documents: AGENT.md, SPEC.md, BUILD_LOG.md, spec/schemas/. Derived content from SAGE_CLOUD_SPEC.md.
Result:  Project scaffold complete. Phase G1 spec drafted in SPEC.md. AGENT.md captures all constraints, stack, ClickUp protocol, and output conventions.
Next:    Peter reviews SPEC.md Phase G1. claude.ai creates ClickUp tasks in Sage Cloud workflow. On Peter's approval (HAND OFF TO CLAUDE CODE), Claude Code begins Phase G1.
Evidence: .build/ directory created with AGENT.md, SPEC.md, BUILD_LOG.md, spec/schemas/. No application code written.

Meta-prompts loaded:
  ✓ LLM-Native Software Engineering (always)
  ✓ API Design (FastAPI REST + MCP tool interface)
  ✓ Database (SQLite artifact store)
  ✓ UI-UX (React shell)
  ✓ Security Engineering (API key middleware)
  ✓ Deployment Engineering (GitHub repo, remote hosts)
  ✓ DevOps (production operation)
  ✓ Testing Strategy (pytest, integration verification)
  ✓ Documentation

---

2026-03-13 | phase-G1 | complete
---
Context: Scaffold initialized. G1 tasks staged in ClickUp Sage Cloud workflow list (901113373077) by claude.ai, approved by Peter, handed off to Claude Code.
Work:
  G1-1 (868hw87m7) — Project scaffold, pyproject.toml, sage_cloud/config.py, sage_cloud/models.py, all stub modules. 31 tests.
  G1-2 (868hw87xp) — sage_cloud/artifact_store.py: ArtifactStore class, full async SQLite CRUD for blobs/pages/schemas/events. 24 tests.
  G1-3 (868hw8841) — sage_cloud/auth.py: verify_api_key FastAPI dependency, X-Sage-Key header + ?key= query param, dev bypass, production guard. 9 tests.
  G1-4 (868hw88dq) — sage_cloud/tools.py: ToolRegistry + 14 core tools + register_core_tools(). Tool metadata (name, description, JSON Schema params) ready for MCP in G2. 22 tests.
  G1-5 (868hw88n2) — sage_cloud/server.py: FastAPI lifespan, all HTTP routes under /api/, generic /api/tools/call endpoint, exception handlers, integration tests. 19 tests.
Result:
  Branch: feature/g1-runtime-core @ SHA 79ac953
  Repo: github.com/pragnakar/Project_Sage Cloud
  Full suite: 105/105 passed — zero failures, zero warnings
  Phase gate posted: [CLAUDE-CODE] Phase G1 complete (868hw8r3f) → OPEN-HUMAN-REVIEW
Notable fixes:
  - SchemaResult/DefineSchemaRequest: renamed .schema_json/.schema → .definition (Pydantic v2 shadowing)
  - auth.py: Settings injected via Depends(get_settings) not direct call — enables test overrides
  - tools.py: ToolRegistry.call() param renamed name→tool_name to avoid kwarg collision
  - server.py: lifespan reads app.dependency_overrides to respect test settings (temp DB isolation)
  - Spec §4 lists 14 tools (4+4+3+3), not 12 as stated in narrative — implemented all 14
Next: Peter reviews phase gate (868hw8r3f). On approval → G2 (MCP transport: stdio + SSE).
Evidence: pytest 105 passed. All 5 G1 tasks COMPLETE in ClickUp. SHA 79ac953 on remote.

---

2026-03-13 | phase-G2 | complete
---
Context: G1 complete (105 tests). Phase gate (868hw8r3f) approved by Peter. G2 tasks staged in ClickUp by claude.ai, handed off to Claude Code on branch feature/g2-mcp-transport.
Work:
  G2-1 (868hw88wy) — sage_cloud/mcp_transport.py: MCPBridge class, register_tools_with_mcp(), run_stdio(). sage_cloud/__main__.py: unified entry point (python -m sage_cloud, --mcp-stdio, --http). mcp_config.example.json: Claude Desktop config. pyproject.toml: mcp[cli]>=1.26.0 added. 12 tests.
  G2-2 (868hw891x) — mount_sse_transport(): GET /mcp/sse (auth via ?key= query param) + POST /mcp/messages mounted on FastAPI app. server.py lifespan calls mount_sse_transport(). __main__.py: --port flag added. README.md: full quick start. 8 tests.
Result:
  Branch: feature/g2-mcp-transport @ SHA 87a5845 — merged to main
  Repo: github.com/pragnakar/Project_Sage Cloud (main is now default branch; feature branches deleted)
  Full suite: 125/125 passed — zero failures, zero warnings
  Phase gate posted: [CLAUDE-CODE] Phase G2 complete (868hw9111) → OPEN-HUMAN-REVIEW
Notable decisions:
  - Used mcp 1.26.0 low-level Server API (not FastMCP) — ToolRegistry schemas flow directly to MCP inputSchema, no duplication
  - MCPBridge is a standalone class: all 12 transport tests use it directly (no JSON-RPC stdio setup needed)
  - SSE routes added via app.router.routes with in-place replacement on each lifespan restart — idempotent for test reuse of module-level FastAPI app
  - SSE auth via ?key= query param only (EventSource API does not support custom headers)
  - SSE streaming path is pragma: no cover in MCP SDK itself; unit tests cover auth + session error responses; full streaming tested end-to-end
  - list/bool tool return values wrapped in {"result": ...} (MCP structured content requires dict)
Next: Peter reviews phase gate (868hw9111). On approval → G3 (page server + React shell).
Evidence: pytest 125 passed. Both G2 tasks COMPLETE in ClickUp. SHA 87a5845 merged to main.

---

2026-03-13 | phase-G3 | complete
---
Context: G2 complete (125 tests). Phase gate (868hw9111) at OPEN-HUMAN-REVIEW. G3 tasks staged in ClickUp by claude.ai, handed off to Claude Code on branch feature/g3-page-server.
Work:
  G3-1 (868hw897m) — sage_cloud/page_server.py: PageServer class, _validate_name(), register_static() with upsert pattern, get_routes() returning unauthenticated APIRouter (GET /api/pages, /api/pages/{name}/source, /api/pages/{name}/meta). sage_cloud/artifact_store.py: get_page_source() added. server.py lifespan updated: register_builtin_pages, include_router(page_server.get_routes()), idempotent route replacement. 15 tests.
  G3-2 (868hw89bx) — sage_shell/index.html: self-contained React 18 shell using CDN React/ReactDOM + Babel standalone. Hash-based router (#/ → dashboard, #/artifacts → artifact browser, #/apps/{name} → DynamicPage). DynamicPage: fetches /api/pages/{name}/source, Babel-transforms JSX, evals named Page component or wraps bare JSX, 4 error states. ErrorBoundary class component with retry. Dark theme matching sage_cloud_architecture.jsx. server.py: SPA catch-all routes (GET /, /artifacts, /apps/{path}) serving index.html via FileResponse. 8 tests.
  G3-3 (868hw89gx) — sage_cloud/builtin_pages.py: sage-dashboard JSX (system state stats grid, registered pages list, recent events, quick links) + sage-artifacts JSX (tabs: Blobs/Schemas/Events, inline inspect). register_builtin_pages() upserts both at startup. server.py: calls register_builtin_pages(store) in lifespan. sage_shell/index.html: SageDashboard and ArtifactBrowser components delegate to DynamicPage. tests/test_g3_integration.py: 12 integration tests covering full create→serve→update→delete cycle. 12 tests.
Result:
  Branch: feature/g3-page-server @ SHA d1ed76c — merged to main
  Tag: sage-cloud-v0.1.0 created on main
  Repo: github.com/pragnakar/Project_Sage Cloud
  Full suite: 160/160 passed — zero failures, zero warnings
  Sage Cloud runtime is functionally complete: HTTP API + MCP stdio + MCP SSE + page server + React shell
Notable decisions:
  - PageServer routes are unauthenticated (GET only, read-only) — shell fetches JSX without a key
  - Built-in pages stored as Python multiline strings in builtin_pages.py, upserted on every lifespan start (handles server restarts cleanly)
  - index.html is fully self-contained (no external App.jsx) — Babel CDN transforms JSX in the browser
  - StaticFiles mount removed: shell has no external assets, catch-all routes (FileResponse) are sufficient and avoid shadowing lifespan-added /api/pages routes
  - DynamicPage supports both named Page components and bare JSX fragments
  - Built-in pages fetch /api/system/state (auth-gated): works in dev bypass mode, gracefully handles 401 in production
Next: Peter reviews G3 output. On approval → G-APP (generalized app module interface).
Evidence: pytest 160 passed. All G3 tasks COMPLETE in ClickUp. SHA d1ed76c merged to main. Tag sage-cloud-v0.1.0 pushed to remote.

---

2026-03-13 | phase-G-APP | complete
---
Context: G3 complete (160 tests, sage-cloud-v0.1.0 tagged). G-APP task (868hw9808) staged in ClickUp by claude.ai and handed off to Claude Code on branch feature/g-app-interface.
Work:
  G-APP (868hw9808) — Generalized app module interface, discovery API, example scaffold, and developer guide.
    sage_cloud/app_interface.py: SageCloudAppModule Protocol (documentation-first, runtime_checkable, not enforced).
    sage_cloud/app_routes.py: unauthenticated GET /api/apps (AppsResponse with core info), GET /api/apps/{name} (AppDetail with tools + pages), GET /api/apps/{name}/health (delegates to module.health_check()).
    sage_cloud/models.py: AppInfo, AppDetail, AppHealth, CoreInfo, AppsResponse, ToolInfo models added.
    sage_cloud/server.py: lifespan now tracks loaded_apps dict (module, meta, status); register() calls are awaited; app_routes mounted idempotently alongside page_server routes; app.state.loaded_apps persisted.
    "sage_cloud_apps/_example/: complete reference implementation — echo_tool, EchoResult, hello.jsx static page, APP_META, health_check(). Directory uses _ prefix (Python scaffold convention).
    docs/APP_MODULE_GUIDE.md: self-sufficient developer guide covering contract, tool/page patterns, testing, API reference, FAQ.
    sage_cloud/page_server.py: _NAME_RE updated to allow underscores (required for _example-hello page names).
    sage_cloud/config.py: SAGE_CLOUD_APPS default updated from 'sage' to '_example'.
    tests/test_app_interface.py: 12 tests — list/detail/health endpoints, namespace isolation, tool callability, graceful degradation for missing modules.
Result:
  Branch: feature/g-app-interface @ SHA a9a5f0a — merged to main @ SHA 22986a5
  Repo: github.com/pragnakar/Project_Sage Cloud
  Full suite: 172/172 passed — zero failures, zero warnings
  Sage Cloud is now forkable: any developer or AI can copy _example/, implement register(), and integrate in <30 minutes
Notable decisions:
  - Protocol is documentation-only (runtime_checkable but not enforced) — avoids forcing isinstance checks or import overhead on app authors
  - App pages filtered by prefix convention: pages named {app_name}-* belong to that app
  - Namespace isolation verified: _example tools register under '_example' namespace, core tools_count stays at 14
  - ModuleNotFoundError on load = silently skipped (app absent from list); other exceptions = recorded as status:'error'
  - _example directory convention signals "reference scaffold" to developers without polluting the namespace
  - G4 (Sage) deferred to Project Sage repo — will integrate via APP_GUIDE contract as an external module
Next: Project Sage follows APP_MODULE_GUIDE.md contract to integrate as a Sage Cloud app module. Sage Cloud runtime is complete.
Evidence: pytest 172 passed. Task 868hw9808 COMPLETE in ClickUp. SHA 22986a5 on main (remote).

---

2026-03-13 | post-G-APP | shell-hotfixes — end-to-end MCP verification
---
Context: Sage Cloud connected to Claude Desktop via MCP stdio. Live testing revealed three shell rendering issues with LLM-generated JSX.
Work:
  Fix 1 (e99d693) — Strip import/export statements before Babel transform.
    LLM-generated pages include `import React from 'react'` and `export default` which are invalid in the browser eval context. Stripped via regex before transform.
  Fix 2 (0502fb7) — Resolve export default component name when no Page function exists.
    LLM names components after the page (e.g. MyTest, Clock) rather than Page. Capture the exported name from `export default function Name` before stripping, fall back to it if Page is not found.
  Fix 3 (ed91b20) — Inject React hooks as named vars into page eval context.
    LLM-generated JSX uses destructured hooks (useState, useEffect, etc.) directly. Injected all 9 common hooks as named Function parameters alongside React.
Result:
  Full Claude Desktop → MCP stdio → create_page → page server → React shell → browser cycle verified working.
  Live pages tested: animated clock (useState/useEffect/intervals), kanban board (drag-and-drop), data-viz bar chart (CSS animations).
  172 tests still passing. No regressions.
  SHA ed91b20 on main (remote).
Notable:
  - All three issues are inherent to LLM code generation style — unlikely to need further fixes for common patterns
  - Shell now handles: named Page component, export default function AnyName, bare JSX, React.useState style, destructured hook style

---

2026-03-13 | task-868hwpqxk | DELETE /api/apps/{name} — complete
---
Context: Sage Cloud runtime complete (172 tests). Delete App task staged in ClickUp and handed off to Claude Code on branch feature/delete-app.
Work:
  868hwpqxk — Authenticated DELETE /api/apps/{name} with purge_data and force flags.
    sage_cloud/tools.py: ToolRegistry.unregister_namespace(namespace) -> int
    sage_cloud/artifact_store.py: delete_schema(name) -> bool implemented
    sage_cloud/models.py: AppDeleteResult(name, tools_removed, pages_removed, blobs_removed, schemas_removed, directory_removed)
    sage_cloud/app_routes.py: DELETE /api/apps/{name} — 404 if unknown, 409 if loaded without force=true, unregisters tools, deletes pages, purges blobs/schemas on purge_data=true, removes directory on force=true
    tests/test_delete_app.py: 12 tests — auth guard, 404, 409 protection, error-state delete, force delete, page/tool removal, purge_data blobs, purge_data schemas
Result:
  Branch: feature/delete-app @ SHA fed4ea9 — pushed to remote
  Full suite: 184/184 passed — zero failures, zero warnings
  Task 868hwpqxk COMPLETE in ClickUp.
Notable:
  - force=true tests patch shutil.rmtree to prevent deletion of real "sage_cloud_apps/_example/ during test runs
  - delete_schema was absent from ArtifactStore — added to support purge_data=true schema cleanup
  - Error-state apps can be deleted without force=true; only status="loaded" apps require it
Next: Merge feature/delete-app → main.
Evidence: pytest 184 passed. SHA fed4ea9 on remote branch feature/delete-app.

---

2026-03-16 | task-868hwpquk | Export App as ZIP — complete
---
Context: Delete App merged to main (184 tests). Export App task handed off to Claude Code on branch feature/export-app.
Work:
  868hwpquk — GET /api/apps/{name}/export endpoint.
    sage_cloud/app_routes.py: export_app() — builds ZIP in memory via zipfile.ZipFile + io.BytesIO, packages "sage_cloud_apps/{name}/ (no __pycache__), writes _export_meta.json; ?include_data=true adds _export_pages.json and _export_blobs.json
    Returns StreamingResponse(application/zip) with Content-Disposition: attachment; filename={name}.zip
    tests/test_export_app.py: 13 tests — 404, content-type, attachment header, valid ZIP, loader.py present, __init__.py present, __pycache__ excluded, metadata JSON, include_data pages/blobs, roundtrip source match
Result:
  Branch: feature/export-app @ SHA 406322a — merged to main via PR #1
  Full suite: 197/197 passed — zero failures, zero warnings
  Task 868hwpquk COMPLETE in ClickUp.
Notable:
  - Export is unauthenticated (consistent with other GET /api/apps/* endpoints)
  - Error-state apps with no directory on disk produce a ZIP with only _export_meta.json (no crash)
  - include_data reads live store state (pages/blobs) at export time — not a snapshot

---

2026-03-16 | task-868hwpqf3 | Import App from ZIP — complete
---
Context: Export App merged to main (197 tests). Import App task at HAND OFF TO CLAUDE CODE. Branch feature/import-app off main.
Work:
  868hwpqf3 — POST /api/apps/import: multipart ZIP upload, validate, extract, hot-load.
    sage_cloud/models.py: AppImportResult(name, status, tools_registered, pages_registered, message)
    sage_cloud/app_routes.py: import_app() — 10 MB limit, ZIP validation, single top-level dir detection, Python identifier check, path traversal rejection, __init__.py required, extract to "sage_cloud_apps/{name}/, importlib hot-load (reload if re-importing), returns AppImportResult
    sage_cloud/server.py: added /api/apps/import to _dynamic_paths for idempotent lifespan mounting
    tests/test_import_app.py: 14 tests — auth, 7 validation cases (non-zip, missing init, bare files, multiple dirs, invalid name, path traversal, oversized), happy path (mocked loader), disk extraction, 422 loader missing
Result:
  Branch: feature/import-app — merged to main via PR #2
  Full suite: 211/211 passed — zero failures, zero warnings
  Task 868hwpqf3 COMPLETE in ClickUp.
Notable:
  - Happy path tests mock importlib.import_module — extracted code in tmp_path is not on sys.path, so real import would fail in tests; extraction itself tested separately
  - Path traversal check covers both absolute paths and .. components
  - Hot-load uses importlib.reload() if module already in sys.modules (re-import scenario)

---

2026-03-16 | v0.3.0 | Dashboard UI overhaul (Claude AI review round 1 + round 2) — complete
---
Context: v0.2.0 shipped Delete/Export/Import App. Two rounds of Claude AI review produced a prioritized recommendation list; all items implemented and merged to main.

Work — Round 1 (sage-cloud-ui-recommendations.md):
  sage_cloud/builtin_pages.py (_DASHBOARD_JSX):
    - Replaced native <select> Actions with custom Dropdown component (stable ref, defined before Page())
    - API key validation: debounced fetch to /api/system/state, color dot indicator (green/red/gray)
    - Import ZIP: spinner state, success/error toast via showToast(), inline importMsg banner
    - Search/filter input on Registered Pages (debounced, filters name + description)
    - System/example page badges (sage- prefix = system tag, _ prefix = example tag)
    - Delete action hidden for system pages
    - Description truncation (overflow ellipsis + title tooltip, italic placeholder for missing)
    - Quick Links section removed entirely
    CSS: @keyframes spin for Import ZIP spinner
  sage_cloud/builtin_pages.py (_ARTIFACTS_JSX):
    - Pages tab added as first tab (was missing entirely)
    - Initial fetch extended to Promise.all([/api/system/artifacts, /api/pages])

Work — Round 2 (Claude AI review feedback):
  sage_cloud/builtin_pages.py:
    - fmtUptime(s): converts raw uptime_seconds to "Xm Ys" / "Xh Ym" human-readable format
    - openSource(name): fetches JSX source, renders in-app modal with <pre> viewer (both dashboard + artifact browser) — replaces window.open new-tab
    - showToast() added to doDelete + doDeletePage success and error paths
    - Stats grid cards clickable: Pages/Blobs/Schemas/Artifacts navigate to /#/artifacts?tab=<tab>
    - navArtifacts(tab) helper sets window.location.hash
    - Artifact Browser: compact/table view toggle for pages tab
    - Artifact Browser: reads initial tab from window.location.hash on mount (?tab=X)
  sage_shell/index.html:
    - parseRoute(): handles /artifacts?tab=X (startsWith check)
    - Nav: "API Docs" (/docs) and "Health" (/health) links added right-aligned via .nav-right CSS class
  sage_cloud/app_routes.py + sage_cloud/__init__.py + sage_cloud/__main__.py + sage_cloud/server.py + pyproject.toml:
    - Version bumped 0.2.0 → 0.3.0 across all files

Result:
  Branch: main @ SHA 0fdc443 (UI), bumped to 0.3.0
  Full suite: 211/211 passed — zero failures, zero warnings
Notable:
  - Dropdown component defined outside Page() function — stable React reference, no remount on render
  - sessionStorage persists API key across page refreshes
  - Source modal closes on click-outside (e.target === e.currentTarget check)
  - Tab deep-link: /#/artifacts?tab=blobs navigates directly to blobs tab on artifact browser mount

---

2026-03-18 | v0.3.0-session-2 | post-release fixes + multi-page JSON bundles — complete
---
Context: v0.3.0 shipped (SHA c8a86e8, 243 tests). Series of bug fixes and the multi-page JSON bundle feature added in a follow-up session.

Fixes:
  sage_cloud/__main__.py:
    - --mcp-stdio --http: all uvicorn log handlers redirected to stderr to prevent
      INFO: lines from polluting the MCP stdio JSON stream (SyntaxError in Claude Desktop)
    - _generate_api_key(): respects pre-set SAGE_CLOUD_API_KEYS env var instead of always overwriting
  sage_cloud/server.py:
    - GET /api/config (no auth): returns api_key, base_url, dashboard_url for browser discovery
  sage_cloud/builtin_pages.py:
    - Dashboard always fetches /api/config on load and overwrites sessionStorage — fixes stale
      key causing "Delete failed: invalid api key" after restart
  sage_cloud/artifact_store.py:
    - _page_url(): returns full absolute URL (http://localhost:8000/apps/name) so Claude
      no longer uses <sage-cloud-port> placeholders in responses
  claude_desktop_config.json:
    - Changed args from [--mcp-stdio] to [--mcp-stdio, --http]
    - Added SAGE_CLOUD_API_KEYS, SAGE_CLOUD_HOST, SAGE_CLOUD_PORT to env for stable configuration
  sage_cloud/tools.py:
    - get_sage_cloud_config(): 15th core tool — returns api_key, host, port, base_url, dashboard_url
      so Claude can discover connection details via MCP without manual copy-paste

Multi-page App Feature:
  sage_cloud/models.py:
    - AppResult, AppPageResult, AppPageMeta response models
    - CreateAppRequest, CreateAppPageRequest, UpdateAppPageRequest, ListAppPagesRequest
  sage_cloud/artifact_store.py:
    - New DB tables: apps, app_pages (composite PK, ON DELETE CASCADE)
    - Helpers: _app_base_url(), _app_page_url() (index → trailing slash)
    - Methods: create_app, get_app_layout, create_app_page, update_app_page,
      get_app_page_source, list_app_pages
  sage_cloud/tools.py:
    - create_app, create_app_page, update_app_page, list_app_pages (tools 16-19)
  sage_cloud/page_server.py:
    - GET /api/app-pages/{app}/layout/source (204 if no layout; registered before wildcard)
    - GET /api/app-pages/{app}/{page}/source (no auth — browser fetches JSX at runtime)
  sage_cloud/server.py:
    - POST /api/tools/create_app, create_app_page, update_app_page, list_app_pages (auth required)
    - New paths added to _dynamic_paths
  sage_shell/index.html:
    - Hash router replaced with path-based router (usePathname, navigate, popstate)
    - parseRoute() distinguishes: /apps/{name} → standalone, /apps/{name}/ → app index,
      /apps/{name}/{page} → app sub-page
    - DynamicAppPage: fetches layout + page in parallel, renders <Layout><Page/></Layout>
    - _transformJsx() extracted as shared helper used by both DynamicPage and DynamicAppPage
    - NavLink component intercepts same-origin clicks for SPA navigation (no full reload)
  Tests:
    - tests/test_app_store.py: 14 store-level tests
    - tests/test_app_tools.py: 4 tool-level tests
    - tests/test_app_page_routes.py: 13 HTTP integration tests

Result:
  Branch: main @ SHA c8a86e8
  Full suite: 243/243 passed — zero failures, zero warnings
  Sage Cloud package reinstalled at v0.3.0
Notable:
  - /apps/{name} (no trailing slash) = standalone page; /apps/{name}/ = multi-page app root
  - Layout JSX receives children prop: function Layout({children}){return <div>{children}</div>;}
  - Navigation inside app pages uses plain <a href="/apps/myapp/clock"> — no hash tricks
  - 19 core tools total (was 15)

---

2026-03-18 | v0.3.0-session-3 | dual export, last_opened_at, unified web-apps, dashboard UX — complete
---
Context: v0.3.0-session-2 complete (SHA 7f638fa, 243 tests). Full session of new features and UX improvements.

Work:

  sage_cloud/artifact_store.py:
    - Schema migrations (idempotent try/except ALTER TABLE): last_opened_at TEXT on pages + apps tables
    - touch_page(name) / touch_app(name): UPDATE last_opened_at = now, return rowcount > 0
    - list_apps(): added updated_at + last_opened_at to SELECT; page_count index shifted [3] → [5]
    - update_page / get_page / list_pages / upsert_page: pass last_opened_at through to models

  sage_cloud/models.py:
    - PageResult + PageMeta: added last_opened_at: str | None = None

  sage_cloud/server.py:
    - GET /apps/{path:path}: records access time — module apps → loaded_apps dict (in-memory),
      multi-page apps → store.touch_app(), standalone pages → touch_page() with touch_app() fallback
    - GET /api/web-apps: unified endpoint returning all three kinds (standalone pages, module apps,
      app_bundles) each with created_at, updated_at, last_opened_at; module app timestamps derived
      from min/max of associated {name}-* pages

  sage_cloud/page_server.py:
    - GET /api/pages/{name}/export: new manifest-based ZIP format — manifest.json at root,
      pages/{name}.jsx, optional blobs/ directory when ?include_data=true
    - Manifest schema: {sage_cloud_version, exported_at, name, description, kind:"page", pages[], blobs[]}
    - GET /api/pages/{name}/store + PUT /api/pages/{name}/store: blob namespace endpoints for pages

  sage_cloud/app_routes.py:
    - export_app(): replaced _export_meta.json/_export_pages.json/_export_blobs.json with
      manifest.json (kind:"module_app") + blobs/ directory
    - import_app(): refactored into 4-path router:
        PATH A — manifest.json at root → kind:"page" restores page+blobs and returns immediately;
                                          kind:"module_app" pre-reads blobs, extracts app dir, falls
                                          through to hot-load
        PATH B — bare .jsx files → legacy page import (unchanged)
        PATH C — other bare files → 400 error
        PATH D — no manifest, no bare files → legacy module app (unchanged)
      Blob restore executes after hot-load for PATH A module_app + PATH D

  sage_cloud/builtin_pages.py:
    - fmtDate(iso): "18 Mar" absolute short format for creation dates
    - fmtRelative(iso): "4d ago" relative format for modified/opened dates
    - Three-column timestamp layout in Available Web Apps: Created / Modified / Opened
      with column headers, hover tooltips (full datetime), and relative/absolute display
    - confirmDataExport state {name, kind, url, filename}: confirmation modal before data export
    - triggerDownload: shows "Preparing export…" loading toast (ok=null, indigo) before fetch;
      derives filename from Content-Disposition header
    - Toast render: ok===null → indigo (#6366f1 / #818cf8) for neutral/info state
    - Actions per kind: page + app_bundle get "Export App" + "Export App + Data" (→ modal);
      multi_page_bundle retains "Export Bundle" unchanged
    - Fixed \s regex escape: replaced /[\s]/ with /[\x20\t]/ to silence SyntaxWarning

  tests/:
    - test_page_server.py: 3 new tests — manifest present, include_data blobs, roundtrip restore
    - test_export_app.py: 4 tests updated to match new manifest.json + blobs/ ZIP format
    - test_server.py: updated for unified /api/web-apps response shape

Result:
  Branch: main @ SHA (pending commit)
  Full suite: 266/266 passed — zero failures, zero warnings
Notable:
  - Manifest-based import: manifest.json is a "bare file" (no /), checked first before bare-jsx path
  - Module app last_opened_at lives in loaded_apps dict — resets on server restart (intentional)
  - Module app timestamps in /api/web-apps derived from associated {name}-* pages (no DB row)
  - Touch routing edge case: /apps/myapp (no slash) tries touch_page first, touch_app as fallback

---

2026-03-18 | v0.3.0-session-3 | dual export, last_opened_at, unified web-apps — uncommitted
---
Context: v0.3.0-session-2 complete (SHA 7f638fa, 266 tests after this session). Series of feature additions building on the multi-page JSON bundle work.

Work:
  Dual Export (manifest-based ZIP):
    sage_cloud/page_server.py:
      - page_export route updated: new ?include_data=true param, ZIP structure changed to
        manifest.json + pages/{name}.jsx + optional blobs/ directory
      - manifest.json: {sage_cloud_version, exported_at, name, description, kind:"page", pages[], blobs[]}
      - Removed duplicate import json as _json; added datetime import
      - Added GET/PUT /api/pages/{name}/store endpoints (blob store proxy for page-scoped data)
    sage_cloud/app_routes.py:
      - export_app: replaced _export_meta.json/_export_pages.json/_export_blobs.json with
        manifest.json at ZIP root (kind:"module_app") + blobs/ directory
      - import_app: complete refactor into 4 routing paths:
          PATH A: manifest.json present → dispatch by kind (page or module_app)
          PATH B: bare .jsx files → legacy page import (return immediately)
          PATH C: other bare files → error
          PATH D: no manifest, no bare files → legacy module app (full dir extraction)
      - Blob restoration after hot-load for PATH A module_app

  last_opened_at tracking:
    sage_cloud/artifact_store.py:
      - Schema migrations: ALTER TABLE pages/apps ADD COLUMN last_opened_at TEXT (idempotent try/except)
      - Updated update_page, get_page, list_pages, upsert_page to carry last_opened_at field
      - Added touch_page(name) → bool: UPDATE pages SET last_opened_at = now WHERE name = ?
      - Updated list_apps(): added updated_at and last_opened_at to SELECT; page_count index shifted
      - Added touch_app(name) → bool: same pattern for apps table
    sage_cloud/models.py:
      - last_opened_at: str | None = None added to PageResult and PageMeta
    sage_cloud/server.py:
      - GET /apps/{path:path}: records access time on every browser visit
          Module apps → in-memory loaded_apps[name]["last_opened_at"]
          Multi-page apps (/apps/name/...) → store.touch_app(primary)
          Standalone pages → store.touch_page(primary) with touch_app fallback

  Unified /api/web-apps endpoint:
    sage_cloud/server.py:
      - GET /api/web-apps: returns three kinds (page, app_bundle, multi_page_bundle) normalized
      - All three kinds return created_at, updated_at, last_opened_at
      - Module apps derive created_at/updated_at from min/max of {name}-* pages in pages table

  Dashboard timestamp columns:
    sage_cloud/builtin_pages.py:
      - fmtDate(iso): absolute short format → "18 Mar"
      - fmtRelative(iso): relative format → "4d ago"
      - Column header row: Created / Modified / Opened with tooltip on each
      - Each row: three right-aligned timestamp columns (fmtDate, fmtRelative, fmtRelative or —)
      - All timestamps have title={new Date(wa.xxx).toLocaleString()} for ISO on hover

  Dual Export UI in Dashboard:
      - confirmDataExport state: {name, kind, url, filename}
      - triggerDownload: shows "Preparing export…" loading toast (ok=null, indigo) before fetch
      - Filename derived from Content-Disposition response header
      - Toast render: handles ok === null → indigo color
      - Confirmation modal with ⚠ warning before data export
      - Page actions: "Export App" (plain) + "Export App + Data" (→ confirmation modal)
      - App bundle actions: same two options

  Tests:
    tests/test_page_server.py:
      - test_page_export_contains_manifest: verifies manifest.json + pages/{name}.jsx in ZIP
      - test_page_export_with_data_includes_blobs: verifies ?include_data=true adds blobs
      - test_page_export_with_data_roundtrip: export+data → delete → import → verify restored
    tests/test_export_app.py:
      - Updated 4 tests to match new manifest.json + blobs/ format (removed old _export_*.json checks)

Result:
  Branch: main (uncommitted changes)
  Full suite: 266/266 passed — zero failures, zero warnings
  SHA: HEAD at 7f638fa (pre-commit)
Notable:
  - manifest.json at ZIP root uses "bare file" position — import routing checks manifest first
    before treating bare files as legacy .jsx (routing order matters)
  - \s in JS regex inside Python string → SyntaxWarning; fixed with \x20\t literal characters
  - Module app last_opened_at is session-local (in-memory dict); resets on server restart — intentional
  - list_apps() column index shift (updated_at, last_opened_at added → page_count moved [3]→[5])
Next: Commit session-3 work. Address Artifact Browser bug (sage-artifacts fetches /api/system/artifacts
      without auth header → all tabs except Pages show empty).
Evidence: pytest 266 passed (local).
