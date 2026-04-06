"""add auth profiles

Revision ID: 0004_auth_profiles
Revises: 0003_schema_registry_fingerprint
Create Date: 2026-04-06 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_auth_profiles"
down_revision = "0003_schema_registry_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_profiles",
        sa.Column("auth_profile_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("auth_context", sa.JSON(), nullable=False),
        sa.Column("session_state_path", sa.String(length=2048), nullable=True),
        sa.Column(
            "validation_status",
            sa.Enum(
                "pending",
                "validated",
                "failed",
                name="auth_profile_validation_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_profiles_run_id", "auth_profiles", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_profiles_run_id", table_name="auth_profiles")
    op.drop_table("auth_profiles")
