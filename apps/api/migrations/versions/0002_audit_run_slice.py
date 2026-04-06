"""add audit run intake slice

Revision ID: 0002_audit_run_slice
Revises: 0001_baseline
Create Date: 2026-04-06 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_audit_run_slice"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "in_progress",
                "completed",
                "failed",
                name="audit_run_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "current_stage",
            sa.Enum(
                "intake",
                "orchestration",
                "completed",
                "failed",
                name="audit_run_stage_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Enum(
                "manifest/full",
                "partial",
                "crawler_only",
                name="audit_run_mode_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_inputs",
        sa.Column("input_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_url_or_name", sa.String(length=2048), nullable=False),
        sa.Column("auth_metadata", sa.JSON(), nullable=False),
        sa.Column("manifest_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_audit_inputs_run_id"),
    )
    op.create_index("ix_audit_inputs_run_id", "audit_inputs", ["run_id"], unique=False)

    op.create_table(
        "schema_registry_entries",
        sa.Column("schema_registry_entry_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("audit_runs.run_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("schema_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schema_registry_entries_run_id", "schema_registry_entries", ["run_id"], unique=False)

    op.create_table(
        "report_records",
        sa.Column("report_record_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("report_uri", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_records_run_id", "report_records", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_report_records_run_id", table_name="report_records")
    op.drop_table("report_records")
    op.drop_index("ix_schema_registry_entries_run_id", table_name="schema_registry_entries")
    op.drop_table("schema_registry_entries")
    op.drop_index("ix_audit_inputs_run_id", table_name="audit_inputs")
    op.drop_table("audit_inputs")
    op.drop_table("audit_runs")
