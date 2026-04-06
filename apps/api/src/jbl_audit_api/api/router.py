from __future__ import annotations

from fastapi import APIRouter

from jbl_audit_api.api.routes.assets import router as assets_router
from jbl_audit_api.api.routes.defects import router as defects_router
from jbl_audit_api.api.routes.auth_profiles import router as auth_profiles_router
from jbl_audit_api.api.routes.health import router as health_router
from jbl_audit_api.api.routes.processes import router as processes_router
from jbl_audit_api.api.routes.runs import router as runs_router
from jbl_audit_api.api.routes.schemas import router as schemas_router


router = APIRouter()
router.include_router(assets_router)
router.include_router(defects_router)
router.include_router(auth_profiles_router)
router.include_router(health_router)
router.include_router(processes_router)
router.include_router(runs_router)
router.include_router(schemas_router)
