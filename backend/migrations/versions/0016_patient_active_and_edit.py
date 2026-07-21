"""patients: active flag (exclusao = desativacao, item 5.1)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-13

Adiciona `active` a `patients` (default true), para suportar "exclusao"
como desativacao na tela de listagem de pacientes - nunca apaga o
registro (historico de observacoes/analises/auditoria permanece integro),
mesmo principio ja usado em `Employee.active`/`CareUnit.active`/
`MedicalSpecialty.active`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("patients", "active", server_default=None)


def downgrade() -> None:
    op.drop_column("patients", "active")
