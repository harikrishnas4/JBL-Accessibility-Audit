from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jbl_audit_api.db.models import AuditRunMode, AuditRunStage, AuditRunStatus
from jbl_audit_api.schemas.orchestration import RunPlanResponse


class AuditInputCreateRequest(BaseModel):
    course_url_or_name: str = Field(min_length=1, max_length=2048)
    auth_metadata: dict[str, Any] = Field(default_factory=dict)
    manifest_metadata: dict[str, Any] | None = None
    mode: AuditRunMode | None = None


class AuditInputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    input_id: str
    run_id: str
    course_url_or_name: str
    auth_metadata: dict[str, Any]
    manifest_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SchemaRegistryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_registry_entry_id: str
    run_id: str | None
    schema_name: str
    schema_version: str
    schema_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ReportRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_record_id: str
    run_id: str
    report_type: str
    report_uri: str
    created_at: datetime
    updated_at: datetime


class AuditRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: AuditRunStatus
    current_stage: AuditRunStage
    mode: AuditRunMode
    created_at: datetime
    updated_at: datetime
    run_plan: RunPlanResponse | None = None


class AuditRunDetailResponse(AuditRunSummaryResponse):
    audit_input: AuditInputResponse
    schema_registry_entries: list[SchemaRegistryEntryResponse]
    report_records: list[ReportRecordResponse]
