"""patients: height_cm (item 5.1 - insumo para calculo de IMC)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-13

Adiciona `height_cm` (altura em cm, opcional) a `patients`. Combinada com
o peso mais recente (`ObservationType.WEIGHT`, uma serie temporal
separada - o peso muda, a altura de um adulto praticamente nao),
permite calcular o IMC (docs/CLASSIFICACAO_DADOS_CLINICOS.md secao 12).

Pacientes existentes ficam com `height_cm=NULL` (nunca inventa um valor);
o profissional preenche na proxima edicao do cadastro.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("height_cm", sa.Numeric(5, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "height_cm")
