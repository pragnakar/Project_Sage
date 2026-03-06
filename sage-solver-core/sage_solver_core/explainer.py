"""SAGE Core — Result Narrator and Infeasibility Explainer.

Translates solver results into natural language narratives suitable for relay
by an LLM to the end user.  Output is plain text (no Markdown) — the LLM
layer handles formatting.

No filesystem access. No print() calls. No global state. Every function
takes Python objects in and returns a string.

Public API
----------
explain_result(result, model, detail_level="standard") -> str
explain_infeasibility(iis, model) -> str
"""

from __future__ import annotations

import logging
from typing import Literal

from sage_solver_core.models import (
    IISResult,
    LPModel,
    MIPModel,
    PortfolioModel,
    SchedulingModel,
    SolverResult,
)

logger = logging.getLogger("sage.explainer")

# Union type for any model accepted by this module
AnyModel = LPModel | MIPModel | PortfolioModel | SchedulingModel

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain_result(
    result: SolverResult,
    model: AnyModel,
    detail_level: Literal["brief", "standard", "detailed"] = "standard",
) -> str:
    """Generate a natural language explanation of a solver result.

    Args:
        result: The solver result to explain.
        model: The original domain model (used for domain-specific language).
        detail_level: Verbosity of the explanation:
            - "brief": One-line status and objective.
            - "standard": Status, objective, top variables, binding constraints,
              one key insight.
            - "detailed": Standard plus full sensitivity narrative.

    Returns:
        A plain-text string explanation (no Markdown).
    """
    domain = _detect_domain(model)

    if result.status == "infeasible":
        if result.iis:
            return explain_infeasibility(result.iis, model)
        return (
            "The model is infeasible. No feasible solution exists. "
            "Use compute_iis() to identify the conflicting constraints."
        )

    if result.status == "unbounded":
        return (
            "The model is unbounded. The objective can improve without limit. "
            "Check that all decision variables have finite upper bounds "
            "(for a maximization problem) or that the constraint set is not empty."
        )

    if result.status == "time_limit_reached":
        obj_str = (
            f"{result.objective_value:.4f}"
            if result.objective_value is not None
            else "not available"
        )
        return (
            f"The solver reached the time limit before proving optimality. "
            f"Best {_obj_label(domain)} found: {obj_str}. "
            f"Elapsed time: {result.solve_time_seconds:.2f}s. "
            f"Increase the time limit or simplify the model for a proven optimal solution."
        )

    if result.status == "solver_error":
        return (
            "The solver encountered an internal error. "
            "Check the model formulation for numerical issues such as very large or "
            "very small coefficients."
        )

    # Status is "optimal" — generate the appropriate level of explanation
    if detail_level == "brief":
        return _brief(result, model, domain)
    elif detail_level == "standard":
        return _standard(result, model, domain)
    else:
        return _detailed(result, model, domain)


def explain_infeasibility(
    iis: IISResult,
    model: AnyModel,
) -> str:
    """Explain why a model has no feasible solution.

    Args:
        iis: The Irreducible Infeasible Subsystem computed by the solver.
        model: The original domain model (used for domain-specific context).

    Returns:
        A plain-text explanation including a quantitative argument where possible.
    """
    domain = _detect_domain(model)

    if domain == "portfolio":
        return _explain_infeasibility_portfolio(iis, model)  # type: ignore[arg-type]
    elif domain == "scheduling":
        return _explain_infeasibility_scheduling(iis, model)  # type: ignore[arg-type]
    else:
        return _explain_infeasibility_generic(iis, model)


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------


def _detect_domain(model: AnyModel) -> str:
    if isinstance(model, PortfolioModel):
        return "portfolio"
    if isinstance(model, SchedulingModel):
        return "scheduling"
    if isinstance(model, MIPModel):
        return "mip"
    return "lp"


# ---------------------------------------------------------------------------
# Brief explanation
# ---------------------------------------------------------------------------


