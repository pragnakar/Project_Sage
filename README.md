# SAGE — Solver-Augmented Generation Engine

**SAGE** is an MCP server that gives any LLM — Claude, ChatGPT, Cursor, Copilot — the ability to formulate and solve mathematical optimization problems using certified open-source solvers.

> Status: **Alpha — MVP under active development**

## What it does

- Solves **Linear Programs (LP)**, **Mixed-Integer Programs (MIP)**, **Portfolio Optimization (QP)**, and **Workforce Scheduling** problems
- Returns provably optimal solutions with certificates and sensitivity analysis
- Diagnoses infeasible problems with an **Irreducible Infeasible Subsystem (IIS)** and suggests relaxations
- Reads from and writes back to **Excel and CSV** files

## Quick Start

```bash
pip install sage-mcp
```

Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "sage": {
      "command": "python",
      "args": ["-m", "sage_mcp"]
    }
  }
}
```

## Architecture

```
sage/
├── sage-core/    ← Pure optimization engine (solver, builder, fileio, explainer)
├── sage-mcp/     ← Local MCP server (V1)
└── sage-cloud/   ← Cloud API (V2, coming later)
```

## License

MIT — Copyright (c) 2026 Pragnakar Pedapenki
