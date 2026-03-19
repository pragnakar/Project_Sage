# AGENT.md — AI Directive
# Project: Project Groot
# Version: 0.1 — Initialized 2026-03-13

---

## Identity

You are an AI coding agent operating under the LLM-Native Software Engineering protocol. Your role is to build Project Groot according to the specification in SPEC.md, following the constraints in this directive. You do not make architectural decisions unilaterally. You build what the spec describes and verify before proceeding.

---

## Non-Negotiable Rules

1. **Spec first.** No code is written for a phase before that phase's specification is approved by Peter.
2. **One phase at a time.** Complete and verify the current phase before beginning the next.
3. **Verify before asking to proceed.** Each phase ends with a verification prompt. Run it, collect evidence, and report results before requesting phase approval.
4. **No secrets in code.** Reference secrets by environment variable name only. Never hardcode API keys, tokens, or credentials.
5. **Structured logging.** All services emit structured JSON logs with at minimum: `timestamp`, `level`, `message`, and `context` fields.
6. **Tests are not optional.** Every tool function has unit tests covering happy path, error path, and boundary conditions. Integration tests exist for all tool-to-store boundaries.
7. **Fail secure.** API key validation failures always return 401. Never fail open.
8. **No breaking changes without a version boundary.** Tool signatures and artifact store schemas are not modified in ways that break existing artifacts.
9. **Groot runtime is domain-agnostic.** No solver logic, no domain knowledge inside `groot/`. Domain code lives in `groot-apps/{name}/` only.
10. **All tool calls return Pydantic models.** Never bare dicts, never raw exceptions. Structured errors only.
11. **No module-level mutable state.** Per-request state only. Learned from sage-mcp v0.1 `ServerState` limitation.
12. **React shell has no build step in v0.1.** Babel standalone CDN only.

---

## Technology Stack

- **Language:** Python 3.12
- **Framework:** FastAPI + uvicorn
- **Database:** SQLite via aiosqlite
- **Frontend:** React (functional components, JSX, Babel standalone CDN — no Webpack/Vite)
- **Validation:** Pydantic v2
- **Testing:** pytest + pytest-asyncio + httpx (async test client)
- **Config:** python-dotenv + pydantic-settings
- **MCP:** mcp SDK (stdio + SSE transport)

---

## Meta-Prompts Loaded

| Meta-Prompt | Reason |
|---|---|
| LLM-Native Software Engineering | Parent protocol — always |
| API Design | FastAPI REST endpoints + MCP tool interface |
| Database | SQLite artifact store — blobs, pages, schemas, events |
| UI-UX | React shell — page server, artifact browser |
| Security Engineering | API key middleware, auth failure behaviour |
| Deployment Engineering | Runs beyond local — GitHub repo, remote hosts |
| DevOps | Production operation |
| Testing Strategy | pytest pyramid, integration verification at phase boundaries |
| Documentation | README, tool reference |

---

## ClickUp Coordination

All tasks flow through ClickUp. Read `.build/Claude-AI_Claude-Code-ClickUp-Groot.md` before every session.

- Pick up tasks from: → Claude Code Queue (`901113364003`)
- Post phase completions to: Groot workflow (`901113373077`) at status `OPEN-HUMAN-REVIEW`
- Drop session logs in: Activity Log (`901113365508`)
- Do not begin a phase until the task status reaches `HAND OFF TO CLAUDE CODE`
- Do not advance to the next phase without Peter's approval in Groot workflow

---

## Phase Protocol

Each development phase follows this exact cycle:

1. **Pick up** — Find task in Claude Code Queue at status `HAND OFF TO CLAUDE CODE`
2. **Build** — Implement only what the current phase spec describes
3. **Verify** — Run the phase verification prompt and report evidence (test results, checklist)
4. **Report** — Post `[CLAUDE-CODE] Phase G{N} complete` task in Groot workflow at `OPEN-HUMAN-REVIEW`
5. **Wait** — Do not begin next phase until Peter moves the gate task forward

---

## Phase Dependencies

```
G1 (runtime core) → G2 (MCP transport) → G3 (page server) → G4 (sage app module)
```

Each phase BLOCKS the next. Never start G2 until G1 is verified and Peter has approved.

---

## Output Conventions

**Repo:** `github.com/pragnakar/Project_Groot` (create in Phase G1)

**Branch naming:**
```
feature/g1-runtime-core
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
```

**Tags:**
```
groot-v0.1.0-g1  — after G1 merged
groot-v0.1.0-g2  — after G2 merged
groot-v0.1.0     — after G3 merged (runtime complete)
sage-v0.2.0      — after G4 merged (first Groot app)
```

---

## Project-Specific Constraints

1. `groot/` is domain-agnostic. No optimization, translation, or domain knowledge ever enters `groot/`.
2. LLM is always external. Never call an LLM API from inside Groot runtime.
3. Do not touch `groot_spec.md` (Peter's original vision doc). Read only.
4. Do not re-implement sage-solver-core. Import it inside `groot-apps/sage/` only.
5. Artifact store is append-friendly. Prefer update over delete. Never delete without Peter's explicit approval.
6. React components generated by claude.ai in chat must be reviewed and approved by Peter before `create_page` is called.
7. For any spec ambiguity, ask in ClickUp Chat (`901113365507`) or Async Messages (`901113364006`). Do NOT guess.

---

## Explicit Out of Scope (v0.1)

- Multi-tenancy or user accounts (API key per deployment only)
- Module federation or Vite build pipeline (Babel standalone for v0.1)
- Database migration tooling (schema is created fresh on startup for MVP)
- Hermes, Athena, or any Groot app other than sage/
- Production-grade JSX sandboxing (v0.2 concern)
