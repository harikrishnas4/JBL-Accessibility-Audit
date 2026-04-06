from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jbl_audit_api.db.models import AuthProfileValidationStatus


class AuthProfileCreateRequest(BaseModel):
    run_id: str
    auth_context: dict[str, Any] = Field(default_factory=dict)
    session_state_path: str | None = None
    validation_status: AuthProfileValidationStatus


class AuthProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auth_profile_id: str
    run_id: str
    auth_context: dict[str, Any]
    session_state_path: str | None
    validation_status: AuthProfileValidationStatus
    created_at: datetime
