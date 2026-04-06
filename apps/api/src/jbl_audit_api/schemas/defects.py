from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from jbl_audit_api.db.models import AssetLayer, DefectPriority, FindingState


class DefectComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    defect_component_id: str
    defect_id: str
    run_id: str
    asset_id: str
    finding_id: str | None
    shared_key: str | None
    locator: str | None
    created_at: datetime


class DefectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    defect_id: str
    run_id: str
    issue_id: str
    defect_signature: str
    rule_id: str
    wcag_sc: str | None
    finding_state: FindingState
    priority: DefectPriority
    layer: AssetLayer
    owner_team: str | None
    shared_key: str | None
    target_fingerprint: str | None
    message_key: str
    message: str
    finding_origin: str
    impacted_asset_count: int
    created_at: datetime
    updated_at: datetime
    components: list[DefectComponentResponse]


class DefectListResponse(BaseModel):
    defect_count: int
    defects: list[DefectResponse]
