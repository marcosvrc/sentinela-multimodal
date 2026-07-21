"""feature_flags: escolha de provedor (AWS/Azure) para imagem e sentimento

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-20

Adiciona `image_recognition_provider` (`AWS_REKOGNITION` | `AZURE_VISION`)
e `sentiment_analysis_provider` (`AWS_COMPREHEND` | `AZURE_LANGUAGE`) na
linha singleton de feature flags - permite alternar entre os adaptadores
reais equivalentes sem editar `.env`/reiniciar o processo, mesmo padrao
das demais colunas desta tabela. Default mantem o comportamento anterior
(AWS), nunca alterando o resultado de instalacoes existentes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    # server_default so para preencher a linha singleton ja existente sem
    # erro de NOT NULL; remove depois para o modelo ORM permanecer a fonte
    # de verdade em novas inserts (mesmo padrao das migrations 0018/0020).
    op.alter_column("feature_flags", "image_recognition_provider", server_default=None)
    op.alter_column("feature_flags", "sentiment_analysis_provider", server_default=None)


def downgrade() -> None:
    op.drop_column("feature_flags", "sentiment_analysis_provider")
    op.drop_column("feature_flags", "image_recognition_provider")
