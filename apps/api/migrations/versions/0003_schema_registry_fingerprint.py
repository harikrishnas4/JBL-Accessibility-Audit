"""add schema registry fingerprint

Revision ID: 0003_schema_registry_fingerprint
Revises: 0002_audit_run_slice
Create Date: 2026-04-06 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_schema_registry_fingerprint"
down_revision = "0002_audit_run_slice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schema_registry_entries",
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_schema_registry_entries_fingerprint",
        "schema_registry_entries",
        ["fingerprint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_schema_registry_entries_fingerprint", table_name="schema_registry_entries")
    op.drop_column("schema_registry_entries", "fingerprint")
