from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from jbl_audit_api.core.dependencies import get_normalization_service
from jbl_audit_api.schemas.defects import DefectListResponse
from jbl_audit_api.services.normalization import NormalizationService

router = APIRouter(tags=["defects"])


@router.get("/defects", response_model=DefectListResponse)
def get_defects(
    run_id: str | None = Query(default=None, max_length=36),
    service: NormalizationService = Depends(get_normalization_service),
) -> DefectListResponse:
    return DefectListResponse.model_validate(service.list_defects(run_id))
