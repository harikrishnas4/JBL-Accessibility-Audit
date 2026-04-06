"""add raw findings and evidence artifacts

Revision ID: 0009_raw_findings_and_evidence
Revises: 0008_run_plans_and_scan_batches
Create Date: 2026-04-07 05:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_raw_findings_and_evidence"
down_revision = "0008_run_plans_and_scan_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_findings",
        sa.Column("finding_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column(
            "result_type",
            sa.Enum(
                "violation",
                "pass",
                "incomplete",
                "inapplicable",
                name="raw_finding_result_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(length=255), nullable=False),
        sa.Column("wcag_sc", sa.String(length=32), nullable=True),
        sa.Column("resolution_state", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=64), nullable=True),
        sa.Column("message", sa.String(length=4096), nullable=False),
        sa.Column("target_fingerprint", sa.String(length=1024), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_raw_findings_run_id", "raw_findings", ["run_id"], unique=False)
    op.create_index("ix_raw_findings_asset_id", "raw_findings", ["asset_id"], unique=False)
    op.create_index("ix_raw_findings_rule_id", "raw_findings", ["rule_id"], unique=False)

    op.create_table(
        "evidence_artifacts",
        sa.Column("evidence_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("finding_id", sa.String(length=36), sa.ForeignKey("raw_findings.finding_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column(
            "artifact_type",
            sa.Enum(
                "screenshot",
                "trace",
                "dom_snapshot_reference",
                name="evidence_artifact_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=2048), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_artifacts_finding_id", "evidence_artifacts", ["finding_id"], unique=False)
    op.create_index("ix_evidence_artifacts_run_id", "evidence_artifacts", ["run_id"], unique=False)
    op.create_index("ix_evidence_artifacts_asset_id", "evidence_artifacts", ["asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evidence_artifacts_asset_id", table_name="evidence_artifacts")
    op.drop_index("ix_evidence_artifacts_run_id", table_name="evidence_artifacts")
    op.drop_index("ix_evidence_artifacts_finding_id", table_name="evidence_artifacts")
    op.drop_table("evidence_artifacts")

    op.drop_index("ix_raw_findings_rule_id", table_name="raw_findings")
    op.drop_index("ix_raw_findings_asset_id", table_name="raw_findings")
    op.drop_index("ix_raw_findings_run_id", table_name="raw_findings")
    op.drop_table("raw_findings")
