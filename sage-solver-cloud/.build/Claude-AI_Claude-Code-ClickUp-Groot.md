# Claude-AI + Claude-Code + ClickUp
## Project Groot Coordination File

Copy of two-instance coordination template, filled for Project Groot.
Based on: `Claude Code → Skills (901113365655)` template v2026-03-13.

---

## What this is

This project uses a two-instance Claude system coordinated through ClickUp:

* **claude.ai** — planning, synthesis, task specification, context management
* **Claude Code** — execution, implementation, reporting results

ClickUp is the shared memory and coordination layer between both instances and Peter.

---

## Human context

Peter Pragnakar Atreides — systems thinker, financial engineering background, Toronto-based. Terse, high-context, top-down. Responds to honest pressure-testing, not validation. Lead with the answer, then justify. If something is wrong, say so immediately.

---

## Workspace

**Claude Space** (ID: `90114111082`) — coordination infrastructure
**Projects Space** (ID: `90030426535`) — Groot folder (ID: `90117770941`)

---

## Shared (Bridge) — Claude Space

| List | ID | Purpose |
|---|---|---|
| → Claude Code Queue | `901113364003` | claude.ai stages work here |
| ← Claude Code Output | `901113364005` | Claude Code drops results here |
| Async Messages | `901113364006` | Flags, questions, ambiguity notices |

---

## Claude Code Home — Claude Space

| List | ID | Purpose |
|---|---|---|
| Workspace | `901113365506` | Scratch space |
| Chat | `901113365507` | Async comms with claude.ai — prefix `[FROM:CODE]` |
| Activity Log | `901113365508` | Per-session logs |
| Skills | `901113365655` | Coordination templates (base template lives here) |

---

## Groot Project Lists — Projects Space

| List | ID | Purpose |
|---|---|---|
| Groot workflow | `901113373077` | Phase tasks, deliverable review — Peter gates here |

**Pattern:** Claude Code posts `[CLAUDE-CODE] Phase G{N} complete — {summary}` to `901113373077` with status `open-human-review` when a phase is done. Peter reviews and approves before the next phase begins.

---

## Claude Code External Memory (Bootloader)

Claude Code has a dedicated persistent memory folder in ClickUp:

Space: Claude (ID: `90114111082`)
Folder: Claude Code (ID: `90117767626`)

Session startup sequence:
1. Read Orientation Notes (task `868hvvjtg`) from Workspace list (`901113365506`)
2. Check Bridge → Claude Code Queue (`901113364003`) for pending tasks
3. Create session log in Activity Log (`901113365508`)

Domain rules: Claude Code has full liberty inside the Claude Code folder. Protocol, Memory, Soul, Evolution, Skills, and Tooling folders are claude.ai's domain — read only for Claude Code. Never modify Secrets values.

---

## Task lifecycle

```
OPEN-HUMAN-REVIEW → CLAUDE AI REVIEW → HUMAN-REVIEW-2 → HAND OFF TO CLAUDE CODE → TESTING-LOCAL → HUMAN-REVIEW-3 → PUSHED TO REMOTE HOSTS → COMPLETE
```

Standard path:
1. Peter **or** Claude Code creates task in Groot workflow (`901113373077`) at `OPEN-HUMAN-REVIEW`
2. Peter reviews, makes any changes, then moves to `CLAUDE AI REVIEW`
3. claude.ai refines and perfects the spec, moves to `HUMAN-REVIEW-2` — Peter reviews
4. Peter approves, sets status → `HAND OFF TO CLAUDE CODE`
5. Claude Code picks up task, builds, sets status → `TESTING-LOCAL`
6. Claude Code tests locally; on pass or fail, adds comment and sets status → `HUMAN-REVIEW-3`
7. Peter reviews and approves, sets status → `PUSHED TO REMOTE HOSTS`
8. Claude Code pushes to remote hosts:
   - **Success** → sets status → `COMPLETE` (final)
   - **Failure** → leaves message in task chat, does NOT advance status

---

## Task spec contract

Every formal task from claude.ai follows this format:

```
## Objective
One sentence: what this task produces.

## Context
Why this matters. What it connects to.

## Specification
Detailed requirements. Acceptance criteria.

## Constraints
What NOT to do. Boundaries.

## Output
What to deliver and where to put it.

---
⛔ DEPENDS_ON: {task_id}  (if applicable)
🔒 BLOCKS: {task_id}      (if applicable)
---
```

