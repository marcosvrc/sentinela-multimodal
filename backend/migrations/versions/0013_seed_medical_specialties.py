"""seed medical specialties catalog (item 5.3)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-12

`medical_specialties` e escopada por instituicao (`uq_specialty_name_per_tenant`
em migrations/versions/0010_administration.py), entao esta seed insere o
catalogo abaixo para cada instituicao ja existente no momento em que a
migration roda - novas instituicoes criadas depois continuam cadastrando
especialidades normalmente pela tela de administracao
(POST /admin/specialties), sem depender desta migration.

Idempotente: usa `ON CONFLICT DO NOTHING` na constraint unica
(institution_id, name), entao pode ser aplicada mais de uma vez (e sobre
instituicoes que ja tenham algumas dessas especialidades cadastradas
manualmente) sem duplicar linhas nem falhar.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Catalogo de especialidades medicas fornecido pelo time clinico.
SPECIALTY_NAMES: list[str] = [
    "Clínica Médica",
    "Cardiologia",
    "Pediatria",
    "Dermatologia",
    "Neurologia",
    "Endocrinologia e Metabologia",
    "Gastroenterologia",
    "Psiquiatria",
    "Geriatria",
    "Infectologia",
    "Medicina de Família e Comunidade",
    "Medicina do Trabalho",
    "Pneumologia",
    "Reumatologia",
    "Oncologia Clínica",
    "Cirurgia Geral",
    "Ginecologia e Obstetrícia",
    "Ortopedia e Traumatologia",
    "Cirurgia Plástica",
    "Urologia",
    "Oftalmologia",
    "Otorrinolaringologia",
    "Cirurgia Vascular",
    "Neurocirurgia",
    "Coloproctologia",
    "Cirurgia Cardiovascular",
    "Anestesiologia",
    "Radiologia e Diagnóstico por Imagem",
    "Patologia Clínica / Medicina Laboratorial",
    "Medicina Nuclear",
    "Patologia",
    "Genética Médica",
]


def upgrade() -> None:
    connection = op.get_bind()
    for name in SPECIALTY_NAMES:
        connection.execute(
            text(
                """
                INSERT INTO medical_specialties (id, institution_id, name, active, created_at)
                SELECT gen_random_uuid(), institutions.id, :name, true, now()
                FROM institutions
                ON CONFLICT (institution_id, name) DO NOTHING
                """
            ),
            {"name": name},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for name in SPECIALTY_NAMES:
        connection.execute(
            text("DELETE FROM medical_specialties WHERE name = :name"),
            {"name": name},
        )
