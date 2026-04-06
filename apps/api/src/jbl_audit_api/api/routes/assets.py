from __future__ import annotations

from fastapi import APIRouter, Depends, status

from jbl_audit_api.core.dependencies import get_asset_service
from jbl_audit_api.schemas.assets import AssetResponse, AssetUpsertRequest, AssetUpsertResponse, CrawlSnapshotResponse
from jbl_audit_api.schemas.classifications import AssetClassificationResponse
from jbl_audit_api.services.assets import AssetService

router = APIRouter(tags=["assets"])


@router.post("/assets/upsert", response_model=AssetUpsertResponse, status_code=status.HTTP_201_CREATED)
def upsert_assets(
    payload: AssetUpsertRequest,
    service: AssetService = Depends(get_asset_service),
) -> AssetUpsertResponse:
    crawl_snapshot, assets, classifications = service.upsert_assets(payload)
    return AssetUpsertResponse(
        run_id=payload.run_id,
        crawl_snapshot=CrawlSnapshotResponse.model_validate(crawl_snapshot),
        assets=[AssetResponse.model_validate(asset) for asset in assets],
        classifications=[
            AssetClassificationResponse.model_validate(classification)
            for classification in classifications
        ],
    )
