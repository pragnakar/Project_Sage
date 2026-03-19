"""Tests for sage_cloud/models.py — instantiation, validation, and serialization."""

import pytest
from pydantic import ValidationError

from sage_cloud.models import (
    ArtifactSummary,
    BlobData,
    BlobMeta,
    BlobResult,
    CreatePageRequest,
    DefineSchemaRequest,
    LogEventRequest,
    LogResult,
    PageMeta,
    PageResult,
    SchemaMeta,
    SchemaResult,
    SystemState,
    ToolError,
    UpdatePageRequest,
    WriteBlobRequest,
)

NOW = "2026-03-13T00:00:00Z"


# ---------------------------------------------------------------------------
# BlobResult
# ---------------------------------------------------------------------------

def test_blob_result_valid():
    m = BlobResult(key="ns/file.txt", size_bytes=42, content_type="text/plain", created_at=NOW, url="/blobs/ns/file.txt")
    assert m.key == "ns/file.txt"
    assert m.size_bytes == 42


def test_blob_result_missing_required():
    with pytest.raises(ValidationError):
        BlobResult(size_bytes=42, content_type="text/plain", created_at=NOW, url="/blobs/x")  # missing key


def test_blob_result_roundtrip():
    m = BlobResult(key="ns/x", size_bytes=1, content_type="text/plain", created_at=NOW, url="/blobs/ns/x")
    assert BlobResult(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# BlobData
# ---------------------------------------------------------------------------

def test_blob_data_valid():
    m = BlobData(key="ns/x", data="hello", content_type="text/plain", created_at=NOW)
    assert m.data == "hello"


def test_blob_data_missing_required():
    with pytest.raises(ValidationError):
        BlobData(data="hello", content_type="text/plain", created_at=NOW)  # missing key


# ---------------------------------------------------------------------------
# BlobMeta
# ---------------------------------------------------------------------------

def test_blob_meta_valid():
    m = BlobMeta(key="ns/x", size_bytes=10, content_type="text/plain", created_at=NOW)
    assert m.size_bytes == 10


def test_blob_meta_roundtrip():
    m = BlobMeta(key="ns/x", size_bytes=10, content_type="text/plain", created_at=NOW)
    assert BlobMeta(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# PageResult / PageMeta
# ---------------------------------------------------------------------------

def test_page_result_valid():
    m = PageResult(name="dashboard", url="/apps/dashboard", created_at=NOW, updated_at=NOW)
    assert m.description == ""


def test_page_result_missing_required():
    with pytest.raises(ValidationError):
        PageResult(url="/apps/dashboard", created_at=NOW, updated_at=NOW)  # missing name


def test_page_meta_roundtrip():
    m = PageMeta(name="dashboard", url="/apps/dashboard", description="main", created_at=NOW, updated_at=NOW)
    assert PageMeta(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# SchemaResult / SchemaMeta
# ---------------------------------------------------------------------------

def test_schema_result_valid():
    m = SchemaResult(name="solve_input", definition={"type": "object"}, created_at=NOW)
    assert m.definition == {"type": "object"}


def test_schema_result_missing_required():
    with pytest.raises(ValidationError):
        SchemaResult(definition={"type": "object"}, created_at=NOW)  # missing name


def test_schema_meta_roundtrip():
    m = SchemaMeta(name="x", created_at=NOW)
    assert SchemaMeta(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# LogResult
# ---------------------------------------------------------------------------

def test_log_result_valid():
    m = LogResult(id=1, timestamp=NOW, message="started", level="info")
    assert m.level == "info"


def test_log_result_default_level():
    m = LogResult(id=1, timestamp=NOW, message="started")
    assert m.level == "info"


def test_log_result_missing_required():
    with pytest.raises(ValidationError):
        LogResult(timestamp=NOW, message="x")  # missing id


# ---------------------------------------------------------------------------
# SystemState
# ---------------------------------------------------------------------------

def test_system_state_valid():
    m = SystemState(uptime_seconds=3.5, artifact_count=10, page_count=2, blob_count=5, schema_count=3)
    assert m.registered_apps == []


def test_system_state_with_apps():
    m = SystemState(uptime_seconds=1.0, artifact_count=0, page_count=0, blob_count=0, schema_count=0, registered_apps=["sage"])
    assert "sage" in m.registered_apps


def test_system_state_roundtrip():
    m = SystemState(uptime_seconds=1.0, artifact_count=1, page_count=1, blob_count=1, schema_count=1, registered_apps=["sage"])
    assert SystemState(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# ArtifactSummary
# ---------------------------------------------------------------------------

def test_artifact_summary_defaults():
    m = ArtifactSummary()
    assert m.pages == []
    assert m.blobs == []
    assert m.schemas == []
    assert m.recent_events == []


def test_artifact_summary_roundtrip():
    m = ArtifactSummary(
        blobs=[BlobMeta(key="ns/x", size_bytes=1, content_type="text/plain", created_at=NOW)],
    )
    assert ArtifactSummary(**m.model_dump()) == m


# ---------------------------------------------------------------------------
# ToolError
# ---------------------------------------------------------------------------

def test_tool_error_valid():
    m = ToolError(error="not_found", detail="key does not exist", tool_name="read_blob")
    assert m.error == "not_found"


def test_tool_error_defaults():
    m = ToolError(error="internal")
    assert m.detail == ""
    assert m.tool_name == ""


def test_tool_error_missing_required():
    with pytest.raises(ValidationError):
        ToolError(detail="x")  # missing error


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

def test_write_blob_request_valid():
    m = WriteBlobRequest(key="ns/x", data="hello")
    assert m.content_type == "text/plain"


def test_write_blob_request_missing_required():
    with pytest.raises(ValidationError):
        WriteBlobRequest(data="hello")  # missing key


def test_create_page_request_valid():
    m = CreatePageRequest(name="dashboard", jsx_code="<div/>")
    assert m.description == ""


def test_create_page_request_missing_required():
    with pytest.raises(ValidationError):
        CreatePageRequest(jsx_code="<div/>")  # missing name


def test_update_page_request_valid():
    m = UpdatePageRequest(name="dashboard", jsx_code="<div/>")
    assert m.jsx_code == "<div/>"


def test_define_schema_request_valid():
    m = DefineSchemaRequest(name="x", definition={"type": "object"})
    assert m.definition == {"type": "object"}


def test_log_event_request_defaults():
    m = LogEventRequest(message="hello")
    assert m.level == "info"
    assert m.context == {}
