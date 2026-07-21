"""analysis_modality_states + analysis_queue_messages (item 10)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_modality_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id"),
            nullable=False,
        ),
        sa.Column("modality_type", sa.String(length=20), nullable=False),
        sa.Column(
            "media_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_analysis_modality_states_analysis_id", "analysis_modality_states", ["analysis_id"]
    )

    op.create_table(
        "analysis_queue_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("receipt_handle", sa.String(length=64), nullable=True, unique=True),
        sa.Column("visible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_queue_messages_status", "analysis_queue_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_analysis_queue_messages_status", table_name="analysis_queue_messages")
    op.drop_table("analysis_queue_messages")
    op.drop_index("ix_analysis_modality_states_analysis_id", table_name="analysis_modality_states")
    op.drop_table("analysis_modality_states")
