# Project SAGE — Technical Specification v1.0

## Solver-Augmented Generation Engine

**Author:** Pragnakar Pedapenki (pragnakar@gmail.com)
**Date:** March 5, 2026
**Status:** MVP Build Specification — Ready for Implementation

---

## 1. What SAGE Is

SAGE is an MCP (Model Context Protocol) server that gives any LLM — Claude, ChatGPT, Cursor, Copilot — the ability to formulate and solve mathematical optimization problems using certified open-source solvers. It bridges the gap between natural language intent and rigorous operations research.

**The core insight:** LLMs hallucinate math. Solvers can't interpret intent. SAGE sits at the junction — the LLM translates human intent into structured problem definitions, SAGE translates those into solver-native format, dispatches to the solver, and returns certified results with explanations.

**Key differentiator:** SAGE doesn't approximate. It returns provably optimal solutions with certificates, sensitivity analysis, and when problems are infeasible, it identifies the exact minimal set of conflicting constraints (IIS) and suggests relaxations.

---

## 2. Architecture

### 2.1 Dual-Version Strategy

SAGE is built as three packages from day one to support both local and cloud deployment without rewriting the core engine.

```
sage/
├── sage-core/          ← The engine (80% of intelligence)
│   ├── sage_core/
│   │   ├── __init__.py
│   │   ├── models.py        ← Problem type schemas (Pydantic)
│   │   ├── builder.py       ← Structured definition → mathematical model
│   │   ├── solver.py        ← HiGHS + OR-Tools dispatch + wrapper
│   │   ├── fileio.py        ← DataFrame ↔ Excel/CSV conversion
│   │   ├── explainer.py     ← Results → natural language narrative
│   │   └── relaxation.py    ← Infeasibility → suggested fixes
│   ├── tests/
│   │   ├── test_models.py
│   │   ├── test_solver.py
│   │   ├── test_fileio.py
│   │   ├── test_explainer.py
│   │   └── test_integration.py
│   └── pyproject.toml
│
├── sage-mcp/            ← V1: Local MCP server
│   ├── sage_mcp/
│   │   ├── __init__.py
│   │   ├── server.py        ← MCP tool definitions
│   │   └── local_io.py      ← Local filesystem bridge
│   ├── pyproject.toml
│   └── claude_desktop_config.json
│
├── sage-cloud/          ← V2: Cloud API (built later)
│   ├── sage_cloud/
│   │   ├── __init__.py
│   │   ├── api.py           ← FastAPI routes
│   │   ├── auth.py          ← API key / OAuth
│   │   ├── queue.py         ← Async job management
│   │   └── storage.py       ← S3/GCS file bridge
│   ├── Dockerfile
│   └── pyproject.toml
│
├── examples/
│   ├── portfolio_optimization.xlsx
│   ├── nurse_scheduling.csv
│   ├── transport_routing.xlsx
│   └── blending_problem.csv
│
├── CLAUDE.md             ← Instructions for Claude Code
├── SAGE_SPEC.md          ← This file
├── README.md
└── LICENSE               ← MIT
```

### 2.2 Design Principle: Clean Separation

**sage-core** has ZERO opinions about deployment. It takes Python objects in and returns Python objects out. No HTTP, no MCP protocol, no file system calls, no `print()` statements. Every function takes data as arguments and returns structured results.

This means:
- sage-mcp imports sage-core, reads local files, passes DataFrames to core, gets results back, writes local files
- sage-cloud imports sage-core, receives uploads via HTTP, passes DataFrames to core, gets results back, returns via API

The core never changes between versions.

### 2.3 V1 Runtime (Local)

```
User speaks to Claude Desktop / Claude Code / Cursor
    │
    │ MCP Protocol (stdin/stdout, local subprocess)
    │
┌───▼──────────────────────────────────┐
│   sage-mcp (local MCP server)        │
│   ┌────────────────────────────────┐ │
│   │         sage-core              │ │
│   │  Model Builder → Solver →     │ │
│   │  Explainer → File I/O         │ │
│   └────────────────────────────────┘ │
└──────────────────────────────────────┘
    All on user's local machine
    No network calls. No cloud. No data leakage.
```

### 2.4 V2 Runtime (Cloud — built later)

