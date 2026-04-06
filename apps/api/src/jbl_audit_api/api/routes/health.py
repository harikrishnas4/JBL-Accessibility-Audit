from __future__ import annotations

from fastapi import APIRouter, Depends

from jbl_audit_api.core.config import Settings
from jbl_audit_api.core.dependencies import get_app_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }
