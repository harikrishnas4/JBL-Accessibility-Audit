from __future__ import annotations

from fastapi import APIRouter, Depends, status

from jbl_audit_api.core.dependencies import get_auth_profile_service
from jbl_audit_api.schemas.auth_profiles import AuthProfileCreateRequest, AuthProfileResponse
from jbl_audit_api.services.auth_profiles import AuthProfileService

router = APIRouter(tags=["auth_profiles"])


@router.post("/auth-profiles", response_model=AuthProfileResponse, status_code=status.HTTP_201_CREATED)
def create_auth_profile(
    payload: AuthProfileCreateRequest,
    service: AuthProfileService = Depends(get_auth_profile_service),
) -> AuthProfileResponse:
    return AuthProfileResponse.model_validate(service.create_auth_profile(payload))


@router.get("/auth-profiles/{auth_profile_id}", response_model=AuthProfileResponse)
def get_auth_profile(
    auth_profile_id: str,
    service: AuthProfileService = Depends(get_auth_profile_service),
) -> AuthProfileResponse:
    return AuthProfileResponse.model_validate(service.get_auth_profile(auth_profile_id))
