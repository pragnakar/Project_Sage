Claude-AI + Claude-Code + ClickUp — SAGE

Two-Instance Coordination Document

Copy .build/Claude-AI_Claude-Code-ClickUp-Sage.md into any SAGE sub-project. Fill in PROJECT-SPECIFIC sections. Leave the rest as-is.

What This Is

SAGE uses a two-instance Claude system coordinated through ClickUp:

[CLAUDE-AI] claude.ai — planning, synthesis, task specification, architecture decisions, context management, cross-project thinking
[CLAUDE-CODE] Claude Code — execution, implementation, testing, git operations, reporting results

ClickUp is the shared memory and coordination layer between both instances and Peter (human operator).

Both instances prefix all ClickUp comments, chat messages, and task updates with their identity tag:

[CLAUDE-AI] — posted by claude.ai
[CLAUDE-CODE] — posted by Claude Code

Human Context

Peter Pragnakar Atreides — systems thinker, financial engineering background, Toronto-based.

Terse and high-context. Thinks top-down, fast.
Responds to honest pressure-testing, not validation.
Lead with the answer, then justify.
If something is wrong, say so immediately.
SAGE is the beachhead project of Mission RnD — a civilizational portfolio grounded in cybernetics.

Project: SAGE — Solver-Augmented Grounding Engine

Repo: https://github.com/pragnakar/Project_Sage
PyPI: pip install sage-solver-mcp / uvx sage-solver-mcp
Current version: sage-solver-core 0.1.3 + sage-solver-mcp 0.1.3
Status: Phase 1 (local MCP server) COMPLETE. Phase 2 (sage-solver-cloud) IN PROGRESS.

ClickUp Workspace

Space: Projects (ID: 90030426535)
Folder: SAGE (ID: 90117730088)
Workflow List: workflow (ID: 901113316569)
This Document: https://app.clickup.com/2258523/docs/24xjv-3151

Claude Code External Memory (Bootloader)

Claude Code has a dedicated persistent memory folder in ClickUp:

Space: Claude (ID: 90114111082)
Folder: Claude Code (ID: 90117767626)

This is the bootloader — every new Claude Code session should read from this folder
to rehydrate context before starting work.

Lists in Claude Code folder:
- Workspace     (901113365506) — orientation notes, scratch reference
- Chat          (901113365507) — async comms with claude.ai, prefix [FROM:CODE]
- Activity Log  (901113365508) — per-session logs, create one each session
- Skills        (901113365655) — coordination templates (this file lives here)

Session startup sequence (run in order):
1. Read Orientation Notes (task 868hvvjtg) from Workspace list
2. Check Bridge → Claude Code Queue (901113364003) for pending tasks
3. Create session log in Activity Log (901113365508)

Domain: Claude Code has full liberty inside the Claude Code folder. The folders
Protocol, Memory, Soul, Evolution, Skills (🎯), and Tooling in the Claude space
are claude.ai's domain — read only for Claude Code.

Workflow Statuses


Task Lifecycle

Open-Human-Review
       ↓
Claude-AI-Review         ← [CLAUDE-AI] reviews, adds spec, comments questions
       ↓
Human-AI-Review-2        ← Peter confirms
       ↓
Hand-off-to-Claude-Code  ← [CLAUDE-AI] writes full spec in task description
       ↓
Testing-Local            ← [CLAUDE-CODE] implements + runs pytest
       ↓
Push-to-Remote           ← [CLAUDE-CODE] pushes to GitHub + PyPI/MCP Registry
       ↓
closed                   ← Done

Blocked tasks: set status → blocked, comment [CLAUDE-CODE] Blocked: waiting on {task_id}.

Task Spec Contract

Every task handed off to Claude Code follows this format:

## Objective
One sentence: what this task produces.

## Context
Why this matters. What it connects to in SAGE architecture.

## Specification
Detailed requirements. Acceptance criteria. File paths. Function signatures if relevant.

## Constraints
What NOT to do. Boundaries. Design rules from .build/AGENT.md that apply.

## Output
What to deliver. Where to put it. Commit message format. Whether to bump version.

---
⛔ DEPENDS_ON: {task_id}  (if applicable)
🔒 BLOCKS: {task_id}      (if applicable)
---

Communication Protocol

Both instances use ClickUp task comments and the workflow list as the communication layer.

[CLAUDE-AI] writes task specs, reviews outputs, asks clarifying questions via comments
[CLAUDE-CODE] posts implementation summaries, test results, blockers, and git SHAs via comments
Either instance can create tasks in the workflow list
Tag the other instance in comments using [CLAUDE-AI] or [CLAUDE-CODE] prefix

Async questions: Post a comment on the relevant task prefixed [CLAUDE-CODE] QUESTION: or [CLAUDE-AI] QUESTION:. Do not guess. Do not proceed on ambiguous specs.

SAGE-Specific Constraints for Claude Code

sage-solver-core never touches the filesystem. No exceptions.
Every solver call returns a SolverResult. Never expose raw HiGHS output.
All errors are SAGEError subclasses. No bare exceptions.
No PuLP. Direct highspy bindings only.
No print(). Return structured data or logging.
Do not build sage-solver-cloud beyond what the current task specifies.
Do not use WidthType.PERCENTAGE in Excel formatting.
Run full test suite before and after every change. Both packages. 470 passing is the baseline.
Conventional commit messages always: feat:, fix:, test:, docs:, refactor:.
Read .build/AGENT.md at the start of every Claude Code session.

Dev Setup (Claude Code reference)

git clone https://github.com/pragnakar/Project_Sage && cd Project_Sage
pip install -e sage-solver-core/ && pip install -e sage-solver-mcp/
cd sage-solver-core && pytest tests/ -v   # expect 393 passed
cd ../sage-solver-mcp && pytest tests/ -v # expect 77 passed

Claude Desktop config:

{
  "mcpServers": {
    "sage": { "command": "/opt/homebrew/bin/uvx", "args": ["sage-solver-mcp"] }
  }
}

Current State Summary

Phase 1 — COMPLETE (v0.1.3)


Published to: PyPI, MCP Registry, Claude Desktop Extensions.

Phase 2 — IN PROGRESS (sage-solver-cloud)

Target: FastAPI server so ChatGPT and any SSE-capable LLM can call SAGE remotely.

sage-solver-cloud/
└── sage_solver_cloud/
    ├── api.py           ← FastAPI; HTTP routes mirror the 7 MCP tools
    ├── auth.py          ← API key auth (header-based)
    ├── jobs.py          ← Async job manager (long-running solves)
    ├── storage.py       ← S3/GCS file bridge
    ├── mcp_transport.py ← Remote MCP via SSE (unlocks ChatGPT)
    └── web/             ← Interactive result UI (Jinja2)

Constraints:

Imports sage-solver-core only — never re-implements solver logic
Multi-tenant: isolated state per request
Async-first: long-running solves must not block event loop
SSE transport, not stdio
V1 is auth-free; V2 introduces API key auth

7 MCP Tool Names (fixed — do not rename)

solve_optimization     read_data_file     solve_from_file
explain_solution       check_feasibility  generate_template
suggest_relaxations

Document Maintenance

This document is the source of truth for the two-instance coordination protocol on SAGE.

[CLAUDE-AI] updates this document when architecture, workflow, or phase status changes
[CLAUDE-CODE] reads this document at the start of every session
Peter may update the PROJECT-SPECIFIC section at any time

File location in repo: .build/Claude-AI_Claude-Code-ClickUp-Sage.md
ClickUp document: https://app.clickup.com/2258523/docs/24xjv-3151
Last updated: 2026-03-13 — authored by [CLAUDE-AI]
