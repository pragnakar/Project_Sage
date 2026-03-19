"""SAGE MCP — Fallback solvers for when HiGHS is unavailable.

Provides scipy (LP) and PuLP (MIP) fallback paths that accept the same
SolverInput used by sage-solver-core and return a compatible SolverResult.

These are ONLY used when the primary sage-solver-core solver throws a
technical error (exception, crash). They are never used for normal results
like infeasible or unbounded — those are valid outcomes, not errors.
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from sage_solver_core.models import SolverInput, SolverResult

logger = logging.getLogger(__name__)

# Sentinel for "no upper bound" in SolverInput
_INF = 1e30


def fallback_solve(solver_input: SolverInput) -> tuple[SolverResult, str]:
    """Attempt to solve using scipy or PuLP as a fallback.

    Returns:
        A tuple of (SolverResult, solver_name) where solver_name is
        'scipy' or 'PuLP'.

    Raises:
        RuntimeError: If no fallback solver is available or the fallback
        also fails with a technical error.
    """
    has_integers = any(t in ("integer", "binary") for t in solver_input.variable_types)

    if not has_integers:
        try:
            result = _solve_with_scipy(solver_input)
            return result, "scipy"
        except Exception as exc:
            logger.warning("scipy fallback failed: %s", exc)

    # Try PuLP (LP and MIP)
    try:
        result = _solve_with_pulp(solver_input)
        return result, "PuLP"
    except Exception as exc:
        logger.warning("PuLP fallback failed: %s", exc)
        raise RuntimeError(
            f"All fallback solvers failed. Last error: {exc}"
        ) from exc


def _solve_with_scipy(si: SolverInput) -> SolverResult:
    """Solve an LP using scipy.optimize.linprog."""
    from scipy.optimize import linprog  # type: ignore[import-untyped]

    t0 = time.perf_counter()
    n = si.num_variables
    maximize = si.objective_sense == "maximize"

    # Objective: scipy minimizes, negate for maximize
    c = [-coef if maximize else coef for coef in si.objective_coefficients]

    # Bounds
    bounds = []
    for i in range(n):
        lb = si.variable_lower_bounds[i]
        ub = si.variable_upper_bounds[i]
        bounds.append((lb, ub if ub < _INF else None))

    # Constraints from dense matrix
    A_ub, b_ub = [], []
    A_eq, b_eq = [], []

    for j in range(si.num_constraints):
        row = si.constraint_matrix[j]
        sense = si.constraint_senses[j]
        rhs = si.constraint_rhs[j]

        if sense == "<=":
            A_ub.append(row)
            b_ub.append(rhs)
        elif sense == ">=":
            A_ub.append([-x for x in row])
            b_ub.append(-rhs)
        elif sense == "==":
            A_eq.append(row)
            b_eq.append(rhs)

    res = linprog(
        c,
        A_ub=A_ub if A_ub else None,
        b_ub=b_ub if b_ub else None,
        A_eq=A_eq if A_eq else None,
        b_eq=b_eq if b_eq else None,
        bounds=bounds,
        method="highs",
    )

    solve_time = time.perf_counter() - t0

    if res.success:
        obj_val = -res.fun if maximize else res.fun
        var_values = {si.variable_names[i]: float(res.x[i]) for i in range(n)}
        return SolverResult(
            status="optimal",
            objective_value=obj_val,
            bound=obj_val,
            gap=0.0,
            solve_time_seconds=solve_time,
            variable_values=var_values,
            shadow_prices=None,
            reduced_costs=None,
            constraint_slack=None,
            binding_constraints=None,
            objective_ranges=None,
            rhs_ranges=None,
            iis=None,
        )

    status: Literal["infeasible", "unbounded", "solver_error"]
    if res.status == 2:
        status = "infeasible"
    elif res.status == 3:
        status = "unbounded"
    else:
        status = "solver_error"

    return SolverResult(
        status=status,
        objective_value=None,
        bound=None,
        gap=None,
        solve_time_seconds=solve_time,
        variable_values=None,
        shadow_prices=None,
        reduced_costs=None,
        constraint_slack=None,
        binding_constraints=None,
        objective_ranges=None,
        rhs_ranges=None,
        iis=None,
    )


def _solve_with_pulp(si: SolverInput) -> SolverResult:
    """Solve an LP or MIP using PuLP with its default CBC solver."""
    import pulp  # type: ignore[import-untyped]

    t0 = time.perf_counter()
    n = si.num_variables

    sense = pulp.LpMaximize if si.objective_sense == "maximize" else pulp.LpMinimize
    prob = pulp.LpProblem("sage_fallback", sense)

    # Variables
    lp_vars: list[pulp.LpVariable] = []
    for i in range(n):
        cat = pulp.LpContinuous
        vtype = si.variable_types[i]
        if vtype == "integer":
            cat = pulp.LpInteger
        elif vtype == "binary":
            cat = pulp.LpBinary
        ub = si.variable_upper_bounds[i]
        lp_vars.append(pulp.LpVariable(
            si.variable_names[i],
            lowBound=si.variable_lower_bounds[i],
            upBound=ub if ub < _INF else None,
            cat=cat,
        ))

    # Objective
    prob += pulp.lpSum(
        si.objective_coefficients[i] * lp_vars[i] for i in range(n)
    )

    # Constraints
    for j in range(si.num_constraints):
        expr = pulp.lpSum(
            si.constraint_matrix[j][i] * lp_vars[i] for i in range(n)
        )
        rhs = si.constraint_rhs[j]
        sense_str = si.constraint_senses[j]
        cname = si.constraint_names[j]

        if sense_str == "<=":
            prob += expr <= rhs, cname
        elif sense_str == ">=":
            prob += expr >= rhs, cname
        elif sense_str == "==":
            prob += expr == rhs, cname

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    solve_time = time.perf_counter() - t0
    pulp_status = pulp.LpStatus[prob.status]

    if pulp_status == "Optimal":
        var_values = {
            si.variable_names[i]: float(lp_vars[i].varValue)
            for i in range(n)
        }
        obj_val = float(pulp.value(prob.objective))
        return SolverResult(
            status="optimal",
            objective_value=obj_val,
            bound=obj_val,
            gap=0.0,
            solve_time_seconds=solve_time,
            variable_values=var_values,
            shadow_prices=None,
            reduced_costs=None,
            constraint_slack=None,
            binding_constraints=None,
            objective_ranges=None,
            rhs_ranges=None,
            iis=None,
        )

    status_map: dict[str, Literal["infeasible", "unbounded", "solver_error"]] = {
        "Infeasible": "infeasible",
        "Unbounded": "unbounded",
        "Not Solved": "solver_error",
        "Undefined": "solver_error",
    }
    status = status_map.get(pulp_status, "solver_error")

    return SolverResult(
        status=status,
        objective_value=None,
        bound=None,
        gap=None,
        solve_time_seconds=solve_time,
        variable_values=None,
        shadow_prices=None,
        reduced_costs=None,
        constraint_slack=None,
        binding_constraints=None,
        objective_ranges=None,
        rhs_ranges=None,
        iis=None,
    )
