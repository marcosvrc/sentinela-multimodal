"""identity access controls: care_units, patient_care_assignments,
user_sessions, auth_failed_attempts, break_glass_grants, users.active
(secao 5.2 do escopo)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
    )

    op.create_table(
        "care_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "name", name="uq_care_unit_per_tenant"),
    )
    op.create_index("ix_care_units_institution_id", "care_units", ["institution_id"])

    op.create_table(
        "patient_care_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "care_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("care_units.id"),
            nullable=True,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_by", sa.String(length=255), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_patient_care_assignments_patient_id", "patient_care_assignments", ["patient_id"]
    )
    op.create_index(
        "ix_patient_care_assignments_user_id", "patient_care_assignments", ["user_id"]
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("session_token_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "auth_failed_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_auth_failed_attempts_external_subject", "auth_failed_attempts", ["external_subject"]
    )

    op.create_table(
        "break_glass_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id"),
            nullable=False,
        ),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_break_glass_grants_patient_id", "break_glass_grants", ["patient_id"]
    )
    op.create_index("ix_break_glass_grants_user_id", "break_glass_grants", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_break_glass_grants_user_id", table_name="break_glass_grants")
    op.drop_index("ix_break_glass_grants_patient_id", table_name="break_glass_grants")
    op.drop_table("break_glass_grants")

    op.drop_index("ix_auth_failed_attempts_external_subject", table_name="auth_failed_attempts")
    op.drop_table("auth_failed_attempts")

    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index(
        "ix_patient_care_assignments_user_id", table_name="patient_care_assignments"
    )
    op.drop_index(
        "ix_patient_care_assignments_patient_id", table_name="patient_care_assignments"
    )
    op.drop_table("patient_care_assignments")

    op.drop_index("ix_care_units_institution_id", table_name="care_units")
    op.drop_table("care_units")

    op.drop_column("users", "active")
