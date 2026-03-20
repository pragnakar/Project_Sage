"""Tests for the Jobs REST API (Stage 11)."""

import json
import re

import pytest

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

TEST_SOLVER_INPUT = {
    "num_variables": 2,
    "num_constraints": 1,
    "variable_names": ["x", "y"],
    "variable_lower_bounds": [0.0, 0.0],
    "variable_upper_bounds": [10.0, 10.0],
    "variable_types": ["continuous", "continuous"],
    "constraint_names": ["c1"],
    "constraint_matrix": [[1.0, 1.0]],
    "constraint_senses": ["<="],
    "constraint_rhs": [10.0],
    "objective_coefficients": [3.0, 2.0],
    "objective_sense": "maximize",
}

TASK_ID_PATTERN = re.compile(r"^[a-z]{2,4}-[0-9a-f]{4}$")


def _submit_job(client, auth_headers, **overrides):
    """Helper to submit a job and return the response."""
    body = {
        "solver_input": TEST_SOLVER_INPUT,
        "problem_name": "test-problem",
    }
    body.update(overrides)
    return client.post("/api/jobs", json=body, headers=auth_headers)


def _write_job_blob(client, auth_headers, task_id, job_data):
    """Write a job blob directly via the blob store for test setup."""
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )


def _write_index_with_entry(client, auth_headers, entries):
    """Write a jobs/index blob with given entries."""
    index = {"schema_version": "2.0", "jobs": entries}
    client.post(
        "/api/tools/write_blob",
        json={
            "key": "jobs/index",
            "data": json.dumps(index),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )


# ---------------------------------------------------------------------------
# 1. Submit job
# ---------------------------------------------------------------------------

def test_submit_job(client, auth_headers):
    """POST /api/jobs with valid solver_input returns 201 with task_id."""
    resp = _submit_job(client, auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert TASK_ID_PATTERN.match(data["task_id"])


# ---------------------------------------------------------------------------
# 2. List jobs
# ---------------------------------------------------------------------------

def test_list_jobs(client, auth_headers):
    """Create 3 jobs, GET /api/jobs returns all 3."""
    for i in range(3):
        _submit_job(client, auth_headers, problem_name=f"job-{i}")

    resp = client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 3


# ---------------------------------------------------------------------------
# 3. List jobs with status filter
# ---------------------------------------------------------------------------

def test_list_jobs_status_filter(client, auth_headers):
    """Filter jobs by status."""
    # Submit two jobs (both queued)
    r1 = _submit_job(client, auth_headers, problem_name="a")
    r2 = _submit_job(client, auth_headers, problem_name="b")

    # Manually change one job to "complete" via blob rewrite
    task_id = r1.json()["task_id"]
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    job_data["status"] = "complete"
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )
    # Update index too
    idx_resp = client.post(
        "/api/tools/read_blob",
        json={"key": "jobs/index"},
        headers=auth_headers,
    )
    idx_data = json.loads(idx_resp.json()["data"])
    for entry in idx_data["jobs"]:
        if entry["task_id"] == task_id:
            entry["status"] = "complete"
    client.post(
        "/api/tools/write_blob",
        json={
            "key": "jobs/index",
            "data": json.dumps(idx_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )

    # Filter by queued
    resp = client.get("/api/jobs?status=queued", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Filter by complete
    resp = client.get("/api/jobs?status=complete", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# 4. List jobs with problem_type filter
# ---------------------------------------------------------------------------

def test_list_jobs_problem_type_filter(client, auth_headers):
    """Filter jobs by problem_type."""
    _submit_job(client, auth_headers, problem_name="lp-job", problem_type="LP")
    _submit_job(client, auth_headers, problem_name="mip-job", problem_type="MIP")

    resp = client.get("/api/jobs?problem_type=LP", headers=auth_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["problem_type"] == "LP"

    resp = client.get("/api/jobs?problem_type=MIP", headers=auth_headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["problem_type"] == "MIP"


# ---------------------------------------------------------------------------
# 5. Get job
# ---------------------------------------------------------------------------

def test_get_job(client, auth_headers):
    """GET /api/jobs/{task_id} returns full job blob."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    resp = client.get(f"/api/jobs/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["status"] == "queued"
    assert data["problem_name"] == "test-problem"
    assert "solver_input" in data


# ---------------------------------------------------------------------------
# 6. Get job 404
# ---------------------------------------------------------------------------

def test_get_job_not_found(client, auth_headers):
    """GET /api/jobs/nonexistent returns 404."""
    resp = client.get("/api/jobs/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Progress endpoint
# ---------------------------------------------------------------------------

def test_progress_endpoint(client, auth_headers):
    """GET /api/jobs/{task_id}/progress returns lightweight fields."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    resp = client.get(f"/api/jobs/{task_id}/progress", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["status"] == "queued"
    assert "elapsed_seconds" in data
    assert "gap_pct" in data
    assert "stall_detected" in data


# ---------------------------------------------------------------------------
# 8. Pause running job
# ---------------------------------------------------------------------------

def test_pause_running_job(client, auth_headers):
    """Pause a running job sets pause_requested."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    # Manually set status to "running"
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    job_data["status"] = "running"
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )

    resp = client.post(f"/api/jobs/{task_id}/pause", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["pause_requested"] is True

    # Verify blob was updated
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    assert job_data["pause_requested"] is True


# ---------------------------------------------------------------------------
# 9. Pause non-running -> 409
# ---------------------------------------------------------------------------

def test_pause_non_running_returns_409(client, auth_headers):
    """Pausing a non-running (complete) job returns 409."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    # Set to complete
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    job_data["status"] = "complete"
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )

    resp = client.post(f"/api/jobs/{task_id}/pause", headers=auth_headers)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 10. Resume paused job
# ---------------------------------------------------------------------------

def test_resume_paused_job(client, auth_headers):
    """Resume a paused job with incumbent_solution sets status to queued."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    # Set to paused with incumbent
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    job_data["status"] = "paused"
    job_data["incumbent_solution"] = {"x": 6.0, "y": 4.0}
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )

    resp = client.post(f"/api/jobs/{task_id}/resume", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["status"] == "queued"

    # Verify blob
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    assert job_data["status"] == "queued"
    assert job_data["pause_requested"] is False
    assert ["resume"] in job_data["bound_history"]


# ---------------------------------------------------------------------------
# 11. Resume without incumbent -> 400
# ---------------------------------------------------------------------------

def test_resume_without_incumbent_cold_restarts(client, auth_headers):
    """Resume a paused job without incumbent_solution succeeds with a warning."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    # Set to paused without incumbent
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    job_data["status"] = "paused"
    job_data["incumbent_solution"] = None
    client.post(
        "/api/tools/write_blob",
        json={
            "key": f"jobs/{task_id}",
            "data": json.dumps(job_data),
            "content_type": "application/json",
        },
        headers=auth_headers,
    )

    resp = client.post(f"/api/jobs/{task_id}/resume", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["warning"] is not None
    assert "from scratch" in data["warning"]


# ---------------------------------------------------------------------------
# 12. Soft delete
# ---------------------------------------------------------------------------

def test_soft_delete(client, auth_headers):
    """DELETE sets status to 'deleted' and deleted_at."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    resp = client.delete(f"/api/jobs/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["status"] == "deleted"

    # Verify blob
    blob_resp = client.post(
        "/api/tools/read_blob",
        json={"key": f"jobs/{task_id}"},
        headers=auth_headers,
    )
    job_data = json.loads(blob_resp.json()["data"])
    assert job_data["status"] == "deleted"
    assert job_data["deleted_at"] is not None


# ---------------------------------------------------------------------------
# 13. Deleted job still readable
# ---------------------------------------------------------------------------

def test_deleted_job_still_readable(client, auth_headers):
    """After soft delete, GET still returns the job blob."""
    r = _submit_job(client, auth_headers)
    task_id = r.json()["task_id"]

    client.delete(f"/api/jobs/{task_id}", headers=auth_headers)

    resp = client.get(f"/api/jobs/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["status"] == "deleted"


# ---------------------------------------------------------------------------
# 14. task_id format
# ---------------------------------------------------------------------------

def test_task_id_format(client, auth_headers):
    """Generated IDs match {type}-{4hex} pattern."""
    # LP (continuous vars -> detected as LP)
    r1 = _submit_job(client, auth_headers, problem_type="LP")
    assert TASK_ID_PATTERN.match(r1.json()["task_id"])
    assert r1.json()["task_id"].startswith("lp-")

    # MIP
    r2 = _submit_job(client, auth_headers, problem_type="MIP")
    assert TASK_ID_PATTERN.match(r2.json()["task_id"])
    assert r2.json()["task_id"].startswith("mip-")

    # QP
    r3 = _submit_job(client, auth_headers, problem_type="QP")
    assert TASK_ID_PATTERN.match(r3.json()["task_id"])
    assert r3.json()["task_id"].startswith("qp-")
