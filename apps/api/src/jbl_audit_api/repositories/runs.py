from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import AuditRun, RunPlan


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, audit_run: AuditRun) -> AuditRun:
        self.session.add(audit_run)
        self.session.flush()
        return audit_run

    def get(self, run_id: str) -> AuditRun | None:
        return self.session.scalar(
            select(AuditRun)
            .options(
                selectinload(AuditRun.audit_input),
                selectinload(AuditRun.schema_registry_entries),
                selectinload(AuditRun.report_records),
                selectinload(AuditRun.run_plan).selectinload(RunPlan.scan_batches),
            )
            .where(AuditRun.run_id == run_id),
        )
