"""SAGE Core — Model Builder.

Translates domain-specific models (LPModel, MIPModel, PortfolioModel,
SchedulingModel) into the solver-agnostic SolverInput representation.

No filesystem access. No print() calls. No global state. Every function
takes Python objects in and returns Python objects out.

Public API
----------
build_from_lp(model: LPModel) -> SolverInput
build_from_mip(model: MIPModel) -> SolverInput
build_from_portfolio(model: PortfolioModel) -> SolverInput
build_from_scheduling(model: SchedulingModel) -> SolverInput
validate_model(model: LPModel | MIPModel) -> list[ValidationIssue]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from sage_solver_core.models import (
    LPModel,
    MIPModel,
    ModelBuildError,
    PortfolioModel,
    SchedulingModel,
    SolverInput,
)

logger = logging.getLogger("sage.builder")

# Sentinel for +∞ / -∞ in SolverInput's list[float] fields.
# HiGHS treats values >= kHighsInf (≈ 1e30) as infinite.
_INF: float = 1e30


# ---------------------------------------------------------------------------
# Validation issue dataclass
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation warning or error detected in a model.

    Attributes:
        severity: ``"warning"`` for non-fatal issues; ``"error"`` for blocking
            structural problems that will cause the build or solve to fail.
        message: Human-readable description.
        details: Optional structured context dict.
    """

    severity: str  # "warning" | "error"
    message: str
    details: dict = dataclass_field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.message}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_constraint_rows(
    constraints: list,
    var_idx: dict[str, int],
    n: int,
    context_label: str,
) -> tuple[list[list[float]], list[str], list[float]]:
    """Build dense constraint matrix rows from a list of LinearConstraint objects.

    Args:
        constraints: List of ``LinearConstraint`` instances.
        var_idx: Mapping of variable name → column index.
        n: Number of variables (width of each row).
        context_label: Label for error messages (e.g., model name).

    Returns:
        Tuple of (matrix, senses, rhs_values).

    Raises:
        ModelBuildError: If a constraint references a variable not in ``var_idx``.
    """
    matrix: list[list[float]] = []
    senses: list[str] = []
    rhs: list[float] = []

    for c in constraints:
        row = [0.0] * n
        for vname, coeff in c.coefficients.items():
            if vname not in var_idx:
                raise ModelBuildError(
                    f"Constraint '{c.name}' references undefined variable '{vname}'",
                    details={
                        "model": context_label,
                        "constraint": c.name,
                        "undefined_variable": vname,
                        "defined_variables": list(var_idx.keys()),
                    },
                    suggestions=[
                        f"Add variable '{vname}' to the model's variable list",
                        f"Remove '{vname}' from constraint '{c.name}'",
                    ],
                )
            row[var_idx[vname]] = float(coeff)
        matrix.append(row)
        senses.append(c.sense)
        rhs.append(float(c.rhs))

    return matrix, senses, rhs


# ---------------------------------------------------------------------------
# Public API — LP and MIP builders
# ---------------------------------------------------------------------------


