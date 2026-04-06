"""add process flows

Revision ID: 0007_process_flows
Revises: 0006_asset_classifications
Create Date: 2026-04-07 01:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_process_flows"
down_revision = "0006_asset_classifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "process_flows",
        sa.Column("process_flow_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "flow_type",
            sa.Enum(
                "learner_default",
                "quiz_flow",
                "lti_flow",
                name="process_flow_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("flow_name", sa.String(length=255), nullable=False),
        sa.Column("auth_context", sa.JSON(), nullable=False),
        sa.Column("entry_locator", sa.String(length=2048), nullable=False),
        sa.Column("flow_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_process_flows_run_id", "process_flows", ["run_id"], unique=False)

    op.create_table(
        "process_flow_steps",
        sa.Column("process_flow_step_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "process_flow_id",
            sa.String(length=36),
            sa.ForeignKey("process_flows.process_flow_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=64), nullable=False),
        sa.Column(
            "step_status",
            sa.Enum(
                "present",
                "missing",
                name="process_flow_step_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("locator", sa.String(length=2048), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id", "asset_id"], ["assets.run_id", "assets.asset_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("process_flow_id", "step_order", name="uq_process_flow_steps_flow_order"),
    )
    op.create_index("ix_process_flow_steps_process_flow_id", "process_flow_steps", ["process_flow_id"], unique=False)
    op.create_index("ix_process_flow_steps_run_id", "process_flow_steps", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_process_flow_steps_run_id", table_name="process_flow_steps")
    op.drop_index("ix_process_flow_steps_process_flow_id", table_name="process_flow_steps")
    op.drop_table("process_flow_steps")
    op.drop_index("ix_process_flows_run_id", table_name="process_flows")
    op.drop_table("process_flows")
