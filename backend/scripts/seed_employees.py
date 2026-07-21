"""Popula a tela de Funcionarios com 25 registros ficticios (dados
sinteticos - nunca dados reais, ESCOPO_PROJETO.md secao 8.2), usando os
nomes mais populares do Brasil, especialidade medica aleatoria (dentre as
ja cadastradas por `scripts/seed_medical_specialties` ou pela migration
0013) e papel de acesso aleatorio, respeitando a mesma regra de negocio da
tela de administracao: Enfermeiro so recebe o papel ENFERMEIRO; Medico
recebe MEDICO ou um papel administrativo/de auditoria
(`app.administration.service.ALLOWED_ROLES_BY_PROFESSIONAL_TYPE`).

Cada funcionario tambem cria a conta de acesso vinculada (mesmo fluxo da
tela /admin/employees - ver `app.administration.service.create_employee`),
com um `external_subject` sintetico previsivel (`seed-employee-<matricula>`).

Idempotente: matricula e CPF sao gerados deterministicamente a partir do
indice do funcionario, entao reexecutar o script apenas ignora quem ja
existe (mesmo erro 409 que a API retornaria).

Uso:
    uv run python -m scripts.seed_employees
"""

from __future__ import annotations

import random

from app.administration import service as administration_service
from app.api.schemas.administration import EmployeeCreate
from app.core.db import SessionLocal
from app.core.enums import EmployeeProfessionalType
from app.core.errors import ApiError
from app.identity import service as identity_service

DEV_INSTITUTION_NAME = "Instituicao de Desenvolvimento"
SEED_ACTOR = "seed-employees-script"

# Nomes e sobrenomes mais populares do Brasil (fonte: pesquisas de registro
# civil/IBGE recorrentes sobre nomes e sobrenomes mais comuns no pais).
# Combinados aleatoriamente para gerar 25 nomes completos sinteticos - nao
# correspondem a nenhuma pessoa real.
FIRST_NAMES_MALE = [
    "José", "João", "Antônio", "Francisco", "Carlos", "Paulo", "Pedro",
    "Lucas", "Luiz", "Marcos", "Gabriel", "Rafael", "Daniel", "Bruno",
    "Eduardo", "Felipe", "Rodrigo", "Gustavo", "Leonardo", "Thiago",
]
FIRST_NAMES_FEMALE = [
    "Maria", "Ana", "Francisca", "Antônia", "Adriana", "Juliana", "Márcia",
    "Fernanda", "Patrícia", "Aline", "Sandra", "Camila", "Amanda", "Bruna",
    "Jéssica", "Letícia", "Larissa", "Vanessa", "Beatriz", "Gabriela",
]
LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira",
    "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins",
    "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes", "Vieira",
    "Barbosa", "Rocha", "Dias", "Nascimento", "Andrade", "Moreira",
]

EMPLOYEE_COUNT = 25

# Roles administrativas/de auditoria disponiveis para o tipo MEDICO -
# usadas para sortear o papel de acesso respeitando a mesma regra do
# backend (ALLOWED_ROLES_BY_PROFESSIONAL_TYPE).
_MEDICO_ROLES = list(
    administration_service.get_allowed_roles(EmployeeProfessionalType.MEDICO)
)
_ENFERMEIRO_ROLES = list(
    administration_service.get_allowed_roles(EmployeeProfessionalType.ENFERMEIRO)
)


def _generate_cpf(seed_index: int) -> str:
    """Gera um CPF estruturalmente valido (algoritmo modulo 11, mesma
    verificacao de `app.administration.service.is_valid_cpf`) a partir de
    um indice determinístico - garante que o script produz sempre os
    mesmos 25 CPFs em reexecucoes, sem depender de aleatoriedade para essa
    parte."""
    rng = random.Random(f"cpf-{seed_index}")
    base = [rng.randint(0, 9) for _ in range(9)]

    def _check_digit(digits: list[int]) -> int:
        weights = range(len(digits) + 1, 1, -1)
        total = sum(digit * weight for digit, weight in zip(digits, weights, strict=True))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first_check = _check_digit(base)
    second_check = _check_digit([*base, first_check])
    digits = [*base, first_check, second_check]
    return "".join(str(d) for d in digits)


def _generate_full_names(count: int) -> list[str]:
    rng = random.Random("sentinelhealth-seed-employees-names")
    names: set[str] = set()
    while len(names) < count:
        is_female = rng.random() < 0.5
        first = rng.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
        last_1, last_2 = rng.sample(LAST_NAMES, 2)
        names.add(f"{first} {last_1} {last_2}")
    return sorted(names)


def main() -> None:
    session = SessionLocal()
    try:
        institution = identity_service.get_or_create_institution(session, DEV_INSTITUTION_NAME)
        session.commit()
        session.refresh(institution)
        print(f"Instituicao: {institution.id} ({institution.name})")

        specialties, _ = administration_service.list_specialties(
            session, institution.id, page=1, page_size=100, active_only=True
        )
        if not specialties:
            print(
                "Nenhuma especialidade ativa encontrada. Rode antes a migration "
                "0013 (seed do catalogo de especialidades) ou cadastre "
                "especialidades pela tela de administracao."
            )
            return

        full_names = _generate_full_names(EMPLOYEE_COUNT)
        rng = random.Random("sentinelhealth-seed-employees-assignments")

        created_count = 0
        skipped_count = 0

        for index, full_name in enumerate(full_names, start=1):
            professional_type = (
                EmployeeProfessionalType.ENFERMEIRO
                if rng.random() < 0.3
                else EmployeeProfessionalType.MEDICO
            )
            role = rng.choice(
                _ENFERMEIRO_ROLES
                if professional_type is EmployeeProfessionalType.ENFERMEIRO
                else _MEDICO_ROLES
            )
            specialty = rng.choice(specialties)
            registration_number = f"SEED-{index:04d}"
            external_subject = f"seed-employee-{registration_number.lower()}"
            local_part = full_name.lower().replace(" ", ".")
            email = f"{local_part}.{index}@example.com"

            data = EmployeeCreate(
                full_name=full_name,
                cpf=_generate_cpf(index),
                registration_number=registration_number,
                email=email,
                specialty_id=specialty.id,
                professional_type=professional_type,
                role=role,
                external_subject=external_subject,
            )

            try:
                administration_service.create_employee(session, institution.id, data, SEED_ACTOR)
                created_count += 1
                print(
                    f"  [CRIADO]  {full_name:<32} {professional_type.value:<11} "
                    f"{role.value:<24} {specialty.name}"
                )
            except ApiError as exc:
                session.rollback()
                skipped_count += 1
                print(f"  [PULADO]  {full_name:<32} ({exc.code}: ja existe)")

        print()
        print(f"Total: {created_count} criados, {skipped_count} ja existiam.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