```
User speaks to ChatGPT / Claude / any client
    │
    │ MCP over SSE/HTTP (remote)
    │
┌───▼──────────────────────────────────┐
│   sage-cloud (FastAPI on cloud)      │
│   Auth → Queue → sage-core → S3     │
│   Multi-tenant, rate-limited         │
└──────────────────────────────────────┘
```

V2 unlocks ChatGPT integration (which requires remote MCP servers via SSE).

---

## 3. Components — Detailed Specification

### 3.1 sage-core/models.py — Problem Type Schemas

Use Pydantic v2 models. These schemas define the structured input the LLM must produce.

**Supported problem types for MVP:**

#### 3.1.1 Linear Programming (LP)

```python
class LPVariable(BaseModel):
    name: str
    lower_bound: float | None = 0.0
    upper_bound: float | None = None

class LinearConstraint(BaseModel):
    name: str
    coefficients: dict[str, float]  # variable_name → coefficient
    sense: Literal["<=", ">=", "=="]
    rhs: float

class LinearObjective(BaseModel):
    sense: Literal["minimize", "maximize"]
    coefficients: dict[str, float]  # variable_name → coefficient

class LPModel(BaseModel):
    name: str
    description: str | None = None
    variables: list[LPVariable]
    constraints: list[LinearConstraint]
    objective: LinearObjective
```

#### 3.1.2 Mixed-Integer Programming (MIP)

Extends LP with integer/binary variable types:

```python
class MIPVariable(BaseModel):
    name: str
    lower_bound: float | None = 0.0
    upper_bound: float | None = None
    var_type: Literal["continuous", "integer", "binary"] = "continuous"

class MIPModel(BaseModel):
    name: str
    description: str | None = None
    variables: list[MIPVariable]
    constraints: list[LinearConstraint]
    objective: LinearObjective
    time_limit_seconds: float | None = 60.0
    mip_gap_tolerance: float | None = 0.0001
```

#### 3.1.3 Portfolio Optimization (Domain-Specific Wrapper)

```python
class Asset(BaseModel):
    name: str
    expected_return: float
    sector: str | None = None

class PortfolioModel(BaseModel):
    assets: list[Asset]
    covariance_matrix: list[list[float]]  # n x n
    risk_aversion: float = 1.0
    constraints: PortfolioConstraints

class PortfolioConstraints(BaseModel):
    max_allocation_per_asset: float | None = None
    min_allocation_per_asset: float | None = None
    max_sector_allocation: dict[str, float] | None = None
    min_total_allocation: float = 1.0  # fully invested
    max_total_allocation: float = 1.0
    forbidden_assets: list[str] | None = None
```

#### 3.1.4 Scheduling (Domain-Specific Wrapper)

```python
class Worker(BaseModel):
    name: str
    max_hours: float
    skills: list[str] | None = None
    unavailable_shifts: list[str] | None = None

class Shift(BaseModel):
    name: str
    duration_hours: float
    required_workers: int
    required_skills: list[str] | None = None

class SchedulingModel(BaseModel):
    workers: list[Worker]
    shifts: list[Shift]
    planning_horizon_days: int = 7
    max_consecutive_days: int | None = 5
    min_rest_hours: float | None = 8.0
```

### 3.2 sage-core/builder.py — Model Builder

This module translates domain-specific models (Portfolio, Scheduling) into generic LP/MIP models. It also validates models and catches common errors before sending to the solver.

**Key functions:**

```python
def build_from_lp(model: LPModel) -> SolverInput:
    """Direct translation of LP model to solver-native format."""

def build_from_portfolio(model: PortfolioModel) -> SolverInput:
    """Translates portfolio optimization into a quadratic program.
    Uses mean-variance (Markowitz) formulation.
    Decision variables: weight per asset.
    Objective: maximize return - risk_aversion * variance.
    Constraints: allocation limits, sector limits, full investment."""

def build_from_scheduling(model: SchedulingModel) -> SolverInput:
    """Translates scheduling into MIP.
    Decision variables: binary assignment (worker, shift, day).
    Constraints: coverage, max hours, consecutive days, rest time, skills."""

def validate_model(model: LPModel | MIPModel) -> list[ValidationError]:
    """Pre-solver validation:
    - Check for empty constraint sets
    - Check for variables not in any constraint
    - Check for obviously unbounded models
    - Check coefficient magnitudes (numerical stability)
    - Check for duplicate variable/constraint names"""
```

**SolverInput** is an intermediate representation:

