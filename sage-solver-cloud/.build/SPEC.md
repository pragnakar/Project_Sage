# SPEC.md — Project Specification
# Project: Sage Cloud
# Version: 0.1 — Phase G1 Draft
# Last Updated: 2026-03-13

---

## Project Overview

Sage Cloud is a domain-agnostic LLM runtime environment built on FastAPI. It gives any MCP-compatible LLM agent a persistent execution layer: a SQLite-backed artifact store, a validated tool interface (12 core tools), a React page server, and a pluggable domain module system. The LLM is always external — Claude, ChatGPT, or any MCP client calls Sage Cloud over MCP (stdio or SSE) or REST HTTP. Sage Cloud never embeds a model. Domain tools and pages register at startup as app modules via a generalized protocol (`AppProtocol`). An example scaffold ships with Sage Cloud; domain-specific apps (sage, hermes, etc.) integrate from their own repositories.

---

## Goals

1. Ship a working Sage Cloud runtime (FastAPI + SQLite + 12 tools + MCP + React shell) in ≤5 Claude Code sessions
2. Ship a generalized app module interface so any developer or AI can fork Sage Cloud and build their own app
3. Validate the flywheel: artifacts accumulated across sessions, pages registered and served live

## Non-Goals (v0.1)

- Multi-tenancy, user accounts, or role-based access (API key per deployment only)
- Vite/Webpack build pipeline — Babel standalone CDN only
- Database migration tooling — schema is created fresh on first startup
- Any domain-specific app module (sage, hermes, athena) — these integrate from their own repos
- Production-grade JSX sandboxing

---

## Architecture

### System Components

| Component | Description |
|---|---|
| `sage_cloud/server.py` | FastAPI app, lifespan, health check, tool routes, app module loader |
| `sage_cloud/artifact_store.py` | SQLite + filesystem CRUD for blobs, pages, schemas, events |
| `sage_cloud/tools.py` | 12 core tools implemented against artifact_store; tool registry |
| `sage_cloud/models.py` | Pydantic v2 schemas for all tool I/O |
| `sage_cloud/auth.py` | API key middleware (X-Sage-Key header or ?key= query param) |
| `sage_cloud/mcp_transport.py` | MCP stdio + SSE transport; registers all 12 tools as MCP tools |
| `sage_cloud/page_server.py` | Dynamic route registration; JSX delivery endpoint |
| `sage_cloud/config.py` | pydantic-settings Settings class; env var config |
| `sage_shell/` | React shell app — route shell, Babel standalone JSX eval, built-in pages |
| `"sage_cloud_apps/_example/` | Example app scaffold — minimal demo tool + page + README |
| `docs/APP_MODULE_GUIDE.md` | Developer guide for building Sage Cloud app modules |

### Data Flow

1. LLM client (Claude Desktop, ChatGPT, HTTP) sends tool call over MCP or REST
2. `auth.py` middleware validates API key — 401 on failure
3. `tools.py` dispatches to correct tool function; validates input via Pydantic
4. Tool reads/writes `artifact_store.py` — SQLite + filesystem
5. Tool returns Pydantic model response
6. For pages: `page_server.py` serves JSX source; React shell fetches and Babel-evals it at `/apps/:name`

### Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime | FastAPI + uvicorn | Async, Pydantic-native, MCP-compatible |
| Storage | SQLite + filesystem (aiosqlite) | Zero-dependency for MVP; upgrade path to Postgres + S3 |
| Frontend | React + Babel standalone CDN | No build step; LLM JSX codegen quality; component accumulation |
| MCP transport | stdio + SSE | Both: stdio for Claude Desktop, SSE for ChatGPT/remote |
| App modules | Import at startup via `importlib` | Simple; no service discovery overhead for MVP |
| State | Per-request only | Multi-app safety; learned from sage-mcp ServerState limitation |
| Auth | API key (env var) | Sufficient for MVP single-deployment |

---

## Phase Plan

### Phase G1 — Runtime Core (CURRENT)

**Objective:** Build the FastAPI app, SQLite artifact store, all 12 core tools, API key auth, and tests — the complete runtime without MCP or UI.

**Branch:** `feature/g1-runtime-core`

**Deliverables:**
- [ ] GitHub repo `github.com/pragnakar/Project_Sage Cloud` created
- [ ] `pyproject.toml` — sage-solver-cloud package (fastapi, uvicorn, pydantic, aiosqlite, python-dotenv, mcp)
- [ ] `sage_cloud/config.py` — Settings class (SAGE_CLOUD_API_KEYS, SAGE_CLOUD_DB_PATH, SAGE_CLOUD_APPS)
- [ ] `sage_cloud/models.py` — Pydantic schemas: BlobResult, BlobMeta, PageResult, PageMeta, SchemaResult, SchemaMeta, LogResult, SystemState, ArtifactSummary
- [ ] `sage_cloud/artifact_store.py` — SQLite init + async CRUD for blobs, pages, schemas, events
- [ ] `sage_cloud/auth.py` — API key middleware (header + query param)
- [ ] `sage_cloud/tools.py` — All 12 core tools + ToolRegistry
- [ ] `sage_cloud/server.py` — FastAPI app, lifespan (DB init), tool routes, health check
- [ ] `tests/test_artifact_store.py` — CRUD round-trip tests
- [ ] `tests/test_tools.py` — All 12 tools, happy + error paths
- [ ] `tests/test_auth.py` — Valid key, invalid key, missing key

