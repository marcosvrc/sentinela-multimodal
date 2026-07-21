"""audit events (append-only) + chain state

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sequence",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("analysis_id", sa.String(length=100), nullable=True),
        sa.Column("workflow_id", sa.String(length=100), nullable=True),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_audit_events_institution_id", "audit_events", ["institution_id"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])

    op.create_table(
        "audit_chain_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_hash", sa.String(length=64), nullable=True),
    )

    # Linha singleton que ancora o inicio da cadeia (prev_hash=None no
    # primeiro evento). Ver app.audit.service.record_event.
    audit_chain_state_table = sa.table(
        "audit_chain_state",
        sa.column("id", sa.Integer),
        sa.column("last_hash", sa.String),
    )
    op.bulk_insert(audit_chain_state_table, [{"id": 1, "last_hash": None}])


def downgrade() -> None:
    op.drop_table("audit_chain_state")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_institution_id", table_name="audit_events")
    op.drop_table("audit_events")