def build_from_lp(model: LPModel) -> SolverInput:
    """Translate an LPModel into solver-native SolverInput.

    Performs a direct one-to-one mapping:
    - Each ``LPVariable`` becomes a continuous decision variable.
    - Each ``LinearConstraint`` becomes a dense row in the constraint matrix.
    - ``LinearObjective`` coefficients are mapped to variable column indices.

    Variables that appear in the objective but not in any constraint receive
    a zero coefficient in that constraint's row (not an error — valid LP).

    Args:
        model: Validated LP problem definition.

    Returns:
        :class:`SolverInput` ready for :func:`sage_core.solver.solve`.

    Raises:
        ModelBuildError: If the objective or any constraint references a
            variable name not defined in ``model.variables``.
    """
    var_names = [v.name for v in model.variables]
    var_idx: dict[str, int] = {v.name: i for i, v in enumerate(model.variables)}
    n = len(var_names)

    # Variable bounds (None → sentinel ±1e30)
    var_lb = [v.lower_bound if v.lower_bound is not None else -_INF for v in model.variables]
    var_ub = [v.upper_bound if v.upper_bound is not None else _INF for v in model.variables]

    # Objective coefficients
    obj_coeffs = [0.0] * n
    for vname, coeff in model.objective.coefficients.items():
        if vname not in var_idx:
            raise ModelBuildError(
                f"Objective references undefined variable '{vname}'",
                details={
                    "model": model.name,
                    "undefined_variable": vname,
                    "defined_variables": var_names,
                },
                suggestions=[
                    f"Add variable '{vname}' to the model's variable list",
                    "Remove the term from the objective",
                ],
            )
        obj_coeffs[var_idx[vname]] = float(coeff)

    constraint_names = [c.name for c in model.constraints]
    matrix, senses, rhs = _build_constraint_rows(
        model.constraints, var_idx, n, model.name
    )

    logger.debug(
        "build_from_lp: '%s' — %d vars, %d constraints",
        model.name,
        n,
        len(model.constraints),
    )
    return SolverInput(
        num_variables=n,
        num_constraints=len(model.constraints),
        variable_names=var_names,
        variable_lower_bounds=var_lb,
        variable_upper_bounds=var_ub,
        variable_types=["continuous"] * n,
        constraint_names=constraint_names,
        constraint_matrix=matrix,
        constraint_senses=senses,
        constraint_rhs=rhs,
        objective_coefficients=obj_coeffs,
        objective_sense=model.objective.sense,
    )


def build_from_mip(model: MIPModel) -> SolverInput:
    """Translate a MIPModel into solver-native SolverInput.

    Same logic as :func:`build_from_lp` with two additions:
    - Variable types (``continuous`` / ``integer`` / ``binary``) are preserved.
    - Binary variables are always bounded ``[0.0, 1.0]`` regardless of the
      values stored in ``lower_bound`` / ``upper_bound``.
    - Solver parameters (``time_limit_seconds``, ``mip_gap_tolerance``) are
      forwarded from the model.

    Args:
        model: Validated MIP problem definition.

    Returns:
        :class:`SolverInput` ready for :func:`sage_core.solver.solve`.

    Raises:
        ModelBuildError: If the objective or any constraint references a
            variable name not defined in ``model.variables``.
    """
    var_names = [v.name for v in model.variables]
    var_idx: dict[str, int] = {v.name: i for i, v in enumerate(model.variables)}
    n = len(var_names)

    var_lb: list[float] = []
    var_ub: list[float] = []
    var_types: list[str] = []

    for v in model.variables:
        if v.var_type == "binary":
            var_lb.append(0.0)
            var_ub.append(1.0)
        else:
            var_lb.append(v.lower_bound if v.lower_bound is not None else -_INF)
            var_ub.append(v.upper_bound if v.upper_bound is not None else _INF)
        var_types.append(v.var_type)

    # Objective coefficients
    obj_coeffs = [0.0] * n
    for vname, coeff in model.objective.coefficients.items():
        if vname not in var_idx:
            raise ModelBuildError(
                f"Objective references undefined variable '{vname}'",
                details={
                    "model": model.name,
                    "undefined_variable": vname,
                    "defined_variables": var_names,
                },
                suggestions=[f"Add variable '{vname}' to the model's variable list"],
            )
        obj_coeffs[var_idx[vname]] = float(coeff)

    constraint_names = [c.name for c in model.constraints]
    matrix, senses, rhs = _build_constraint_rows(
        model.constraints, var_idx, n, model.name
    )

    logger.debug(
        "build_from_mip: '%s' — %d vars (%d integer/binary), %d constraints",
        model.name,
        n,
        sum(1 for t in var_types if t in ("integer", "binary")),
        len(model.constraints),
    )
    return SolverInput(
        num_variables=n,
        num_constraints=len(model.constraints),
        variable_names=var_names,
        variable_lower_bounds=var_lb,
        variable_upper_bounds=var_ub,
        variable_types=var_types,
        constraint_names=constraint_names,
        constraint_matrix=matrix,
        constraint_senses=senses,
        constraint_rhs=rhs,
        objective_coefficients=obj_coeffs,
        objective_sense=model.objective.sense,
        time_limit_seconds=model.time_limit_seconds,
        mip_gap_tolerance=model.mip_gap_tolerance,
    )


