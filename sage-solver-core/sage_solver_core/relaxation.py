"""SAGE Core — Constraint Relaxation Suggester.

For an infeasible model, identifies the minimum relaxation of each IIS
constraint that would restore feasibility, re-solves the relaxed model, and
ranks suggestions by least disruption (smallest percentage change first).

Uses binary search to find the minimum feasible RHS relaxation per constraint.
Each binary search requires O(log(1/epsilon)) LP re-solves — approximately
25 solves per constraint.

No filesystem access. No print() calls. No global state. Every function
takes Python objects in and returns Python objects out.

Public API
----------
suggest_relaxations(iis, model, solver_input) -> list[RelaxationSuggestion]
"""

from __future__ import annotations

import copy
import logging
from typing import Union

from sage_solver_core.models import (
    IISResult,
    LPModel,
    MIPModel,
    PortfolioModel,
    RelaxationSuggestion,
    SchedulingModel,
    SolverInput,
    SolverResult,
)
from sage_solver_core.solver import solve

logger = logging.getLogger("sage.relaxation")

# Union type for any domain model (model arg is used for explanation text only)
AnyModel = Union[LPModel, MIPModel, PortfolioModel, SchedulingModel]

# Multipliers of |original_rhs| (or 1.0 if rhs == 0) used to probe for a
# feasible upper bound before binary search begins
_PROBE_FACTORS = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 100.0, 1000.0]

# Number of binary-search iterations — 25 gives ~10^-7 relative precision
_BISECT_ITERS = 25


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest_relaxations(
    iis: IISResult,
    model: AnyModel,
    solver_input: SolverInput,
) -> list[RelaxationSuggestion]:
    """Compute minimum constraint relaxations that restore feasibility.

    For each constraint named in the IIS:
      1. Binary-search the RHS to find the smallest change that makes the
         overall model feasible (with all other constraints unchanged).
      2. Re-solve at that relaxation to get the new objective value.
      3. Build a :class:`RelaxationSuggestion` with a plain-language explanation.

    For variable bounds named in the IIS:
      4. Suggest expanding the bound by a factor search.

    Suggestions are ranked by ``relaxation_percent`` (ascending) so the
    least-disruptive fix appears first.

    Args:
        iis: The Irreducible Infeasible Subsystem from :func:`sage_core.solver.solve`.
        model: The domain model (used only for explanation text).
        solver_input: The solver representation of the infeasible model.

    Returns:
        Ranked list of :class:`RelaxationSuggestion` objects (may be empty if
        no single-constraint relaxation can restore feasibility).
    """
    suggestions: list[RelaxationSuggestion] = []

    # Build a lookup: constraint name → index in solver_input
    cname_to_idx: dict[str, int] = {
        name: i for i, name in enumerate(solver_input.constraint_names)
    }

    # --- Process IIS constraints ---
    for cname in iis.conflicting_constraints:
        if cname not in cname_to_idx:
            logger.warning("IIS constraint '%s' not found in solver_input — skipping", cname)
            continue

        c_idx = cname_to_idx[cname]
        original_rhs = solver_input.constraint_rhs[c_idx]
        sense = solver_input.constraint_senses[c_idx]

        suggestion = _relax_one_constraint(
            solver_input=solver_input,
            c_idx=c_idx,
            c_name=cname,
            original_rhs=original_rhs,
            sense=sense,
            model=model,
        )
        if suggestion is not None:
            suggestions.append(suggestion)

    # --- Process IIS variable bounds ---
    vname_to_idx: dict[str, int] = {
        name: i for i, name in enumerate(solver_input.variable_names)
    }
    for vname in iis.conflicting_variable_bounds:
        if vname not in vname_to_idx:
            logger.warning("IIS variable '%s' not found in solver_input — skipping", vname)
            continue

        v_idx = vname_to_idx[vname]
        suggestion = _relax_one_variable_bound(
            solver_input=solver_input,
            v_idx=v_idx,
            v_name=vname,
            model=model,
        )
        if suggestion is not None:
            suggestions.append(suggestion)

    # Rank by smallest relaxation percentage first, then by best objective
    suggestions.sort(key=lambda s: (s.relaxation_percent, -(_obj_or_zero(s))))

    # Assign priority ranks (1-based)
    for i, s in enumerate(suggestions):
        # Re-assign priority via a new object copy with updated priority
        suggestions[i] = s.model_copy(update={"priority": i + 1})

    logger.debug(
        "suggest_relaxations: %d IIS constraints, %d variable bounds → %d suggestions",
        len(iis.conflicting_constraints),
        len(iis.conflicting_variable_bounds),
        len(suggestions),
    )
    return suggestions


