"""structured_clinical_inputs + risk_consolidations (item 12)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "structured_clinical_inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    op.create_table(
        "risk_consolidations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.Integer(), sa.ForeignKey("risk_levels.code"), nullable=True),
        sa.Column("classification_label", sa.String(length=200), nullable=True),
        sa.Column("inconclusive_reason", sa.String(length=40), nullable=True),
        sa.Column("inconclusive_detail", sa.Text(), nullable=True),
        sa.Column("code_evaluations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_status", sa.String(length=20), nullable=False),
        sa.Column("llm_summary", sa.Text(), nullable=True),
        sa.Column("llm_uncertainty_note", sa.Text(), nullable=True),
        sa.Column("llm_error", sa.String(length=500), nullable=True),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("llm_prompt_version", sa.String(length=50), nullable=True),
        sa.Column("llm_input_hash", sa.String(length=64), nullable=True),
        sa.Column("llm_output_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_risk_consolidations_analysis_id", "risk_consolidations", ["analysis_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_risk_consolidations_analysis_id", table_name="risk_consolidations")
    op.drop_table("risk_consolidations")
    op.drop_column("analyses", "structured_clinical_inputs")