```python
class SolverInput(BaseModel):
    """Solver-agnostic intermediate representation."""
    num_variables: int
    num_constraints: int
    variable_names: list[str]
    variable_lower_bounds: list[float]
    variable_upper_bounds: list[float]
    variable_types: list[Literal["continuous", "integer", "binary"]]
    constraint_names: list[str]
    constraint_matrix: list[list[float]]  # sparse would be better for large problems
    constraint_senses: list[Literal["<=", ">=", "=="]]
    constraint_rhs: list[float]
    objective_coefficients: list[float]
    objective_sense: Literal["minimize", "maximize"]
    # Quadratic terms (for portfolio optimization)
    objective_quadratic: list[list[float]] | None = None
    # Solver parameters
    time_limit_seconds: float | None = 60.0
    mip_gap_tolerance: float | None = 0.0001
```

### 3.3 sage-core/solver.py — Solver Wrapper

**Primary solver:** HiGHS (via `highspy` Python bindings)
- MIT licensed
- Handles LP, MIP, QP
- Production-grade, benchmarks competitively with Gurobi/CPLEX
- Install: `pip install highspy`

**Secondary solver:** OR-Tools (via `ortools` Python bindings)
- Apache 2.0 licensed
- Better for constraint programming and vehicle routing
- Install: `pip install ortools`

**Key functions:**

```python
def solve(solver_input: SolverInput, solver: str = "highs") -> SolverResult:
    """Dispatch to appropriate solver and return certified result.

    Steps:
    1. Translate SolverInput to solver-native format
    2. Set parameters (time limit, gap tolerance)
    3. Solve
    4. Extract solution, status, certificate
    5. Extract sensitivity analysis (shadow prices, reduced costs)
    6. If infeasible, compute IIS
    7. Return structured SolverResult
    """

def compute_iis(solver_input: SolverInput) -> IISResult:
    """Compute Irreducible Infeasible Subsystem.
    The minimal set of constraints that conflict.
    Uses HiGHS IIS or iterative deletion method."""
```

**SolverResult:**

```python
class SolverResult(BaseModel):
    status: Literal[
        "optimal",
        "infeasible",
        "unbounded",
        "time_limit_reached",
        "solver_error"
    ]
    objective_value: float | None = None
    bound: float | None = None  # best bound (for MIP)
    gap: float | None = None  # optimality gap (for MIP)
    solve_time_seconds: float
    variable_values: dict[str, float] | None = None
    # Sensitivity analysis (LP only)
    shadow_prices: dict[str, float] | None = None  # constraint name → dual value
    reduced_costs: dict[str, float] | None = None  # variable name → reduced cost
    constraint_slack: dict[str, float] | None = None
    binding_constraints: list[str] | None = None
    # Ranges (LP only)
    objective_ranges: dict[str, tuple[float, float]] | None = None
    rhs_ranges: dict[str, tuple[float, float]] | None = None
    # Infeasibility analysis
    iis: IISResult | None = None

class IISResult(BaseModel):
    conflicting_constraints: list[str]
    conflicting_variable_bounds: list[str]
    explanation: str  # human-readable explanation
```

### 3.4 sage-core/fileio.py — Excel/CSV Handler

This is strategically important. Most enterprise optimization data lives in Excel. SAGE meets users where they are.

**Key functions:**

