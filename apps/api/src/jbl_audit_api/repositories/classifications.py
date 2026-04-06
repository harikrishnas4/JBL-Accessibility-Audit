from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jbl_audit_api.db.models import AssetClassification


class AssetClassificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_run(self, run_id: str) -> list[AssetClassification]:
        return list(
            self.session.scalars(
                select(AssetClassification)
                .where(AssetClassification.run_id == run_id)
                .order_by(AssetClassification.asset_id),
            ),
        )

    def list_for_run_by_asset_ids(self, run_id: str, asset_ids: list[str]) -> list[AssetClassification]:
        if not asset_ids:
            return []
        return list(
            self.session.scalars(
                select(AssetClassification).where(
                    AssetClassification.run_id == run_id,
                    AssetClassification.asset_id.in_(asset_ids),
                ),
            ),
        )

    def save(self, classifications: list[AssetClassification]) -> list[AssetClassification]:
        self.session.add_all(classifications)
        self.session.flush()
        return classifications
