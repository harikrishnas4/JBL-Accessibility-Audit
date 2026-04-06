"""add asset classifications

Revision ID: 0006_asset_classifications
Revises: 0005_inventory_scope_assets
Create Date: 2026-04-07 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_asset_classifications"
down_revision = "0005_inventory_scope_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_classifications",
        sa.Column("classification_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column(
            "layer",
            sa.Enum(
                "platform",
                "course_shell",
                "content",
                "component",
                "document",
                "media",
                "third_party",
                name="asset_layer_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "handling_path",
            sa.Enum(
                "automated",
                "automated_plus_manual",
                "manual_only",
                "evidence_only",
                "excluded",
                name="asset_handling_path_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("shared_key", sa.String(length=255), nullable=True),
        sa.Column("owner_team", sa.String(length=255), nullable=True),
        sa.Column("third_party", sa.Boolean(), nullable=False),
        sa.Column("third_party_evidence", sa.String(length=255), nullable=True),
        sa.Column("auth_context", sa.JSON(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["audit_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id", "asset_id"], ["assets.run_id", "assets.asset_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "asset_id", name="uq_asset_classifications_run_asset"),
    )
    op.create_index("ix_asset_classifications_run_id", "asset_classifications", ["run_id"], unique=False)
    op.create_index("ix_asset_classifications_shared_key", "asset_classifications", ["shared_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_asset_classifications_shared_key", table_name="asset_classifications")
    op.drop_index("ix_asset_classifications_run_id", table_name="asset_classifications")
    op.drop_table("asset_classifications")