```python
def read_data(filepath: str, file_format: str = "auto") -> dict[str, pd.DataFrame]:
    """Read Excel or CSV file into DataFrames.

    For Excel: reads all sheets, returns {sheet_name: DataFrame}
    For CSV: returns {"data": DataFrame}

    Handles:
    - Auto-detection of headers
    - Blank row/column stripping
    - Merged cell unmerging (forward fill)
    - Formula cells → evaluated values
    - Type coercion (strings to numbers where possible)
    - Encoding detection for CSV
    """

def read_data_from_bytes(content: bytes, filename: str) -> dict[str, pd.DataFrame]:
    """Same as read_data but from bytes (for cloud version)."""

def write_results_excel(
    result: SolverResult,
    model_name: str,
    output_path: str,
    original_data: dict[str, pd.DataFrame] | None = None
) -> str:
    """Write optimization results to a formatted Excel file.

    Creates multiple sheets:
    - Summary: status, objective value, solve time
    - Solution: variable names and values
    - Sensitivity: shadow prices, reduced costs, ranges
    - Constraints: slack, binding status
    - Infeasibility (if applicable): IIS constraints, suggested relaxations

    Formatting:
    - Headers with color fills
    - Number formatting (2-4 decimal places)
    - Conditional formatting on binding constraints
    - Column auto-width
    - Frozen header row

    Returns: path to output file
    """

def write_results_csv(result: SolverResult, output_path: str) -> str:
    """Simple CSV output for programmatic consumption."""

def generate_template(problem_type: str, output_path: str) -> str:
    """Generate a blank Excel template for a given problem type.

    Templates:
    - portfolio: assets sheet (name, expected_return, sector) + covariance sheet + constraints sheet
    - scheduling: workers sheet + shifts sheet + constraints sheet
    - transport: origins sheet + destinations sheet + costs sheet + supply/demand sheet
    - generic_lp: variables sheet + constraints sheet + objective sheet

    Each sheet has:
    - Column headers with descriptions in row 2
    - Example data in rows 3-5
    - Data validation where appropriate
    - Instructions sheet explaining what to fill in

    Returns: path to template file
    """

def dataframe_to_model(
    dfs: dict[str, pd.DataFrame],
    problem_type: str
) -> LPModel | MIPModel | PortfolioModel | SchedulingModel:
    """Parse DataFrames (from Excel/CSV) into a typed model.

    This is the critical bridge between Excel data and solver input.
    Must handle messy real-world data gracefully:
    - Extra columns (ignore)
    - Missing optional columns (use defaults)
    - String numbers ("1,000.50" → 1000.5)
    - Percentage strings ("5%" → 0.05)

    Raises: DataValidationError with specific column/row/cell references
    """
```

### 3.5 sage-core/explainer.py — Result Narrator

Translates solver results into natural language suitable for LLM to relay to user.

```python
def explain_result(
    result: SolverResult,
    model: LPModel | MIPModel | PortfolioModel | SchedulingModel,
    detail_level: Literal["brief", "standard", "detailed"] = "standard"
) -> str:
    """Generate natural language explanation of results.

    Brief: "Optimal solution found. Objective value: $45,230. Solved in 0.3s."

    Standard: Above + top variable values, binding constraints, key insights.

    Detailed: Above + full sensitivity analysis narrative:
    "Asset X is at its upper bound of 20%. The shadow price of the ESG constraint
    is -0.003, meaning relaxing it by 1% would improve returns by 0.3%.
    The minimum return constraint is non-binding with slack of 1.2%."
    """

def explain_infeasibility(
    iis: IISResult,
    model: LPModel | MIPModel | PortfolioModel | SchedulingModel
) -> str:
    """Explain why the problem has no feasible solution.

    Example: "The model is infeasible. The conflict involves 3 constraints:
    1. Total allocation must equal 100%
    2. Maximum 15% in any single asset
    3. Minimum 50% in technology sector
    With only 3 tech assets available, the maximum possible tech allocation
    is 45% (3 × 15%), which conflicts with the 50% minimum."
    """
```

### 3.6 sage-core/relaxation.py — Constraint Relaxation Suggester

```python
def suggest_relaxations(
    iis: IISResult,
    model: LPModel | MIPModel,
    solver_input: SolverInput
) -> list[RelaxationSuggestion]:
    """For each constraint in the IIS, compute what relaxation would
    make the model feasible.

    Returns ranked suggestions:
    1. Relax constraint X RHS from 100 to 105 (+5%)
    2. Remove constraint Y entirely
    3. Relax variable Z upper bound from 0.2 to 0.25

    Each suggestion includes:
    - Which constraint/bound to relax
    - By how much
    - What the new optimal objective would be (resolved)
    - Trade-off explanation
    """

class RelaxationSuggestion(BaseModel):
    constraint_name: str
    current_value: float
    suggested_value: float
    relaxation_amount: float
    relaxation_percent: float
    new_objective_value: float | None = None
    explanation: str
    priority: int  # 1 = most impactful
```

---

## 4. MCP Server — Tool Definitions

### 4.1 sage-mcp/server.py

The MCP server exposes these tools. Tool names are semantic — the LLM doesn't need to know about HiGHS.

**Tools:**

#### Tool 1: `solve_optimization`
```
Description: Solve a mathematical optimization problem (LP, MIP, portfolio, scheduling).
Input: A structured problem definition as JSON matching one of the supported schemas.
Output: Solution with certificate, variable values, and explanation.
```

