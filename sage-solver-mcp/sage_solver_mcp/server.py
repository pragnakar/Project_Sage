"""SAGE MCP server — exposes SAGE optimization tools to Claude Desktop and
other MCP clients via the stdio transport.

Seven tools are registered:
  1. solve_optimization   — LP / MIP / portfolio / scheduling
  2. read_data_file       — read Excel/CSV and return a data preview
  3. solve_from_file      — read + solve + write results in one step
  4. explain_solution     — narrate the most recent solve result
  5. check_feasibility    — check feasibility and explain if infeasible
  6. generate_template    — create a blank Excel template for a problem type
  7. suggest_relaxations  — rank constraint relaxations for the last infeasible result

All tool handlers are pure async functions.  They call sage-core synchronously
(sage-core has no async API) and run file I/O through local_io.py.

Server state
------------
A single ``ServerState`` instance is created at module level and shared across
all tool calls.  It stores:
  - last_result      : the most recent SolverResult
  - last_model       : the model that produced last_result
  - last_solver_input: the SolverInput that produced last_result
  - last_iis         : IISResult if the last solve was infeasible

Error policy
------------
Every tool handler wraps its body in try/except.  SAGEErrors become
informative error messages with suggestions.  Unexpected exceptions become
a generic "please report this bug" message.  The server never crashes.
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import ValidationError

from sage_solver_core.builder import (
    build_from_lp,
    build_from_mip,
    build_from_portfolio,
    build_from_scheduling,
)
from sage_solver_core.models import SAGEError
from sage_solver_core.explainer import explain_infeasibility, explain_result
from sage_solver_core.fileio import dataframe_to_model, generate_template, read_data, read_data_from_bytes, write_results_excel
from sage_solver_core.models import (
    IISResult,
    LPModel,
    MIPModel,
    PortfolioModel,
    SchedulingModel,
    SolverInput,
    SolverResult,
)
from sage_solver_core.relaxation import suggest_relaxations
from sage_solver_core.solver import solve

from sage_solver_mcp.local_io import default_output_dir, output_path_for, resolve_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

AnyModel = LPModel | MIPModel | PortfolioModel | SchedulingModel


@dataclass
class ServerState:
    last_result: SolverResult | None = None
    last_model: AnyModel | None = None
    last_solver_input: SolverInput | None = None
    last_iis: IISResult | None = None


_state = ServerState()

# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------

server = Server("sage")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _text(content: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=content)]


def _error_text(message: str) -> list[types.TextContent]:
    return _text(f"[SAGE Error]\n{message}")


def _detect_model_type(data: dict[str, Any]) -> str:
    """Infer the model type from a JSON payload.

    Checks an explicit ``problem_type`` field first, then falls back to
    structural detection based on key presence.
    """
    explicit = data.get("problem_type", "").lower()
    if explicit in ("lp", "mip", "portfolio", "scheduling"):
        return explicit

    if "assets" in data and "covariance_matrix" in data:
        return "portfolio"
    if "workers" in data and "shifts" in data:
        return "scheduling"
    if "variables" in data and "constraints" in data:
        # Distinguish MIP vs LP by var_type field presence
        vars_ = data.get("variables", [])
        if vars_ and any(v.get("var_type", "continuous") != "continuous" for v in vars_):
            return "mip"
        return "lp"

    return "lp"


def _parse_model(data: dict[str, Any]) -> tuple[AnyModel, SolverInput]:
    """Parse a JSON dict into a typed model and build the SolverInput."""
    model_type = _detect_model_type(data)
    # Remove meta-field before passing to Pydantic
    data = {k: v for k, v in data.items() if k != "problem_type"}

    if model_type == "portfolio":
        model = PortfolioModel.model_validate(data)
        si = build_from_portfolio(model)
    elif model_type == "scheduling":
        model = SchedulingModel.model_validate(data)
        si = build_from_scheduling(model)
    elif model_type == "mip":
        model = MIPModel.model_validate(data)
        si = build_from_mip(model)
    else:
        model = LPModel.model_validate(data)
        si = build_from_lp(model)

    return model, si


def _format_solution_summary(result: SolverResult, model: AnyModel) -> str:
    """Return a concise solution summary with explanation."""
    explanation = explain_result(result, model, "standard")
    lines = [explanation]

    if result.status == "optimal" and result.variable_values:
        lines.append("\nVariable values:")
        for name, val in sorted(result.variable_values.items()):
            lines.append(f"  {name}: {val:.6g}")

    if result.status == "infeasible" and result.iis:
        lines.append(f"\nConflicting constraints: {', '.join(result.iis.conflicting_constraints)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 1: solve_optimization
# ---------------------------------------------------------------------------

_SOLVE_OPTIMIZATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "A structured optimization problem definition. Include a 'problem_type' field "
        "('lp', 'mip', 'portfolio', or 'scheduling') plus the fields for that type. "
        "If problem_type is omitted, it is inferred from the structure."
    ),
    "properties": {
        "problem_type": {
            "type": "string",
            "enum": ["lp", "mip", "portfolio", "scheduling"],
            "description": "Optional explicit problem type discriminator.",
        }
    },
    "additionalProperties": True,
}

# ---------------------------------------------------------------------------
# Tool 2: read_data_file
# ---------------------------------------------------------------------------

_READ_DATA_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["filepath"],
    "properties": {
        "filepath": {
            "type": "string",
            "description": "Path to an Excel (.xlsx) or CSV file. Relative paths are resolved from the current working directory. ~ is expanded.",
        },
        "problem_type": {
            "type": "string",
            "enum": ["portfolio", "scheduling", "transport", "generic_lp"],
            "description": "Optional hint for how to interpret the file structure.",
        },
    },
}

# ---------------------------------------------------------------------------
# Tool 3: solve_from_file
# ---------------------------------------------------------------------------

_SOLVE_FROM_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["filepath", "problem_type"],
    "properties": {
        "filepath": {
            "type": "string",
            "description": "Path to the Excel/CSV data file.",
        },
        "problem_type": {
            "type": "string",
            "enum": ["portfolio", "scheduling", "transport", "generic_lp"],
            "description": "Problem type used to parse the file.",
        },
        "objective": {
            "type": "string",
            "description": "Optional override for the optimization objective (e.g. 'minimize cost').",
        },
        "constraints_description": {
            "type": "string",
            "description": "Optional natural-language description of any additional constraints.",
        },
    },
}

# ---------------------------------------------------------------------------
# Tool 4: explain_solution
# ---------------------------------------------------------------------------

_EXPLAIN_SOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "detail_level": {
            "type": "string",
            "enum": ["brief", "standard", "detailed"],
            "description": "How much detail to include. Default: standard.",
        }
    },
}

# ---------------------------------------------------------------------------
# Tool 5: check_feasibility
# ---------------------------------------------------------------------------

_CHECK_FEASIBILITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Same format as solve_optimization. The problem is solved purely to "
        "determine feasibility; if infeasible, the IIS and relaxation suggestions "
        "are returned."
    ),
    "properties": {
        "problem_type": {
            "type": "string",
            "enum": ["lp", "mip", "portfolio", "scheduling"],
        }
    },
    "additionalProperties": True,
}

# ---------------------------------------------------------------------------
# Tool 6: generate_template
# ---------------------------------------------------------------------------

_GENERATE_TEMPLATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["problem_type"],
    "properties": {
        "problem_type": {
            "type": "string",
            "enum": ["portfolio", "scheduling", "transport", "generic_lp"],
            "description": "Type of template to generate.",
        },
        "output_directory": {
            "type": "string",
            "description": "Directory to write the template into. Defaults to the current working directory.",
        },
    },
}

# ---------------------------------------------------------------------------
# Tool 7: suggest_relaxations
# ---------------------------------------------------------------------------

_SUGGEST_RELAXATIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "description": (
        "Uses the most recent infeasible result stored in server state. "
        "No input required — call solve_optimization or check_feasibility first."
    ),
}

# ---------------------------------------------------------------------------
# @server.list_tools
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="solve_optimization",
            description=(
                "Solve a mathematical optimization problem — linear programming (LP), "
                "mixed-integer programming (MIP), portfolio optimization, or workforce "
                "scheduling. Returns the optimal solution with variable values, objective "
                "value, solve time, and a plain-English explanation. If infeasible, "
                "returns the minimal infeasibility certificate (IIS)."
            ),
            inputSchema=_SOLVE_OPTIMIZATION_SCHEMA,
        ),
        types.Tool(
            name="read_data_file",
            description=(
                "Read an Excel (.xlsx) or CSV file containing optimization data. "
                "Returns a structured preview: detected sheets, row/column counts, "
                "column names, and the first 5 rows of each sheet. Use this before "
                "solve_from_file to confirm the data looks right."
            ),
            inputSchema=_READ_DATA_FILE_SCHEMA,
        ),
        types.Tool(
            name="solve_from_file",
            description=(
                "Read data from an Excel or CSV file, build and solve the optimization "
                "model, and write the results to a new Excel file next to the input. "
                "Returns the solution summary and the path to the output file."
            ),
            inputSchema=_SOLVE_FROM_FILE_SCHEMA,
        ),
        types.Tool(
            name="explain_solution",
            description=(
                "Get a natural-language explanation of the most recent optimization result. "
                "Choose detail_level: 'brief' for a one-line summary, 'standard' for key "
                "values and binding constraints, or 'detailed' for full sensitivity analysis."
            ),
            inputSchema=_EXPLAIN_SOLUTION_SCHEMA,
        ),
        types.Tool(
            name="check_feasibility",
            description=(
                "Check whether an optimization problem has a feasible solution without "
                "fully optimizing it. If the problem is infeasible, returns the minimal "
                "conflicting constraint set (IIS) and ranked relaxation suggestions."
            ),
            inputSchema=_CHECK_FEASIBILITY_SCHEMA,
        ),
        types.Tool(
            name="generate_template",
            description=(
                "Generate a blank Excel template for a specific problem type "
                "(portfolio, scheduling, transport, or generic_lp). The template "
                "contains pre-formatted sheets with column headers, descriptions, "
                "and example rows — ready for the user to fill in their data."
            ),
            inputSchema=_GENERATE_TEMPLATE_SCHEMA,
        ),
        types.Tool(
            name="suggest_relaxations",
            description=(
                "For the most recent infeasible optimization result, compute which "
                "constraints to relax and by how much to restore feasibility. Returns "
                "a ranked list of suggestions — each with the constraint name, current "
                "value, suggested value, percentage change, and trade-off explanation. "
                "Call solve_optimization or check_feasibility first."
            ),
            inputSchema=_SUGGEST_RELAXATIONS_SCHEMA,
        ),
    ]


# ---------------------------------------------------------------------------
# @server.call_tool — dispatch
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    try:
        if name == "solve_optimization":
            return await _handle_solve_optimization(arguments)
        elif name == "read_data_file":
            return await _handle_read_data_file(arguments)
        elif name == "solve_from_file":
            return await _handle_solve_from_file(arguments)
        elif name == "explain_solution":
            return await _handle_explain_solution(arguments)
        elif name == "check_feasibility":
            return await _handle_check_feasibility(arguments)
        elif name == "generate_template":
            return await _handle_generate_template(arguments)
        elif name == "suggest_relaxations":
            return await _handle_suggest_relaxations(arguments)
        else:
            return _error_text(f"Unknown tool: {name!r}")
    except SAGEError as exc:
        logger.warning("SAGEError in tool %r: %s", name, exc)
        return _error_text(
            f"{type(exc).__name__}: {exc}\n\n"
            "Suggestions:\n"
            "- Verify the model structure matches the expected schema.\n"
            "- Check that all variable names in constraints appear in the variables list.\n"
            "- For file errors, confirm the path is correct and the file is readable."
        )
    except (FileNotFoundError, OSError) as exc:
        logger.warning("File error in tool %r: %s", name, exc)
        return _error_text(
            f"File not found or not readable: {exc}\n\n"
            "Suggestions:\n"
            "- Check that the file path is correct.\n"
            "- Use an absolute path or ~ for your home directory.\n"
            "- Ensure the file exists and you have read permission."
        )
    except Exception:
        logger.exception("Unexpected error in tool %r", name)
        return _error_text(
            "An unexpected error occurred:\n\n"
            + traceback.format_exc()
            + "\nPlease report this bug at https://github.com/your-org/sage/issues"
        )


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


async def _handle_solve_optimization(args: dict[str, Any]) -> list[types.TextContent]:
    try:
        model, si = _parse_model(args)
    except (ValidationError, ValueError) as exc:
        return _error_text(
            f"Model validation error: {exc}\n\n"
            "Suggestions:\n"
            "- Ensure all required fields are present (name, variables, constraints, objective for LP/MIP).\n"
            "- Check that 'variables' is a list, not a string or other type.\n"
            "- For portfolio models, include 'assets' and 'covariance_matrix'.\n"
            "- For scheduling, include 'workers' and 'shifts'."
        )
    result = solve(si)

    _state.last_result = result
    _state.last_model = model
    _state.last_solver_input = si
    _state.last_iis = result.iis if result.status == "infeasible" else None

    summary = _format_solution_summary(result, model)
    return _text(summary)


async def _handle_read_data_file(args: dict[str, Any]) -> list[types.TextContent]:
    filepath = args["filepath"]
    problem_type = args.get("problem_type")

    try:
        resolved = resolve_path(filepath)
    except FileNotFoundError as exc:
        return _error_text(str(exc))

    dfs = read_data(str(resolved))

    lines = [f"File: {resolved}"]
    lines.append(f"Sheets detected: {', '.join(dfs.keys())}\n")

    for sheet_name, df in dfs.items():
        lines.append(f"Sheet: {sheet_name!r}")
        lines.append(f"  Rows: {len(df)}  Columns: {len(df.columns)}")
        lines.append(f"  Columns: {', '.join(str(c) for c in df.columns)}")
        if len(df) > 0:
            preview = df.head(5).to_string(index=False, max_cols=10)
            lines.append("  Preview (first 5 rows):")
            for row in preview.splitlines():
                lines.append(f"    {row}")
        lines.append("")

    if problem_type:
        lines.append(f"Tip: use solve_from_file with problem_type={problem_type!r} to solve this data.")

    return _text("\n".join(lines))


async def _handle_solve_from_file(args: dict[str, Any]) -> list[types.TextContent]:
    filepath = args["filepath"]
    problem_type = args["problem_type"]

    try:
        resolved = resolve_path(filepath)
    except FileNotFoundError as exc:
        return _error_text(str(exc))

    dfs = read_data(str(resolved))
    model = dataframe_to_model(dfs, problem_type)

    if isinstance(model, PortfolioModel):
        si = build_from_portfolio(model)
    elif isinstance(model, SchedulingModel):
        si = build_from_scheduling(model)
    elif isinstance(model, MIPModel):
        si = build_from_mip(model)
    else:
        si = build_from_lp(model)  # type: ignore[arg-type]

    result = solve(si)

    _state.last_result = result
    _state.last_model = model
    _state.last_solver_input = si
    _state.last_iis = result.iis if result.status == "infeasible" else None

    # Write results Excel next to input
    out_path = output_path_for(str(resolved), "_optimized")
    model_name = getattr(model, "name", problem_type)
    write_results_excel(result, model_name, str(out_path))

    summary = _format_solution_summary(result, model)
    return _text(f"{summary}\n\nResults written to: {out_path}")


async def _handle_explain_solution(args: dict[str, Any]) -> list[types.TextContent]:
    if _state.last_result is None or _state.last_model is None:
        return _error_text(
            "No solve result available. Run solve_optimization or solve_from_file first."
        )

    detail_level = args.get("detail_level", "standard")
    if detail_level not in ("brief", "standard", "detailed"):
        detail_level = "standard"

    explanation = explain_result(_state.last_result, _state.last_model, detail_level)  # type: ignore[arg-type]
    return _text(explanation)


async def _handle_check_feasibility(args: dict[str, Any]) -> list[types.TextContent]:
    try:
        model, si = _parse_model(args)
    except (ValidationError, ValueError) as exc:
        return _error_text(f"Model validation error: {exc}")
    result = solve(si)

    _state.last_result = result
    _state.last_model = model
    _state.last_solver_input = si
    _state.last_iis = result.iis if result.status == "infeasible" else None

    if result.status == "optimal":
        return _text(
            f"The problem is FEASIBLE.\n"
            f"Objective value: {result.objective_value:.6g}\n"
            f"A feasible (and optimal) solution exists."
        )

    if result.status == "infeasible":
        iis = result.iis
        lines = ["The problem is INFEASIBLE."]

        if iis:
            inf_explanation = explain_infeasibility(iis, model)  # type: ignore[arg-type]
            lines.append(inf_explanation)

            # Suggest relaxations
            suggestions = suggest_relaxations(iis, model, si)  # type: ignore[arg-type]
            if suggestions:
                lines.append("\nRelaxation suggestions (least disruptive first):")
                for s in suggestions[:5]:
                    lines.append(
                        f"  [{s.priority}] {s.constraint_name}: "
                        f"{s.current_value:.4g} → {s.suggested_value:.4g} "
                        f"({s.relaxation_percent:+.1f}%) — {s.explanation}"
                    )
            else:
                lines.append(
                    "\nNo single-constraint relaxation can restore feasibility. "
                    "The model requires structural changes (add capacity, reduce demand)."
                )

        return _text("\n".join(lines))

    # Other statuses (unbounded, time_limit, solver_error)
    return _text(
        f"Solver status: {result.status}\n"
        + explain_result(result, model, "brief")
    )


async def _handle_generate_template(args: dict[str, Any]) -> list[types.TextContent]:
    problem_type = args["problem_type"]
    output_directory = args.get("output_directory")

    try:
        if output_directory:
            out_dir = resolve_path(output_directory) if output_directory else default_output_dir()
        else:
            out_dir = default_output_dir()

        out_path = out_dir / f"{problem_type}_template.xlsx"
        generate_template(problem_type, str(out_path))
    except SAGEError as exc:
        return _error_text(
            f"Could not generate template: {exc}\n\n"
            "Supported problem types: generic_lp, portfolio, scheduling, transport"
        )

    return _text(
        f"Template generated: {out_path}\n\n"
        f"Fill in the sheets, then use solve_from_file with problem_type={problem_type!r} to solve."
    )


async def _handle_suggest_relaxations(args: dict[str, Any]) -> list[types.TextContent]:
    if _state.last_iis is None:
        if _state.last_result is not None and _state.last_result.status != "infeasible":
            return _error_text(
                "The last solve was not infeasible — no relaxations to suggest.\n"
                "Run solve_optimization or check_feasibility with an infeasible problem first."
            )
        return _error_text(
            "No infeasible result available. "
            "Run solve_optimization or check_feasibility with an infeasible problem first."
        )

    assert _state.last_model is not None
    assert _state.last_solver_input is not None

    suggestions = suggest_relaxations(
        _state.last_iis,
        _state.last_model,  # type: ignore[arg-type]
        _state.last_solver_input,
    )

    if not suggestions:
        return _text(
            "No single-constraint relaxation can restore feasibility for the last infeasible result.\n"
            "The model likely requires structural changes (add more capacity, reduce requirements, etc.)."
        )

    lines = [f"Relaxation suggestions ({len(suggestions)} found, ranked by least disruption):"]
    for s in suggestions:
        obj_info = f", new objective: {s.new_objective_value:.4g}" if s.new_objective_value is not None else ""
        lines.append(
            f"\n[{s.priority}] Constraint: {s.constraint_name}\n"
            f"    Current value:   {s.current_value:.4g}\n"
            f"    Suggested value: {s.suggested_value:.4g}\n"
            f"    Change:          {s.relaxation_amount:+.4g} ({s.relaxation_percent:+.1f}%){obj_info}\n"
            f"    Explanation:     {s.explanation}"
        )

    return _text("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Start the SAGE MCP server using stdio transport."""
    import asyncio

    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run_server())
