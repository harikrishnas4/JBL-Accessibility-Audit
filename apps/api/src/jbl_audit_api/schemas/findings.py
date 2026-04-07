from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jbl_audit_api.db.models import EvidenceArtifactType, RawFindingResultType


class EvidenceArtifactCreateRequest(BaseModel):
    artifact_type: EvidenceArtifactType
    storage_path: str = Field(min_length=1, max_length=2048)
    artifact_metadata: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime


class RawFindingCreateRequest(BaseModel):
    result_type: RawFindingResultType
    rule_id: str = Field(min_length=1, max_length=255)
    wcag_sc: str | None = Field(default=None, max_length=32)
    resolution_state: str = Field(min_length=1, max_length=64)
    severity: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4096)
    target_fingerprint: str | None = Field(default=None, max_length=1024)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime
    evidence_artifacts: list[EvidenceArtifactCreateRequest] = Field(default_factory=list)


class AssetFindingsIngestRequest(BaseModel):
    findings: list[RawFindingCreateRequest] = Field(min_length=1)
    scan_metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_artifact_id: str
    finding_id: str
    run_id: str
    asset_id: str
    artifact_type: EvidenceArtifactType
    storage_path: str
    artifact_metadata: dict[str, Any]
    captured_at: datetime


class RawFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    run_id: str
    asset_id: str
    result_type: RawFindingResultType
    rule_id: str
    wcag_sc: str | None
    resolution_state: str
    severity: str | None
    message: str
    target_fingerprint: str | None
    raw_payload: dict[str, Any]
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
    evidence_artifacts: list[EvidenceArtifactResponse]


class RunFindingsResponse(BaseModel):
    run_id: str
    finding_count: int
    result_counts: dict[str, int]
    findings: list[RawFindingResponse]


class AssetFindingsIngestResponse(BaseModel):
    run_id: str
    asset_id: str
    persisted_finding_count: int
    evidence_artifact_count: int
    result_counts: dict[str, int]
    scan_metadata: dict[str, Any]
