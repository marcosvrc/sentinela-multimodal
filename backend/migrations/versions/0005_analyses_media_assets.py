"""analyses + media_assets (upload/quarantine)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyses",
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
        sa.Column("status", sa.String(length=30), nullable=False, server_default="CREATED"),
        sa.Column("additional_text", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_analyses_institution_id", "analyses", ["institution_id"])
    op.create_index("ix_analyses_patient_id", "analyses", ["patient_id"])

    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id"),
            nullable=False,
        ),
        sa.Column("modality_type", sa.String(length=20), nullable=False),
        sa.Column(
            "upload_state", sa.String(length=20), nullable=False, server_default="AWAITING_UPLOAD"
        ),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_mime_type", sa.String(length=100), nullable=False),
        sa.Column("declared_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=True),
        sa.Column("actual_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("rejection_reason", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_media_assets_institution_id", "media_assets", ["institution_id"])
    op.create_index("ix_media_assets_analysis_id", "media_assets", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_media_assets_analysis_id", table_name="media_assets")
    op.drop_index("ix_media_assets_institution_id", table_name="media_assets")
    op.drop_table("media_assets")
    op.drop_index("ix_analyses_patient_id", table_name="analyses")
    op.drop_index("ix_analyses_institution_id", table_name="analyses")
    op.drop_table("analyses")