# ---------------------------------------------------------------------------
# Single-constraint relaxation
# ---------------------------------------------------------------------------


def _relax_one_constraint(
    solver_input: SolverInput,
    c_idx: int,
    c_name: str,
    original_rhs: float,
    sense: str,
    model: AnyModel,
) -> RelaxationSuggestion | None:
    """Find the minimum RHS relaxation of constraint c_idx that restores feasibility."""
    # Step 1: find a feasible RHS value via probing
    feasible_rhs = _probe_feasible_rhs(solver_input, c_idx, original_rhs, sense)

    if feasible_rhs is None:
        logger.debug(
            "Constraint '%s': could not find a feasible RHS via probing — no suggestion generated",
            c_name,
        )
        return None

    # Step 2: binary search to find minimum feasible RHS
    min_rhs = _bisect_rhs(solver_input, c_idx, original_rhs, feasible_rhs)

    # Step 3: re-solve at min_rhs to get objective value
    final_result = _solve_with_rhs(solver_input, c_idx, min_rhs)
    new_obj = final_result.objective_value if final_result.status == "optimal" else None

    # Step 4: compute relaxation metrics
    relaxation_amount = min_rhs - original_rhs
    if abs(original_rhs) > 1e-10:
        relaxation_percent = abs(relaxation_amount / original_rhs) * 100.0
    else:
        relaxation_percent = abs(relaxation_amount) * 100.0  # treat as % of 1

    explanation = _constraint_relaxation_explanation(
        c_name=c_name,
        original_rhs=original_rhs,
        min_rhs=min_rhs,
        relaxation_percent=relaxation_percent,
        sense=sense,
        new_obj=new_obj,
        model=model,
    )

    return RelaxationSuggestion(
        constraint_name=c_name,
        current_value=original_rhs,
        suggested_value=min_rhs,
        relaxation_amount=relaxation_amount,
        relaxation_percent=relaxation_percent,
        new_objective_value=new_obj,
        explanation=explanation,
        priority=1,  # will be overwritten during ranking
    )


# ---------------------------------------------------------------------------
# Single variable-bound relaxation
# ---------------------------------------------------------------------------


def _relax_one_variable_bound(
    solver_input: SolverInput,
    v_idx: int,
    v_name: str,
    model: AnyModel,
) -> RelaxationSuggestion | None:
    """Suggest relaxing a variable's bound to restore feasibility."""
    ub = solver_input.variable_upper_bounds[v_idx]
    lb = solver_input.variable_lower_bounds[v_idx]

    # Determine which bound is more likely conflicting:
    # If ub == 0 or ub == lb (forced to a single value), suggest expanding ub
    if ub is not None and ub <= lb + 1e-10:
        # Variable is fixed or has zero range — try relaxing upper bound
        suggestion = _relax_variable_upper_bound(solver_input, v_idx, v_name, lb, ub, model)
        if suggestion:
            return suggestion

    # If neither ub nor lb is obviously conflicting, try relaxing ub to 1 (for binary)
    # or by some factor
    if ub is not None and ub < 1e29:  # finite ub
        suggestion = _relax_variable_upper_bound(solver_input, v_idx, v_name, lb, ub, model)
        if suggestion:
            return suggestion

    return None


