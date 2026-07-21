"""feature_flags: tela de administracao de IA/multimodalidade

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-16

Linha singleton (id=1) que permite ligar/desligar em runtime: provedor de
LLM (OpenAI/Gemini - Gemini ainda sem adaptador real, ver
app.integrations.llm), quais modalidades de midia (audio/video/imagem)
novas analises aceitam, e os dois motores independentes do worker de
visao computacional (YOLOv8/OpenPose, ADR 0016).

Defaults seguem a mesma convencao "seguro por padrao" do restante do
projeto (LLM_PROVIDER=LOCAL/VISION_PROVIDER=LOCAL/TRANSCRIPTION_PROVIDER=
LOCAL em `.env`): LLM real desligado, multimodalidade toda habilitada
(comportamento historico de upload), visao computacional desligada. Ligar
um provider real e sempre uma acao explicita do administrador na tela de
feature flags.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("llm_provider_enabled", sa.Boolean(), nullable=False),
        sa.Column("llm_provider", sa.String(length=20), nullable=False),
        sa.Column("llm_openai_model", sa.String(length=100), nullable=False),
        sa.Column("llm_gemini_model", sa.String(length=100), nullable=False),
        sa.Column("modality_audio_enabled", sa.Boolean(), nullable=False),
        sa.Column("modality_video_enabled", sa.Boolean(), nullable=False),
        sa.Column("modality_image_enabled", sa.Boolean(), nullable=False),
        sa.Column("vision_detection_enabled", sa.Boolean(), nullable=False),
        sa.Column("vision_pose_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(length=200), nullable=True),
    )

    feature_flags_table = sa.table(
        "feature_flags",
        sa.column("id", sa.Integer),
        sa.column("llm_provider_enabled", sa.Boolean),
        sa.column("llm_provider", sa.String),
        sa.column("llm_openai_model", sa.String),
        sa.column("llm_gemini_model", sa.String),
        sa.column("modality_audio_enabled", sa.Boolean),
        sa.column("modality_video_enabled", sa.Boolean),
        sa.column("modality_image_enabled", sa.Boolean),
        sa.column("vision_detection_enabled", sa.Boolean),
        sa.column("vision_pose_enabled", sa.Boolean),
    )
    op.bulk_insert(
        feature_flags_table,
        [
            {
                "id": 1,
                "llm_provider_enabled": False,
                "llm_provider": "OPENAI",
                "llm_openai_model": "gpt-4o-mini",
                "llm_gemini_model": "gemini-1.5-flash",
                "modality_audio_enabled": True,
                "modality_video_enabled": True,
                "modality_image_enabled": True,
                "vision_detection_enabled": False,
                "vision_pose_enabled": False,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
