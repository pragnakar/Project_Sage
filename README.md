# SAGE — Solver-Augmented Grounding Engine

**SAGE** grounds AI in mathematical truth. It is a local MCP server that gives Claude Desktop — and any MCP-compatible agent — the ability to formulate, solve, and certify mathematical optimization problems using production-grade open-source solvers.

> Status: **v0.1.3 — Alpha** · Author: Peter Pragnakar Atreides

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
      "command": "uvx",
      "args": ["sage-solver-mcp"]
    }
  }
}
```

> **What is `uvx`?** It is a command from the [uv](https://github.com/astral-sh/uv) Python toolchain that runs a PyPI package ephemerally — no manual `pip install` required. If you have uv installed (`brew install uv` on macOS), `uvx sage-solver-mcp` fetches and runs SAGE automatically. If Claude Desktop cannot find `uvx` on your PATH, use the full path: `"/opt/homebrew/bin/uvx"` (macOS) or the output of `which uvx`.

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

## Usage Examples

Each example shows the user prompt, which tool is called, a representative input payload, and the output SAGE returns.

---

### Example 1 — Solve a staffing LP

**User prompt:** I need to figure out how many full-time and part-time employees to schedule to minimize cost. Full-time costs $200/day and covers 8 hours, part-time costs $100/day and covers 4 hours. I need at least 40 hours covered each day and at most 6 full-time staff.

**Tool:** `solve_optimization`

```json
{
  "problem_type": "lp",
  "name": "staffing",
  "variables": [
    {"name": "ft", "lb": 0, "ub": 6},
    {"name": "pt", "lb": 0}
  ],
  "constraints": [
    {"name": "coverage", "expression": {"ft": 8, "pt": 4}, "sense": ">=", "rhs": 40}
  ],
  "objective": {"sense": "minimize", "coefficients": {"ft": 200, "pt": 100}}
}
```

**Output:** Optimal: ft=2, pt=6, cost=$1,000/day. The coverage constraint is binding. Sensitivity: each additional required hour costs $25.

---

### Example 2 — Diagnose an infeasible schedule

**User prompt:** My shift schedule says workers need at least 3 people on Monday AND no more than 2 people total — is that solvable?

**Tool:** `check_feasibility`

```json
{
  "problem_type": "lp",
  "name": "schedule_check",
  "variables": [{"name": "workers", "lb": 0}],
  "constraints": [
    {"name": "min_staff", "expression": {"workers": 1}, "sense": ">=", "rhs": 3},
    {"name": "max_staff", "expression": {"workers": 1}, "sense": "<=", "rhs": 2}
  ],
  "objective": {"sense": "minimize", "coefficients": {"workers": 0}}
}
```

**Output:** INFEASIBLE. Conflicting constraints: `min_staff` (≥3) and `max_staff` (≤2) are mutually exclusive. Suggestion: relax `max_staff` to ≥3 (+50%) or reduce `min_staff` to ≤2 (−33%).

---

### Example 3 — Portfolio optimization from Excel

**User prompt:** I have a portfolio spreadsheet with expected returns and a covariance matrix. Optimize it for a target return of 8% while minimizing risk.

**Tools:** `read_data_file` → `solve_from_file`

`read_data_file` output: Detected sheets: `assets` (5 rows, columns: ticker, expected_return), `covariance` (5×5 matrix). Preview looks correct.

`solve_from_file` output: Optimal allocation — AAPL: 32%, MSFT: 28%, GOOGL: 18%, BND: 22%, CASH: 0%. Portfolio variance: 0.0042 (σ=6.5%). Results written to `portfolio_optimized.xlsx`.

---

### Example 4 — Generate a template, solve, then explain in detail

**User prompt:** Can you create a scheduling template I can fill in? Then after I solve it, give me a detailed explanation.

**Step 1 — Tool:** `generate_template` with `problem_type: "scheduling"`

Output: Template written to `scheduling_template.xlsx` with sheets: `workers` (name, availability, cost), `shifts` (name, start, end, required_count), `instructions`.

**Step 2 — Tool:** `explain_solution` with `detail_level: "detailed"`

Output: "The optimal schedule assigns Alice and Bob to the morning shift (cost: $480) and Carlos to the evening shift (cost: $220). The evening minimum-staffing constraint has a shadow price of $45 — each additional required worker increases cost by $45. The morning capacity constraint has 1 unit of slack."

---

### Example 5 — Integer programming with relaxation suggestions

**User prompt:** I want to buy whole units of 3 products to maximize profit, but I can only spend $500 and store 20 cubic feet. Product A: $80, 3 ft³, $120 profit. Product B: $50, 5 ft³, $70 profit. Product C: $120, 2 ft³, $200 profit.

**Tool:** `solve_optimization` (MIP with integer variables A, B, C; budget ≤ 500; storage ≤ 20; maximize 120A + 70B + 200C)

**Tool:** `suggest_relaxations` (called automatically on infeasible sub-problem)

**Output:** Optimal integer solution: A=2, B=0, C=3, profit=$840. If the budget constraint is binding, `suggest_relaxations` ranks options: relax budget by $20 (+4%) to $520, or drop 1 unit of C and add 1 unit of A for $760 profit within the original $500 limit.

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

393 tests · 0 failures · sage-solver-core 0.1.3 · sage-solver-mcp 0.1.3

---

## License

MIT — Copyright (c) 2026 Peter Pragnakar Atreides
