"""Popula unidades assistenciais (`/admin/care-units`) com a lista padrao
de setores hospitalares fornecida pelo time clinico.

Idempotente: `identity_service.create_care_unit` tem uma constraint unica
(institution_id, name) - reexecutar o script apenas ignora as unidades
que ja existirem, sem duplicar nem falhar.

Uso:
    uv run python -m scripts.seed_care_units
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.identity import service as identity_service

DEV_INSTITUTION_NAME = "Instituicao de Desenvolvimento"

CARE_UNIT_NAMES: list[str] = [
    "Triagem (Acolhimento)",
    "Sala Vermelha",
    "Sala Amarela",
    "Pronto-Socorro Adulto",
    "Pronto-Socorro Infantil",
    "Clínica Médica",
    "Clínica Cirúrgica",
    "Pediatria",
    "Maternidade",
    "UTI Adulto",
    "UTI Pediátrica",
    "UTI Neonatal",
    "Unidade Coronariana (UCO)",
    "Salas de Operação (SO)",
    "Recuperação Pós-Anestésica (RPA)",
    "Centro de Parto Normal (CPN)",
    "Centro de Imagem",
    "Laboratório de Análises Clínicas",
    "Hemodinâmica",
    "Endoscopia e Colonoscopia",
    "Banco de Sangue",
    "Farmácia Hospitalar",
    "Central de Material e Esterilização (CME)",
    "Serviço Social",
    "Emergência",
]


def main() -> None:
    session = SessionLocal()
    try:
        institution = identity_service.get_or_create_institution(session, DEV_INSTITUTION_NAME)
        session.commit()
        session.refresh(institution)
        print(f"Instituicao: {institution.id} ({institution.name})")
        print()

        created_count = 0
        skipped_count = 0
        for name in CARE_UNIT_NAMES:
            try:
                identity_service.create_care_unit(session, institution.id, name)
                session.commit()
                created_count += 1
                print(f"  [CRIADA]   {name}")
            except IntegrityError:
                session.rollback()
                skipped_count += 1
                print(f"  [EXISTIA]  {name}")

        print()
        print(f"Total: {created_count} criadas, {skipped_count} ja existiam.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
