"""Regras de negocio do cadastro de paciente.

Mantido separado das rotas HTTP para permitir reuso (ex: futura importacao
em lote) e para isolar a traducao de erros de infraestrutura (IntegrityError
do Postgres) em erros de dominio estaveis.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.patients import PatientCreate, PatientUpdate
from app.audit import service as audit_service
from app.core.enums import AuditCategory, AuditResult
from app.core.errors import ApiError
from app.identity import service as identity_service
from app.media.models import Analysis
from app.patients.models import Patient


def create_patient(
    db: Session,
    institution_id: uuid.UUID,
    data: PatientCreate,
    actor: str,
    *,
    created_by_user_id: uuid.UUID | None = None,
    actor_role: str | None = None,
) -> Patient:
    patient = Patient(
        institution_id=institution_id,
        medical_record_number=data.medical_record_number,
        full_name=data.full_name,
        birth_date=data.birth_date,
        registered_sex=data.registered_sex,
        email=data.email,
        height_cm=data.height_cm,
    )
    db.add(patient)
    try:
        # Flush isolado primeiro: se o INSERT do paciente violar a
        # constraint de unicidade, falha aqui sem gravar nenhum evento de
        # auditoria (nao ha "criacao" para registrar).
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_MEDICAL_RECORD_NUMBER",
            message="Ja existe um paciente com este identificador institucional/prontuario.",
            status_code=409,
            field_errors={
                "medical_record_number": "Identificador ja cadastrado nesta instituicao."
            },
        ) from exc

    # Registrado na mesma transacao do INSERT do paciente: se a gravacao do
    # evento de auditoria falhar, o commit abaixo nunca ocorre e a criacao
    # do paciente e revertida - falha de auditoria bloqueia a operacao que
    # a originou.
    audit_service.record_event(
        db,
        actor=actor,
        actor_role=actor_role,
        category=AuditCategory.DATA,
        action="PATIENT_CREATE",
        resource_type="patient",
        resource_id=str(patient.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
    )

    if created_by_user_id is not None:
        # O profissional que cadastra o paciente recebe automaticamente um
        # vinculo assistencial ativo - sem isso, ele proprio nao conseguiria
        # acessar o paciente que acabou de criar. Vinculos adicionais
        # (outros profissionais/unidade) sao geridos por
        # `app.identity.service.create_patient_care_assignment` via
        # administracao.
        identity_service.create_patient_care_assignment(
            db,
            institution_id=institution_id,
            patient_id=patient.id,
            user_id=created_by_user_id,
            care_unit_id=None,
            assigned_by=actor,
        )

    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, institution_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.institution_id == institution_id)
    )
    if patient is None:
        # Resposta indistinguivel de "nao encontrado" tambem para tentativas
        # de acesso entre instituicoes diferentes (isolamento multi-tenant).
        raise ApiError(
            code="PATIENT_NOT_FOUND", message="Paciente nao encontrado.", status_code=404
        )
    return patient


def get_patients_by_ids(
    db: Session, institution_id: uuid.UUID, patient_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Patient]:
    """Busca em lote por id, restrita a instituicao do requisitante - usado
    para "enriquecer" listagens que referenciam pacientes (ex: historico de
    analises) sem N+1 queries. Retorna vazio para conjunto vazio."""
    if not patient_ids:
        return {}
    patients = db.scalars(
        select(Patient).where(
            Patient.id.in_(patient_ids), Patient.institution_id == institution_id
        )
    ).all()
    return {patient.id: patient for patient in patients}


def update_patient(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    data: PatientUpdate,
    actor: str,
    actor_role: str | None = None,
) -> Patient:
    """Atualiza apenas os campos explicitamente enviados (`model_fields_set`,
    nao apenas os diferentes de `None` - permite limpar `email`/`height_cm`
    enviando `null` deliberadamente, distinto de simplesmente omitir o
    campo). A tela de edicao envia o registro completo apos carregar os
    dados atuais; outros fluxos (ex.: reativar/desativar) enviam so
    `active`."""
    patient = get_patient(db, institution_id, patient_id)
    fields_sent = data.model_fields_set

    if "medical_record_number" in fields_sent:
        patient.medical_record_number = data.medical_record_number  # type: ignore[assignment]
    if "full_name" in fields_sent:
        patient.full_name = data.full_name  # type: ignore[assignment]
    if "birth_date" in fields_sent:
        patient.birth_date = data.birth_date  # type: ignore[assignment]
    if "registered_sex" in fields_sent:
        patient.registered_sex = data.registered_sex  # type: ignore[assignment]
    if "email" in fields_sent:
        patient.email = data.email
    if "height_cm" in fields_sent:
        patient.height_cm = data.height_cm
    if "active" in fields_sent:
        patient.active = data.active  # type: ignore[assignment]

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_MEDICAL_RECORD_NUMBER",
            message="Ja existe um paciente com este identificador institucional/prontuario.",
            status_code=409,
            field_errors={
                "medical_record_number": "Identificador ja cadastrado nesta instituicao."
            },
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        actor_role=actor_role,
        category=AuditCategory.DATA,
        action="PATIENT_UPDATE",
        resource_type="patient",
        resource_id=str(patient.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
    )
    db.commit()
    db.refresh(patient)
    return patient


def list_patients(
    db: Session,
    institution_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    search: str | None = None,
    active: bool | None = True,
    has_analyses: bool | None = None,
) -> tuple[list[Patient], int]:
    """Lista paginada, com busca opcional por nome ou numero de prontuario.

    `search` casa por substring (case-insensitive) em `full_name` OU em
    `medical_record_number` - a mesma caixa de busca serve para os dois
    campos.

    `active` e tri-state: `True` (padrao) mostra so pacientes ativos,
    `False` so os desativados, `None` mostra todos - mesmo padrao usado
    em `administration_service.list_employees`/`list_specialties`.

    `has_analyses` e tri-state: `True` mostra so pacientes com pelo menos
    uma `Analysis` (qualquer estado) ja registrada, `False` so os que
    nunca tiveram nenhuma, `None` (padrao) nao filtra - usado pelo filtro
    "Tem analise" da listagem de pacientes, que tambem decide se o icone
    de atalho para o historico de analises aparece na linha.
    """
    filters = [Patient.institution_id == institution_id]
    if active is not None:
        filters.append(Patient.active.is_(active))
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            Patient.full_name.ilike(pattern) | Patient.medical_record_number.ilike(pattern)
        )

    analysis_exists = exists().where(Analysis.patient_id == Patient.id)
    if has_analyses is True:
        filters.append(analysis_exists)
    elif has_analyses is False:
        filters.append(~analysis_exists)

    total_items = db.scalar(select(func.count()).select_from(Patient).where(*filters))

    items = db.scalars(
        select(Patient)
        .where(*filters)
        .order_by(Patient.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return list(items), int(total_items or 0)


def get_patient_ids_with_analyses(
    db: Session, institution_id: uuid.UUID, patient_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Subconjunto de `patient_ids` que tem ao menos uma `Analysis`
    registrada - usado para decidir, por paciente, se o icone de atalho
    para o historico de analises aparece na listagem (sem N+1 queries)."""
    if not patient_ids:
        return set()
    rows = db.scalars(
        select(Analysis.patient_id)
        .where(Analysis.institution_id == institution_id, Analysis.patient_id.in_(patient_ids))
        .distinct()
    ).all()
    return set(rows)


def compute_patient_age(patient: Patient, as_of: date | None = None) -> int:
    from app.observations.validation import compute_age

    return compute_age(patient.birth_date, as_of or date.today())
