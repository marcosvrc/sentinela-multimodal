"""reports: persiste o ultimo apoio a analise clinica (IA) gerado

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-17

`Report.clinical_support_summary` guarda o RESULTADO MAIS RECENTE do
botao "Analisar dados clinicos" da tela de revisao da analise
(`app.clinical_support.service.generate_analysis_clinical_support_summary`).

Antes desta migration, esse resumo nunca era persistido (gerado sob
demanda a cada clique, sem gravar em lugar nenhum) - o que fazia a secao
"Apoio a analise clinica (IA)" nunca aparecer no PDF exportado, porque o
PDF e renderizado a partir de `Report.content` (snapshot montado por
`app.reports.builder`), que nao tinha acesso a esse dado.

Continua sendo um apoio SOB DEMANDA (o profissional ainda pode gerar de
novo quantas vezes quiser, cada clique sobrescreve esta coluna com um
resumo novo) - a diferenca e que agora o ULTIMO resumo gerado sobrevive
ate a confirmacao do relatorio e passa a integrar o PDF exportado.
Nullable: uma analise pode ser confirmada sem que o profissional tenha
clicado no botao nenhuma vez.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "clinical_support_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reports", "clinical_support_summary")