**Acceptance Criteria:**
- [ ] `pytest tests/` — all tests pass, zero failures
- [ ] `POST /tools/write_blob` → `GET /tools/read_blob` round-trip works end to end
- [ ] `GET /tools/list_blobs` returns correct results with prefix filter
- [ ] `GET /tools/get_system_state` returns uptime, artifact counts
- [ ] Invalid API key returns 401; missing key returns 401; valid key passes
- [ ] All tool responses are Pydantic models — no bare dicts in responses
- [ ] No module-level mutable state anywhere in `sage_cloud/`

**Verification Prompt:**
> "Review the Phase G1 implementation against SPEC.md and AGENT.md. Check each acceptance criterion. For each: state PASS or FAIL with specific evidence (test output, line numbers, or observed behaviour). List any items not yet implemented. Do not mark the phase complete until all criteria pass."

---

### Phase G2 — MCP Transport (PLANNED)

**Objective:** Expose all 12 core tools over MCP stdio and SSE transports so Claude Desktop and ChatGPT can call them.

**Branch:** `feature/g2-mcp-transport`

*Spec to be detailed after Phase G1 approval.*

**Key deliverables (stub):**
- `sage_cloud/mcp_transport.py` — register all 12 tools as MCP tools
- stdio transport entry point (`__main__.py`)
- SSE transport endpoint
- Verified: Claude Desktop can call `write_blob` and `read_blob` via MCP

---

### Phase G3 — Page Server + React Shell (PLANNED)

**Objective:** Add the dynamic page server and React shell so LLM-registered pages render live at `/apps/:name`.

**Branch:** `feature/g3-page-server`

*Spec to be detailed after Phase G2 approval.*

**Key deliverables (stub):**
- `sage_cloud/page_server.py` — dynamic route registration, JSX delivery
- `sage_shell/` — React shell, Babel standalone, built-in dashboard + artifact browser
- Verified: `create_page("test", jsx)` → `/apps/test` renders component
- Tag: `sage-cloud-v0.1.0`

---

### Phase G4 — Sage App Module ❌ DEFERRED

> **Status:** Deferred to Project Sage's own repository (decision 2026-03-13).
> **Rationale:** Sage has its own development lifecycle, dependency tree, and release cadence. Coupling it into Sage Cloud would violate domain-agnosticism. Sage will consume Sage Cloud as a dependency and integrate via the generalized app module interface.

**Original tasks G4-1, G4-2, G4-3:** Closed with deferral comments in ClickUp.

---

### Phase G-APP — Generalized App Module Interface (Replaces G4)

**Objective:** Ship the generalized app module protocol, example scaffold, and developer documentation so any developer or AI agent can fork Sage Cloud and build their own app module.

**Branch:** `feature/g-app-module-interface`

**ClickUp task:** 868hw9808 (at HUMAN-REVIEW-2)

**Key deliverables:**
- `sage_cloud/app_protocol.py` — `AppProtocol` (Python Protocol class) with `register(tool_registry, page_server, store)`
- `"sage_cloud_apps/_example/loader.py` — minimal working example (one demo tool + one demo page)
- App discovery and validation in `sage_cloud/server.py` — clear errors for bad loaders
- `GET /api/apps` and `GET /api/apps/{name}` — introspection endpoints
- `docs/APP_MODULE_GUIDE.md` — complete developer guide
- Tag: `sage-cloud-v0.1.0` (after G3 + G-APP pass)

---

## Data Models

| Entity | Table | Key Fields |
|---|---|---|
| Blob | `blobs` | key (TEXT PK), data (BLOB), content_type, size_bytes, created_at, updated_at |
| Page | `pages` | name (TEXT PK), jsx_code (TEXT), description, created_at, updated_at |
| Schema | `schemas` | name (TEXT PK), schema_json (TEXT), created_at |
| Event | `events` | id (INTEGER PK AUTOINCREMENT), timestamp, level, message, context_json |

Full SQL in `SAGE_CLOUD_SPEC.md` section 5.

---

## API Contracts

| Method | Path | Purpose | Phase |
|---|---|---|---|
| GET | `/health` | Health check | G1 |
| POST | `/tools/write_blob` | Write blob to store | G1 |
| GET | `/tools/read_blob` | Read blob by key | G1 |
| GET | `/tools/list_blobs` | List blobs by prefix | G1 |
| DELETE | `/tools/delete_blob` | Delete blob | G1 |
| POST | `/tools/create_page` | Register JSX page | G1 |
| PUT | `/tools/update_page` | Replace page JSX | G1 |
| GET | `/tools/list_pages` | List all pages | G1 |
| DELETE | `/tools/delete_page` | Delete page | G1 |
| POST | `/tools/define_schema` | Store JSON schema | G1 |
| GET | `/tools/get_schema` | Retrieve schema | G1 |
| GET | `/tools/list_schemas` | List all schemas | G1 |
| POST | `/tools/log_event` | Append log entry | G1 |
| GET | `/tools/get_system_state` | Runtime state | G1 |
| GET | `/tools/list_artifacts` | Full inventory | G1 |
| GET | `/api/pages/:name/source` | Serve JSX source | G3 |
| GET | `/` | React shell | G3 |
| GET | `/apps/:name` | Render registered page | G3 |
| GET | `/api/apps` | List loaded app modules | G-APP |
| GET | `/api/apps/:name` | App detail (tools, pages, status) | G-APP |

---

## Open Questions

- [ ] MCP SDK version — confirm latest compatible with FastAPI SSE; check if SSE deprecated in favor of Streamable HTTP — *Decision pending G2*
- [x] ~~sage-solver-core version to pin~~ — *No longer applicable: G4 deferred to Project Sage repo*
