from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jbl_audit_api.db.models import AssetHandlingPath, AssetLayer
from jbl_audit_api.integrations.docproc import CanonicalSchemaType


class ManifestDatasetRequest(BaseModel):
    schema_type: CanonicalSchemaType
    records: list[dict[str, str]] = Field(default_factory=list)


class ManifestClassificationContextRequest(BaseModel):
    datasets: list[ManifestDatasetRequest] = Field(default_factory=list)


class AssetClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    classification_id: str
    run_id: str
    asset_id: str
    layer: AssetLayer
    handling_path: AssetHandlingPath
    shared_key: str | None
    owner_team: str | None
    third_party: bool
    third_party_evidence: str | None
    auth_context: dict[str, Any]
    exclusion_reason: str | None
    created_at: datetime
    updated_at: datetime