#### Tool 2: `read_data_file`
```
Description: Read an Excel (.xlsx) or CSV file containing optimization data.
Input: { "filepath": string, "problem_type": string (optional) }
Output: Parsed data summary — number of rows, columns, detected structure, preview.
```

#### Tool 3: `solve_from_file`
```
Description: Read data from an Excel/CSV file and solve the optimization problem.
Input: { "filepath": string, "problem_type": string, "objective": string, "constraints_description": string (optional) }
Output: Full solution with results written back to a new Excel file.
```

#### Tool 4: `explain_solution`
```
Description: Get a detailed explanation of the most recent optimization result.
Input: { "detail_level": "brief" | "standard" | "detailed" }
Output: Natural language explanation including sensitivity analysis.
```

#### Tool 5: `check_feasibility`
```
Description: Check if a problem has a feasible solution without optimizing.
Input: Same as solve_optimization.
Output: Feasible/Infeasible + if infeasible, the IIS and relaxation suggestions.
```

#### Tool 6: `generate_template`
```
Description: Generate a blank Excel template for a specific problem type.
Input: { "problem_type": "portfolio" | "scheduling" | "transport" | "generic_lp", "output_path": string }
Output: Path to generated template file.
```

#### Tool 7: `suggest_relaxations`
```
Description: For an infeasible problem, suggest which constraints to relax and by how much.
Input: Reference to the most recent infeasible result.
Output: Ranked list of relaxation suggestions with trade-off analysis.
```

### 4.2 MCP Server Configuration

For Claude Desktop, users add this to their config:

```json
{
  "mcpServers": {
    "sage": {
      "command": "uvx",
      "args": ["sage-mcp"],
      "env": {}
    }
  }
}
```

Or if installed via pip:

```json
{
  "mcpServers": {
    "sage": {
      "command": "python",
      "args": ["-m", "sage_mcp"],
      "env": {}
    }
  }
}
```

---

## 5. Dependencies

### Core Dependencies (sage-core)
```
highspy >= 1.7.0        # HiGHS solver Python bindings
ortools >= 9.9          # Google OR-Tools
pandas >= 2.1           # Data manipulation
openpyxl >= 3.1         # Excel read/write
pydantic >= 2.5         # Schema validation
numpy >= 1.24           # Numerical operations
```

### MCP Dependencies (sage-mcp)
```
mcp >= 1.0              # MCP Python SDK
sage-core               # Local dependency
```

### Cloud Dependencies (sage-cloud, V2)
```
fastapi >= 0.110
uvicorn >= 0.27
python-multipart        # File uploads
boto3                   # S3 (if AWS)
sage-core               # Same core
```

---

## 6. Build Sequence

### Phase 1: Foundation (Hours 1-8)

1. **Set up project structure** — monorepo with three packages, pyproject.toml for each
2. **Implement models.py** — all Pydantic schemas (LPModel, MIPModel, PortfolioModel, SchedulingModel, SolverResult, IISResult)
3. **Implement solver.py** — HiGHS wrapper for LP and MIP, SolverResult extraction, basic sensitivity analysis
4. **Write tests** — solve known LP/MIP problems, verify optimal values match expected

### Phase 2: Model Builder + File I/O (Hours 9-20)

5. **Implement builder.py** — LP passthrough, portfolio→QP builder, scheduling→MIP builder, model validation
6. **Implement fileio.py** — Excel/CSV reader with messy data handling, template generator, results writer with formatting
7. **Implement dataframe_to_model** — the critical bridge from Excel data to typed models
8. **Write tests** — round-trip tests (create template → fill data → parse → solve → write results)

### Phase 3: Intelligence Layer (Hours 21-30)

9. **Implement explainer.py** — result narration at three detail levels, sensitivity analysis narrative
10. **Implement relaxation.py** — IIS extraction, relaxation computation, suggestion ranking
11. **Implement infeasibility explanation** — translate IIS into human-readable diagnosis
12. **Write tests** — intentionally infeasible problems, verify IIS correctness, verify explanations make sense

### Phase 4: MCP Server (Hours 31-38)

13. **Implement sage-mcp/server.py** — all 7 MCP tools, proper error handling, structured responses
14. **Implement local_io.py** — filesystem bridge (resolve paths, check file existence, handle permissions)
15. **End-to-end testing** — connect to Claude Desktop, run full conversation flows
16. **Edge case handling** — solver timeout, malformed input, file not found, unsupported formats

