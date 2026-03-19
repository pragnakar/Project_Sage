"""Tests for sage_cloud.schemas — job blob schema models."""

import json

import pytest
from pydantic import ValidationError

from sage_cloud.schemas import (
    SageJob,
    SageJobIndex,
    SageJobIndexEntry,
    SageNotificationEntry,
    SageNotifications,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

MINIMAL_JOB = dict(
    task_id="job-001",
    created_at="2026-03-19T10:00:00Z",
    updated_at="2026-03-19T10:00:00Z",
    status="queued",
    problem_type="lp",
    problem_name="Test LP",
)

FULL_JOB = dict(
    **{**MINIMAL_JOB, "status": "complete"},
    description="A fully populated job",
    variable_count=100,
    constraint_count=50,
    objective_sense="maximize",
    best_bound=26.0,
    best_incumbent=26.0,
    gap_pct=0.0,
    elapsed_seconds=42,
    bound_history=[[1.0, 20.0, 18.0], [5.0, 26.0, 26.0]],
    cost_breakdown={"compute": 0.003, "storage": 0.001},
    solver_log=["Iteration 1: bound=20", "Optimal found"],
    solution={"x": 6, "y": 4},
    solution_summary="Optimal: x=6, y=4, obj=26",
    tags=["test", "lp"],
    control="run",
)


# ── SageJob ───────────────────────────────────────────────────────────────

class TestSageJob:
    def test_minimal_construction(self):
        job = SageJob(**MINIMAL_JOB)
        assert job.task_id == "job-001"
        assert job.status == "queued"
        assert job.problem_type == "lp"

    def test_defaults(self):
        job = SageJob(**MINIMAL_JOB)
        assert job.schema_version == "1.0"
        assert job.description == ""
        assert job.variable_count == 0
        assert job.constraint_count == 0
        assert job.objective_sense == "minimize"
        assert job.best_bound is None
        assert job.best_incumbent is None
        assert job.gap_pct is None
        assert job.elapsed_seconds == 0
        assert job.bound_history == []
        assert job.cost_breakdown is None
        assert job.solver_log == []
        assert job.solution is None
        assert job.solution_summary == ""
        assert job.tags == []
        assert job.control == "run"

    def test_full_construction(self):
        job = SageJob(**FULL_JOB)
        assert job.best_bound == 26.0
        assert job.solution == {"x": 6, "y": 4}
        assert len(job.bound_history) == 2

    def test_json_round_trip(self):
        original = SageJob(**FULL_JOB)
        json_str = original.model_dump_json()
        parsed = SageJob.model_validate_json(json_str)
        assert parsed == original

    def test_dict_round_trip(self):
        original = SageJob(**FULL_JOB)
        data = original.model_dump()
        assert isinstance(data, dict)
        parsed = SageJob.model_validate(data)
        assert parsed == original

    def test_serializes_to_valid_json(self):
        job = SageJob(**MINIMAL_JOB)
        raw = job.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["task_id"] == "job-001"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "status": "bogus"})

    def test_invalid_problem_type_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "problem_type": "bogus"})

    def test_invalid_objective_sense_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "objective_sense": "bogus"})

    def test_invalid_control_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "control": "bogus"})

    def test_all_valid_statuses(self):
        for s in ("queued", "running", "paused", "complete", "failed"):
            job = SageJob(**{**MINIMAL_JOB, "status": s})
            assert job.status == s

    def test_all_valid_problem_types(self):
        for pt in ("lp", "mip", "scheduling", "portfolio", "nlp"):
            job = SageJob(**{**MINIMAL_JOB, "problem_type": pt})
            assert job.problem_type == pt


# ── SageJobIndex ──────────────────────────────────────────────────────────

class TestSageJobIndex:
    def test_empty_index(self):
        idx = SageJobIndex()
        assert idx.schema_version == "1.0"
        assert idx.jobs == []

    def test_with_entries(self):
        entry = SageJobIndexEntry(
            task_id="job-001",
            created_at="2026-03-19T10:00:00Z",
            status="queued",
            problem_name="Test LP",
        )
        idx = SageJobIndex(jobs=[entry])
        assert len(idx.jobs) == 1
        assert idx.jobs[0].task_id == "job-001"

    def test_json_round_trip(self):
        entry = SageJobIndexEntry(
            task_id="job-001",
            created_at="2026-03-19T10:00:00Z",
            status="complete",
            problem_name="Test LP",
        )
        original = SageJobIndex(jobs=[entry])
        parsed = SageJobIndex.model_validate_json(original.model_dump_json())
        assert parsed == original

    def test_serializes_to_valid_json(self):
        idx = SageJobIndex()
        parsed = json.loads(idx.model_dump_json())
        assert parsed["schema_version"] == "1.0"
        assert parsed["jobs"] == []


# ── SageNotifications ─────────────────────────────────────────────────────

class TestSageNotifications:
    def test_empty_notifications(self):
        n = SageNotifications()
        assert n.schema_version == "1.0"
        assert n.pending == []

    def test_with_entries(self):
        entry = SageNotificationEntry(
            task_id="job-001",
            completed_at="2026-03-19T10:05:00Z",
            problem_name="Test LP",
            status="complete",
        )
        n = SageNotifications(pending=[entry])
        assert len(n.pending) == 1
        assert n.pending[0].completed_at == "2026-03-19T10:05:00Z"

    def test_json_round_trip(self):
        entry = SageNotificationEntry(
            task_id="job-001",
            completed_at="2026-03-19T10:05:00Z",
            problem_name="Test LP",
            status="failed",
        )
        original = SageNotifications(pending=[entry])
        parsed = SageNotifications.model_validate_json(original.model_dump_json())
        assert parsed == original

    def test_serializes_to_valid_json(self):
        n = SageNotifications()
        parsed = json.loads(n.model_dump_json())
        assert parsed["schema_version"] == "1.0"
        assert parsed["pending"] == []
