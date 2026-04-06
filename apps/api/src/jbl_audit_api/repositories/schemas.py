from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from jbl_audit_api.db.models import SchemaRegistryEntry


class SchemaRegistryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_fingerprint(self, fingerprint: str) -> SchemaRegistryEntry | None:
        return self.session.scalar(
            select(SchemaRegistryEntry).where(SchemaRegistryEntry.fingerprint == fingerprint),
        )

    def list_entries(self) -> list[SchemaRegistryEntry]:
        return self.session.scalars(
            select(SchemaRegistryEntry)
            .where(SchemaRegistryEntry.fingerprint.is_not(None))
            .order_by(SchemaRegistryEntry.updated_at.desc()),
        ).all()

    def upsert(
        self,
        *,
        fingerprint: str,
        schema_name: str,
        schema_version: str,
        schema_payload: dict,
        now: datetime,
        run_id: str | None = None,
    ) -> SchemaRegistryEntry:
        record = self.get_by_fingerprint(fingerprint)
        if record is None:
            record = SchemaRegistryEntry(
                schema_registry_entry_id=schema_payload["schema_registry_entry_id"],
                fingerprint=fingerprint,
                run_id=run_id,
                schema_name=schema_name,
                schema_version=schema_version,
                schema_payload=schema_payload,
                created_at=now,
                updated_at=now,
            )
            self.session.add(record)
            self.session.flush()
            return record

        schema_payload["schema_registry_entry_id"] = record.schema_registry_entry_id
        record.run_id = run_id
        record.schema_name = schema_name
        record.schema_version = schema_version
        record.schema_payload = schema_payload
        record.updated_at = now
        self.session.flush()
        return record
