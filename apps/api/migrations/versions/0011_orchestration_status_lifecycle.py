"""update orchestration status lifecycle

Revision ID: 0011_orchestration_status_lifecycle
Revises: 0010_defects_and_manual_review_tasks
Create Date: 2026-04-07 14:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_orchestration_status_lifecycle"
down_revision = "0010_defects_and_manual_review_tasks"
branch_labels = None
depends_on = None


OLD_RUN_PLAN_STATUS = sa.Enum(
    "awaiting_assets",
    "planned",
    "dispatched",
    "manual_pending",
    name="run_plan_status_enum",
    native_enum=False,
)

NEW_RUN_PLAN_STATUS = sa.Enum(
    "awaiting_assets",
    "queued",
    "running",
    "completed",
    "failed",
    "manual_pending",
    name="run_plan_status_enum",
    native_enum=False,
)

OLD_SCAN_BATCH_STATUS = sa.Enum(
    "planned",
    "dispatched",
    "manual_pending",
    name="scan_batch_status_enum",
    native_enum=False,
)

NEW_SCAN_BATCH_STATUS = sa.Enum(
    "queued",
    "running",
    "completed",
    "failed",
    "manual_pending",
    name="scan_batch_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.execute("UPDATE run_plans SET status = 'queued' WHERE status IN ('planned', 'dispatched')")
    op.execute("UPDATE scan_batches SET status = 'queued' WHERE status IN ('planned', 'dispatched')")

    with op.batch_alter_table("run_plans") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=OLD_RUN_PLAN_STATUS,
            type_=NEW_RUN_PLAN_STATUS,
            existing_nullable=False,
        )

    with op.batch_alter_table("scan_batches") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=OLD_SCAN_BATCH_STATUS,
            type_=NEW_SCAN_BATCH_STATUS,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE run_plans SET status = 'dispatched' WHERE status IN ('queued', 'running', 'completed', 'failed')")
    op.execute("UPDATE scan_batches SET status = 'dispatched' WHERE status IN ('queued', 'running', 'completed', 'failed')")

    with op.batch_alter_table("scan_batches") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=NEW_SCAN_BATCH_STATUS,
            type_=OLD_SCAN_BATCH_STATUS,
            existing_nullable=False,
        )

    with op.batch_alter_table("run_plans") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=NEW_RUN_PLAN_STATUS,
            type_=OLD_RUN_PLAN_STATUS,
            existing_nullable=False,
        )
