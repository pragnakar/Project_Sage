# SAGE — Solver-Augmented Generation Engine

**SAGE** is a local MCP server that gives Claude Desktop the ability to formulate and solve mathematical optimization problems using certified open-source solvers (HiGHS, OSQP).

> Status: **v0.1.0 — Alpha**

---

## What it does

| Capability | Detail |
|---|---|
| Problem types | LP, MIP, Portfolio Optimization (QP), Workforce Scheduling |
| Solvers | HiGHS (LP/MIP), OSQP (QP) |
| File I/O | Read/write Excel (.xlsx) and CSV |
| Infeasibility | IIS detection + ranked relaxation suggestions |
| Sensitivity | Dual values, reduced costs, allowable ranges |

---

## Quick Start

### 1. Install

```bash
# From PyPI (once published)
pip install sage-mcp

# From source (development)
git clone https://github.com/pragnakar/sage
cd sage
pip install -e sage-core/
pip install -e sage-mcp/
```

### 2. Configure Claude Desktop

Find your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the SAGE server:
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

Restart Claude Desktop and you will see the SAGE tools in the toolbar.

### 3. Try it

Ask Claude:
> "Solve this LP: maximize 3x + 5y subject to x + 2y ≤ 12, x ≤ 8, y ≤ 5, x,y ≥ 0"

Or with a file:
> "Read examples/portfolio_5_assets.xlsx and solve it as a portfolio optimization"

---

## MCP Tools

| Tool | Description |
|---|---|
| `solve_optimization` | Solve LP / MIP / portfolio / scheduling from JSON |
| `read_data_file` | Read an Excel or CSV file and return a preview |
| `solve_from_file` | Read + solve + write results in one step |
| `explain_solution` | Narrate the most recent solve result |
| `check_feasibility` | Check feasibility; if infeasible, compute IIS |
| `generate_template` | Create a blank Excel template for a problem type |
| `suggest_relaxations` | Rank constraint relaxations for the last infeasible result |

---

## Example Prompts

**Portfolio optimization**
```
Read examples/portfolio_5_assets.xlsx and solve it as a portfolio problem.
Explain the result in detail and suggest what would change if I removed the 30% bond minimum.
```

**LP from scratch**
```
Solve this LP and show me the sensitivity analysis:
maximize 5x + 4y
subject to:
  6x + 4y <= 24
  x + 2y <= 6
  x, y >= 0
```

**Infeasibility diagnosis**
```
I have a scheduling problem with 3 nurses and 6 required shifts.
Check if it's feasible and if not, tell me which constraints conflict.
```

**Template workflow**
```
Generate a portfolio template, fill in my 8 assets, and solve it with risk aversion 2.5.
```

---

## Example Files

| File | Problem | Description |
|---|---|---|
| `examples/portfolio_5_assets.xlsx` | Portfolio QP | 5 assets (equity + bonds), 5×5 covariance matrix |
| `examples/nurse_scheduling.xlsx` | Scheduling MIP | 8 nurses, 3 shifts (Morning/Evening/Night), 7 days |
| `examples/transport_routing.xlsx` | Transport LP | 3 warehouses, 5 stores, cost matrix |
| `examples/blending_problem.csv` | Blending LP | 6 ingredients, nutrient requirements |

---

## Architecture

```
Project_Sage/
├── sage-core/          # Pure optimization engine — solver, models, fileio, explainer
│   └── sage_core/
│       ├── models.py   # Pydantic models (LPModel, MIPModel, PortfolioModel, SchedulingModel)
│       ├── solver.py   # HiGHS + OSQP solver adapters
│       ├── builder.py  # JSON → SolverInput builders
│       ├── fileio.py   # Excel/CSV read/write, template generation
│       └── explainer.py# Natural language solution narration + IIS explanation
├── sage-mcp/           # Local MCP server (this package)
│   └── sage_mcp/
│       ├── server.py   # 7 MCP tools, ServerState, stdio transport
│       └── local_io.py # Path resolution and file I/O helpers
├── sage-cloud/         # FastAPI cloud API (future — v0.2)
└── examples/           # Ready-to-use example files
```

**Data flow:**
```
Claude Desktop → stdio JSON-RPC → sage-mcp → sage-core → HiGHS/OSQP
                                     ↑                        ↓
                                  local_io           SolverResult + IIS
```

---

## Supported Problem Types

### Linear Program (LP)
Variables with continuous bounds, linear objective, linear constraints (<=, >=, =).

### Mixed-Integer Program (MIP)
Same as LP but variables can be `continuous`, `integer`, or `binary`.

### Portfolio Optimization
Markowitz mean-variance: minimize risk (quadratic) for a target return, with optional sector and weight constraints.

### Workforce Scheduling
Assign workers to shifts over a planning horizon. Constraints: min/max workers per shift, rest periods, skill requirements.

---

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, test instructions, and branch conventions.

---

## License

MIT — Copyright (c) 2026 Pragnakar Pedapenki
