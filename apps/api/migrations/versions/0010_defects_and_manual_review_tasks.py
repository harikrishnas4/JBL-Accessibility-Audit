"""add defects and manual review tasks

Revision ID: 0010_defects_and_manual_review_tasks
Revises: 0009_raw_findings_and_evidence
Create Date: 2026-04-07 06:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_defects_and_manual_review_tasks"
down_revision = "0009_raw_findings_and_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "defects",
        sa.Column("defect_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.String(length=32), nullable=False),
        sa.Column("defect_signature", sa.String(length=2048), nullable=False),
        sa.Column("rule_id", sa.String(length=255), nullable=False),
        sa.Column("wcag_sc", sa.String(length=32), nullable=True),
        sa.Column(
            "finding_state",
            sa.Enum(
                "pass",
                "fail",
                "needs_manual_review",
                "inapplicable",
                "blocked",
                name="finding_state_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "P1",
                "P2",
                "P3",
                "P4",
                name="defect_priority_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
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
        sa.Column("owner_team", sa.String(length=255), nullable=True),
        sa.Column("shared_key", sa.String(length=255), nullable=True),
        sa.Column("target_fingerprint", sa.String(length=1024), nullable=True),
        sa.Column("message_key", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=4096), nullable=False),
        sa.Column("finding_origin", sa.String(length=64), nullable=False),
        sa.Column("impacted_asset_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "defect_signature", name="uq_defects_run_signature"),
    )
    op.create_index("ix_defects_run_id", "defects", ["run_id"], unique=False)
    op.create_index("ix_defects_issue_id", "defects", ["issue_id"], unique=False)
    op.create_index("ix_defects_rule_id", "defects", ["rule_id"], unique=False)
    op.create_index("ix_defects_shared_key", "defects", ["shared_key"], unique=False)

    op.create_table(
        "defect_components",
        sa.Column("defect_component_id", sa.String(length=36), primary_key=True),
        sa.Column("defect_id", sa.String(length=36), sa.ForeignKey("defects.defect_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column("finding_id", sa.String(length=36), sa.ForeignKey("raw_findings.finding_id", ondelete="SET NULL"), nullable=True),
        sa.Column("shared_key", sa.String(length=255), nullable=True),
        sa.Column("locator", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("defect_id", "asset_id", name="uq_defect_components_defect_asset"),
    )
    op.create_index("ix_defect_components_defect_id", "defect_components", ["defect_id"], unique=False)
    op.create_index("ix_defect_components_run_id", "defect_components", ["run_id"], unique=False)
    op.create_index("ix_defect_components_finding_id", "defect_components", ["finding_id"], unique=False)

    op.create_table(
        "manual_review_tasks",
        sa.Column("manual_review_task_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=True),
        sa.Column("finding_id", sa.String(length=36), sa.ForeignKey("raw_findings.finding_id", ondelete="SET NULL"), nullable=True),
        sa.Column("defect_id", sa.String(length=36), sa.ForeignKey("defects.defect_id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "task_type",
            sa.Enum(
                "finding_review",
                "asset_review",
                "at_validation",
                name="manual_review_task_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                name="manual_review_task_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "P1",
                "P2",
                "P3",
                "P4",
                name="defect_priority_enum",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "source_state",
            sa.Enum(
                "pass",
                "fail",
                "needs_manual_review",
                "inapplicable",
                "blocked",
                name="finding_state_enum",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("task_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_manual_review_tasks_run_id", "manual_review_tasks", ["run_id"], unique=False)
    op.create_index("ix_manual_review_tasks_asset_id", "manual_review_tasks", ["asset_id"], unique=False)
    op.create_index("ix_manual_review_tasks_finding_id", "manual_review_tasks", ["finding_id"], unique=False)
    op.create_index("ix_manual_review_tasks_defect_id", "manual_review_tasks", ["defect_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_manual_review_tasks_defect_id", table_name="manual_review_tasks")
    op.drop_index("ix_manual_review_tasks_finding_id", table_name="manual_review_tasks")
    op.drop_index("ix_manual_review_tasks_asset_id", table_name="manual_review_tasks")
    op.drop_index("ix_manual_review_tasks_run_id", table_name="manual_review_tasks")
    op.drop_table("manual_review_tasks")

    op.drop_index("ix_defect_components_finding_id", table_name="defect_components")
    op.drop_index("ix_defect_components_run_id", table_name="defect_components")
    op.drop_index("ix_defect_components_defect_id", table_name="defect_components")
    op.drop_table("defect_components")

    op.drop_index("ix_defects_shared_key", table_name="defects")
    op.drop_index("ix_defects_rule_id", table_name="defects")
    op.drop_index("ix_defects_issue_id", table_name="defects")
    op.drop_index("ix_defects_run_id", table_name="defects")
    op.drop_table("defects")
