"""feature_flags: toggle Amazon Comprehend (analise de sentimento)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-17

Novo toggle `sentiment_analysis_enabled` na linha singleton de feature
flags - liga o Amazon Comprehend `DetectSentiment` (`app.integrations.
sentiment_analysis`) como enriquecimento CONTEXTUAL dos processadores de
texto e audio (transcricao) - ESCOPO_PROJETO.md secao 4.2: "Analise de
sentimento, quando utilizada, sera apenas contextual e nunca determinara
risco clinico".

Default `False`, mesma convencao "seguro por padrao" das migrations 0017/
0018: chamar um servico AWS pago e sempre uma decisao explicita do
administrador na tela `/admin/feature-flags`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "sentiment_analysis_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # server_default so para preencher a linha singleton ja existente sem
    # erro de NOT NULL; remove depois para o modelo ORM permanecer a fonte
    # de verdade do valor em novas inserts (mesmo padrao das migrations
    # 0018/0020).
    op.alter_column("feature_flags", "sentiment_analysis_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("feature_flags", "sentiment_analysis_enabled")
