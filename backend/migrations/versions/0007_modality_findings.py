"""modality_findings (item 11)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "modality_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id"),
            nullable=False,
        ),
        sa.Column(
            "modality_state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_modality_states.id"),
            nullable=False,
        ),
        sa.Column("modality_type", sa.String(length=20), nullable=False),
        sa.Column("nature", sa.String(length=40), nullable=False),
        sa.Column("quality_state", sa.String(length=20), nullable=False),
        sa.Column("quality_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_modality_findings_analysis_id", "modality_findings", ["analysis_id"])
    op.create_index(
        "ix_modality_findings_modality_state_id", "modality_findings", ["modality_state_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_modality_findings_modality_state_id", table_name="modality_findings")
    op.drop_index("ix_modality_findings_analysis_id", table_name="modality_findings")
    op.drop_table("modality_findings")
