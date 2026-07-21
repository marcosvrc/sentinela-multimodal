"""feature_flags: toggle do apoio a analise clinica (IA) automatico

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-17

Novo toggle `auto_clinical_support_enabled` na linha singleton de feature
flags - liga a chamada automatica de `app.clinical_support.service.
generate_analysis_clinical_support_summary` pelo worker
(`app.orchestrator.worker`) ao final do processamento de cada analise,
substituindo o botao manual "Analisar dados clinicos" na tela de revisao.

So dispara quando ha conteudo clinicamente relevante identificado (ver
`app.clinical_support.service.should_run_automatic_clinical_support`).

Default `False`, mesma convencao "seguro por padrao" das demais migrations
de feature flag deste projeto (0017/0018/0021): uma chamada adicional ao
LLM em toda analise processada e sempre uma decisao explicita do
administrador na tela `/admin/feature-flags`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "auto_clinical_support_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # server_default so para preencher a linha singleton ja existente sem
    # erro de NOT NULL; remove depois para o modelo ORM permanecer a fonte
    # de verdade do valor em novas inserts (mesmo padrao das migrations
    # anteriores).
    op.alter_column("feature_flags", "auto_clinical_support_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("feature_flags", "auto_clinical_support_enabled")
