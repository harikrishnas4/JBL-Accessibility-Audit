"""add crawl snapshots and assets

Revision ID: 0005_inventory_scope_assets
Revises: 0004_auth_profiles
Create Date: 2026-04-06 23:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_inventory_scope_assets"
down_revision = "0004_auth_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_snapshots",
        sa.Column("crawl_snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_locator", sa.String(length=2048), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visited_locators", sa.JSON(), nullable=False),
        sa.Column("excluded_locators", sa.JSON(), nullable=False),
        sa.Column("snapshot_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crawl_snapshots_run_id", "crawl_snapshots", ["run_id"], unique=True)

    op.create_table(
        "assets",
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column(
            "crawl_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("crawl_snapshots.crawl_snapshot_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asset_type", sa.String(length=128), nullable=False),
        sa.Column("source_system", sa.String(length=255), nullable=False),
        sa.Column("locator", sa.String(length=2048), nullable=False),
        sa.Column(
            "scope_status",
            sa.Enum(
                "in_scope",
                "out_of_scope",
                name="asset_scope_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("scope_reason", sa.String(length=512), nullable=True),
        sa.Column("layer", sa.String(length=128), nullable=False),
        sa.Column("shared_key", sa.String(length=255), nullable=True),
        sa.Column("owner_team", sa.String(length=255), nullable=True),
        sa.Column("auth_context", sa.JSON(), nullable=False),
        sa.Column("handling_path", sa.String(length=255), nullable=False),
        sa.Column("component_fingerprint", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "asset_id"),
    )
    op.create_index("ix_assets_crawl_snapshot_id", "assets", ["crawl_snapshot_id"], unique=False)
    op.create_index("ix_assets_shared_key", "assets", ["shared_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assets_shared_key", table_name="assets")
    op.drop_index("ix_assets_crawl_snapshot_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_crawl_snapshots_run_id", table_name="crawl_snapshots")
    op.drop_table("crawl_snapshots")
