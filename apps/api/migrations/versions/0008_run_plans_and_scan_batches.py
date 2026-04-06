"""add run plans and scan batches

Revision ID: 0008_run_plans_and_scan_batches
Revises: 0007_process_flows
Create Date: 2026-04-07 03:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_run_plans_and_scan_batches"
down_revision = "0007_process_flows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_plans",
        sa.Column("run_plan_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "awaiting_assets",
                "planned",
                "dispatched",
                "manual_pending",
                name="run_plan_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("dispatcher_name", sa.String(length=128), nullable=False),
        sa.Column("viewport_matrix", sa.JSON(), nullable=False),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("scan_batch_count", sa.Integer(), nullable=False),
        sa.Column("manual_task_count", sa.Integer(), nullable=False),
        sa.Column("orchestration_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_plans_run_id", "run_plans", ["run_id"], unique=True)

    op.create_table(
        "scan_batches",
        sa.Column("scan_batch_id", sa.String(length=36), primary_key=True),
        sa.Column("run_plan_id", sa.String(length=36), sa.ForeignKey("run_plans.run_plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_key", sa.String(length=255), nullable=False),
        sa.Column(
            "batch_type",
            sa.Enum(
                "scan_worker",
                "manual_review_stub",
                name="scan_batch_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "planned",
                "dispatched",
                "manual_pending",
                name="scan_batch_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("chapter_key", sa.String(length=128), nullable=True),
        sa.Column("shared_key", sa.String(length=255), nullable=True),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        sa.Column("viewport_matrix", sa.JSON(), nullable=False),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("task_contract", sa.JSON(), nullable=False),
        sa.Column("dispatcher_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_plan_id", "batch_key", name="uq_scan_batches_plan_batch_key"),
    )
    op.create_index("ix_scan_batches_run_plan_id", "scan_batches", ["run_plan_id"], unique=False)
    op.create_index("ix_scan_batches_run_id", "scan_batches", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_batches_run_id", table_name="scan_batches")
    op.drop_index("ix_scan_batches_run_plan_id", table_name="scan_batches")
    op.drop_table("scan_batches")
    op.drop_index("ix_run_plans_run_id", table_name="run_plans")
    op.drop_table("run_plans")
