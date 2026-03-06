# SAGE — Solver-Augmented Grounding Engine

**SAGE** grounds AI in mathematical truth. It is a local MCP server that gives Claude Desktop — and any MCP-compatible agent — the ability to formulate, solve, and certify mathematical optimization problems using production-grade open-source solvers.

> Status: **v0.1.0 — Alpha** · Author: Peter Pragnakar Atreides

---

## Why SAGE Exists

Large Language Models are probabilistic text generators. When you ask an LLM to allocate a budget, design a schedule, optimize a route, or balance a portfolio, it generates text that *resembles* a solution. No simplex method runs underneath. No branch-and-bound search. No constraint check. The model cannot prove optimality, certify feasibility, or — critically — declare with certainty that no feasible solution exists.

> **One of the most valuable outcomes in decision-making is a mathematically certified statement of infeasibility.** It tells decision-makers their goals conflict, their assumptions are inconsistent, or their constraints must be renegotiated. LLMs have no native mechanism to produce this. SAGE provides it.

SAGE introduces a hybrid intelligence architecture: LLMs handle language and ambiguity; solvers handle optimality and feasibility. Each component does what it is best suited for.

### The Runtime Advantage

LLMs operate as single-pass inference systems — token generation stops when the response is done. Optimization solvers work differently: they are inherently iterative and stateful, designed to run for minutes, hours, or days while continuously improving. At any point they can return the best solution found so far, a bound on the optimal objective, and a certificate of optimality or infeasibility.

This "anytime" property enables SAGE to:
- Decompose large problems using Benders decomposition, column generation, or Lagrangian relaxation
- Run long-horizon solves asynchronously while the LLM remains conversationally responsive
- Checkpoint, pause, and resume optimization without losing progress

The result: AI shifts from *immediate but approximate* to *sustained and mathematically grounded*.

---

## What it does

| Capability | Detail |
|---|---|
| Problem types | LP, MIP, Portfolio Optimization (QP), Workforce Scheduling |
| Solvers | HiGHS (LP/MIP), OSQP (QP) |
| File I/O | Read/write Excel (.xlsx) and CSV |
| Infeasibility | IIS detection + ranked relaxation suggestions |
| Sensitivity | Dual values, reduced costs, allowable ranges |
| Explanation | Plain-language narration of every result |

---

## Quick Start

### 1. Install

```bash
# From PyPI (once published)
pip install sage-solver-mcp

# From source (development)
git clone https://github.com/pragnakar/Project_Sage
cd sage
pip install -e sage-solver-core/
pip install -e sage-solver-mcp/
```

### 2. Configure Claude Desktop

Find your config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the SAGE server:
```json
{
  "mcpServers": {
    "sage": {
      "command": "python",
      "args": ["-m", "sage_solver_mcp"]
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
maximize 5x + 4y subject to 6x + 4y <= 24, x + 2y <= 6, x,y >= 0
```

**Infeasibility diagnosis**
```
I have a scheduling problem with 3 nurses and 6 required shifts.
Check if it's feasible and if not, tell me which constraints conflict and how to fix them.
```

**Template workflow**
```
Generate a portfolio template, I'll fill in my 8 assets,
then solve it with risk aversion 2.5 and explain the sensitivity.
```

---

## Example Files

| File | Problem | Result |
|---|---|---|
| `examples/portfolio_5_assets.xlsx` | Portfolio QP — 5 assets (equity + bonds) | Optimal allocation |
| `examples/nurse_scheduling.xlsx` | Scheduling MIP — 8 nurses, 3 shifts, 7 days | Infeasible: IIS computed |
| `examples/transport_routing.xlsx` | Transport LP — 3 warehouses → 5 stores | Optimal routes, $2,472 cost |
| `examples/blending_problem.xlsx` | Blending LP — 6 ingredients, nutrient constraints | Optimal blend, $23.47/100kg |

---

## Architecture

```
Project_Sage/
├── sage-solver-core/          # Pure optimization engine — solver, models, fileio, explainer
│   └── sage_solver_core/
│       ├── models.py   # Pydantic models (LPModel, MIPModel, PortfolioModel, SchedulingModel)
│       ├── solver.py   # HiGHS + OSQP solver adapters
│       ├── builder.py  # JSON → SolverInput builders
│       ├── fileio.py   # Excel/CSV read/write, template generation
│       └── explainer.py# Natural language solution narration + IIS explanation
├── sage-solver-mcp/           # Local MCP server (this package — v0.1)
├── sage-cloud/         # Cloud API (future — v0.2)
└── examples/           # Ready-to-use example files
```

**Data flow:**
```
Claude Desktop → stdio JSON-RPC → sage-solver-mcp → sage-solver-core → HiGHS/OSQP
                                                               ↓
                                                    SolverResult + IIS + Sensitivity
```

---

## Supported Problem Types

### Linear Program (LP)
Variables with continuous bounds, linear objective, linear constraints (<=, >=, =).

### Mixed-Integer Program (MIP)
Same as LP but variables can be `continuous`, `integer`, or `binary`.

### Portfolio Optimization (QP)
Markowitz mean-variance: minimize risk (quadratic) for a target return, with optional sector and weight constraints.

### Workforce Scheduling
Assign workers to shifts over a planning horizon. Constraints: min/max workers per shift, rest periods, skill requirements.

---

## Roadmap

| Phase | Focus |
|---|---|
| v0.1 (now) | LP, MIP, Portfolio QP, Scheduling — 7 MCP tools, local stdio server |
| v0.2 | sage-cloud FastAPI — remote deployment, async long-running solves |
| v0.3 | Simulation — Monte Carlo, discrete-event, stochastic programming |
| v1.0 | Decision Intelligence Platform — industry templates, solver marketplace |

The long-term ambition is a planetary-scale optimization fabric: interconnected, federated models that co-optimize transportation, energy, supply chains, and infrastructure across institutions — turning SAGE from a single-user tool into shared decision infrastructure.

---

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test instructions, and branch conventions.

459 tests · 0 failures · sage-solver-core 0.1.0 · sage-solver-mcp 0.1.0

---

## License

MIT — Copyright (c) 2026 Peter Pragnakar Atreides