def _relax_variable_upper_bound(
    solver_input: SolverInput,
    v_idx: int,
    v_name: str,
    lb: float,
    original_ub: float,
    model: AnyModel,
) -> RelaxationSuggestion | None:
    """Binary-search the minimum UB expansion that restores feasibility."""
    base = max(abs(original_ub), 1.0)
    feasible_ub = None

    for factor in _PROBE_FACTORS:
        candidate_ub = original_ub + base * factor
        result = _solve_with_ub(solver_input, v_idx, candidate_ub)
        if result.status == "optimal":
            feasible_ub = candidate_ub
            break

    if feasible_ub is None:
        return None

    # Binary search between original_ub and feasible_ub
    lo, hi = original_ub, feasible_ub
    for _ in range(_BISECT_ITERS):
        mid = (lo + hi) / 2
        r = _solve_with_ub(solver_input, v_idx, mid)
        if r.status == "optimal":
            hi = mid
        else:
            lo = mid

    min_ub = hi
    final_result = _solve_with_ub(solver_input, v_idx, min_ub)
    new_obj = final_result.objective_value if final_result.status == "optimal" else None

    relaxation_amount = min_ub - original_ub
    if abs(original_ub) > 1e-10:
        relaxation_percent = abs(relaxation_amount / original_ub) * 100.0
    else:
        relaxation_percent = abs(relaxation_amount) * 100.0

    explanation = _bound_relaxation_explanation(
        v_name=v_name,
        original_ub=original_ub,
        min_ub=min_ub,
        relaxation_percent=relaxation_percent,
        new_obj=new_obj,
        model=model,
    )

    return RelaxationSuggestion(
        constraint_name=f"{v_name}_upper_bound",
        current_value=original_ub,
        suggested_value=min_ub,
        relaxation_amount=relaxation_amount,
        relaxation_percent=relaxation_percent,
        new_objective_value=new_obj,
        explanation=explanation,
        priority=1,
    )


# ---------------------------------------------------------------------------
# Binary search helpers
# ---------------------------------------------------------------------------


def _probe_feasible_rhs(
    solver_input: SolverInput,
    c_idx: int,
    original_rhs: float,
    sense: str,
) -> float | None:
    """Find a RHS value that makes the model feasible by probing increasing deltas."""
    base = max(abs(original_rhs), 1.0)

    for factor in _PROBE_FACTORS:
        if sense == "<=":
            # Relax by increasing RHS
            candidate = original_rhs + base * factor
        elif sense == ">=":
            # Relax by decreasing RHS
            candidate = original_rhs - base * factor
        else:
            # == constraint: try both increasing and decreasing
            for delta_sign in (+1, -1):
                candidate = original_rhs + delta_sign * base * factor
                r = _solve_with_rhs(solver_input, c_idx, candidate)
                if r.status == "optimal":
                    return candidate
            continue

        r = _solve_with_rhs(solver_input, c_idx, candidate)
        if r.status == "optimal":
            return candidate

    return None


def _bisect_rhs(
    solver_input: SolverInput,
    c_idx: int,
    infeasible_rhs: float,
    feasible_rhs: float,
) -> float:
    """Binary search between infeasible_rhs and feasible_rhs for the minimum feasible RHS.

    Returns the minimum RHS value at which the model is feasible.
    The "feasible" side is the side where the objective improves.
    """
    # Determine which direction feasibility lies
    # feasible_rhs may be either larger or smaller than infeasible_rhs
    feasible_is_larger = feasible_rhs > infeasible_rhs

    lo = min(infeasible_rhs, feasible_rhs)
    hi = max(infeasible_rhs, feasible_rhs)

    for _ in range(_BISECT_ITERS):
        mid = (lo + hi) / 2
        r = _solve_with_rhs(solver_input, c_idx, mid)
        if feasible_is_larger:
            # feasible side is hi; infeasible side is lo
            if r.status == "optimal":
                hi = mid  # can we do better (smaller RHS)?
            else:
                lo = mid  # need larger RHS
        else:
            # feasible side is lo; infeasible side is hi
            if r.status == "optimal":
                lo = mid  # can we do better (larger RHS)?
            else:
                hi = mid  # need smaller RHS

    # Return the minimum feasible value
    return hi if feasible_is_larger else lo


# ---------------------------------------------------------------------------
# Solver helpers — create modified SolverInput and solve
# ---------------------------------------------------------------------------


