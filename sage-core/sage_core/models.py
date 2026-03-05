"""SAGE Core — Pydantic schemas for all problem types and solver I/O.

This module defines every data structure that crosses a boundary inside SAGE:
  - Problem type schemas (LP, MIP, Portfolio, Scheduling)
  - Solver intermediate representation (SolverInput)
  - Solver results (SolverResult, IISResult)
  - Relaxation suggestions (RelaxationSuggestion)
  - Structured error types (SAGEError hierarchy + SAGEErrorResponse)

All models use Pydantic v2.  No business logic lives here — only data
validation and serialization.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("sage.models")

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class SAGEError(Exception):
    """Base exception for all SAGE errors.

    Args:
        message: Human-readable description of the error.
        details: Structured details dictionary for the LLM layer to interpret.
        suggestions: Ordered list of actionable remediation steps.
    """

    def __init__(
        self,
        message: str,
        details: dict | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict = details or {}
        self.suggestions: list[str] = suggestions or []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"


class DataValidationError(SAGEError):
    """Input data does not match the expected schema.

    Typical causes: missing columns, wrong data types, out-of-range values.
    Includes structured context: file, sheet, row, column, expected/actual values.
    """


class ModelBuildError(SAGEError):
    """Cannot construct a valid mathematical model from the provided input.

    Typical causes: no variables, contradictory constraints, unsupported
    problem structure.
    """


class SolverError(SAGEError):
    """Solver failed unexpectedly.

    Note: infeasibility and unboundedness are *valid* solver outcomes, not
    SolverErrors.  This exception is reserved for unexpected internal solver
    failures (bad return codes, memory errors, etc.).
    """


class FileIOError(SAGEError):
    """Cannot read or write a file.

    Includes: file path, operation attempted, underlying OS error.
    """


# ---------------------------------------------------------------------------
# Structured error response (returned through MCP layer)
# ---------------------------------------------------------------------------


class SAGEErrorResponse(BaseModel):
    """Structured error payload returned by MCP tools on failure.

    Attributes:
        error_type: Name of the SAGEError subclass.
        message: Human-readable error description.
        details: Structured context for the LLM to interpret and relay.
        suggestions: Ordered list of remediation steps the user can take.
    """

    error_type: str
    message: str
    details: dict = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)

    @classmethod
    def from_exception(cls, exc: SAGEError) -> "SAGEErrorResponse":
        """Build a response from a SAGEError instance.

        Args:
            exc: The caught SAGEError.

        Returns:
            A SAGEErrorResponse ready for MCP serialization.
        """
        return cls(
            error_type=type(exc).__name__,
            message=exc.message,
            details=exc.details,
            suggestions=exc.suggestions,
        )


# ---------------------------------------------------------------------------
# LP schemas
# ---------------------------------------------------------------------------


class LPVariable(BaseModel):
    """A decision variable in a linear program.

    Attributes:
        name: Unique variable identifier.
        lower_bound: Minimum value (default 0; use None for -∞).
        upper_bound: Maximum value (default None for +∞).
    """

    name: str = Field(..., min_length=1, description="Unique variable name")
    lower_bound: float | None = Field(default=0.0, description="Lower bound (None = -inf)")
    upper_bound: float | None = Field(default=None, description="Upper bound (None = +inf)")

    @model_validator(mode="after")
    def bounds_are_consistent(self) -> "LPVariable":
        """Ensure lower_bound <= upper_bound when both are finite."""
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError(
                f"Variable '{self.name}': lower_bound ({self.lower_bound}) "
                f"must be <= upper_bound ({self.upper_bound})"
            )
        return self


class LinearConstraint(BaseModel):
    """A single linear constraint: sum(coeff_i * x_i) sense rhs.

    Attributes:
        name: Unique constraint identifier.
        coefficients: Mapping of variable name → coefficient value.
        sense: Constraint direction.
        rhs: Right-hand side scalar.
    """

    name: str = Field(..., min_length=1, description="Unique constraint name")
    coefficients: dict[str, float] = Field(
        ..., description="variable_name → coefficient"
    )
    sense: Literal["<=", ">=", "=="] = Field(..., description="Constraint direction")
    rhs: float = Field(..., description="Right-hand side value")

    @field_validator("coefficients")
    @classmethod
    def coefficients_not_empty(cls, v: dict[str, float]) -> dict[str, float]:
        """Reject empty coefficient dictionaries."""
        if not v:
            raise ValueError("coefficients must not be empty")
        return v


class LinearObjective(BaseModel):
    """The objective function for an LP/MIP problem.

    Attributes:
        sense: Whether to minimize or maximize.
        coefficients: Mapping of variable name → objective coefficient.
    """

    sense: Literal["minimize", "maximize"] = Field(..., description="Optimization direction")
    coefficients: dict[str, float] = Field(
        ..., description="variable_name → objective coefficient"
    )

    @field_validator("coefficients")
    @classmethod
    def coefficients_not_empty(cls, v: dict[str, float]) -> dict[str, float]:
        """Reject empty coefficient dictionaries."""
        if not v:
            raise ValueError("coefficients must not be empty")
        return v


class LPModel(BaseModel):
    """A complete linear program.

    Attributes:
        name: Model identifier used in logging and output filenames.
        description: Optional human-readable description.
        variables: Decision variables.
        constraints: Linear constraints.
        objective: Objective function.
    """

    name: str = Field(..., min_length=1, description="Model name")
    description: str | None = Field(default=None, description="Optional model description")
    variables: list[LPVariable] = Field(..., min_length=1, description="Decision variables")
    constraints: list[LinearConstraint] = Field(
        default_factory=list, description="Linear constraints"
    )
    objective: LinearObjective = Field(..., description="Objective function")

    @field_validator("variables")
    @classmethod
    def variable_names_unique(cls, v: list[LPVariable]) -> list[LPVariable]:
        """Ensure all variable names are distinct."""
        names = [var.name for var in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate variable names: {list(set(duplicates))}")
        return v

    @field_validator("constraints")
    @classmethod
    def constraint_names_unique(cls, v: list[LinearConstraint]) -> list[LinearConstraint]:
        """Ensure all constraint names are distinct."""
        names = [c.name for c in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate constraint names: {list(set(duplicates))}")
        return v


# ---------------------------------------------------------------------------
# MIP schemas
# ---------------------------------------------------------------------------


class MIPVariable(BaseModel):
    """A decision variable in a mixed-integer program.

    Extends LP variables with an explicit type (continuous/integer/binary).
    Binary variables automatically clamp bounds to [0, 1].

    Attributes:
        name: Unique variable identifier.
        lower_bound: Minimum value (default 0; use None for -∞).
        upper_bound: Maximum value (default None for +∞; binary forces 1).
        var_type: Variable type.
    """

    name: str = Field(..., min_length=1, description="Unique variable name")
    lower_bound: float | None = Field(default=0.0, description="Lower bound (None = -inf)")
    upper_bound: float | None = Field(default=None, description="Upper bound (None = +inf)")
    var_type: Literal["continuous", "integer", "binary"] = Field(
        default="continuous", description="Variable integrality type"
    )

    @model_validator(mode="after")
    def binary_bounds_and_consistency(self) -> "MIPVariable":
        """Enforce binary bounds [0,1] and general bound consistency."""
        if self.var_type == "binary":
            if self.lower_bound not in (None, 0.0):
                raise ValueError(
                    f"Binary variable '{self.name}': lower_bound must be 0 or None, "
                    f"got {self.lower_bound}"
                )
            if self.upper_bound not in (None, 1.0):
                raise ValueError(
                    f"Binary variable '{self.name}': upper_bound must be 1 or None, "
                    f"got {self.upper_bound}"
                )
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError(
                f"Variable '{self.name}': lower_bound ({self.lower_bound}) "
                f"must be <= upper_bound ({self.upper_bound})"
            )
        return self


class MIPModel(BaseModel):
    """A complete mixed-integer linear program.

    Attributes:
        name: Model identifier.
        description: Optional human-readable description.
        variables: Decision variables (may be integer or binary).
        constraints: Linear constraints.
        objective: Objective function.
        time_limit_seconds: Solver wall-clock limit (None = unlimited).
        mip_gap_tolerance: Acceptable relative optimality gap (default 0.01%).
    """

    name: str = Field(..., min_length=1, description="Model name")
    description: str | None = Field(default=None, description="Optional model description")
    variables: list[MIPVariable] = Field(..., min_length=1, description="Decision variables")
    constraints: list[LinearConstraint] = Field(
        default_factory=list, description="Linear constraints"
    )
    objective: LinearObjective = Field(..., description="Objective function")
    time_limit_seconds: float | None = Field(
        default=60.0, gt=0, description="Solver time limit in seconds"
    )
    mip_gap_tolerance: float | None = Field(
        default=0.0001,
        ge=0.0,
        le=1.0,
        description="Relative MIP optimality gap tolerance",
    )

    @field_validator("variables")
    @classmethod
    def variable_names_unique(cls, v: list[MIPVariable]) -> list[MIPVariable]:
        """Ensure all variable names are distinct."""
        names = [var.name for var in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate variable names: {list(set(duplicates))}")
        return v

    @field_validator("constraints")
    @classmethod
    def constraint_names_unique(cls, v: list[LinearConstraint]) -> list[LinearConstraint]:
        """Ensure all constraint names are distinct."""
        names = [c.name for c in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate constraint names: {list(set(duplicates))}")
        return v


# ---------------------------------------------------------------------------
# Portfolio optimization schemas
# ---------------------------------------------------------------------------


class Asset(BaseModel):
    """A single financial asset in a portfolio optimization problem.

    Attributes:
        name: Unique asset identifier (e.g., ticker symbol).
        expected_return: Annualized expected return as a decimal (e.g., 0.08 = 8%).
        sector: Optional sector classification for sector-level constraints.
    """

    name: str = Field(..., min_length=1, description="Asset identifier (e.g., ticker)")
    expected_return: float = Field(..., description="Annualized expected return (decimal)")
    sector: str | None = Field(default=None, description="Sector classification")


class PortfolioConstraints(BaseModel):
    """Allocation constraints for a portfolio optimization problem.

    Attributes:
        max_allocation_per_asset: Maximum weight for any single asset (e.g., 0.20 = 20%).
        min_allocation_per_asset: Minimum weight for any included asset.
        max_sector_allocation: Per-sector maximum weights {sector_name: max_weight}.
        min_total_allocation: Minimum total weight (default 1.0 = fully invested).
        max_total_allocation: Maximum total weight (default 1.0 = no leverage).
        forbidden_assets: Asset names that must have zero allocation.
    """

    max_allocation_per_asset: float | None = Field(
        default=None, gt=0, le=1, description="Max weight per asset"
    )
    min_allocation_per_asset: float | None = Field(
        default=None, ge=0, lt=1, description="Min weight per asset"
    )
    max_sector_allocation: dict[str, float] | None = Field(
        default=None, description="sector_name → max allocation"
    )
    min_total_allocation: float = Field(
        default=1.0, ge=0, le=1, description="Minimum total portfolio weight"
    )
    max_total_allocation: float = Field(
        default=1.0, ge=0, description="Maximum total portfolio weight"
    )
    forbidden_assets: list[str] | None = Field(
        default=None, description="Asset names forced to zero allocation"
    )

    @model_validator(mode="after")
    def allocation_bounds_consistent(self) -> "PortfolioConstraints":
        """Ensure min <= max for total and per-asset allocations."""
        if self.min_total_allocation > self.max_total_allocation:
            raise ValueError(
                f"min_total_allocation ({self.min_total_allocation}) "
                f"must be <= max_total_allocation ({self.max_total_allocation})"
            )
        if (
            self.min_allocation_per_asset is not None
            and self.max_allocation_per_asset is not None
            and self.min_allocation_per_asset > self.max_allocation_per_asset
        ):
            raise ValueError(
                f"min_allocation_per_asset ({self.min_allocation_per_asset}) "
                f"must be <= max_allocation_per_asset ({self.max_allocation_per_asset})"
            )
        return self


class PortfolioModel(BaseModel):
    """A Markowitz mean-variance portfolio optimization problem.

    The builder translates this into a quadratic program:
      maximize  sum(r_i * w_i) - risk_aversion * w^T Q w
      subject to allocation constraints.

    Attributes:
        assets: List of assets with expected returns and optional sector tags.
        covariance_matrix: n×n covariance matrix (must be positive semi-definite).
        risk_aversion: Trade-off parameter λ (higher = more conservative).
        constraints: Allocation constraints.
    """

    assets: list[Asset] = Field(..., min_length=1, description="Portfolio assets")
    covariance_matrix: list[list[float]] = Field(
        ..., description="n×n covariance matrix"
    )
    risk_aversion: float = Field(
        default=1.0, gt=0, description="Risk aversion coefficient λ"
    )
    constraints: PortfolioConstraints = Field(
        default_factory=PortfolioConstraints, description="Allocation constraints"
    )

    @model_validator(mode="after")
    def covariance_dimensions_match(self) -> "PortfolioModel":
        """Ensure the covariance matrix is n×n where n = number of assets."""
        n = len(self.assets)
        if len(self.covariance_matrix) != n:
            raise ValueError(
                f"covariance_matrix has {len(self.covariance_matrix)} rows "
                f"but there are {n} assets"
            )
        for i, row in enumerate(self.covariance_matrix):
            if len(row) != n:
                raise ValueError(
                    f"covariance_matrix row {i} has {len(row)} columns, expected {n}"
                )
        return self

    @field_validator("assets")
    @classmethod
    def asset_names_unique(cls, v: list[Asset]) -> list[Asset]:
        """Ensure all asset names are distinct."""
        names = [a.name for a in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate asset names: {list(set(duplicates))}")
        return v


# ---------------------------------------------------------------------------
# Scheduling schemas
# ---------------------------------------------------------------------------


class Worker(BaseModel):
    """A worker (employee) in a scheduling problem.

    Attributes:
        name: Unique worker identifier.
        max_hours: Maximum total hours the worker can be scheduled.
        skills: Optional list of skill tags the worker possesses.
        unavailable_shifts: Shift names for which this worker is unavailable.
    """

    name: str = Field(..., min_length=1, description="Unique worker identifier")
    max_hours: float = Field(..., gt=0, description="Maximum schedulable hours")
    skills: list[str] | None = Field(default=None, description="Worker skill tags")
    unavailable_shifts: list[str] | None = Field(
        default=None, description="Shift names where worker is unavailable"
    )


class Shift(BaseModel):
    """A shift in a scheduling problem.

    Attributes:
        name: Unique shift identifier.
        duration_hours: Length of the shift in hours.
        required_workers: Number of workers needed to cover this shift.
        required_skills: Skill tags at least one covering worker must possess.
    """

    name: str = Field(..., min_length=1, description="Unique shift identifier")
    duration_hours: float = Field(..., gt=0, description="Shift duration in hours")
    required_workers: int = Field(..., ge=1, description="Minimum workers needed")
    required_skills: list[str] | None = Field(
        default=None, description="Skills required for this shift"
    )


class SchedulingModel(BaseModel):
    """A binary MIP workforce scheduling problem.

    The builder creates binary variables x[worker, shift, day] and enforces
    coverage, hour limits, consecutive-day limits, rest requirements, and
    skill matching.

    Attributes:
        workers: Available workers.
        shifts: Shifts to be covered.
        planning_horizon_days: Number of days in the schedule (default 7).
        max_consecutive_days: Maximum consecutive days a worker may work.
        min_rest_hours: Minimum hours between two consecutive shifts.
    """

    workers: list[Worker] = Field(..., min_length=1, description="Available workers")
    shifts: list[Shift] = Field(..., min_length=1, description="Shifts to cover")
    planning_horizon_days: int = Field(
        default=7, ge=1, description="Number of days in the planning horizon"
    )
    max_consecutive_days: int | None = Field(
        default=5, ge=1, description="Max consecutive working days"
    )
    min_rest_hours: float | None = Field(
        default=8.0, ge=0, description="Minimum rest hours between shifts"
    )

    @field_validator("workers")
    @classmethod
    def worker_names_unique(cls, v: list[Worker]) -> list[Worker]:
        """Ensure all worker names are distinct."""
        names = [w.name for w in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate worker names: {list(set(duplicates))}")
        return v

    @field_validator("shifts")
    @classmethod
    def shift_names_unique(cls, v: list[Shift]) -> list[Shift]:
        """Ensure all shift names are distinct."""
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate shift names: {list(set(duplicates))}")
        return v


# ---------------------------------------------------------------------------
# Solver intermediate representation
# ---------------------------------------------------------------------------


class SolverInput(BaseModel):
    """Solver-agnostic intermediate representation of any optimization problem.

    The builder layer translates domain models (LP, MIP, Portfolio, Scheduling)
    into this flat, dense representation which the solver layer consumes
    directly.

    Attributes:
        num_variables: Total number of decision variables.
        num_constraints: Total number of constraints.
        variable_names: Ordered list of variable names.
        variable_lower_bounds: Lower bounds, parallel to variable_names.
        variable_upper_bounds: Upper bounds (use 1e30 for +∞), parallel to variable_names.
        variable_types: Integrality types, parallel to variable_names.
        constraint_names: Ordered list of constraint names.
        constraint_matrix: Dense constraint matrix (num_constraints × num_variables).
        constraint_senses: Senses, parallel to constraint_names.
        constraint_rhs: Right-hand sides, parallel to constraint_names.
        objective_coefficients: Linear objective coefficients, parallel to variable_names.
        objective_sense: Direction of optimization.
        objective_quadratic: Optional quadratic objective matrix (for QP / portfolio).
        time_limit_seconds: Solver wall-clock limit (None = unlimited).
        mip_gap_tolerance: Relative MIP optimality gap tolerance.
    """

    num_variables: int = Field(..., ge=1)
    num_constraints: int = Field(..., ge=0)
    variable_names: list[str]
    variable_lower_bounds: list[float]
    variable_upper_bounds: list[float]
    variable_types: list[Literal["continuous", "integer", "binary"]]
    constraint_names: list[str]
    constraint_matrix: list[list[float]]  # [num_constraints][num_variables]
    constraint_senses: list[Literal["<=", ">=", "=="]]
    constraint_rhs: list[float]
    objective_coefficients: list[float]
    objective_sense: Literal["minimize", "maximize"]
    objective_quadratic: list[list[float]] | None = None
    time_limit_seconds: float | None = Field(default=60.0, gt=0)
    mip_gap_tolerance: float | None = Field(default=0.0001, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def dimensions_consistent(self) -> "SolverInput":
        """Verify that all parallel arrays have matching lengths."""
        n = self.num_variables
        m = self.num_constraints

        checks = {
            "variable_names": len(self.variable_names),
            "variable_lower_bounds": len(self.variable_lower_bounds),
            "variable_upper_bounds": len(self.variable_upper_bounds),
            "variable_types": len(self.variable_types),
            "objective_coefficients": len(self.objective_coefficients),
        }
        for field_name, length in checks.items():
            if length != n:
                raise ValueError(
                    f"{field_name} has length {length}, expected num_variables={n}"
                )

        constraint_checks = {
            "constraint_names": len(self.constraint_names),
            "constraint_senses": len(self.constraint_senses),
            "constraint_rhs": len(self.constraint_rhs),
            "constraint_matrix": len(self.constraint_matrix),
        }
        for field_name, length in constraint_checks.items():
            if length != m:
                raise ValueError(
                    f"{field_name} has length {length}, expected num_constraints={m}"
                )

        for i, row in enumerate(self.constraint_matrix):
            if len(row) != n:
                raise ValueError(
                    f"constraint_matrix row {i} has {len(row)} columns, expected {n}"
                )

        if self.objective_quadratic is not None:
            if len(self.objective_quadratic) != n:
                raise ValueError(
                    f"objective_quadratic has {len(self.objective_quadratic)} rows, "
                    f"expected {n}"
                )
            for i, row in enumerate(self.objective_quadratic):
                if len(row) != n:
                    raise ValueError(
                        f"objective_quadratic row {i} has {len(row)} columns, expected {n}"
                    )

        return self


# ---------------------------------------------------------------------------
# Solver result schemas
# ---------------------------------------------------------------------------


class IISResult(BaseModel):
    """Irreducible Infeasible Subsystem — the minimal conflicting constraint set.

    Attributes:
        conflicting_constraints: Names of constraints in the IIS.
        conflicting_variable_bounds: Variable names whose bounds are part of the conflict.
        explanation: Human-readable narrative of why the conflict exists.
    """

    conflicting_constraints: list[str] = Field(
        default_factory=list, description="Constraint names in the IIS"
    )
    conflicting_variable_bounds: list[str] = Field(
        default_factory=list, description="Variable names with conflicting bounds"
    )
    explanation: str = Field(..., description="Human-readable infeasibility explanation")


class SolverResult(BaseModel):
    """Certified result returned by the solver layer.

    This is the primary output of sage-core — a structured, self-contained
    record of what the solver found.

    Attributes:
        status: Outcome of the solve.
        objective_value: Optimal objective value (None if not optimal).
        bound: Best bound (for MIP gap reporting).
        gap: Relative optimality gap (for MIP; 0 means proven optimal).
        solve_time_seconds: Wall-clock time consumed by the solver.
        variable_values: Solution values keyed by variable name.
        shadow_prices: Dual values keyed by constraint name (LP only).
        reduced_costs: Reduced costs keyed by variable name (LP only).
        constraint_slack: Slack values keyed by constraint name.
        binding_constraints: Names of constraints with zero slack.
        objective_ranges: Allowable ranges for objective coefficients (LP only).
        rhs_ranges: Allowable ranges for RHS values (LP only).
        iis: Infeasibility analysis (populated when status == "infeasible").
    """

    status: Literal[
        "optimal",
        "infeasible",
        "unbounded",
        "time_limit_reached",
        "solver_error",
    ] = Field(..., description="Solver outcome")
    objective_value: float | None = Field(
        default=None, description="Optimal objective value"
    )
    bound: float | None = Field(default=None, description="Best bound (MIP)")
    gap: float | None = Field(default=None, ge=0, description="Relative optimality gap (MIP)")
    solve_time_seconds: float = Field(..., ge=0, description="Wall-clock solve time")
    variable_values: dict[str, float] | None = Field(
        default=None, description="Solution: variable_name → value"
    )
    # LP sensitivity analysis
    shadow_prices: dict[str, float] | None = Field(
        default=None, description="Dual values: constraint_name → shadow price"
    )
    reduced_costs: dict[str, float] | None = Field(
        default=None, description="Reduced costs: variable_name → reduced cost"
    )
    constraint_slack: dict[str, float] | None = Field(
        default=None, description="Slack: constraint_name → slack value"
    )
    binding_constraints: list[str] | None = Field(
        default=None, description="Names of constraints at zero slack"
    )
    # Ranging (LP only)
    objective_ranges: dict[str, tuple[float, float]] | None = Field(
        default=None, description="Objective coefficient allowable ranges"
    )
    rhs_ranges: dict[str, tuple[float, float]] | None = Field(
        default=None, description="RHS allowable ranges"
    )
    # Infeasibility analysis
    iis: IISResult | None = Field(
        default=None, description="IIS (populated when infeasible)"
    )

    @model_validator(mode="after")
    def result_coherence(self) -> "SolverResult":
        """Ensure status-dependent fields are consistent."""
        if self.status == "optimal" and self.objective_value is None:
            raise ValueError("objective_value must be set when status is 'optimal'")
        if self.status == "optimal" and self.variable_values is None:
            raise ValueError("variable_values must be set when status is 'optimal'")
        if self.status != "infeasible" and self.iis is not None:
            raise ValueError("iis should only be set when status is 'infeasible'")
        return self


# ---------------------------------------------------------------------------
# Relaxation suggestion
# ---------------------------------------------------------------------------


class RelaxationSuggestion(BaseModel):
    """A single constraint-relaxation proposal for an infeasible model.

    Attributes:
        constraint_name: The constraint or bound to relax.
        current_value: Current RHS or bound value.
        suggested_value: Proposed relaxed value.
        relaxation_amount: Absolute change (suggested - current).
        relaxation_percent: Relative change as a percentage.
        new_objective_value: Objective after re-solving with this relaxation.
        explanation: Human-readable trade-off description.
        priority: Rank (1 = most impactful / least disruptive).
    """

    constraint_name: str = Field(..., description="Constraint or bound being relaxed")
    current_value: float = Field(..., description="Current RHS or bound value")
    suggested_value: float = Field(..., description="Proposed relaxed value")
    relaxation_amount: float = Field(..., description="Absolute change amount")
    relaxation_percent: float = Field(..., description="Relative change as percentage")
    new_objective_value: float | None = Field(
        default=None, description="Objective value after re-solving"
    )
    explanation: str = Field(..., description="Human-readable trade-off explanation")
    priority: int = Field(..., ge=1, description="Rank (1 = highest priority)")
