from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jbl_audit_api.db.models import AuthProfile


class AuthProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, auth_profile: AuthProfile) -> AuthProfile:
        self.session.add(auth_profile)
        self.session.flush()
        return auth_profile

    def get(self, auth_profile_id: str) -> AuthProfile | None:
        return self.session.scalar(
            select(AuthProfile).where(AuthProfile.auth_profile_id == auth_profile_id),
        )
