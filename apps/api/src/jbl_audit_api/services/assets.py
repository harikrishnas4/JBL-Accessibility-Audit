from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import Asset, AssetClassification, CrawlSnapshot
from jbl_audit_api.repositories.assets import AssetRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.assets import AssetUpsertRequest
from jbl_audit_api.services.classifications import AssetClassificationService
from jbl_audit_api.services.normalization import NormalizationService
from jbl_audit_api.services.orchestration import OrchestrationService


class AssetService:
    def __init__(
        self,
        repository: AssetRepository,
        run_repository: RunRepository,
        classification_service: AssetClassificationService,
        normalization_service: NormalizationService,
        orchestration_service: OrchestrationService,
    ) -> None:
        self.repository = repository
        self.run_repository = run_repository
        self.classification_service = classification_service
        self.normalization_service = normalization_service
        self.orchestration_service = orchestration_service

    def upsert_assets(
        self,
        payload: AssetUpsertRequest,
    ) -> tuple[CrawlSnapshot, list[Asset], list[AssetClassification]]:
        if self.run_repository.get(payload.run_id) is None:
            raise NotFoundError(f"run '{payload.run_id}' does not exist")

        now = datetime.now(UTC)
        crawl_snapshot = self.repository.get_crawl_snapshot_for_run(payload.run_id)
        if crawl_snapshot is None:
            crawl_snapshot = CrawlSnapshot(
                crawl_snapshot_id=str(uuid.uuid4()),
                run_id=payload.run_id,
                entry_locator=payload.crawl_snapshot.entry_locator,
                started_at=payload.crawl_snapshot.started_at,
                completed_at=payload.crawl_snapshot.completed_at,
                visited_locators=payload.crawl_snapshot.visited_locators,
                excluded_locators=[item.model_dump() for item in payload.crawl_snapshot.excluded_locators],
                snapshot_metadata=payload.crawl_snapshot.snapshot_metadata,
                created_at=now,
                updated_at=now,
            )
        else:
            crawl_snapshot.entry_locator = payload.crawl_snapshot.entry_locator
            crawl_snapshot.started_at = payload.crawl_snapshot.started_at
            crawl_snapshot.completed_at = payload.crawl_snapshot.completed_at
            crawl_snapshot.visited_locators = payload.crawl_snapshot.visited_locators
            crawl_snapshot.excluded_locators = [
                item.model_dump() for item in payload.crawl_snapshot.excluded_locators
            ]
            crawl_snapshot.snapshot_metadata = payload.crawl_snapshot.snapshot_metadata
            crawl_snapshot.updated_at = now
        self.repository.save_crawl_snapshot(crawl_snapshot)

        existing_assets = {
            asset.asset_id: asset
            for asset in self.repository.list_assets_for_run_by_ids(
                payload.run_id,
                [item.asset_id for item in payload.assets],
            )
        }

        assets_to_save: list[Asset] = []
        for item in payload.assets:
            asset = existing_assets.get(item.asset_id)
            if asset is None:
                asset = Asset(
                    run_id=payload.run_id,
                    asset_id=item.asset_id,
                    created_at=now,
                )
            asset.crawl_snapshot_id = crawl_snapshot.crawl_snapshot_id
            asset.asset_type = item.asset_type
            asset.source_system = item.source_system
            asset.locator = item.locator
            asset.scope_status = item.scope_status
            asset.scope_reason = item.scope_reason
            asset.layer = item.layer
            asset.shared_key = item.shared_key
            asset.owner_team = item.owner_team
            asset.auth_context = item.auth_context
            asset.handling_path = item.handling_path
            asset.component_fingerprint = item.component_fingerprint
            asset.updated_at = item.updated_at
            assets_to_save.append(asset)

        self.repository.save_assets(assets_to_save)
        persisted_assets = self.repository.list_assets_for_run(payload.run_id)
        classifications = self.classification_service.classify_assets(
            payload.run_id,
            persisted_assets,
            payload.manifest_context,
        )
        self.normalization_service.sync_run(payload.run_id)
        self.orchestration_service.refresh_run_plan(payload.run_id)
        return crawl_snapshot, persisted_assets, classifications
