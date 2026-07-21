"""Cria instituicao e usuarios de desenvolvimento (um por papel).

TEMPORARIO: existe apenas porque o modulo de administracao (criacao de
instituicoes/usuarios) e o modulo de identidade (Cognito) ainda nao foram
implementados. Sera removido quando o provisionamento real existir.
Idempotente: reutiliza instituicao/usuarios existentes (por nome e por
`external_subject`, respectivamente).

Uso:
    uv run python -m scripts.seed_dev_data

O valor impresso para cada usuario e o `external_subject` a enviar no
cabecalho `X-Dev-Subject` (ver app/core/security.py e o banner de
desenvolvimento do frontend).
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service

DEV_INSTITUTION_NAME = "Instituicao de Desenvolvimento"

_DEV_USERS: list[tuple[str, str, UserRole]] = [
    ("dev-medico", "Dra. Ana Medico (dev)", UserRole.MEDICO),
    ("dev-enfermeiro", "Enf. Bruno Enfermeiro (dev)", UserRole.ENFERMEIRO),
    ("dev-admin-tecnico", "Carla Admin Tecnico (dev)", UserRole.ADMINISTRADOR_TECNICO),
    ("dev-admin-clinico", "Dr. Diego Admin Clinico (dev)", UserRole.ADMINISTRADOR_CLINICO),
    ("dev-auditor", "Elisa Auditora (dev)", UserRole.AUDITOR),
]


def main() -> None:
    session = SessionLocal()
    try:
        institution = identity_service.get_or_create_institution(session, DEV_INSTITUTION_NAME)
        session.commit()
        session.refresh(institution)
        print(f"Instituicao de desenvolvimento: {institution.id} ({institution.name})")
        print()
        print("Usuarios de desenvolvimento (cabecalho X-Dev-Subject):")

        for external_subject, full_name, role in _DEV_USERS:
            user = identity_service.get_or_create_user(
                session,
                institution_id=institution.id,
                external_subject=external_subject,
                full_name=full_name,
                role=role.value,
            )
            session.commit()
            print(f"  {role.value:<24} X-Dev-Subject: {user.external_subject}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