# ---------------------------------------------------------------------------
# Public API — Portfolio builder (Markowitz QP)
# ---------------------------------------------------------------------------


def build_from_portfolio(model: PortfolioModel) -> SolverInput:
    """Translate a PortfolioModel into a quadratic program (Markowitz QP).

    **Formulation:**

    HiGHS minimises ``c^T w + 0.5 * w^T Q w``.  We encode the Markowitz
    mean-variance objective as:

        minimize  -r^T w + λ · w^T Cov w

    by setting::

        c_i = -r_i                              (negate expected returns)
        Q_ij = 2 · risk_aversion · Cov[i][j]   (factor of 2 absorbs HiGHS 0.5)

    This is equivalent to maximizing ``r^T w - λ · w^T Cov w``.  The reported
    ``objective_value`` will be the negative of the Markowitz utility; the
    optimal weights are correct regardless of sign convention.

    **Variable bounds:**
    - Default: ``w_i ∈ [0, 1]``
    - ``PortfolioConstraints.min_allocation_per_asset`` → variable lower bound
    - ``PortfolioConstraints.max_allocation_per_asset`` → variable upper bound
    - ``PortfolioConstraints.forbidden_assets`` → ``w_i = 0`` (lb = ub = 0)

    **Constraints generated:**
    1. Total allocation: ``sum(w_i) == min_total_allocation`` if min == max,
       else separate ``>=`` / ``<=`` constraints.
    2. Sector caps: ``sum(w_i for i in sector s) <= max_sector_allocation[s]``
       for each sector with a defined cap.

    Args:
        model: Validated portfolio optimization problem.

    Returns:
        :class:`SolverInput` with ``objective_quadratic`` set, ready for
        :func:`sage_core.solver.solve`.

    Raises:
        ModelBuildError: If the covariance matrix is not symmetric (within 1e-8).
    """
    n = len(model.assets)
    asset_names = [a.name for a in model.assets]
    asset_idx: dict[str, int] = {a.name: i for i, a in enumerate(model.assets)}
    pc = model.constraints
    cov = model.covariance_matrix

    # --- Symmetry check -------------------------------------------------------
    tol = 1e-8
    for i in range(n):
        for j in range(i + 1, n):
            if abs(cov[i][j] - cov[j][i]) > tol:
                raise ModelBuildError(
                    f"Covariance matrix is not symmetric: "
                    f"cov[{i}][{j}]={cov[i][j]:.6g} ≠ cov[{j}][{i}]={cov[j][i]:.6g}",
                    details={
                        "row": i,
                        "col": j,
                        "cov_ij": cov[i][j],
                        "cov_ji": cov[j][i],
                        "difference": abs(cov[i][j] - cov[j][i]),
                    },
                    suggestions=[
                        "Ensure covariance_matrix[i][j] == covariance_matrix[j][i] for all i, j",
                        "Use (cov[i][j] + cov[j][i]) / 2 to symmetrise your matrix",
                    ],
                )

    # --- Variable bounds (per-asset and forbidden) ----------------------------
    forbidden_set = set(pc.forbidden_assets or [])
    var_lb: list[float] = []
    var_ub: list[float] = []

    for asset in model.assets:
        if asset.name in forbidden_set:
            var_lb.append(0.0)
            var_ub.append(0.0)
        else:
            lb = float(pc.min_allocation_per_asset) if pc.min_allocation_per_asset is not None else 0.0
            ub = float(pc.max_allocation_per_asset) if pc.max_allocation_per_asset is not None else 1.0
            var_lb.append(lb)
            var_ub.append(ub)

    # --- Objective: minimize -r^T w + λ · w^T Cov w --------------------------
    obj_coeffs = [-a.expected_return for a in model.assets]

    lam = model.risk_aversion
    obj_quadratic = [
        [2.0 * lam * cov[i][j] for j in range(n)]
        for i in range(n)
    ]

    # --- Constraints ----------------------------------------------------------
    constraint_names: list[str] = []
    constraint_matrix: list[list[float]] = []
    constraint_senses: list[str] = []
    constraint_rhs: list[float] = []

    def _add(name: str, row: list[float], sense: str, rhs: float) -> None:
        constraint_names.append(name)
        constraint_matrix.append(row)
        constraint_senses.append(sense)
        constraint_rhs.append(rhs)

    all_ones = [1.0] * n

    # Total allocation
    if abs(pc.min_total_allocation - pc.max_total_allocation) < 1e-10:
        _add("total_allocation", all_ones, "==", pc.min_total_allocation)
    else:
        _add("total_allocation_min", all_ones, ">=", pc.min_total_allocation)
        _add("total_allocation_max", all_ones, "<=", pc.max_total_allocation)

    # Sector caps
    if pc.max_sector_allocation:
        # Group non-forbidden assets by sector
        sector_indices: dict[str, list[int]] = {}
        for asset in model.assets:
            if asset.sector is not None and asset.name not in forbidden_set:
                sector_indices.setdefault(asset.sector, []).append(asset_idx[asset.name])

        for sector, max_alloc in pc.max_sector_allocation.items():
            idxs = sector_indices.get(sector, [])
            if idxs:  # skip sectors not represented in the asset list
                row = [0.0] * n
                for idx in idxs:
                    row[idx] = 1.0
                _add(f"sector_{sector}_max", row, "<=", float(max_alloc))

    m = len(constraint_names)
    logger.debug(
        "build_from_portfolio: %d assets, λ=%.3g, %d constraints",
        n,
        lam,
        m,
    )
    return SolverInput(
        num_variables=n,
        num_constraints=m,
        variable_names=asset_names,
        variable_lower_bounds=var_lb,
        variable_upper_bounds=var_ub,
        variable_types=["continuous"] * n,
        constraint_names=constraint_names,
        constraint_matrix=constraint_matrix,
        constraint_senses=constraint_senses,
        constraint_rhs=constraint_rhs,
        objective_coefficients=obj_coeffs,
        objective_sense="minimize",  # minimize negative Markowitz utility
        objective_quadratic=obj_quadratic,
    )


