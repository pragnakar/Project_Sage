# CLAUDE.md — Sage Cloud
# Claude Code session startup file

---

## Session startup sequence

Run this every session, in order, before touching any code:

1. Read `.build/AGENT.md` — your directive, rules, constraints, and output conventions
2. Read `.build/SPEC.md` — find the current active phase and its acceptance criteria
3. Read `.build/BUILD_LOG.md` — last entry tells you exactly where the build left off
4. Read `.build/Claude-AI_Claude-Code-ClickUp-SageCloud.md` — ClickUp coordination protocol
5. Check ClickUp → Claude Code Queue (`901113364003`) for pending tasks
6. Create a session log entry in Activity Log (`901113365508`)

Then report:
> "Resuming Sage Cloud. Last session: [last BUILD_LOG entry summary]. Current phase: [phase]. Ready to continue with: [next action]."

Ask: "Anything changed since last session I should know about?"

---

## What this project is

Sage Cloud is a domain-agnostic LLM runtime environment (FastAPI + SQLite + React). External LLM agents call Sage Cloud tools over MCP or REST HTTP to store artifacts, register live React pages, and run domain-specific tools. The LLM is always external — Sage Cloud never embeds a model. `sage/` is the first Sage Cloud app module.

---

## Workflow (ClickUp-gated)

```
OPEN-HUMAN-REVIEW → CLAUDE AI REVIEW → HUMAN-REVIEW-2 → HAND OFF TO CLAUDE CODE
→ TESTING-LOCAL → HUMAN-REVIEW-3 → PUSHED TO REMOTE HOSTS → COMPLETE
```

- Tasks enter at `OPEN-HUMAN-REVIEW` (created by Peter or Claude Code)
- Claude Code picks up work only when a task reaches `HAND OFF TO CLAUDE CODE`
- After build + local test → set status `TESTING-LOCAL`, add comment (pass or fail)
- Move to `HUMAN-REVIEW-3` for Peter to review
- Peter gates push → `PUSHED TO REMOTE HOSTS` → Claude Code pushes → `COMPLETE`
- Push failure: leave message in task chat, do not advance status

**ClickUp locations:**

| Purpose | List | ID |
|---|---|---|
| Tasks to pick up | → Claude Code Queue | `901113364003` |
| Results output | ← Claude Code Output | `901113364005` |
| Sage Cloud phase gates | Sage Cloud workflow | `901113373077` |
| Session logs | Activity Log | `901113365508` |
| Async comms | Chat | `901113365507` |

**ClickUp space/folder:**
- Space: Projects (`90030426535`) → Folder: Sage Cloud (`90117770941`)

---

## Phase dependency chain

```
G1 (runtime core) → G2 (MCP transport) → G3 (page server) → G4 (sage module)
```

Never begin a phase until the previous phase is verified and Peter has approved the gate task in Sage Cloud workflow (`901113373077`).

---

## Hard rules (never violate)

- No code in `sage_cloud/` that knows about domains (optimization, translation, etc.)
- No LLM API calls from inside Sage Cloud runtime
- No module-level mutable state
- No bare dicts — all tool returns are Pydantic models
- No secrets hardcoded — env vars only
- No React build step in v0.1 — Babel standalone CDN only
- Do not modify `sage_cloud_spec.md` (Peter's original vision doc)
- Do not touch Protocol, Memory, Soul, Evolution, Skills, or Tooling ClickUp folders (claude.ai domain)
- For any spec ambiguity → ask in Chat (`901113365507`) or Async Messages (`901113364006`). Never guess.

---

## Meta-prompts

Located at `.META_PROMPTS/` (separate git repo — read only, do not modify).

Key files:
- `.META_PROMPTS/BOOTSTRAP.md` — initialization protocol
- `.META_PROMPTS/LLM_NATIVE_SOFTWARE_ENGINEERING/LLM_NATIVE_SOFTWARE_ENGINEERING.md` — parent protocol
- `.META_PROMPTS/Testing_Strategy/Testing_Strategy.md` — test architecture

---

## If `.build/` does not exist

Read `.META_PROMPTS/BOOTSTRAP.md` and follow its initialization sequence. Do not write application code until initialization is complete and Peter has approved the Phase 1 spec.
