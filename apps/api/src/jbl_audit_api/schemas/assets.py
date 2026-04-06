from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jbl_audit_api.db.models import AssetScopeStatus
from jbl_audit_api.schemas.classifications import AssetClassificationResponse, ManifestClassificationContextRequest


class CrawlExclusionRequest(BaseModel):
    locator: str = Field(min_length=1, max_length=2048)
    reason: str = Field(min_length=1, max_length=512)


class CrawlSnapshotUpsertRequest(BaseModel):
    entry_locator: str = Field(min_length=1, max_length=2048)
    started_at: datetime
    completed_at: datetime
    visited_locators: list[str] = Field(default_factory=list)
    excluded_locators: list[CrawlExclusionRequest] = Field(default_factory=list)
    snapshot_metadata: dict[str, Any] = Field(default_factory=dict)


class AssetUpsertItemRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=128)
    asset_type: str = Field(min_length=1, max_length=128)
    source_system: str = Field(min_length=1, max_length=255)
    locator: str = Field(min_length=1, max_length=2048)
    scope_status: AssetScopeStatus
    scope_reason: str | None = Field(default=None, max_length=512)
    layer: str = Field(min_length=1, max_length=128)
    shared_key: str | None = Field(default=None, max_length=255)
    owner_team: str | None = Field(default=None, max_length=255)
    auth_context: dict[str, Any] = Field(default_factory=dict)
    handling_path: str = Field(min_length=1, max_length=255)
    component_fingerprint: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime

    @model_validator(mode="after")
    def validate_scope_reason(self) -> "AssetUpsertItemRequest":
        if self.scope_status == AssetScopeStatus.out_of_scope and not self.scope_reason:
            raise ValueError("scope_reason is required when scope_status is out_of_scope")
        return self


class AssetUpsertRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=36)
    crawl_snapshot: CrawlSnapshotUpsertRequest
    assets: list[AssetUpsertItemRequest] = Field(min_length=1)
    manifest_context: ManifestClassificationContextRequest | None = None


class CrawlExclusionResponse(BaseModel):
    locator: str
    reason: str


class CrawlSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    crawl_snapshot_id: str
    run_id: str
    entry_locator: str
    started_at: datetime
    completed_at: datetime
    visited_locators: list[str]
    excluded_locators: list[CrawlExclusionResponse]
    snapshot_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    asset_id: str
    crawl_snapshot_id: str | None
    asset_type: str
    source_system: str
    locator: str
    scope_status: AssetScopeStatus
    scope_reason: str | None
    layer: str
    shared_key: str | None
    owner_team: str | None
    auth_context: dict[str, Any]
    handling_path: str
    component_fingerprint: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AssetUpsertResponse(BaseModel):
    run_id: str
    crawl_snapshot: CrawlSnapshotResponse
    assets: list[AssetResponse]
    classifications: list[AssetClassificationResponse]
