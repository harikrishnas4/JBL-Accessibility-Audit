from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from jbl_audit_api.db.models import RunPlanStatus, ScanBatchStatus, ScanBatchType


class ScanBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_batch_id: str
    run_plan_id: str
    run_id: str
    batch_key: str
    batch_type: ScanBatchType
    status: ScanBatchStatus
    chapter_key: str | None
    shared_key: str | None
    asset_ids: list[str]
    viewport_matrix: list[dict[str, Any]]
    retry_policy: dict[str, Any]
    task_contract: dict[str, Any]
    dispatcher_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_plan_id: str
    run_id: str
    status: RunPlanStatus
    dispatcher_name: str
    viewport_matrix: list[dict[str, Any]]
    retry_policy: dict[str, Any]
    scan_batch_count: int
    manual_task_count: int
    orchestration_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    scan_batches: list[ScanBatchResponse]