---

## Dependency protocol

Before starting any task, check description for DEPENDS_ON:
* If blocker status ≠ complete or done → do not proceed
* Set status → blocked, add comment explaining what you're waiting for

Phase dependencies for Groot v0.1:
```
G1 (runtime core) → G2 (MCP transport) → G3 (page server) → G4 (sage app module)
```
Each phase BLOCKS the next. Do not begin G2 until G1 is complete and Peter has reviewed.

---

## Secrets access

For REST API calls the MCP can't handle, read the API key from Secrets → API Keys (task `868hvrv85`). Pull fresh each time — never hardcode.

Auth header: `Authorization: {token}`, `Content-Type: application/json`
Base URL: `https://api.clickup.com/api/v2`

---

## Status values

These statuses apply to the Groot workflow list (`901113373077`) in the Projects space (`90030426535`), Groot folder (`90117770941`).

| Status | Who moves it | Action |
|---|---|---|
| `OPEN-HUMAN-REVIEW` | Peter or Claude Code | Either creates task here; Peter reviews and makes any changes before moving forward |
| `CLAUDE AI REVIEW` | Peter | Peter moves it here; claude.ai refines and perfects the spec |
| `HUMAN-REVIEW-2` | claude.ai | claude.ai moves it here after refining; Peter reviews |
| `HAND OFF TO CLAUDE CODE` | Peter | Peter approves spec and hands off; Claude Code picks up and builds |
| `TESTING-LOCAL` | Claude Code | Claude Code sets this after build; tests locally |
| `HUMAN-REVIEW-3` | Claude Code | Claude Code moves here after test (pass or fail with comment); Peter reviews |
| `PUSHED TO REMOTE HOSTS` | Peter | Peter approves; Claude Code pushes to remote hosts |
| `COMPLETE` | Claude Code | Claude Code sets after successful push — **final status** |

On push failure: Claude Code leaves a message in the task chat and does NOT move to `COMPLETE`.

---

## Rules

* If a spec is ambiguous → ask in Chat or Async Messages, do NOT guess
* Always leave a comment on a task when completing it
* Claude Code does not modify Protocol, Memory, Soul, Evolution, Skills, or Tooling folders
* Claude Code is not a background process — it only runs when a session is open
* Conventional commit messages always
* Never proceed to next phase without Peter's approval in Groot workflow list

---

## Domain boundaries

| Domain | Owner | Access |
|---|---|---|
| Claude Code folder | Claude Code | Full liberty |
| Bridge (→ Queue, ← Output) | Shared | Claude Code reads Queue, writes Output |
| Groot workflow (`901113373077`) | Shared | Claude Code writes phase completions; Peter approves |
| Protocol, Memory, Soul, Evolution, Skills, Tooling | claude.ai | Claude Code: read only |
| Secrets | Shared | Read only. Never modify key values. |

---

## PROJECT-SPECIFIC: Project Groot

### Project name
Project Groot — Domain-agnostic LLM runtime environment

### What Groot is (one paragraph for orientation)
Groot is a FastAPI-based runtime that gives any external MCP-compatible LLM agent a persistent execution layer: an artifact store (SQLite + filesystem), a validated tool interface, a React page server, and a pluggable domain module system. The LLM is always external — Claude, ChatGPT, or any MCP client calls Groot tools over MCP (stdio or SSE) or REST HTTP. Groot never embeds a model. Domain-specific tools and pages register at startup as app modules. `sage/` is the first Groot app, wrapping sage-solver-core.

### Current status (as of 2026-03-13)
- Spec: `GROOT_SPEC_V0.1.md` — COMPLETE (authored by claude.ai Cowork instance)
- Architecture diagram: `groot_architecture.jsx` — React component, first Groot artifact
- Claude Code Queue: Phase G1 task staged (`868hw3jww`)
- GitHub repo: NOT YET CREATED — Claude Code creates it in Phase G1
- Phase G1: pending Claude Code execution
- sage-solver-core: already shipped v0.1.3, 470 tests passing — import only in sage/ module

### Key documents Claude Code must read at session start
1. `GROOT_SPEC_V0.1.md` — full build spec, 4 phases, tool interface, data model
2. `groot_spec.md` — Peter's original vision (the why)
3. `BACK_TO_WORK_SPEC.md` — sage-cloud spec (becomes Phase G4)
4. `HANDOFF.md` — sage-solver-core architecture (do not re-implement anything)

