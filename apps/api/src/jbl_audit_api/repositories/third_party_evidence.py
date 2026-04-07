from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jbl_audit_api.db.models import ThirdPartyEvidence


class ThirdPartyEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[ThirdPartyEvidence]:
        return list(
            self.session.scalars(
                select(ThirdPartyEvidence).order_by(
                    ThirdPartyEvidence.domain,
                    ThirdPartyEvidence.provider_key,
                    ThirdPartyEvidence.linked_shared_key,
                ),
            ),
        )
