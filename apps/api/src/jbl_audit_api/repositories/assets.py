from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jbl_audit_api.db.models import Asset, CrawlSnapshot


class AssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_crawl_snapshot_for_run(self, run_id: str) -> CrawlSnapshot | None:
        return self.session.scalar(
            select(CrawlSnapshot).where(CrawlSnapshot.run_id == run_id),
        )

    def save_crawl_snapshot(self, crawl_snapshot: CrawlSnapshot) -> CrawlSnapshot:
        self.session.add(crawl_snapshot)
        self.session.flush()
        return crawl_snapshot

    def list_assets_for_run(self, run_id: str) -> list[Asset]:
        return list(
            self.session.scalars(
                select(Asset)
                .where(Asset.run_id == run_id)
                .order_by(Asset.asset_id),
            ),
        )

    def list_assets_for_run_by_ids(self, run_id: str, asset_ids: list[str]) -> list[Asset]:
        if not asset_ids:
            return []
        return list(
            self.session.scalars(
                select(Asset).where(
                    Asset.run_id == run_id,
                    Asset.asset_id.in_(asset_ids),
                ),
            ),
        )

    def save_assets(self, assets: list[Asset]) -> list[Asset]:
        self.session.add_all(assets)
        self.session.flush()
        return assets
