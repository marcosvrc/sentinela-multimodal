"""administration: medical_specialties, employees (item 5.3)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_specialties",
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
        sa.UniqueConstraint("institution_id", "name", name="uq_specialty_name_per_tenant"),
    )
    op.create_index(
        "ix_medical_specialties_institution_id", "medical_specialties", ["institution_id"]
    )

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "specialty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medical_specialties.id"),
            nullable=True,
        ),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=False),
        sa.Column("registration_number", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "cpf", name="uq_employee_cpf_per_tenant"),
        sa.UniqueConstraint(
            "institution_id",
            "registration_number",
            name="uq_employee_registration_per_tenant",
        ),
    )
    op.create_index("ix_employees_institution_id", "employees", ["institution_id"])
    op.create_index("ix_employees_specialty_id", "employees", ["specialty_id"])

    # `clinical_rule_approvals.decision` (criada na migration 0002) so
    # aceitava "approved"/"rejected" (20 caracteres bastavam). O fluxo de
    # publicacao/rollback do item 5.3 introduz decisoes mais descritivas
    # (`retired_by_new_publication` tem 26 caracteres) - alargar a coluna
    # em vez de abreviar o vocabulario.
    op.alter_column(
        "clinical_rule_approvals",
        "decision",
        type_=sa.String(length=30),
        existing_type=sa.String(length=20),
    )


def downgrade() -> None:
    op.alter_column(
        "clinical_rule_approvals",
        "decision",
        type_=sa.String(length=20),
        existing_type=sa.String(length=30),
    )

    op.drop_index("ix_employees_specialty_id", table_name="employees")
    op.drop_index("ix_employees_institution_id", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_medical_specialties_institution_id", table_name="medical_specialties")
    op.drop_table("medical_specialties")