def _brief(result: SolverResult, model: AnyModel, domain: str) -> str:
    obj_val = result.objective_value
    sense = _sense_from_model(model)
    sense_word = "maximized" if sense == "maximize" else "minimized"
    time_str = f"{result.solve_time_seconds:.3f}s"

    if domain == "portfolio":
        # Compute and report the actual expected return (more meaningful than raw QP obj)
        exp_return = _portfolio_expected_return(result, model)  # type: ignore[arg-type]
        return (
            f"Optimal portfolio allocation found. "
            f"Expected return: {exp_return:.2%}. "
            f"Solved in {time_str}."
        )
    elif domain == "scheduling":
        return (
            f"Optimal schedule found. "
            f"Objective value: {obj_val:.4f} ({sense_word}). "
            f"Solved in {time_str}."
        )
    else:
        return (
            f"Optimal solution found. "
            f"Objective value: {obj_val:.4f} ({sense_word}). "
            f"Solved in {time_str}."
        )


# ---------------------------------------------------------------------------
# Standard explanation
# ---------------------------------------------------------------------------


def _standard(result: SolverResult, model: AnyModel, domain: str) -> str:
    parts: list[str] = []

    # Header line (same as brief)
    parts.append(_brief(result, model, domain))

    # Top variables
    if result.variable_values:
        parts.append(_top_variables_section(result.variable_values, domain, model, n=5))

    # Binding constraints
    if result.binding_constraints:
        parts.append(_binding_constraints_section(result, domain))

    # Key insight
    insight = _key_insight(result, model, domain)
    if insight:
        parts.append(f"Key insight: {insight}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Detailed explanation
# ---------------------------------------------------------------------------


def _detailed(result: SolverResult, model: AnyModel, domain: str) -> str:
    parts: list[str] = []

    # Start with standard
    parts.append(_standard(result, model, domain))

    # Sensitivity narrative
    sensitivity = _sensitivity_narrative(result, model, domain)
    if sensitivity:
        parts.append(sensitivity)

    # Objective coefficient ranges
    obj_ranges = _objective_ranges_narrative(result, model)
    if obj_ranges:
        parts.append(obj_ranges)

    # RHS ranges
    rhs_ranges = _rhs_ranges_narrative(result, model)
    if rhs_ranges:
        parts.append(rhs_ranges)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _top_variables_section(
    var_values: dict[str, float],
    domain: str,
    model: AnyModel,
    n: int = 5,
) -> str:
    if domain == "portfolio":
        label = "Asset allocations"
        formatter = lambda name, val: f"  {name}: {val:.2%}"
    elif domain == "scheduling":
        # Only show assigned shifts (value > 0.5) — binary vars
        assigned = {k: v for k, v in var_values.items() if v > 0.5}
        if not assigned:
            return "No assignments made."
        label = "Assigned shifts"
        formatter = lambda name, val: f"  {name}: assigned"
        # Take top n by variable name for readability
        items = list(assigned.items())[:n]
        lines = [f"{label} (showing {len(items)} of {len(assigned)} total):"]
        for name, val in items:
            lines.append(formatter(name, val))
        if len(assigned) > n:
            lines.append(f"  ... and {len(assigned) - n} more assignments.")
        return "\n".join(lines)
    else:
        label = "Key variable values"
        formatter = lambda name, val: f"  {name} = {val:.4f}"

    # Sort by absolute value descending, take top n
    sorted_vars = sorted(var_values.items(), key=lambda x: abs(x[1]), reverse=True)[:n]
    lines = [f"{label} (top {min(n, len(sorted_vars))} by magnitude):"]
    for name, val in sorted_vars:
        lines.append(formatter(name, val))
    if len(var_values) > n:
        lines.append(f"  ... and {len(var_values) - n} more variables.")
    return "\n".join(lines)


def _binding_constraints_section(result: SolverResult, domain: str) -> str:
    if not result.binding_constraints:
        return "No binding constraints (all constraints have slack)."

    if domain == "portfolio":
        label = "Binding allocation constraints"
    elif domain == "scheduling":
        label = "Binding scheduling constraints"
    else:
        label = "Binding constraints (zero slack)"

    lines = [f"{label}:"]
    for cname in result.binding_constraints:
        sp = ""
        if result.shadow_prices and cname in result.shadow_prices:
            sp_val = result.shadow_prices[cname]
            if abs(sp_val) > 1e-8:
                sp = f" (shadow price: {sp_val:+.4f})"
        lines.append(f"  {cname}{sp}")
    return "\n".join(lines)


def _key_insight(result: SolverResult, model: AnyModel, domain: str) -> str:
    """Generate one key insight about the solution."""
    if domain == "portfolio":
        return _portfolio_key_insight(result, model)  # type: ignore[arg-type]
    elif domain == "scheduling":
        return _scheduling_key_insight(result, model)  # type: ignore[arg-type]
    else:
        return _generic_key_insight(result, model)


def _portfolio_key_insight(result: SolverResult, model: PortfolioModel) -> str:
    if not result.variable_values or not result.binding_constraints:
        return ""
    # Find the most constrained asset (at its bound with highest shadow price)
    if result.shadow_prices:
        most_impactful = max(
            result.binding_constraints,
            key=lambda c: abs(result.shadow_prices.get(c, 0.0)),
            default=None,
        )
        if most_impactful and most_impactful in result.shadow_prices:
            sp = result.shadow_prices[most_impactful]
            if abs(sp) > 1e-8:
                return (
                    f"The '{most_impactful}' constraint is the most restrictive "
                    f"(shadow price: {sp:+.4f}). Relaxing it by 1 percentage point "
                    f"would change the risk-adjusted return by {abs(sp):.4f}."
                )
    # Fallback: mention the dominant asset
    dominant = max(result.variable_values.items(), key=lambda x: x[1])
    return f"The largest allocation is to '{dominant[0]}' at {dominant[1]:.2%}."


def _scheduling_key_insight(result: SolverResult, model: SchedulingModel) -> str:
    if not result.variable_values:
        return ""
    # Count total assignments
    total = sum(1 for v in result.variable_values.values() if v > 0.5)
    total_possible = len(model.workers) * len(model.shifts) * model.planning_horizon_days
    utilization = total / total_possible if total_possible > 0 else 0.0
    return (
        f"Total of {total} shift assignments made out of {total_possible} possible "
        f"({utilization:.0%} utilization). "
        f"Schedule covers {model.planning_horizon_days} day(s) with "
        f"{len(model.shifts)} shift type(s) and {len(model.workers)} worker(s)."
    )


def _generic_key_insight(result: SolverResult, model: AnyModel) -> str:
    if not result.binding_constraints:
        return "No constraints are binding — there is slack in the system."
    n_binding = len(result.binding_constraints)
    most_impactful = ""
    if result.shadow_prices and result.binding_constraints:
        most_impactful_name = max(
            result.binding_constraints,
            key=lambda c: abs(result.shadow_prices.get(c, 0.0)),
        )
        sp = result.shadow_prices.get(most_impactful_name, 0.0)
        if abs(sp) > 1e-8:
            most_impactful = (
                f" The most restrictive constraint is '{most_impactful_name}' "
                f"with a shadow price of {sp:+.4f}."
            )
    return f"{n_binding} constraint(s) are fully utilized (binding).{most_impactful}"


# ---------------------------------------------------------------------------
# Sensitivity narrative (for detailed level)
# ---------------------------------------------------------------------------


def _sensitivity_narrative(result: SolverResult, model: AnyModel, domain: str) -> str:
    if not result.shadow_prices and not result.reduced_costs:
        if isinstance(model, MIPModel) or domain in ("mip", "scheduling"):
            return (
                "Sensitivity analysis: Not available for mixed-integer programs. "
                "Shadow prices and reduced costs are only computed for LP relaxations."
            )
        return ""

    parts: list[str] = ["Sensitivity analysis:"]
    sense = _sense_from_model(model)

    # Shadow prices for all constraints
    if result.shadow_prices:
        parts.append(_constraint_sensitivity_block(result, sense, domain))

    # Reduced costs for variables
    if result.reduced_costs and result.variable_values:
        parts.append(_variable_sensitivity_block(result, sense, domain))

    return "\n\n".join(parts)


def _constraint_sensitivity_block(result: SolverResult, sense: str, domain: str) -> str:
    lines = ["Constraints:"]
    if not result.shadow_prices:
        return ""

    # Look up constraint senses — not directly available in SolverResult,
    # so we infer from slack: binding = 0 slack, non-binding has slack
    binding_set = set(result.binding_constraints or [])
    slack = result.constraint_slack or {}

    for cname, sp in result.shadow_prices.items():
        slack_val = slack.get(cname, 0.0)
        is_binding = cname in binding_set

        if is_binding and abs(sp) > 1e-8:
            # Determine what relaxation means
            obj_change = _describe_shadow_price_effect(sp, sense, domain)
            rhs_range_str = ""
            if result.rhs_ranges and cname in result.rhs_ranges:
                lo, hi = result.rhs_ranges[cname]
                lo_str = f"{lo:.4f}" if lo is not None else "-inf"
                hi_str = f"{hi:.4f}" if hi is not None else "+inf"
                rhs_range_str = (
                    f" The right-hand side can range from {lo_str} to {hi_str} "
                    f"before the optimal basis changes."
                )
            lines.append(
                f"  {cname} [binding]: Shadow price = {sp:+.4f}. "
                f"{obj_change}{rhs_range_str}"
            )
        elif is_binding and abs(sp) <= 1e-8:
            lines.append(
                f"  {cname} [binding, degenerate]: Constraint is at its limit "
                f"but the shadow price is effectively zero — relaxing it would "
                f"not improve the objective."
            )
        else:
            lines.append(
                f"  {cname} [non-binding]: Slack = {slack_val:.4f}. "
                f"This constraint has capacity to spare and does not currently "
                f"limit the optimal solution."
            )
    return "\n".join(lines)


def _describe_shadow_price_effect(sp: float, sense: str, domain: str) -> str:
    """Generate a human-readable description of what a shadow price means."""
    abs_sp = abs(sp)

    if domain == "portfolio":
        unit = "percentage point"
        obj_word = "risk-adjusted return"
    elif domain in ("lp", "mip"):
        unit = "unit"
        obj_word = "objective value"
    else:
        unit = "unit"
        obj_word = "objective"

    if sense == "maximize":
        if sp > 0:
            return (
                f"Increasing the right-hand side by 1 {unit} would improve "
                f"the {obj_word} by {abs_sp:.4f}."
            )
        else:
            return (
                f"This constraint is currently at its limit. Tightening it "
                f"(decreasing the right-hand side) by 1 {unit} would reduce "
                f"the {obj_word} by {abs_sp:.4f}."
            )
    else:  # minimize
        if sp < 0:
            return (
                f"Increasing the right-hand side by 1 {unit} would improve "
                f"(decrease) the {obj_word} by {abs_sp:.4f}."
            )
        else:
            return (
                f"This constraint is currently at its limit. Tightening it "
                f"(decreasing the right-hand side) by 1 {unit} would worsen "
                f"the {obj_word} by {abs_sp:.4f}."
            )


def _variable_sensitivity_block(result: SolverResult, sense: str, domain: str) -> str:
    if not result.reduced_costs or not result.variable_values:
        return ""

    lines = ["Variable bounds and reduced costs:"]
    for vname, rc in result.reduced_costs.items():
        val = result.variable_values.get(vname, 0.0)

        if domain == "portfolio":
            val_str = f"{val:.2%}"
        else:
            val_str = f"{val:.4f}"

        if abs(rc) < 1e-8:
            lines.append(
                f"  {vname} = {val_str}: Reduced cost = 0.00 (variable is "
                f"optimally set between its bounds — not at either limit)."
            )
        elif rc > 0:
            # At lower bound (for minimize), or at upper bound (for maximize)
            if sense == "maximize":
                lines.append(
                    f"  {vname} = {val_str} [at upper bound]: Reduced cost = {rc:+.4f}. "
                    f"Increasing the upper bound by 1 unit would improve the "
                    f"objective by {rc:.4f}."
                )
            else:
                lines.append(
                    f"  {vname} = {val_str} [at lower bound]: Reduced cost = {rc:+.4f}. "
                    f"This variable cannot profitably enter the solution further."
                )
        else:  # rc < 0
            if sense == "maximize":
                lines.append(
                    f"  {vname} = {val_str} [at lower bound]: Reduced cost = {rc:+.4f}. "
                    f"This variable is not in the optimal solution at this bound."
                )
            else:
                lines.append(
                    f"  {vname} = {val_str} [at upper bound]: Reduced cost = {rc:+.4f}. "
                    f"Increasing the upper bound by 1 unit would improve "
                    f"(decrease) the objective by {abs(rc):.4f}."
                )
    return "\n".join(lines)


def _objective_ranges_narrative(result: SolverResult, model: AnyModel) -> str:
    if not result.objective_ranges:
        return ""

    sense = _sense_from_model(model)
    lines = ["Objective coefficient ranges (how much each coefficient can change before the optimal basis changes):"]
    for vname, (lo, hi) in result.objective_ranges.items():
        lo_str = f"{lo:.4f}" if lo is not None else "-inf"
        hi_str = f"{hi:.4f}" if hi is not None else "+inf"
        lines.append(f"  {vname}: allowable range [{lo_str}, {hi_str}]")
    return "\n".join(lines)


def _rhs_ranges_narrative(result: SolverResult, model: AnyModel) -> str:
    if not result.rhs_ranges:
        return ""

    lines = ["Right-hand side ranges (how much each constraint's limit can change before the basis changes):"]
    for cname, (lo, hi) in result.rhs_ranges.items():
        lo_str = f"{lo:.4f}" if lo is not None else "-inf"
        hi_str = f"{hi:.4f}" if hi is not None else "+inf"
        lines.append(f"  {cname}: allowable range [{lo_str}, {hi_str}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Infeasibility explanations
# ---------------------------------------------------------------------------


def _explain_infeasibility_generic(iis: IISResult, model: AnyModel) -> str:
    n_constraints = len(iis.conflicting_constraints)
    n_bounds = len(iis.conflicting_variable_bounds)

    parts: list[str] = []
    parts.append(
        f"The model is infeasible. The solver identified {n_constraints} conflicting "
        f"constraint(s)"
        + (f" and {n_bounds} conflicting variable bound(s)" if n_bounds else "")
        + " that cannot all be satisfied simultaneously."
    )

    if iis.conflicting_constraints:
        parts.append("Conflicting constraints:")
        for cname in iis.conflicting_constraints:
            constraint_detail = _lookup_constraint_detail(cname, model)
            parts.append(f"  - {cname}{constraint_detail}")

    if iis.conflicting_variable_bounds:
        parts.append("Conflicting variable bounds:")
        for vname in iis.conflicting_variable_bounds:
            parts.append(f"  - {vname}")

    parts.append(
        "To restore feasibility, at least one of these constraints must be relaxed "
        "or removed. Use suggest_relaxations() for ranked options."
    )

    return "\n\n".join(parts)


def _explain_infeasibility_portfolio(iis: IISResult, model: PortfolioModel) -> str:
    parts: list[str] = []
    n_assets = len(model.assets)
    pc = model.constraints

    parts.append(
        f"The portfolio model is infeasible. The allocation constraints cannot all be "
        f"satisfied simultaneously across {n_assets} asset(s)."
    )

    # Quantitative analysis
    quant_parts: list[str] = []

    # Check if min_alloc * n_assets > max_total
    if pc.min_allocation_per_asset is not None:
        min_alloc = pc.min_allocation_per_asset
        min_required = min_alloc * n_assets
        max_total = pc.max_total_allocation
        if min_required > max_total + 1e-8:
            quant_parts.append(
                f"Minimum allocation of {min_alloc:.2%} per asset across {n_assets} assets "
                f"requires at least {min_required:.2%} total, but the maximum total "
                f"allocation is {max_total:.2%}."
            )

    # Check sector conflicts
    if pc.max_sector_allocation:
        for sector, max_alloc in pc.max_sector_allocation.items():
            sector_assets = [a for a in model.assets if a.sector == sector]
            if pc.min_allocation_per_asset is not None and sector_assets:
                min_sector = pc.min_allocation_per_asset * len(sector_assets)
                if min_sector > max_alloc + 1e-8:
                    quant_parts.append(
                        f"Sector '{sector}' has {len(sector_assets)} asset(s) with minimum "
                        f"allocation {pc.min_allocation_per_asset:.2%} each, requiring at least "
                        f"{min_sector:.2%} in that sector, but the sector cap is {max_alloc:.2%}."
                    )

    if quant_parts:
        parts.append("Quantitative conflict:")
        parts.extend(quant_parts)

    if iis.conflicting_constraints:
        parts.append(
            "Conflicting constraints: " + ", ".join(iis.conflicting_constraints)
        )

    parts.append(
        "Options to restore feasibility: lower the minimum allocation per asset, "
        "increase the maximum total allocation, raise sector caps, or reduce the "
        "number of required assets."
    )

    return "\n\n".join(parts)


def _explain_infeasibility_scheduling(iis: IISResult, model: SchedulingModel) -> str:
    parts: list[str] = []
    days = model.planning_horizon_days

    # Compute total shift-slots required
    total_required = sum(
        s.required_workers * days for s in model.shifts
    )

    # Compute rough upper bound on available worker-shift-days
    # (max_hours / shift_duration gives max shifts per worker per planning horizon)
    total_available = 0
    for worker in model.workers:
        for shift in model.shifts:
            max_shifts_for_worker = int(worker.max_hours / shift.duration_hours)
            total_available += min(max_shifts_for_worker, days)

    parts.append(
        f"The scheduling model is infeasible. The coverage requirements cannot be "
        f"met with the available workforce over {days} day(s)."
    )

    # Quantitative argument
    quant_msg = (
        f"Coverage demand: {total_required} total worker-shift assignments required "
        f"({' + '.join(f'{s.required_workers} x {days}d x {s.name}' for s in model.shifts)}).\n"
        f"Available capacity: approximately {total_available} worker-shift assignments "
        f"(based on max hours per worker)."
    )
    if total_required > total_available:
        quant_msg += (
            f"\nThe demand ({total_required}) exceeds the capacity ({total_available}) "
            f"by {total_required - total_available} assignments."
        )
    parts.append(quant_msg)

    if iis.conflicting_constraints:
        n = len(iis.conflicting_constraints)
        parts.append(
            f"The minimal conflicting set involves {n} constraint(s): "
            + ", ".join(iis.conflicting_constraints)
        )

    parts.append(
        "Options to restore feasibility: increase worker max_hours, add more workers, "
        "reduce required_workers per shift, reduce the planning horizon, or allow "
        "skill-restricted workers to cover additional shift types."
    )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _detect_domain(model: AnyModel) -> str:
    if isinstance(model, PortfolioModel):
        return "portfolio"
    if isinstance(model, SchedulingModel):
        return "scheduling"
    if isinstance(model, MIPModel):
        return "mip"
    return "lp"


def _sense_from_model(model: AnyModel) -> str:
    """Return 'minimize' or 'maximize' from any model type."""
    if isinstance(model, PortfolioModel):
        return "minimize"  # Portfolio builder always minimizes
    if isinstance(model, SchedulingModel):
        return "minimize"  # Scheduling builder always minimizes
    # LP / MIP
    return model.objective.sense  # type: ignore[union-attr]


def _obj_label(domain: str) -> str:
    """Return a human-readable label for the objective value."""
    if domain == "portfolio":
        return "Markowitz utility"
    if domain == "scheduling":
        return "objective"
    return "objective value"


def _portfolio_expected_return(result: SolverResult, model: PortfolioModel) -> float:
    """Compute actual expected return from optimal weights and asset returns."""
    if not result.variable_values:
        return 0.0
    total = 0.0
    for asset in model.assets:
        w = result.variable_values.get(asset.name, 0.0)
        total += w * asset.expected_return
    return total


def _lookup_constraint_detail(cname: str, model: AnyModel) -> str:
    """Try to find a constraint by name in the model and return a brief description."""
    if isinstance(model, (LPModel, MIPModel)):
        for c in model.constraints:
            if c.name == cname:
                terms = ", ".join(
                    f"{coef:+.4g}{var}"
                    for var, coef in list(c.coefficients.items())[:3]
                )
                if len(c.coefficients) > 3:
                    terms += ", ..."
                return f": {terms} {c.sense} {c.rhs}"
    return ""
