from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from jbl_audit_api.db.models import (
    Asset,
    AssetClassification,
    Defect,
    DefectComponent,
    ManualReviewTask,
    RawFinding,
)


class DefectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_assets_for_run(self, run_id: str) -> list[Asset]:
        return list(
            self.session.scalars(
                select(Asset)
                .options(
                    selectinload(Asset.classification_record).selectinload(
                        AssetClassification.third_party_evidence,
                    ),
                )
                .where(Asset.run_id == run_id)
                .order_by(Asset.asset_id),
            ),
        )

    def list_raw_findings_for_run(self, run_id: str) -> list[RawFinding]:
        return list(
            self.session.scalars(
                select(RawFinding)
                .options(
                    selectinload(RawFinding.asset)
                    .selectinload(Asset.classification_record)
                    .selectinload(AssetClassification.third_party_evidence),
                    selectinload(RawFinding.evidence_artifacts),
                )
                .where(RawFinding.run_id == run_id)
                .order_by(RawFinding.observed_at, RawFinding.finding_id),
            ),
        )

    def replace_run_outputs(
        self,
        run_id: str,
        defects: list[Defect],
        manual_review_tasks: list[ManualReviewTask],
    ) -> None:
        self.session.execute(delete(ManualReviewTask).where(ManualReviewTask.run_id == run_id))
        self.session.execute(delete(DefectComponent).where(DefectComponent.run_id == run_id))
        self.session.execute(delete(Defect).where(Defect.run_id == run_id))
        self.session.flush()
        self.session.add_all(defects)
        self.session.add_all(manual_review_tasks)
        self.session.flush()

    def list_defects(self, run_id: str | None = None) -> list[Defect]:
        statement = (
            select(Defect)
            .options(
                selectinload(Defect.components)
                .selectinload(DefectComponent.asset)
                .selectinload(Asset.classification_record)
                .selectinload(AssetClassification.third_party_evidence),
            )
            .order_by(Defect.issue_id, Defect.defect_id)
        )
        if run_id is not None:
            statement = statement.where(Defect.run_id == run_id)
        return list(self.session.scalars(statement))

    def list_manual_review_tasks_for_run(self, run_id: str) -> list[ManualReviewTask]:
        return list(
            self.session.scalars(
                select(ManualReviewTask)
                .where(ManualReviewTask.run_id == run_id)
                .order_by(ManualReviewTask.created_at, ManualReviewTask.manual_review_task_id),
            ),
        )
