"""clinical_alerts: anomaly detection alerts (item 4.5)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinical_alerts",
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
            "observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_observations.id"),
            nullable=True,
        ),
        sa.Column("signal_key", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("detector_source", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("expected_action", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=200), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_to", sa.String(length=200), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clinical_alerts_institution_id", "clinical_alerts", ["institution_id"])
    op.create_index("ix_clinical_alerts_patient_id", "clinical_alerts", ["patient_id"])
    op.create_index("ix_clinical_alerts_status", "clinical_alerts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_clinical_alerts_status", table_name="clinical_alerts")
    op.drop_index("ix_clinical_alerts_patient_id", table_name="clinical_alerts")
    op.drop_index("ix_clinical_alerts_institution_id", table_name="clinical_alerts")
    op.drop_table("clinical_alerts")
