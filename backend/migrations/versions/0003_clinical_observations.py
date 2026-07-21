"""clinical observations

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinical_observations",
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
        sa.Column("observation_type", sa.String(length=30), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column(
            "context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origin", sa.String(length=100), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("method", sa.String(length=100), nullable=True),
        sa.Column("reading_quality", sa.String(length=20), nullable=False, server_default="VALID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clinical_observations_patient_id", "clinical_observations", ["patient_id"])
    op.create_index(
        "ix_clinical_observations_institution_id", "clinical_observations", ["institution_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_clinical_observations_institution_id", table_name="clinical_observations")
    op.drop_index("ix_clinical_observations_patient_id", table_name="clinical_observations")
    op.drop_table("clinical_observations")
