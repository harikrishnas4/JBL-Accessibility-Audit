"""add third-party evidence catalog

Revision ID: 0012_third_party_evidence_catalog
Revises: 0011_orchestration_status_lifecycle
Create Date: 2026-04-07 18:10:00
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0012_third_party_evidence_catalog"
down_revision = "0011_orchestration_status_lifecycle"
branch_labels = None
depends_on = None


BIODIGITAL_EVIDENCE_ID = "5a9a6d58-0e9a-435a-989c-977f729d1aa1"
CDN_MEDIA_EVIDENCE_ID = "c8b6dc15-0faf-4db8-a247-94b39f9520d8"


def upgrade() -> None:
    op.create_table(
        "third_party_evidence",
        sa.Column("third_party_evidence_id", sa.String(length=36), primary_key=True),
        sa.Column("provider_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=128), nullable=False),
        sa.Column("evidence_type", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("linked_shared_key", sa.String(length=255), nullable=True),
        sa.Column("provider_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_key", name="uq_third_party_evidence_provider_key"),
    )
    op.create_index("ix_third_party_evidence_domain", "third_party_evidence", ["domain"], unique=False)
    op.create_index(
        "ix_third_party_evidence_linked_shared_key",
        "third_party_evidence",
        ["linked_shared_key"],
        unique=False,
    )

    now = datetime.now(timezone.utc)
    evidence_table = sa.table(
        "third_party_evidence",
        sa.column("third_party_evidence_id", sa.String(length=36)),
        sa.column("provider_name", sa.String(length=255)),
        sa.column("domain", sa.String(length=255)),
        sa.column("status", sa.String(length=128)),
        sa.column("evidence_type", sa.String(length=128)),
        sa.column("notes", sa.String(length=1024)),
        sa.column("linked_shared_key", sa.String(length=255)),
        sa.column("provider_key", sa.String(length=255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        evidence_table,
        [
            {
                "third_party_evidence_id": BIODIGITAL_EVIDENCE_ID,
                "provider_name": "human.biodigital.com",
                "domain": "human.biodigital.com",
                "status": "cross_origin_blocked",
                "evidence_type": "VPAT_requested",
                "notes": "cross_origin_blocked; VPAT_requested",
                "linked_shared_key": None,
                "provider_key": "human.biodigital.com",
                "created_at": now,
                "updated_at": now,
            },
            {
                "third_party_evidence_id": CDN_MEDIA_EVIDENCE_ID,
                "provider_name": "cdn-media.jblearning.com",
                "domain": "cdn-media.jblearning.com",
                "status": "handling_notes_only",
                "evidence_type": "handling_notes_only",
                "notes": "handling_notes_only",
                "linked_shared_key": None,
                "provider_key": "cdn-media.jblearning.com",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    with op.batch_alter_table("asset_classifications") as batch_op:
        batch_op.add_column(sa.Column("third_party_evidence_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            "ix_asset_classifications_third_party_evidence_id",
            ["third_party_evidence_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_asset_classifications_third_party_evidence_id",
            "third_party_evidence",
            ["third_party_evidence_id"],
            ["third_party_evidence_id"],
            ondelete="SET NULL",
        )

    op.execute(
        f"""
        UPDATE asset_classifications
        SET third_party_evidence_id = '{BIODIGITAL_EVIDENCE_ID}'
        WHERE EXISTS (
            SELECT 1
            FROM assets
            WHERE assets.run_id = asset_classifications.run_id
              AND assets.asset_id = asset_classifications.asset_id
              AND (
                  assets.source_system = 'human.biodigital.com'
                  OR assets.locator LIKE '%human.biodigital.com%'
              )
        )
        """,
    )
    op.execute(
        f"""
        UPDATE asset_classifications
        SET third_party_evidence_id = '{CDN_MEDIA_EVIDENCE_ID}'
        WHERE EXISTS (
            SELECT 1
            FROM assets
            WHERE assets.run_id = asset_classifications.run_id
              AND assets.asset_id = asset_classifications.asset_id
              AND (
                  assets.source_system = 'cdn-media.jblearning.com'
                  OR assets.locator LIKE '%cdn-media.jblearning.com%'
              )
        )
        """,
    )

    with op.batch_alter_table("asset_classifications") as batch_op:
        batch_op.drop_column("third_party_evidence")


def downgrade() -> None:
    with op.batch_alter_table("asset_classifications") as batch_op:
        batch_op.add_column(sa.Column("third_party_evidence", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE asset_classifications
        SET third_party_evidence = (
            SELECT third_party_evidence.domain
            FROM third_party_evidence
            WHERE third_party_evidence.third_party_evidence_id = asset_classifications.third_party_evidence_id
        )
        """,
    )

    with op.batch_alter_table("asset_classifications") as batch_op:
        batch_op.drop_constraint("fk_asset_classifications_third_party_evidence_id", type_="foreignkey")
        batch_op.drop_index("ix_asset_classifications_third_party_evidence_id")
        batch_op.drop_column("third_party_evidence_id")

    op.drop_index("ix_third_party_evidence_linked_shared_key", table_name="third_party_evidence")
    op.drop_index("ix_third_party_evidence_domain", table_name="third_party_evidence")
    op.drop_table("third_party_evidence")
