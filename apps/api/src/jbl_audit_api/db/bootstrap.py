from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from jbl_audit_api.db.models import ThirdPartyEvidence

THIRD_PARTY_EVIDENCE_SEEDS = (
    {
        "third_party_evidence_id": "5a9a6d58-0e9a-435a-989c-977f729d1aa1",
        "provider_name": "human.biodigital.com",
        "domain": "human.biodigital.com",
        "status": "cross_origin_blocked",
        "evidence_type": "VPAT_requested",
        "notes": "cross_origin_blocked; VPAT_requested",
        "linked_shared_key": None,
        "provider_key": "human.biodigital.com",
    },
    {
        "third_party_evidence_id": "c8b6dc15-0faf-4db8-a247-94b39f9520d8",
        "provider_name": "cdn-media.jblearning.com",
        "domain": "cdn-media.jblearning.com",
        "status": "handling_notes_only",
        "evidence_type": "handling_notes_only",
        "notes": "handling_notes_only",
        "linked_shared_key": None,
        "provider_key": "cdn-media.jblearning.com",
    },
)


def seed_reference_data(session_factory: sessionmaker) -> None:
    try:
        with session_factory() as session:
            existing_by_provider_key = {
                item.provider_key: item
                for item in session.scalars(select(ThirdPartyEvidence))
            }
            now = datetime.now(UTC)
            changed = False

            for seed in THIRD_PARTY_EVIDENCE_SEEDS:
                existing = existing_by_provider_key.get(seed["provider_key"])
                if existing is None:
                    session.add(
                        ThirdPartyEvidence(
                            **seed,
                            created_at=now,
                            updated_at=now,
                        ),
                    )
                    changed = True
                    continue

                item_changed = False
                for field_name, field_value in seed.items():
                    if getattr(existing, field_name) != field_value:
                        setattr(existing, field_name, field_value)
                        changed = True
                        item_changed = True
                if item_changed:
                    existing.updated_at = now

            if changed:
                session.commit()
    except (OperationalError, ProgrammingError):
        # Local startup should not fail before migrations or create_all have created the table.
        return