def _solve_with_rhs(
    solver_input: SolverInput,
    c_idx: int,
    new_rhs: float,
) -> SolverResult:
    """Solve a copy of solver_input with constraint c_idx RHS set to new_rhs."""
    data = solver_input.model_dump()
    data["constraint_rhs"][c_idx] = new_rhs
    # Disable IIS computation during binary search for speed
    modified = SolverInput(**data)
    # We pass extract_iis=False implicitly — the solver module always
    # computes IIS on infeasible, but that's OK; it's just extra computation.
    # For speed in production, a future optimization could skip IIS here.
    result = solve(modified)
    return result


def _solve_with_ub(
    solver_input: SolverInput,
    v_idx: int,
    new_ub: float,
) -> SolverResult:
    """Solve a copy of solver_input with variable v_idx upper bound set to new_ub."""
    data = solver_input.model_dump()
    data["variable_upper_bounds"][v_idx] = new_ub
    modified = SolverInput(**data)
    return solve(modified)


# ---------------------------------------------------------------------------
# Explanation text generators
# ---------------------------------------------------------------------------


def _constraint_relaxation_explanation(
    c_name: str,
    original_rhs: float,
    min_rhs: float,
    relaxation_percent: float,
    sense: str,
    new_obj: float | None,
    model: AnyModel,
) -> str:
    direction = "increasing" if min_rhs > original_rhs else "decreasing"
    obj_str = ""
    if new_obj is not None:
        obj_str = f" The resulting optimal objective value would be {new_obj:.4f}."

    domain_context = _domain_constraint_context(c_name, model)

    return (
        f"Relax constraint '{c_name}'{domain_context} by {direction} its "
        f"right-hand side from {original_rhs:.4f} to {min_rhs:.4f} "
        f"(a {relaxation_percent:.1f}% change).{obj_str}"
    )


def _bound_relaxation_explanation(
    v_name: str,
    original_ub: float,
    min_ub: float,
    relaxation_percent: float,
    new_obj: float | None,
    model: AnyModel,
) -> str:
    obj_str = ""
    if new_obj is not None:
        obj_str = f" The resulting optimal objective value would be {new_obj:.4f}."

    domain_context = _domain_variable_context(v_name, model)

    return (
        f"Expand the upper bound of variable '{v_name}'{domain_context} from "
        f"{original_ub:.4f} to {min_ub:.4f} (a {relaxation_percent:.1f}% increase).{obj_str}"
    )


def _domain_constraint_context(c_name: str, model: AnyModel) -> str:
    """Return a brief domain-specific parenthetical for a constraint name."""
    if isinstance(model, PortfolioModel):
        if "total_allocation" in c_name:
            return " (total portfolio allocation)"
        if "sector" in c_name:
            sector = c_name.replace("sector_", "").replace("_max", "")
            return f" (sector '{sector}' cap)"
        if "max_alloc" in c_name:
            asset = c_name.replace("max_alloc_", "")
            return f" (maximum allocation for '{asset}')"
        if "min_alloc" in c_name:
            asset = c_name.replace("min_alloc_", "")
            return f" (minimum allocation for '{asset}')"
    elif isinstance(model, SchedulingModel):
        if c_name.startswith("cov_"):
            parts = c_name.split("_")
            if len(parts) >= 3:
                shift = parts[1]
                day = parts[2]
                return f" (coverage requirement: shift '{shift}', {day})"
        if c_name.startswith("hours_"):
            worker = c_name[6:]
            return f" (maximum hours for worker '{worker}')"
    elif isinstance(model, (LPModel, MIPModel)):
        for c in model.constraints:  # type: ignore[union-attr]
            if c.name == c_name and c.rhs != 0:
                return ""
    return ""


def _domain_variable_context(v_name: str, model: AnyModel) -> str:
    """Return a brief domain-specific parenthetical for a variable name."""
    if isinstance(model, PortfolioModel):
        for asset in model.assets:
            if asset.name == v_name:
                return f" (allocation to '{asset.name}')"
    return ""


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _obj_or_zero(s: RelaxationSuggestion) -> float:
    """Return new_objective_value for sorting, using 0 if None."""
    return s.new_objective_value if s.new_objective_value is not None else 0.0
