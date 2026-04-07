from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import AuthProfile
from jbl_audit_api.repositories.auth_profiles import AuthProfileRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.auth_profiles import AuthProfileCreateRequest


class AuthProfileService:
    def __init__(self, repository: AuthProfileRepository, run_repository: RunRepository) -> None:
        self.repository = repository
        self.run_repository = run_repository

    def create_auth_profile(self, payload: AuthProfileCreateRequest) -> AuthProfile:
        if self.run_repository.get(payload.run_id) is None:
            raise NotFoundError(f"run '{payload.run_id}' does not exist")

        now = datetime.now(UTC)
        auth_profile = AuthProfile(
            auth_profile_id=str(uuid.uuid4()),
            run_id=payload.run_id,
            auth_context=payload.auth_context,
            session_state_path=payload.session_state_path,
            validation_status=payload.validation_status,
            created_at=now,
        )
        return self.repository.create(auth_profile)

    def get_auth_profile(self, auth_profile_id: str) -> AuthProfile:
        auth_profile = self.repository.get(auth_profile_id)
        if auth_profile is None:
            raise NotFoundError(f"auth profile '{auth_profile_id}' does not exist")
        return auth_profile
