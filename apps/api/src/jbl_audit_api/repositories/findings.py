from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import Asset, RawFinding


class FindingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_asset(self, run_id: str, asset_id: str) -> Asset | None:
        return self.session.scalar(
            select(Asset).where(
                Asset.run_id == run_id,
                Asset.asset_id == asset_id,
            ),
        )

    def save_findings(self, findings: list[RawFinding]) -> list[RawFinding]:
        self.session.add_all(findings)
        self.session.flush()
        return findings

    def list_findings_for_run(self, run_id: str) -> list[RawFinding]:
        return list(
            self.session.scalars(
                select(RawFinding)
                .options(selectinload(RawFinding.evidence_artifacts))
                .where(RawFinding.run_id == run_id)
                .order_by(RawFinding.observed_at, RawFinding.finding_id),
            ),
        )