# ---------------------------------------------------------------------------
# Public API — Scheduling builder (binary MIP)
# ---------------------------------------------------------------------------


def build_from_scheduling(model: SchedulingModel) -> SolverInput:
    """Translate a SchedulingModel into a binary MIP.

    **Decision variables:**

    ``x[w, s, d] ∈ {0, 1}`` — 1 if worker *w* is assigned to shift *s* on
    day *d*, else 0.

    Variable naming: ``x_{worker_name}_{shift_name}_d{day}`` (zero-indexed).
    Linear index: ``w * num_shifts * num_days + s * num_days + d``.

    **Constraints generated:**

    1. **Coverage** (``num_shifts × planning_horizon_days`` constraints):
       ``∑_w x[w, s, d] ≥ shift.required_workers``  for each (shift, day).

    2. **Max hours** (``num_workers`` constraints):
       ``∑_{s,d} shift.duration_hours · x[w, s, d] ≤ worker.max_hours``
       for each worker.

    3. **Consecutive days** (``num_workers × max(0, D − max_consecutive_days)``
       constraints, only when ``model.max_consecutive_days`` is set):
       ``∑_{d'=d}^{d+max_consecutive} ∑_s x[w, s, d'] ≤ max_consecutive_days``
       for each rolling window of length ``max_consecutive_days + 1``.

    **Variable upper-bound restrictions (encoded as ``ub = 0``):**

    - **Unavailability**: if shift *s* is in ``worker.unavailable_shifts``,
      ``x[w, s, d] = 0`` for all days *d*.
    - **Skill mismatch**: if shift *s* requires skills that worker *w* does
      not possess, ``x[w, s, d] = 0`` for all days *d*.

    .. note::
        ``model.min_rest_hours`` is noted but not encoded as an explicit MIP
        constraint in this builder, as doing so requires explicit shift start
        times.  The consecutive-days limit approximates rest requirements.

    **Objective:** minimize total assignments ``∑_{w,s,d} x[w, s, d]``.

    Args:
        model: Validated scheduling problem definition.

    Returns:
        :class:`SolverInput` ready for :func:`sage_core.solver.solve`.
    """
    workers = model.workers
    shifts = model.shifts
    D = model.planning_horizon_days
    W = len(workers)
    S = len(shifts)
    n = W * S * D

    def _vidx(w: int, s: int, d: int) -> int:
        return w * S * D + s * D + d

    # --- Variable names -------------------------------------------------------
    var_names: list[str] = []
    for w, worker in enumerate(workers):
        for s, shift in enumerate(shifts):
            for d in range(D):
                var_names.append(f"x_{worker.name}_{shift.name}_d{d}")

    # --- Variable bounds (encode restrictions as ub = 0) ----------------------
    var_lb = [0.0] * n
    var_ub = [1.0] * n

    worker_skills: list[set[str]] = [set(w.skills or []) for w in workers]
    shift_req_skills: list[set[str]] = [set(s.required_skills or []) for s in shifts]
    worker_unavail: list[set[str]] = [set(w.unavailable_shifts or []) for w in workers]

    for w in range(W):
        for s in range(S):
            blocked = False
            # Skill check: worker must have ALL skills required by the shift
            req = shift_req_skills[s]
            if req and not req.issubset(worker_skills[w]):
                blocked = True
            # Unavailability check
            if shifts[s].name in worker_unavail[w]:
                blocked = True
            if blocked:
                for d in range(D):
                    var_ub[_vidx(w, s, d)] = 0.0

    # --- Constraints ----------------------------------------------------------
    constraint_names: list[str] = []
    constraint_matrix: list[list[float]] = []
    constraint_senses: list[str] = []
    constraint_rhs: list[float] = []

    def _add(name: str, row: list[float], sense: str, rhs: float) -> None:
        constraint_names.append(name)
        constraint_matrix.append(row)
        constraint_senses.append(sense)
        constraint_rhs.append(rhs)

    # 1. Coverage constraints
    for s, shift in enumerate(shifts):
        for d in range(D):
            row = [0.0] * n
            for w in range(W):
                row[_vidx(w, s, d)] = 1.0
            _add(f"coverage_{shift.name}_d{d}", row, ">=", float(shift.required_workers))

    # 2. Max hours constraints
    for w, worker in enumerate(workers):
        row = [0.0] * n
        for s, shift in enumerate(shifts):
            for d in range(D):
                row[_vidx(w, s, d)] = shift.duration_hours
        _add(f"max_hours_{worker.name}", row, "<=", float(worker.max_hours))

    # 3. Consecutive days constraints (rolling window)
    if model.max_consecutive_days is not None:
        mc = model.max_consecutive_days
        # Windows of length mc+1 days: starts at d_start, ends at d_start+mc
        # Only meaningful when D > mc (i.e., range(D - mc) is non-empty)
        for w, worker in enumerate(workers):
            for d_start in range(max(0, D - mc)):
                d_end = d_start + mc  # inclusive; guaranteed < D since d_start < D-mc
                row = [0.0] * n
                for s in range(S):
                    for d in range(d_start, d_end + 1):
                        row[_vidx(w, s, d)] = 1.0
                _add(f"consec_{worker.name}_from_d{d_start}", row, "<=", float(mc * S))

    # --- Objective: minimize total assignments --------------------------------
    obj_coeffs = [1.0] * n

    m = len(constraint_names)
    logger.debug(
        "build_from_scheduling: %d workers × %d shifts × %d days = %d vars, %d constraints",
        W,
        S,
        D,
        n,
        m,
    )
    return SolverInput(
        num_variables=n,
        num_constraints=m,
        variable_names=var_names,
        variable_lower_bounds=var_lb,
        variable_upper_bounds=var_ub,
        variable_types=["binary"] * n,
        constraint_names=constraint_names,
        constraint_matrix=constraint_matrix,
        constraint_senses=constraint_senses,
        constraint_rhs=constraint_rhs,
        objective_coefficients=obj_coeffs,
        objective_sense="minimize",
        time_limit_seconds=60.0,
        mip_gap_tolerance=0.0001,
    )