### Phase 5: Polish + Ship (Hours 39-45)

17. **Create example files** — 4 demo Excel/CSV files with realistic data
18. **Write README.md** — installation, quick start, demo GIFs, architecture diagram
19. **Package for distribution** — pyproject.toml metadata, entry points, `uvx` compatibility
20. **Create claude_desktop_config.json** — example config for easy setup
21. **Tag v0.1.0** — push to GitHub

---

## 7. Example End-to-End Flows

### Flow 1: Portfolio Optimization from Excel

```
User: "I have a portfolio spreadsheet at ~/Documents/assets.xlsx.
       Optimize for maximum Sharpe ratio with max 20% per asset
       and at least 30% in bonds."

Claude → SAGE [read_data_file]:
  filepath: ~/Documents/assets.xlsx

SAGE reads file, detects:
  - Sheet "Assets": 15 rows (assets), columns: Name, Expected Return, Sector
  - Sheet "Covariance": 15x15 matrix

Claude → SAGE [solve_from_file]:
  filepath: ~/Documents/assets.xlsx
  problem_type: portfolio
  objective: maximize sharpe ratio
  constraints: max 20% per asset, min 30% bonds

SAGE:
  1. fileio.read_data → DataFrames
  2. fileio.dataframe_to_model → PortfolioModel
  3. builder.build_from_portfolio → SolverInput (QP)
  4. solver.solve → SolverResult (status: optimal, 0.4s)
  5. explainer.explain_result → narrative
  6. fileio.write_results_excel → ~/Documents/assets_optimized.xlsx

Claude responds: "Optimal portfolio found. Expected return: 8.2%,
  portfolio volatility: 12.1%. Largest allocations: Treasury Bonds (20%),
  Corporate Bonds (15.3%), AAPL (14.1%). The bonds constraint is binding —
  the solver would prefer only 22% bonds. Relaxing to 25% would improve
  the Sharpe ratio by 0.04. Results saved to assets_optimized.xlsx."
```

### Flow 2: Infeasible Scheduling Problem

```
User: "Schedule 5 nurses for 3 shifts over 7 days.
       Each shift needs 2 nurses. No one works more than 5 shifts.
       Nurse A can't work nights."

Claude → SAGE [solve_optimization]:
  SchedulingModel with constraints

SAGE solves → status: infeasible
SAGE computes IIS → conflicting constraints:
  - Need 2 nurses per shift × 3 shifts × 7 days = 42 nurse-shifts
  - 5 nurses × 5 max shifts = 25 available nurse-shifts
  - 42 > 25: impossible

SAGE suggests relaxations:
  1. Increase max shifts to 9 per nurse (solves it)
  2. Reduce required nurses per shift to 1 for night shift
  3. Add 2 more nurses to the pool

Claude responds: "This schedule is infeasible. You need 42 nurse-shift
  assignments but only have 25 available (5 nurses × 5 shifts max).
  Three options: raise the shift limit to 9 per nurse, reduce night
  shift coverage to 1, or add 2 more nurses."
```

---

## 8. Error Handling Strategy

### 8.1 Error Taxonomy

```python
class SAGEError(Exception):
    """Base error class."""

class DataValidationError(SAGEError):
    """Input data doesn't match expected schema.
    Includes: file path, sheet name, row, column, expected type, actual value."""

class ModelBuildError(SAGEError):
    """Cannot construct a valid mathematical model from the input.
    Includes: which step failed, what's missing or contradictory."""

class SolverError(SAGEError):
    """Solver failed unexpectedly (not infeasibility — that's a valid result).
    Includes: solver name, error code, error message."""

class FileIOError(SAGEError):
    """Cannot read or write file.
    Includes: file path, operation, OS error."""
```

### 8.2 Error Recovery Flow

When any error occurs, SAGE returns a structured error response through MCP that the LLM can interpret and relay to the user with actionable guidance:

```python
class SAGEErrorResponse(BaseModel):
    error_type: str
    message: str
    details: dict  # structured details for the LLM
    suggestions: list[str]  # what the user can do to fix it
```

