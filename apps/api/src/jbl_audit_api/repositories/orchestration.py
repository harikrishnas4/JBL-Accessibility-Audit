from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import Asset, AuditRun, RunPlan, ScanBatch


class OrchestrationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_context(self, run_id: str) -> AuditRun | None:
        return self.session.scalar(
            select(AuditRun)
            .options(
                selectinload(AuditRun.audit_input),
                selectinload(AuditRun.auth_profiles),
                selectinload(AuditRun.crawl_snapshot),
                selectinload(AuditRun.assets).selectinload(Asset.classification_record),
                selectinload(AuditRun.run_plan).selectinload(RunPlan.scan_batches),
            )
            .where(AuditRun.run_id == run_id),
        )

    def save_run_plan(self, run_plan: RunPlan) -> RunPlan:
        self.session.add(run_plan)
        self.session.flush()
        return run_plan

    def replace_batches(self, run_plan: RunPlan, batches: list[ScanBatch]) -> list[ScanBatch]:
        run_plan.scan_batches = []
        self.session.flush()
        run_plan.scan_batches = batches
        self.session.add(run_plan)
        self.session.flush()
        return batches
