"""Tests for sage_cloud.schemas — job blob schema models (v2.0)."""

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

# -- Fixtures ---------------------------------------------------------------

MINIMAL_JOB = dict(
    task_id="job-001",
    problem_name="Test LP",
    problem_type="LP",
    complexity_tier="instant",
    status="queued",
)

FULL_JOB = dict(
    schema_version="2.0",
    task_id="job-002",
    problem_name="Full Portfolio",
    problem_type="PORTFOLIO",
    complexity_tier="background",
    description="A fully populated job",
    status="complete",
    created_at="2026-03-19T10:00:00Z",
    started_at="2026-03-19T10:00:01Z",
    completed_at="2026-03-19T10:00:42Z",
    deleted_at=None,
    deleted_by=None,
    n_vars=100,
    n_constraints=50,
    n_binary=10,
    elapsed_seconds=41.2,
    gap_pct=0.0,
    best_bound=26.0,
    best_incumbent=26.0,
    node_count=42,
    stall_detected=False,
    pause_requested=False,
    bound_history=[[1.0, 20.0, 18.0, "progress"], [5.0, 26.0, 26.0, "optimal"]],
    incumbent_solution={"x": 5, "y": 3},
    solution={"x": 6, "y": 4},
    explanation="Optimal: x=6, y=4, obj=26",
    assumed_constraints=["budget <= 1000"],
    clickup_task_id="abc123",
    notified_at="2026-03-19T10:01:00Z",
    output_webhooks=["https://example.com/hook"],
)


# -- SageJob ----------------------------------------------------------------

class TestSageJob:
    def test_minimal_construction(self):
        job = SageJob(**MINIMAL_JOB)
        assert job.task_id == "job-001"
        assert job.status == "queued"
        assert job.problem_type == "LP"
        assert job.complexity_tier == "instant"

    def test_defaults(self):
        job = SageJob(**MINIMAL_JOB)
        assert job.schema_version == "2.0"
        assert job.description is None
        assert job.n_vars == 0
        assert job.n_constraints == 0
        assert job.n_binary == 0
        assert job.elapsed_seconds == 0.0
        assert job.gap_pct is None
        assert job.best_bound is None
        assert job.best_incumbent is None
        assert job.node_count is None
        assert job.stall_detected is False
        assert job.pause_requested is False
        assert job.bound_history == []
        assert job.incumbent_solution is None
        assert job.solution is None
        assert job.explanation is None
        assert job.assumed_constraints is None
        assert job.clickup_task_id is None
        assert job.notified_at is None
        assert job.output_webhooks == []
        assert job.created_at is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.deleted_at is None
        assert job.deleted_by is None

    def test_full_construction(self):
        job = SageJob(**FULL_JOB)
        assert job.best_bound == 26.0
        assert job.solution == {"x": 6, "y": 4}
        assert len(job.bound_history) == 2
        assert job.n_binary == 10
        assert job.node_count == 42
        assert job.explanation == "Optimal: x=6, y=4, obj=26"
        assert job.clickup_task_id == "abc123"
        assert job.output_webhooks == ["https://example.com/hook"]

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
        assert parsed["schema_version"] == "2.0"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "status": "bogus"})

    def test_invalid_problem_type_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "problem_type": "bogus"})

    def test_invalid_complexity_tier_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "complexity_tier": "bogus"})

    def test_invalid_deleted_by_raises(self):
        with pytest.raises(ValidationError):
            SageJob(**{**MINIMAL_JOB, "deleted_by": "bogus"})

    def test_all_valid_statuses(self):
        for s in ("queued", "running", "paused", "complete", "failed", "stalled", "deleted"):
            job = SageJob(**{**MINIMAL_JOB, "status": s})
            assert job.status == s

    def test_all_valid_problem_types(self):
        for pt in ("LP", "MIP", "QP", "PORTFOLIO", "SCHEDULING"):
            job = SageJob(**{**MINIMAL_JOB, "problem_type": pt})
            assert job.problem_type == pt

    def test_all_valid_complexity_tiers(self):
        for ct in ("instant", "fast", "background"):
            job = SageJob(**{**MINIMAL_JOB, "complexity_tier": ct})
            assert job.complexity_tier == ct

    def test_deleted_by_values(self):
        for db in ("user_ui", "user_chat"):
            job = SageJob(**{**MINIMAL_JOB, "deleted_by": db})
            assert job.deleted_by == db

    def test_v2_full_serialize_deserialize(self):
        """Construct a v2.0 SageJob with all fields, serialize, deserialize, validate."""
        job = SageJob(**FULL_JOB)
        dumped = job.model_dump()
        json_str = json.dumps(dumped)
        loaded = json.loads(json_str)
        restored = SageJob.model_validate(loaded)
        assert restored.schema_version == "2.0"
        assert restored.task_id == "job-002"
        assert restored.problem_type == "PORTFOLIO"
        assert restored.complexity_tier == "background"
        assert restored.n_binary == 10
        assert restored.node_count == 42
        assert restored.stall_detected is False
        assert restored.clickup_task_id == "abc123"
        assert restored.output_webhooks == ["https://example.com/hook"]
        assert restored == job


# -- SageJobIndex -----------------------------------------------------------

class TestSageJobIndex:
    def test_empty_index(self):
        idx = SageJobIndex()
        assert idx.schema_version == "2.0"
        assert idx.jobs == []

    def test_with_entries(self):
        entry = SageJobIndexEntry(
            task_id="job-001",
            created_at="2026-03-19T10:00:00Z",
            status="queued",
            problem_name="Test LP",
            problem_type="LP",
            complexity_tier="instant",
        )
        idx = SageJobIndex(jobs=[entry])
        assert len(idx.jobs) == 1
        assert idx.jobs[0].task_id == "job-001"
        assert idx.jobs[0].problem_type == "LP"
        assert idx.jobs[0].complexity_tier == "instant"

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
        assert parsed["schema_version"] == "2.0"
        assert parsed["jobs"] == []


# -- SageNotifications ------------------------------------------------------

class TestSageNotifications:
    def test_empty_notifications(self):
        n = SageNotifications()
        assert n.schema_version == "2.0"
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
        assert parsed["schema_version"] == "2.0"
        assert parsed["pending"] == []
