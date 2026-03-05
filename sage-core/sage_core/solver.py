"""SAGE Core — HiGHS solver wrapper.

All communication with HiGHS is encapsulated here.  No HiGHS objects are
exposed to callers: input is always a ``SolverInput``, output is always a
``SolverResult`` or ``IISResult``.

Public API
----------
solve(solver_input, solver="highs") -> SolverResult
compute_iis(solver_input) -> IISResult
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from sage_core.models import IISResult, SolverError, SolverInput, SolverResult

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger("sage.solver")

# ---------------------------------------------------------------------------
# Solver availability
# ---------------------------------------------------------------------------

try:
    import highspy  # type: ignore[import]

    _HIGHS_AVAILABLE = True
    _INF: float = highspy.kHighsInf  # float('inf') in highspy 1.13
except ImportError:  # pragma: no cover
    _HIGHS_AVAILABLE = False
    _INF = 1e30


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def solve(
    solver_input: SolverInput,
    solver: str = "highs",
) -> SolverResult:
    """Solve an optimization problem and return a certified result.

    Dispatches to HiGHS for LP, MIP, and QP problems.  Sensitivity analysis
    is extracted automatically for LP problems.  If the problem is infeasible,
    an IIS is computed and attached to the result.

    Args:
        solver_input: Solver-agnostic problem definition.
        solver: Backend to use.  Currently only ``"highs"`` is supported.

    Returns:
        Fully populated :class:`SolverResult`.

    Raises:
        SolverError: If the requested solver is unavailable or encounters an
            unexpected internal failure.
    """
    if solver != "highs":
        raise SolverError(
            f"Unsupported solver: '{solver}'. Supported solvers: ['highs']",
            details={"requested": solver, "available": ["highs"]},
            suggestions=["Use solver='highs' (the default)."],
        )
    if not _HIGHS_AVAILABLE:  # pragma: no cover
        raise SolverError(
            "highspy is not installed.",
            suggestions=["pip install highspy"],
        )
    return _solve_highs(solver_input, extract_iis=True)


def compute_iis(solver_input: SolverInput) -> IISResult:
    """Compute the Irreducible Infeasible Subsystem for an infeasible model.

    Uses the iterative deletion filter algorithm: iterates over constraints,
    removing each in turn and re-solving.  Constraints that are *not* needed
    for infeasibility are permanently dropped; those that *are* needed are
    retained.  The remaining set is the IIS.

    Run-time: O(m) LP solves where m is the number of constraints.

    Args:
        solver_input: The problem definition (expected to be infeasible).

    Returns:
        :class:`IISResult` with the minimal conflicting constraint set.

    Raises:
        SolverError: If highspy is not installed.
    """
    if not _HIGHS_AVAILABLE:  # pragma: no cover
        raise SolverError(
            "highspy is not installed.",
            suggestions=["pip install highspy"],
        )
    return _compute_iis_deletion(solver_input)


# ---------------------------------------------------------------------------
# Internal: HiGHS model construction
# ---------------------------------------------------------------------------


def _build_highs(inp: SolverInput) -> "highspy.Highs":
    """Construct a configured HiGHS instance from a SolverInput.

    Args:
        inp: Solver-agnostic problem definition.

    Returns:
        A HiGHS instance ready to call ``run()``.
    """
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("output_flag", False)

    # ---- Parameters -------------------------------------------------------
    if inp.time_limit_seconds is not None:
        h.setOptionValue("time_limit", float(inp.time_limit_seconds))
    if inp.mip_gap_tolerance is not None:
        h.setOptionValue("mip_rel_gap", float(inp.mip_gap_tolerance))

    # ---- Variables --------------------------------------------------------
    for i in range(inp.num_variables):
        vtype = inp.variable_types[i]
        if vtype == "binary":
            # Binary variables are always bounded [0, 1]
            h.addVar(0.0, 1.0)
        else:
            lb = inp.variable_lower_bounds[i]
            ub = inp.variable_upper_bounds[i]
            h.addVar(
                float(lb) if lb is not None else -_INF,
                float(ub) if ub is not None else _INF,
            )

    # ---- Objective --------------------------------------------------------
    sense = (
        highspy.ObjSense.kMaximize
        if inp.objective_sense == "maximize"
        else highspy.ObjSense.kMinimize
    )
    h.changeObjectiveSense(sense)
    for i, coeff in enumerate(inp.objective_coefficients):
        h.changeColCost(i, float(coeff))

    # ---- Quadratic objective (portfolio / QP) -----------------------------
    if inp.objective_quadratic is not None:
        _pass_hessian(h, inp.objective_quadratic)

    # ---- Variable integrality ---------------------------------------------
    for i, vtype in enumerate(inp.variable_types):
        if vtype in ("integer", "binary"):
            h.changeColIntegrality(i, highspy.HighsVarType.kInteger)
        # "continuous" requires no change — HiGHS default is continuous

    # ---- Constraints ------------------------------------------------------
    for i in range(inp.num_constraints):
        row = inp.constraint_matrix[i]
        sense_str = inp.constraint_senses[i]
        rhs = float(inp.constraint_rhs[i])

        # Build sparse representation (skip zeros)
        indices = [j for j, v in enumerate(row) if v != 0.0]
        values = [float(row[j]) for j in indices]

        if sense_str == "<=":
            lb_row, ub_row = -_INF, rhs
        elif sense_str == ">=":
            lb_row, ub_row = rhs, _INF
        else:  # "=="
            lb_row, ub_row = rhs, rhs

        h.addRow(lb_row, ub_row, len(indices), indices, values)

    return h


def _pass_hessian(h: "highspy.Highs", q_matrix: list[list[float]]) -> None:
    """Pass a quadratic objective Hessian to HiGHS.

    HiGHS minimises ``c^T x + 0.5 * x^T Q x``.  The Hessian is stored in
    upper-triangular row-wise sparse format (format code ``1``).

    The builder layer is responsible for scaling Q correctly (e.g. including
    the ``2 * risk_aversion`` factor for Markowitz so that the ``0.5``
    pre-multiplier yields the right coefficient).

    Args:
        h: Configured HiGHS instance (variables already added).
        q_matrix: Dense n × n symmetric matrix.
    """
    n = len(q_matrix)
    q_starts: list[int] = []
    q_indices: list[int] = []
    q_values: list[float] = []
    nz = 0

    for i in range(n):
        q_starts.append(nz)
        for j in range(i, n):  # upper triangular only
            v = float(q_matrix[i][j])
            if v != 0.0:
                q_indices.append(j)
                q_values.append(v)
                nz += 1
    q_starts.append(nz)

    status = h.passHessian(
        n,
        nz,
        1,  # triangular row-wise format
        np.array(q_starts, dtype=np.int32),
        np.array(q_indices, dtype=np.int32),
        np.array(q_values, dtype=np.float64),
    )
    if status != highspy.HighsStatus.kOk:
        logger.warning("passHessian returned non-OK status: %s", status)


# ---------------------------------------------------------------------------
# Internal: solve and result extraction
# ---------------------------------------------------------------------------


def _solve_highs(inp: SolverInput, *, extract_iis: bool = True) -> SolverResult:
    """Build, run, and extract results from HiGHS.

    Args:
        inp: Problem definition.
        extract_iis: When ``True``, trigger IIS computation on infeasible
            results.  Set to ``False`` for IIS sub-solves to avoid recursion.

    Returns:
        :class:`SolverResult`.
    """
    try:
        h = _build_highs(inp)
    except Exception as exc:
        raise SolverError(
            f"Failed to build HiGHS model: {exc}",
            details={"error": str(exc)},
        ) from exc

    t_start = time.perf_counter()
    try:
        h.run()
    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        raise SolverError(
            f"HiGHS solver call failed: {exc}",
            details={"error": str(exc), "solve_time_seconds": round(elapsed, 6)},
        ) from exc

    elapsed = time.perf_counter() - t_start
    return _extract_result(h, inp, elapsed, extract_iis=extract_iis)


def _extract_result(
    h: "highspy.Highs",
    inp: SolverInput,
    elapsed: float,
    *,
    extract_iis: bool,
) -> SolverResult:
    """Convert a solved HiGHS instance to a :class:`SolverResult`.

    Args:
        h: Solved HiGHS instance.
        inp: Original problem definition (used for variable/constraint names).
        elapsed: Wall-clock time elapsed during ``h.run()``.
        extract_iis: Compute IIS for infeasible results when ``True``.

    Returns:
        :class:`SolverResult`.
    """
    model_status = h.getModelStatus()
    status = _map_status(model_status)
    logger.debug("HiGHS status: %s → SAGE: %s (%.4fs)", model_status, status, elapsed)

    fields: dict = {"status": status, "solve_time_seconds": elapsed}

    if status == "solver_error":
        return SolverResult(**fields)

    # ---- Objective value --------------------------------------------------
    ok_obj, obj_val = h.getInfoValue("objective_function_value")
    has_obj = ok_obj == highspy.HighsStatus.kOk

    # ---- MIP bound and gap -----------------------------------------------
    is_mip = any(vt != "continuous" for vt in inp.variable_types)
    if is_mip:
        ok_b, bound_val = h.getInfoValue("mip_dual_bound")
        ok_g, gap_val = h.getInfoValue("mip_gap")
        if ok_b == highspy.HighsStatus.kOk and bound_val is not None:
            fields["bound"] = float(bound_val)
        if ok_g == highspy.HighsStatus.kOk and gap_val is not None:
            try:
                fields["gap"] = float(gap_val)
            except (ValueError, OverflowError):
                pass  # inf / nan gap before first incumbent

    # ---- Primal solution -------------------------------------------------
    sol = h.getSolution()
    has_primal = (
        hasattr(sol, "col_value")
        and len(sol.col_value) == inp.num_variables
    )

    if has_primal and status in ("optimal", "time_limit_reached"):
        if has_obj:
            fields["objective_value"] = float(obj_val)
        fields["variable_values"] = {
            name: float(sol.col_value[i])
            for i, name in enumerate(inp.variable_names)
        }

    # ---- IIS for infeasible results --------------------------------------
    if status == "infeasible" and extract_iis and inp.num_constraints > 0:
        try:
            fields["iis"] = _compute_iis_deletion(inp)
        except Exception as exc:
            logger.warning("IIS computation failed: %s", exc)

    # ---- Sensitivity analysis (LP only) ----------------------------------
    is_lp = not is_mip
    has_dual = (
        is_lp
        and status == "optimal"
        and hasattr(sol, "row_dual")
        and len(sol.row_dual) == inp.num_constraints
    )
    if has_dual:
        fields.update(_extract_sensitivity(h, inp, sol))

    return SolverResult(**fields)


def _map_status(model_status: "highspy.HighsModelStatus") -> str:
    """Map a HiGHS model status enum to a SAGE status string.

    Args:
        model_status: Return value of ``h.getModelStatus()``.

    Returns:
        One of ``"optimal"``, ``"infeasible"``, ``"unbounded"``,
        ``"time_limit_reached"``, or ``"solver_error"``.
    """
    ms = highspy.HighsModelStatus
    mapping: dict["highspy.HighsModelStatus", str] = {
        ms.kOptimal: "optimal",
        ms.kInfeasible: "infeasible",
        ms.kUnbounded: "unbounded",
        ms.kUnboundedOrInfeasible: "infeasible",
        ms.kTimeLimit: "time_limit_reached",
        ms.kObjectiveBound: "optimal",   # MIP gap tolerance reached
        ms.kObjectiveTarget: "optimal",
        ms.kSolutionLimit: "time_limit_reached",
        ms.kIterationLimit: "time_limit_reached",
    }
    result = mapping.get(model_status, "solver_error")
    if result == "solver_error":
        logger.warning("Unmapped HiGHS status: %s", model_status)
    return result


# ---------------------------------------------------------------------------
# Internal: sensitivity analysis extraction
# ---------------------------------------------------------------------------


def _extract_sensitivity(
    h: "highspy.Highs",
    inp: SolverInput,
    sol: "highspy.HighsSolution",
) -> dict:
    """Extract LP sensitivity data from a solved HiGHS instance.

    Called only for LP problems at optimal status.

    Args:
        h: Solved HiGHS instance.
        inp: Original problem definition.
        sol: Solution object from ``h.getSolution()``.

    Returns:
        Dict of sensitivity fields ready to be merged into SolverResult.
    """
    sensitivity: dict = {}

    # Shadow prices (row dual values)
    sensitivity["shadow_prices"] = {
        inp.constraint_names[i]: float(sol.row_dual[i])
        for i in range(inp.num_constraints)
    }

    # Reduced costs (column dual values)
    if hasattr(sol, "col_dual") and len(sol.col_dual) == inp.num_variables:
        sensitivity["reduced_costs"] = {
            inp.variable_names[j]: float(sol.col_dual[j])
            for j in range(inp.num_variables)
        }

    # Constraint slack and binding constraints
    if hasattr(sol, "row_value") and len(sol.row_value) == inp.num_constraints:
        slack: dict[str, float] = {}
        binding: list[str] = []
        for i in range(inp.num_constraints):
            activity = float(sol.row_value[i])
            rhs = float(inp.constraint_rhs[i])
            sense = inp.constraint_senses[i]
            if sense == "<=":
                s = rhs - activity
            elif sense == ">=":
                s = activity - rhs
            else:  # "=="
                s = 0.0
            slack[inp.constraint_names[i]] = s
            if abs(s) < 1e-8:
                binding.append(inp.constraint_names[i])
        sensitivity["constraint_slack"] = slack
        sensitivity["binding_constraints"] = binding

    # Ranging (objective and RHS allowable ranges)
    try:
        ranging_status, ranging = h.getRanging()
        if ranging_status == highspy.HighsStatus.kOk and ranging.valid:
            obj_ranges = _extract_obj_ranges(ranging, inp)
            rhs_ranges = _extract_rhs_ranges(ranging, inp)
            if obj_ranges:
                sensitivity["objective_ranges"] = obj_ranges
            if rhs_ranges:
                sensitivity["rhs_ranges"] = rhs_ranges
    except Exception as exc:
        logger.debug("Ranging extraction skipped: %s", exc)

    return sensitivity


def _safe_range_float(v: float) -> float | None:
    """Convert a ranging bound to None if it is infinite (not JSON-serializable).

    HiGHS returns ``kHighsInf`` (≈ 1e30) or ``float('inf')`` for unbounded
    ranging values.  We normalise both to ``None`` so the result round-trips
    cleanly through JSON.

    Args:
        v: Raw float from HiGHS ranging.

    Returns:
        The original float, or ``None`` if effectively infinite.
    """
    if abs(v) >= 1e29 or v != v:  # second check catches NaN
        return None
    return v


def _extract_obj_ranges(
    ranging: "highspy.HighsRanging",
    inp: SolverInput,
) -> dict[str, tuple[float | None, float | None]]:
    """Extract objective coefficient allowable ranges.

    ``col_cost_dn.value_[j]`` and ``col_cost_up.value_[j]`` hold the
    *absolute* lower and upper bounds for each objective coefficient (first
    ``n_vars`` entries; the remainder correspond to slack variables).

    Args:
        ranging: HiGHS ranging result (valid and OK).
        inp: Original problem definition.

    Returns:
        Dict mapping variable name to ``(lower_bound, upper_bound)`` on the
        objective coefficient.
    """
    obj_ranges: dict[str, tuple[float | None, float | None]] = {}
    try:
        dn = list(ranging.col_cost_dn.value_)
        up = list(ranging.col_cost_up.value_)
        for j, name in enumerate(inp.variable_names):
            if j < len(dn) and j < len(up):
                lo = _safe_range_float(float(dn[j]))
                hi = _safe_range_float(float(up[j]))
                obj_ranges[name] = (lo, hi)
    except Exception as exc:
        logger.debug("Objective ranging failed: %s", exc)
    return obj_ranges


def _extract_rhs_ranges(
    ranging: "highspy.HighsRanging",
    inp: SolverInput,
) -> dict[str, tuple[float | None, float | None]]:
    """Extract constraint RHS allowable ranges.

    ``row_bound_dn.value_[i]`` and ``row_bound_up.value_[i]`` hold the
    *absolute* lower and upper bounds for each constraint's RHS while the
    current optimal basis remains optimal.

    Args:
        ranging: HiGHS ranging result (valid and OK).
        inp: Original problem definition.

    Returns:
        Dict mapping constraint name to ``(lower_bound, upper_bound)`` on
        the RHS value.  A ``None`` bound means unbounded in that direction.
    """
    rhs_ranges: dict[str, tuple[float | None, float | None]] = {}
    try:
        dn = list(ranging.row_bound_dn.value_)
        up = list(ranging.row_bound_up.value_)
        for i, name in enumerate(inp.constraint_names):
            if i < len(dn) and i < len(up):
                lo = _safe_range_float(float(dn[i]))
                hi = _safe_range_float(float(up[i]))
                rhs_ranges[name] = (lo, hi)
    except Exception as exc:
        logger.debug("RHS ranging failed: %s", exc)
    return rhs_ranges


# ---------------------------------------------------------------------------
# Internal: IIS computation
# ---------------------------------------------------------------------------


def _make_sub_problem(inp: SolverInput, constraint_indices: list[int]) -> SolverInput:
    """Build a SolverInput containing only the specified constraint subset.

    Used by the IIS deletion filter.

    Args:
        inp: Original (infeasible) problem.
        constraint_indices: Indices of constraints to retain.

    Returns:
        New :class:`SolverInput` with the subset of constraints.
    """
    m = len(constraint_indices)
    return SolverInput(
        num_variables=inp.num_variables,
        num_constraints=m,
        variable_names=inp.variable_names,
        variable_lower_bounds=inp.variable_lower_bounds,
        variable_upper_bounds=inp.variable_upper_bounds,
        variable_types=inp.variable_types,
        constraint_names=[inp.constraint_names[i] for i in constraint_indices],
        constraint_matrix=[inp.constraint_matrix[i] for i in constraint_indices],
        constraint_senses=[inp.constraint_senses[i] for i in constraint_indices],
        constraint_rhs=[inp.constraint_rhs[i] for i in constraint_indices],
        objective_coefficients=inp.objective_coefficients,
        objective_sense=inp.objective_sense,
        # Use a generous limit for IIS sub-solves
        time_limit_seconds=30.0,
        mip_gap_tolerance=inp.mip_gap_tolerance,
    )


def _compute_iis_deletion(inp: SolverInput) -> IISResult:
    """Find the IIS via the iterative deletion filter algorithm.

    Algorithm (O(m) feasibility solves):

    1. Start with all constraint indices as candidates.
    2. For each candidate at position ``i``:
       a. Temporarily remove it and re-solve.
       b. If still infeasible → constraint is redundant; drop permanently.
          Do NOT advance ``i`` (the next candidate shifted to position ``i``).
       c. If feasible → constraint is necessary; advance ``i``.
    3. The remaining indices form the IIS.

    Also checks for trivially infeasible variable bounds (lb > ub).

    Args:
        inp: The infeasible problem.

    Returns:
        :class:`IISResult` with the minimal conflicting set.
    """
    # --- Trivial bound conflicts ------------------------------------------
    bound_conflicts: list[str] = []
    for j, name in enumerate(inp.variable_names):
        lb = inp.variable_lower_bounds[j]
        ub = inp.variable_upper_bounds[j]
        if lb is not None and ub is not None and lb > ub:
            desc = f"{name} (lb={lb} > ub={ub})"
            bound_conflicts.append(desc)
            logger.debug("Variable bound conflict: %s", desc)

    # --- Iterative deletion -----------------------------------------------
    active: list[int] = list(range(inp.num_constraints))
    i = 0
    while i < len(active):
        test_indices = active[:i] + active[i + 1 :]

        if not test_indices:
            # Cannot remove the sole remaining constraint
            i += 1
            continue

        sub = _make_sub_problem(inp, test_indices)
        result = _solve_highs(sub, extract_iis=False)

        if result.status == "infeasible":
            # active[i] is redundant for infeasibility — drop permanently
            active = test_indices
            # Do NOT increment i; the element at i is now the next candidate
        else:
            # active[i] is necessary — keep it and advance
            i += 1

    iis_names = [inp.constraint_names[idx] for idx in active]
    explanation = _build_iis_explanation(iis_names, bound_conflicts)
    logger.debug("IIS found: %s", iis_names)

    return IISResult(
        conflicting_constraints=iis_names,
        conflicting_variable_bounds=bound_conflicts,
        explanation=explanation,
    )


def _build_iis_explanation(
    constraint_names: list[str],
    bound_conflicts: list[str],
) -> str:
    """Compose a human-readable IIS explanation string.

    Args:
        constraint_names: Names of constraints in the IIS.
        bound_conflicts: Variable bound conflict descriptions.

    Returns:
        Plain-English explanation suitable for the LLM to relay to the user.
    """
    parts: list[str] = []

    if constraint_names:
        names_str = ", ".join(f"'{n}'" for n in constraint_names)
        n = len(constraint_names)
        parts.append(
            f"The model is infeasible. "
            f"The following {n} constraint{'s' if n != 1 else ''} form an "
            f"Irreducible Infeasible Subsystem (IIS): {names_str}. "
            f"No feasible solution can simultaneously satisfy all of them."
        )

    if bound_conflicts:
        conflicts_str = "; ".join(bound_conflicts)
        parts.append(f"Variable bound conflicts: {conflicts_str}.")

    if not parts:
        parts.append(
            "The model is infeasible but the specific conflicting constraint "
            "set could not be isolated. Check variable bounds and constraint "
            "RHS values."
        )

    return " ".join(parts)
