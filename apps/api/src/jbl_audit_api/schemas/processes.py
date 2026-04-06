from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jbl_audit_api.db.models import ProcessFlowStepStatus, ProcessFlowType


class CrawlGraphNodeRequest(BaseModel):
    locator: str = Field(min_length=1, max_length=2048)
    asset_id: str | None = Field(default=None, max_length=128)
    page_type: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawlGraphEdgeRequest(BaseModel):
    from_locator: str = Field(min_length=1, max_length=2048)
    to_locator: str = Field(min_length=1, max_length=2048)
    transition_type: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=512)


class CrawlGraphRequest(BaseModel):
    entry_locator: str = Field(min_length=1, max_length=2048)
    nodes: list[CrawlGraphNodeRequest] = Field(default_factory=list)
    edges: list[CrawlGraphEdgeRequest] = Field(default_factory=list)


class ProcessUpsertRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=36)
    auth_context: dict[str, Any] | None = None
    crawl_graph: CrawlGraphRequest


class ProcessFlowStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    process_flow_step_id: str
    process_flow_id: str
    run_id: str
    asset_id: str | None
    step_order: int
    step_key: str
    step_status: ProcessFlowStepStatus
    locator: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class ProcessFlowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    process_flow_id: str
    run_id: str
    flow_type: ProcessFlowType
    flow_name: str
    auth_context: dict[str, Any]
    entry_locator: str
    flow_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    steps: list[ProcessFlowStepResponse]


class ProcessUpsertResponse(BaseModel):
    run_id: str
    flows: list[ProcessFlowResponse]