# ---------------------------------------------------------------------------
# Public API — Model validation
# ---------------------------------------------------------------------------


def validate_model(model: LPModel | MIPModel) -> list[ValidationIssue]:
    """Pre-solver validation for LP and MIP models.

    This is a heuristic check designed to catch common modelling mistakes
    before sending the problem to the solver.  It does **not** replace Pydantic
    schema validation (which runs on model construction) and does not guarantee
    the problem is solvable.

    Checks performed:

    1. **Empty constraint set** — model may be unbounded.
    2. **Unused variables** — variables that appear in neither any constraint
       nor the objective.
    3. **Potentially unbounded objective** — in a maximisation problem, a
       variable with a positive objective coefficient, no finite upper bound,
       and no ``<=`` / ``==`` constraint that limits it directly.
    4. **Coefficient magnitude ratio** — if ``max(|coeff|) / min(|coeff|) > 1e6``,
       warn about potential numerical instability.
    5. **Duplicate names** — belt-and-suspenders check (Pydantic already
       enforces this, but explicit errors are reported here too).

    Args:
        model: An ``LPModel`` or ``MIPModel`` instance.

    Returns:
        List of :class:`ValidationIssue` objects.  An empty list means no
        issues were found.  Issues are warnings unless structurally blocking.
    """
    issues: list[ValidationIssue] = []
    var_names = [v.name for v in model.variables]

    # 1. Empty constraint set
    if not model.constraints:
        issues.append(
            ValidationIssue(
                severity="warning",
                message="Model has no constraints. The problem is likely unbounded.",
                details={"num_variables": len(model.variables)},
            )
        )

    # 2. Variables not used in any constraint or objective
    constrained_vars: set[str] = set()
    for c in model.constraints:
        constrained_vars.update(c.coefficients.keys())
    objective_vars: set[str] = set(model.objective.coefficients.keys())

    for vname in var_names:
        if vname not in constrained_vars and vname not in objective_vars:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=(
                        f"Variable '{vname}' does not appear in any constraint "
                        f"or the objective. It is effectively a free variable."
                    ),
                    details={"variable": vname},
                )
            )

    # 3. Potentially unbounded objective (maximisation only)
    if model.objective.sense == "maximize":
        for v in model.variables:
            coeff = model.objective.coefficients.get(v.name, 0.0)
            if coeff <= 0:
                continue
            # Check for a finite variable upper bound
            var_ub = v.upper_bound  # None means +∞
            if var_ub is not None:
                continue
            # Check for any constraint that provides a finite upper bound
            has_upper_constraint = any(
                v.name in c.coefficients
                and c.coefficients[v.name] > 0
                and c.sense in ("<=", "==")
                for c in model.constraints
            )
            if not has_upper_constraint:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=(
                            f"Variable '{v.name}' has a positive objective coefficient "
                            f"({coeff:g}) in a maximisation model, no finite upper bound, "
                            f"and no ≤ or = constraint that directly limits it. "
                            f"The model may be unbounded."
                        ),
                        details={
                            "variable": v.name,
                            "objective_coefficient": coeff,
                        },
                    )
                )

    # 4. Coefficient magnitude ratio
    all_coeffs: list[float] = []
    for c in model.constraints:
        all_coeffs.extend(abs(v) for v in c.coefficients.values() if v != 0.0)
    all_coeffs.extend(
        abs(v) for v in model.objective.coefficients.values() if v != 0.0
    )
    if len(all_coeffs) >= 2:
        max_c = max(all_coeffs)
        min_c = min(all_coeffs)
        if min_c > 0 and max_c / min_c > 1e6:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=(
                        f"Coefficient magnitude range is {max_c / min_c:.2e}× "
                        f"(min={min_c:.4g}, max={max_c:.4g}). "
                        f"This may cause numerical instability. Consider scaling."
                    ),
                    details={
                        "max_coefficient": max_c,
                        "min_coefficient": min_c,
                        "ratio": max_c / min_c,
                    },
                )
            )

    # 5. Duplicate names (belt-and-suspenders; Pydantic normally catches these)
    seen: set[str] = set()
    for vname in var_names:
        if vname in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Duplicate variable name: '{vname}'",
                    details={"variable": vname},
                )
            )
        seen.add(vname)

    seen_c: set[str] = set()
    for c in model.constraints:
        if c.name in seen_c:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Duplicate constraint name: '{c.name}'",
                    details={"constraint": c.name},
                )
            )
        seen_c.add(c.name)

    return issues
