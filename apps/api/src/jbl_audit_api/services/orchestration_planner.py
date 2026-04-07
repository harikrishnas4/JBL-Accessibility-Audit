from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from jbl_audit_api.db.models import Asset, AssetClassification, AssetHandlingPath, ScanBatchType

VIEWPORT_MATRIX: tuple[dict[str, int | str], ...] = (
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 375, "height": 667},
)

DEFAULT_RETRY_POLICY: dict[str, int | str] = {
    "strategy": "fixed",
    "max_attempts": 2,
    "backoff_seconds": 30,
}


@dataclass(slots=True, frozen=True)
class PlannedBatch:
    batch_key: str
    batch_type: ScanBatchType
    chapter_key: str | None
    shared_key: str | None
    asset_ids: tuple[str, ...]
    viewport_matrix: tuple[dict[str, int | str], ...]
    retry_policy: dict[str, int | str]
    task_contract: dict


@dataclass(slots=True, frozen=True)
class BatchPlanningResult:
    planned_batches: tuple[PlannedBatch, ...]
    excluded_asset_ids: tuple[str, ...]
    manual_asset_ids: tuple[str, ...]
    scan_asset_ids: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ClassifiedAssetContext:
    asset: Asset
    classification: AssetClassification


class BatchPlanner:
    def plan(
        self,
        assets: list[ClassifiedAssetContext],
        *,
        manifest_metadata: dict | None,
        crawl_snapshot_metadata: dict | None,
    ) -> BatchPlanningResult:
        excluded_asset_ids: list[str] = []
        manual_asset_ids: list[str] = []
        scan_asset_ids: list[str] = []
        grouped_assets: dict[tuple[str, str, str], list[ClassifiedAssetContext]] = {}

        for item in assets:
            handling_path = item.classification.handling_path
            if item.classification.exclusion_reason or handling_path == AssetHandlingPath.excluded:
                excluded_asset_ids.append(item.asset.asset_id)
                continue

            batch_type = self._resolve_batch_type(handling_path)
            chapter_key = self._resolve_chapter_key(
                item.asset.locator,
                manifest_metadata=manifest_metadata,
                crawl_snapshot_metadata=crawl_snapshot_metadata,
            )
            shared_key = item.classification.shared_key
            group_key = (
                batch_type.value,
                chapter_key or "__unassigned__",
                shared_key or item.asset.asset_id,
            )
            grouped_assets.setdefault(group_key, []).append(item)

            if batch_type == ScanBatchType.scan_worker:
                scan_asset_ids.append(item.asset.asset_id)
            else:
                manual_asset_ids.append(item.asset.asset_id)

        planned_batches = tuple(
            self._build_batch(
                batch_assets,
                batch_type=ScanBatchType(group_key[0]),
                chapter_key=None if group_key[1] == "__unassigned__" else group_key[1],
                shared_key=group_key[2]
                if any(item.classification.shared_key == group_key[2] for item in batch_assets)
                else None,
            )
            for group_key, batch_assets in sorted(grouped_assets.items(), key=lambda entry: entry[0])
        )
        return BatchPlanningResult(
            planned_batches=planned_batches,
            excluded_asset_ids=tuple(sorted(set(excluded_asset_ids))),
            manual_asset_ids=tuple(sorted(set(manual_asset_ids))),
            scan_asset_ids=tuple(sorted(set(scan_asset_ids))),
        )

    def _build_batch(
        self,
        batch_assets: list[ClassifiedAssetContext],
        *,
        batch_type: ScanBatchType,
        chapter_key: str | None,
        shared_key: str | None,
    ) -> PlannedBatch:
        asset_ids = tuple(sorted(item.asset.asset_id for item in batch_assets))
        batch_key = f"{batch_type.value}:{chapter_key or 'unassigned'}:{shared_key or asset_ids[0]}"
        viewport_matrix = VIEWPORT_MATRIX if batch_type == ScanBatchType.scan_worker else ()
        retry_policy = dict(DEFAULT_RETRY_POLICY)

        if batch_type == ScanBatchType.scan_worker:
            task_contract = {
                "contract_type": "scan_worker_contract_v1",
                "assets": [
                    {
                        "asset_id": item.asset.asset_id,
                        "asset_type": item.asset.asset_type,
                        "locator": item.asset.locator,
                        "layer": item.classification.layer.value,
                        "shared_key": item.classification.shared_key,
                        "owner_team": item.classification.owner_team,
                        "handling_path": item.classification.handling_path.value,
                    }
                    for item in sorted(batch_assets, key=lambda entry: entry.asset.asset_id)
                ],
                "viewports": list(viewport_matrix),
                "retry_policy": retry_policy,
            }
        else:
            task_contract = {
                "contract_type": "manual_task_stub_v1",
                "assets": [
                    {
                        "asset_id": item.asset.asset_id,
                        "asset_type": item.asset.asset_type,
                        "locator": item.asset.locator,
                        "layer": item.classification.layer.value,
                        "owner_team": item.classification.owner_team,
                        "handling_path": item.classification.handling_path.value,
                    }
                    for item in sorted(batch_assets, key=lambda entry: entry.asset.asset_id)
                ],
                "reason": "manual_only_or_evidence_only",
            }

        return PlannedBatch(
            batch_key=batch_key,
            batch_type=batch_type,
            chapter_key=chapter_key,
            shared_key=shared_key,
            asset_ids=asset_ids,
            viewport_matrix=tuple(viewport_matrix),
            retry_policy=retry_policy,
            task_contract=task_contract,
        )

    def _resolve_batch_type(self, handling_path: AssetHandlingPath) -> ScanBatchType:
        if handling_path in {AssetHandlingPath.automated, AssetHandlingPath.automated_plus_manual}:
            return ScanBatchType.scan_worker
        return ScanBatchType.manual_review_stub

    def _resolve_chapter_key(
        self,
        locator: str,
        *,
        manifest_metadata: dict | None,
        crawl_snapshot_metadata: dict | None,
    ) -> str | None:
        for source in (manifest_metadata or {}, crawl_snapshot_metadata or {}):
            chapter_map = source.get("chapter_by_locator")
            if isinstance(chapter_map, dict):
                chapter = chapter_map.get(locator)
                if isinstance(chapter, str) and chapter.strip():
                    return chapter.strip()

        query = parse_qs(urlsplit(locator).query)
        if "chapter" in query and query["chapter"]:
            return query["chapter"][0]
        return None