All files delivered via Claude Code Queue task `868hw3jww`.

### Build phases and phase gate tasks

| Phase | Hours | Description | Gate task in 901113373077 |
|---|---|---|---|
| G1 | 1–10 | Runtime core: FastAPI + SQLite + 12 tools + auth | `[CLAUDE-CODE] G1 complete — runtime core` |
| G2 | 11–16 | MCP transport: stdio + SSE | `[CLAUDE-CODE] G2 complete — MCP transport` |
| G3 | 17–26 | Page server + React shell | `[CLAUDE-CODE] G3 complete — page server` → tag `groot-v0.1.0` |
| G4 | 27–38 | sage/ app module (sage-cloud v0.2) | `[CLAUDE-CODE] G4 complete — sage module` → tag `sage-v0.2.0` |

### Constraints specific to Project Groot

1. **Groot runtime is domain-agnostic.** No solver logic, no optimization code, no domain knowledge inside `groot/`. All domain code lives in `groot-apps/{name}/`.
2. **LLM is always external.** Never embed a model, never call an LLM API from inside the Groot runtime. Groot is the runtime; LLMs are its callers.
3. **React for all UI.** No Flutter, no htmx, no Jinja2. LLM codegen quality for JSX is the deciding factor.
4. **No module-level mutable state.** Per-request state only. Learned from sage-mcp v0.1 `ServerState` limitation.
5. **Do not touch sage-solver-core from Groot runtime.** Import it only inside `groot-apps/sage/`. Never add solver dependencies to `groot/pyproject.toml`.
6. **sage/ app module never re-implements solver logic.** It calls `sage-solver-core` functions. Same rule as sage-mcp.
7. **Babel standalone for JSX eval in v0.1.** No Webpack, no Vite, no build step. Ship fast. Mark v0.2 for proper module federation.
8. **Artifact store is append-friendly.** Prefer update over delete. Never delete artifacts without explicit Peter approval.
9. **All tool calls return Pydantic models.** No bare dicts, no raw exceptions. Structured errors only.
10. **Claude Code does not touch `groot_spec.md` (Peter's original vision doc).** Read it for orientation; never overwrite it.

### Output conventions

**Repo:** `github.com/pragnakar/Project_Groot` (create in Phase G1)

**Branch naming:**
```
feature/g{N}-{kebab-description}
e.g. feature/g1-runtime-core
     feature/g2-mcp-transport
     feature/g3-page-server
     feature/g4-sage-module
```

**Commit messages:** Conventional commits
```
feat(groot): add artifact store SQLite backend
feat(sage): register solve_optimization tool
fix(runtime): handle empty artifact store on startup
test(tools): add write_blob round-trip test
docs: update README with phase G1 status
```

**Tags:**
```
groot-v0.1.0-g1  (after G1 merged)
groot-v0.1.0-g2  (after G2 merged)
groot-v0.1.0     (after G3 merged — runtime complete)
sage-v0.2.0      (after G4 merged — first Groot app)
```

**Phase completion deliverable (to Groot workflow `901113373077`):**
```
Name:    [CLAUDE-CODE] Phase G{N} complete — {one-line summary}
Status:  open-human-review
Body:
  ## What was built
  ## Tests passing
  ## How to verify
  ## Next phase ready to start: G{N+1}
  ## DEPENDS_ON: {this task id}
```

**Results files:** Push to GitHub. Link in ← Claude Code Output task.

**In-chat design flow:** claude.ai (Cowork) generates React components in chat → Peter approves → Claude Code calls `create_page` to store in Groot artifact store. Do not build UI components without going through this review cycle.

### Groot tool interface reference (for Claude Code orientation)

Core tools (12 total) Claude Code must implement in Phase G1:

**Storage:** `write_blob`, `read_blob`, `list_blobs`, `delete_blob`
**Pages:** `create_page`, `update_page`, `list_pages`, `delete_page`
**Schemas:** `define_schema`, `get_schema`, `list_schemas`
**System:** `log_event`, `get_system_state`, `list_artifacts`

Full specs in `GROOT_SPEC_V0.1.md` sections 4 and 5.

---

*Template base: Claude Code → Skills (`901113365655`)*
*Project fill-in: claude.ai Cowork instance, 2026-03-13*
*Groot spec ref: `GROOT_SPEC_V0.1.md`, Claude Code Queue task `868hw3jww`*
