from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import AuditInput, AuditRun, AuditRunMode, AuditRunStage, AuditRunStatus
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.runs import AuditInputCreateRequest
from jbl_audit_api.services.orchestration import OrchestrationService


class RunService:
    def __init__(self, repository: RunRepository, orchestration_service: OrchestrationService) -> None:
        self.repository = repository
        self.orchestration_service = orchestration_service

    def create_run(self, payload: AuditInputCreateRequest) -> AuditRun:
        now = datetime.now(UTC)
        resolved_mode = payload.mode or self._resolve_mode(payload.manifest_metadata)
        audit_run = AuditRun(
            run_id=str(uuid.uuid4()),
            status=AuditRunStatus.queued,
            current_stage=AuditRunStage.intake,
            mode=resolved_mode,
            created_at=now,
            updated_at=now,
        )
        audit_run.audit_input = AuditInput(
            input_id=str(uuid.uuid4()),
            run_id=audit_run.run_id,
            course_url_or_name=payload.course_url_or_name,
            auth_metadata=payload.auth_metadata,
            manifest_metadata=payload.manifest_metadata,
            created_at=now,
            updated_at=now,
        )
        created_run = self.repository.create(audit_run)
        self.orchestration_service.initialize_run_plan(created_run.run_id)
        refreshed_run = self.repository.get(created_run.run_id)
        if refreshed_run is None:
            raise NotFoundError(f"run '{created_run.run_id}' does not exist")
        return refreshed_run

    def get_run(self, run_id: str) -> AuditRun:
        audit_run = self.repository.get(run_id)
        if audit_run is None:
            raise NotFoundError(f"run '{run_id}' does not exist")
        return audit_run

    def _resolve_mode(self, manifest_metadata: dict | None) -> AuditRunMode:
        if manifest_metadata:
            return AuditRunMode.manifest_full
        return AuditRunMode.partial