Example: If a column is missing from an Excel file:
```json
{
  "error_type": "DataValidationError",
  "message": "Missing required column 'expected_return' in sheet 'Assets'",
  "details": {
    "file": "assets.xlsx",
    "sheet": "Assets",
    "found_columns": ["Name", "Sector", "Market Cap"],
    "required_columns": ["Name", "expected_return"],
    "missing": ["expected_return"]
  },
  "suggestions": [
    "Add a column named 'expected_return' with decimal values (e.g., 0.08 for 8%)",
    "If the data exists under a different name, tell me which column contains expected returns"
  ]
}
```

---

## 9. Testing Strategy

### Unit Tests (per module)
- models.py: schema validation, serialization/deserialization
- solver.py: known optimal solutions for small LP/MIP problems
- builder.py: portfolio → QP conversion, scheduling → MIP conversion
- fileio.py: read/write round-trips, messy data handling
- explainer.py: output format, sensitivity narrative correctness
- relaxation.py: IIS correctness on known infeasible problems

### Integration Tests
- Full flow: Excel → parse → build → solve → explain → write Excel
- Infeasible flow: detect → IIS → suggest → user picks relaxation → re-solve
- Error flow: bad file → structured error → user fixes → success

### Benchmark Tests (not blocking MVP, but track early)
- Solve time on problems of increasing size (10, 100, 1000, 10000 variables)
- Memory usage on large Excel files
- Correctness against known NETLIB LP benchmarks

---

## 10. Distribution Plan (Post-Build)

### Day 1 After MVP
- Push to GitHub with MIT license
- Publish to PyPI: `pip install sage-mcp`
- Publish to official MCP Registry (registry.modelcontextprotocol.io)
- Submit to Claude Desktop Extensions directory (Anthropic)
- List on PulseMCP, mcp.so, mcpmarket.com

### Week 2-4
- Create demo videos (portfolio optimization, nurse scheduling, infeasibility diagnosis)
- Post on LinkedIn, Twitter/X, r/operations_research, r/LocalLLaMA, Hacker News
- Reach out to HiGHS team at University of Edinburgh for endorsement/link
- Submit to awesome-mcp-servers GitHub lists

### V2 Cloud (unlocks ChatGPT)
- Build sage-cloud with FastAPI + SSE
- Register as ChatGPT MCP App for Business/Enterprise
- Deploy to Cloudflare Workers or Railway

---

## 11. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary solver | HiGHS | MIT license, best OSS LP/MIP solver, active development |
| Secondary solver | OR-Tools | CP and routing capabilities HiGHS lacks |
| Modeling abstraction | Custom (not PuLP) | PuLP adds dependency without enough value; direct highspy is cleaner |
| Schema validation | Pydantic v2 | Industry standard, fast, good error messages |
| Excel library | openpyxl | Read/write, formatting, no Excel installation needed |
| Data manipulation | pandas | Universal, handles messy data well |
| MCP SDK | Official Python SDK | Standard, maintained by Anthropic |
| Package manager | uv/pip | `uvx sage-mcp` for zero-config install |
| Quadratic programming | HiGHS QP | Integrated in HiGHS, no separate solver needed |

---

## 12. What's NOT in MVP (Explicitly Deferred)

- **Simulation / Monte Carlo** — Phase 2
- **Stochastic programming** — Phase 2
- **Vehicle routing** — Phase 2 (OR-Tools VRP)
- **Network flow** — Phase 2
- **WebAssembly / browser solver** — Phase 3
- **GPU acceleration** — Phase 3
- **Async long-running jobs with checkpointing** — V2 cloud
- **Multi-party federated solving** — Phase 4 moonshot
- **Natural language → model (freeform)** — Out of scope; LLM handles this via structured schemas
- **Model versioning / comparison** — Phase 2
- **Interactive what-if analysis** — Phase 2 (but SolverResult contains the data for it)

---

## 13. Success Criteria for MVP

The MVP is done when:

1. A user can install with `pip install sage-mcp` and add one config block to Claude Desktop
2. The user can say "read my Excel file and optimize my portfolio" and get a certified optimal solution written back to Excel
3. The user can hit an infeasible problem and get a clear explanation of why + actionable relaxation suggestions
4. The user can ask "explain the sensitivity analysis" and get a narrative about shadow prices and binding constraints
5. All 4 demo problems (portfolio, scheduling, transport, blending) work end-to-end
6. The README is clear enough that a non-developer finance analyst can set it up in 5 minutes

---

*This specification was generated from an extended design conversation between Pragnakar Pedapenki and Claude (claude.ai) on March 5, 2026. It represents the complete handoff document for implementation via Claude Code.*
