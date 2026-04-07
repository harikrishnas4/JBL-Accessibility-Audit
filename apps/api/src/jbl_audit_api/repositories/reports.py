from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import Asset, AssetClassification, AuditRun, Defect, RawFinding, ReportRecord


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_context(self, run_id: str) -> AuditRun | None:
        return self.session.scalar(
            select(AuditRun)
            .options(
                selectinload(AuditRun.audit_input),
                selectinload(AuditRun.auth_profiles),
                selectinload(AuditRun.assets)
                .selectinload(Asset.classification_record)
                .selectinload(AssetClassification.third_party_evidence),
                selectinload(AuditRun.defects).selectinload(Defect.components),
                selectinload(AuditRun.report_records),
            )
            .where(AuditRun.run_id == run_id),
        )

    def list_raw_findings_by_ids(self, finding_ids: list[str]) -> list[RawFinding]:
        if not finding_ids:
            return []
        return list(
            self.session.scalars(
                select(RawFinding)
                .options(selectinload(RawFinding.evidence_artifacts))
                .where(RawFinding.finding_id.in_(finding_ids)),
            ),
        )

    def get_report_record(self, run_id: str, report_type: str) -> ReportRecord | None:
        return self.session.scalar(
            select(ReportRecord).where(
                ReportRecord.run_id == run_id,
                ReportRecord.report_type == report_type,
            ),
        )

    def save_report_record(self, report_record: ReportRecord) -> ReportRecord:
        self.session.add(report_record)
        self.session.flush()
        return report_record
