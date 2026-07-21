"""clinical rule sets: persistencia versionada das regras clinicas

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinical_rule_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("population", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "required_inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "exclusions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", "version", name="uq_rule_set_code_version"),
    )
    op.create_index("ix_clinical_rule_sets_code", "clinical_rule_sets", ["code"])

    op.create_table(
        "clinical_rule_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_rule_sets.id"),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=500), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=False),
    )
    op.create_index(
        "ix_clinical_rule_sources_rule_set_id", "clinical_rule_sources", ["rule_set_id"]
    )

    op.create_table(
        "clinical_rule_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_rule_sets.id"),
            nullable=False,
        ),
        sa.Column("approver", sa.String(length=200), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_clinical_rule_approvals_rule_set_id", "clinical_rule_approvals", ["rule_set_id"]
    )

    op.create_table(
        "clinical_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_rule_sets.id"),
            nullable=False,
        ),
        sa.Column("rule_key", sa.String(length=100), nullable=False),
        sa.Column("risk_level", sa.Integer(), sa.ForeignKey("risk_levels.code"), nullable=False),
        sa.Column("classification_label", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("rule_set_id", "rule_key", name="uq_clinical_rule_key_per_set"),
    )
    op.create_index("ix_clinical_rules_rule_set_id", "clinical_rules", ["rule_set_id"])

    op.create_table(
        "clinical_rule_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_rules.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("expression", sa.Text(), nullable=False),
    )

    op.create_table(
        "clinical_rule_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinical_rule_sets.id"),
            nullable=False,
        ),
        sa.Column("risk_level", sa.Integer(), sa.ForeignKey("risk_levels.code"), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.UniqueConstraint("rule_set_id", "risk_level", name="uq_rule_action_per_risk_level"),
    )
    op.create_index(
        "ix_clinical_rule_actions_rule_set_id", "clinical_rule_actions", ["rule_set_id"]
    )


def downgrade() -> None:
    op.drop_table("clinical_rule_actions")
    op.drop_table("clinical_rule_conditions")
    op.drop_index("ix_clinical_rules_rule_set_id", table_name="clinical_rules")
    op.drop_table("clinical_rules")
    op.drop_index("ix_clinical_rule_approvals_rule_set_id", table_name="clinical_rule_approvals")
    op.drop_table("clinical_rule_approvals")
    op.drop_index("ix_clinical_rule_sources_rule_set_id", table_name="clinical_rule_sources")
    op.drop_table("clinical_rule_sources")
    op.drop_index("ix_clinical_rule_sets_code", table_name="clinical_rule_sets")
    op.drop_table("clinical_rule_sets")
