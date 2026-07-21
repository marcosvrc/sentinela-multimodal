"""remove aws-only columns and tables (projeto passa a usar apenas Azure
como nuvem gerenciada)

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-21

Remove o que so existia para suportar adaptadores AWS ou o fluxo Cognito,
ja retirados do codigo (ver docs/adr - decisao de usar exclusivamente
Azure Cognitive Services como nuvem gerenciada, sem infraestrutura AWS):

- `feature_flags.image_recognition_provider` / `sentiment_analysis_provider`:
  so escolhiam entre AWS/Azure; agora ha um unico adaptador real (Azure) por
  enriquecimento, sem opcao de provedor.
- `feature_flags.vision_rekognition_video_enabled`: toggle do Amazon
  Rekognition Video, sem equivalente Azure e removido do codigo.
- `feature_flags.llm_bedrock_model`: modelo do Amazon Bedrock, adaptador
  removido (fica OpenAI/local).
- `user_sessions` / `auth_failed_attempts`: sessao revogavel e bloqueio por
  tentativa so faziam sentido com o adaptador de identidade Cognito
  (token real, MFA); o adaptador de identidade agora e exclusivamente
  local (`X-Dev-Subject`, dev/testes).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("feature_flags", "sentiment_analysis_provider")
    op.drop_column("feature_flags", "image_recognition_provider")
    op.drop_column("feature_flags", "vision_rekognition_video_enabled")
    op.drop_column("feature_flags", "llm_bedrock_model")

    op.drop_index("ix_auth_failed_attempts_external_subject", table_name="auth_failed_attempts")
    op.drop_table("auth_failed_attempts")

    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")


def downgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("session_token_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "auth_failed_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_auth_failed_attempts_external_subject", "auth_failed_attempts", ["external_subject"]
    )

    op.add_column(
        "feature_flags",
        sa.Column(
            "llm_bedrock_model",
            sa.String(length=200),
            nullable=False,
            server_default="anthropic.claude-3-5-sonnet-20241022-v2:0",
        ),
    )
    op.add_column(
        "feature_flags",
        sa.Column(
            "vision_rekognition_video_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "feature_flags",
        sa.Column(
            "image_recognition_provider",
            sa.String(length=20),
            nullable=False,
            server_default="AWS_REKOGNITION",
        ),
    )
    op.add_column(
        "feature_flags",
        sa.Column(
            "sentiment_analysis_provider",
            sa.String(length=20),
            nullable=False,
            server_default="AWS_COMPREHEND",
        ),
    )
