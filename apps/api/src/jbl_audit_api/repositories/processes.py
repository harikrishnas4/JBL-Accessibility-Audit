from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import Asset, AuditRun, ProcessFlow


class ProcessRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_context(self, run_id: str) -> AuditRun | None:
        return self.session.scalar(
            select(AuditRun)
            .options(
                selectinload(AuditRun.audit_input),
                selectinload(AuditRun.crawl_snapshot),
                selectinload(AuditRun.assets).selectinload(Asset.classification_record),
                selectinload(AuditRun.process_flows).selectinload(ProcessFlow.steps),
            )
            .where(AuditRun.run_id == run_id),
        )

    def replace_flows_for_run(self, run_id: str, flows: list[ProcessFlow]) -> list[ProcessFlow]:
        existing_flows = list(
            self.session.scalars(
                select(ProcessFlow).where(ProcessFlow.run_id == run_id),
            ),
        )
        for flow in existing_flows:
            self.session.delete(flow)
        self.session.flush()
        self.session.add_all(flows)
        self.session.flush()
        return flows

    def list_flows_for_run(self, run_id: str) -> list[ProcessFlow]:
        return list(
            self.session.scalars(
                select(ProcessFlow)
                .options(selectinload(ProcessFlow.steps))
                .where(ProcessFlow.run_id == run_id)
                .order_by(ProcessFlow.flow_type),
            ),
        )
