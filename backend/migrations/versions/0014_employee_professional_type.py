"""employees: professional_type (item 5.3 - vinculo com papel de acesso)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-12

Adiciona `professional_type` (MEDICO/ENFERMEIRO) a `employees` - a
profissao-base do funcionario, usada para restringir quais papeis de
acesso (`users.role`) ele pode receber ao ser cadastrado
(`app.administration.service.ALLOWED_ROLES_BY_PROFESSIONAL_TYPE`):
Enfermeiro so pode ser ENFERMEIRO; Medico pode ser MEDICO ou qualquer
papel administrativo/de auditoria.

Funcionarios existentes (se houver, de antes desta mudanca) sao migrados
para MEDICO por padrao - e o superconjunto mais permissivo dos papeis que
eles podem ja ter (ADMINISTRADOR_TECNICO/CLINICO, AUDITOR, MEDICO), e pode
ser corrigido manualmente pela tela de administracao caso algum
funcionario legado seja de fato enfermeiro.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "professional_type",
            sa.String(length=20),
            nullable=False,
            server_default="MEDICO",
        ),
    )
    # Remove o default de nivel de banco depois do backfill: novos
    # registros devem sempre informar o tipo profissional explicitamente
    # (EmployeeCreate.professional_type e obrigatorio no schema).
    op.alter_column("employees", "professional_type", server_default=None)


def downgrade() -> None:
    op.drop_column("employees", "professional_type")
