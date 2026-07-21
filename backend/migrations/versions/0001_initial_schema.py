"""initial schema: institutions, users, patients, risk_levels

Revision ID: 0001
Revises:
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column("external_subject", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_institution_id", "users", ["institution_id"])

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column("medical_record_number", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("registered_sex", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "institution_id", "medical_record_number", name="uq_patient_record_per_tenant"
        ),
    )
    op.create_index("ix_patients_institution_id", "patients", ["institution_id"])

    op.create_table(
        "risk_levels",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=False),
        sa.Column("meaning", sa.String(length=200), nullable=False),
    )

    # Seed idempotente da tabela canonica de risco (secao 5.6 do ESCOPO_PROJETO.md)
    risk_levels_table = sa.table(
        "risk_levels",
        sa.column("code", sa.Integer),
        sa.column("label", sa.String),
        sa.column("color_hex", sa.String),
        sa.column("meaning", sa.String),
    )
    op.bulk_insert(
        risk_levels_table,
        [
            {
                "code": 1,
                "label": "Baixo",
                "color_hex": "#2E7D32",
                "meaning": "Registrar e seguir rotina",
            },
            {
                "code": 2,
                "label": "Leve",
                "color_hex": "#F9A825",
                "meaning": "Acompanhar ou repetir medicao",
            },
            {
                "code": 3,
                "label": "Moderado",
                "color_hex": "#EF6C00",
                "meaning": "Solicitar avaliacao clinica",
            },
            {
                "code": 4,
                "label": "Alto",
                "color_hex": "#C62828",
                "meaning": "Alertar equipe assistencial",
            },
            {
                "code": 5,
                "label": "Muito alto",
                "color_hex": "#6A1B9A",
                "meaning": "Intervencao prioritaria",
            },
            {
                "code": 6,
                "label": "Critico",
                "color_hex": "#4A0000",
                "meaning": "Seguir protocolo de emergencia",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("risk_levels")
    op.drop_index("ix_patients_institution_id", table_name="patients")
    op.drop_table("patients")
    op.drop_index("ix_users_institution_id", table_name="users")
    op.drop_table("users")
    op.drop_table("institutions")
