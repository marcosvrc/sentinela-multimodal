"""feature_flags: toggles Amazon Rekognition (imagem/video)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-16

Dois novos toggles independentes na linha singleton de feature flags:

- `image_recognition_enabled`: liga Amazon Rekognition Image
  (`DetectLabels`) como enriquecimento OPCIONAL do processador de imagem
  (`app.processors.image`) - nunca substitui a heuristica de categoria/
  regiao de interesse ja existente.
- `vision_rekognition_video_enabled`: liga Amazon Rekognition Video
  (`StartLabelDetection`/`GetLabelDetection`) como fonte COMPLEMENTAR ao
  worker self-hosted OpenPose/YOLOv8 do processador de video
  (`app.processors.video`) - nunca substitui a estimativa de pose (ver ADR
  0016: Rekognition nao faz pose estimation).

Default `False` para os dois, mesma convencao "seguro por padrao" da
migration 0017 (LLM real, YOLOv8, OpenPose): chamar um servico AWS pago e
sempre uma acao explicita do administrador na tela `/admin/feature-flags`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "image_recognition_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
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
    # server_default so para preencher a linha singleton ja existente sem
    # erro de NOT NULL; remove depois para o modelo ORM (sem server_default
    # declarado) permanecer a fonte de verdade do valor em novas inserts.
    op.alter_column("feature_flags", "image_recognition_enabled", server_default=None)
    op.alter_column("feature_flags", "vision_rekognition_video_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("feature_flags", "vision_rekognition_video_enabled")
    op.drop_column("feature_flags", "image_recognition_enabled")
