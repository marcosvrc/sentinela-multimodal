"""Endpoints de cadastro de paciente e observacoes clinicas.

Todas as rotas usam o mesmo formato de paginacao e erro compartilhado
(`app.api.schemas.common`).

Acesso restrito a papeis assistenciais (medico, enfermeiro): usuarios
somente acessam pacientes e funcoes autorizados para seu papel, e as
telas de paciente sao listadas apenas para medico/enfermeiro.
Administradores e auditores nao tem motivo assistencial para ler dados
clinicos identificados nesta fase.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.schemas.clinical_support import ClinicalSupportSummaryRead
from app.api.schemas.common import PageResponse
from app.api.schemas.observations import ObservationCreate, ObservationRead
from app.api.schemas.patients import (
    BreakGlassGrantRead,
    BreakGlassRequest,
    PatientCareAssignmentCreate,
    PatientCareAssignmentRead,
    PatientCreate,
    PatientRead,
    PatientUpdate,
)
from app.audit import service as audit_service
from app.clinical_support import service as clinical_support_service
from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.enums import AuditCategory, AuditResult, UserRole
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser, require_patient_access, require_role
from app.identity import service as identity_service
from app.observations import service as observations_service
from app.observations.validation import compute_age
from app.patients import service as patients_service
from app.patients.models import Patient

router = APIRouter(prefix="/patients", tags=["patients"])

_require_clinical_staff = require_role(UserRole.MEDICO, UserRole.ENFERMEIRO)
_require_admin = require_role(UserRole.ADMINISTRADOR_TECNICO, UserRole.ADMINISTRADOR_CLINICO)


def _to_patient_read(patient: Patient, *, has_analyses: bool = False) -> PatientRead:
    return PatientRead(
        id=patient.id,
        medical_record_number=patient.medical_record_number,
        full_name=patient.full_name,
        birth_date=patient.birth_date,
        age=compute_age(patient.birth_date, date.today()),
        registered_sex=patient.registered_sex,
        email=patient.email,
        height_cm=float(patient.height_cm) if patient.height_cm is not None else None,
        active=patient.active,
        has_analyses=has_analyses,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


@router.post("", response_model=PatientRead, status_code=201)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PatientRead:
    patient = patients_service.create_patient(
        db,
        current_user.institution_id,
        data,
        current_user.external_subject,
        created_by_user_id=current_user.id,
        actor_role=current_user.role.value,
    )
    return _to_patient_read(patient)


@router.get("", response_model=PageResponse[PatientRead])
def list_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    active: bool | None = Query(default=True),
    has_analyses: bool | None = Query(
        default=None,
        description="Filtra por pacientes com (true) ou sem (false) analise ja registrada.",
    ),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PageResponse[PatientRead]:
    patients, total_items = patients_service.list_patients(
        db,
        current_user.institution_id,
        page,
        page_size,
        search=search,
        active=active,
        has_analyses=has_analyses,
    )
    patient_ids_with_analyses = patients_service.get_patient_ids_with_analyses(
        db, current_user.institution_id, {patient.id for patient in patients}
    )
    return PageResponse.build(
        items=[
            _to_patient_read(patient, has_analyses=patient.id in patient_ids_with_analyses)
            for patient in patients
        ],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PatientRead:
    patient = patients_service.get_patient(db, current_user.institution_id, patient_id)
    require_patient_access(db, current_user, patient_id)
    # Auditado apenas no acesso a um paciente especifico (nao na listagem em
    # massa), para nao gerar tempestade de eventos em telas de busca.
    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.DATA,
        action="PATIENT_VIEW",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
    )
    db.commit()
    return _to_patient_read(patient)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PatientRead:
    require_patient_access(db, current_user, patient_id)
    patient = patients_service.update_patient(
        db,
        current_user.institution_id,
        patient_id,
        data,
        current_user.external_subject,
        actor_role=current_user.role.value,
    )
    return _to_patient_read(patient)


@router.post("/{patient_id}/observations", response_model=ObservationRead, status_code=201)
def create_observation(
    patient_id: uuid.UUID,
    data: ObservationCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ObservationRead:
    require_patient_access(db, current_user, patient_id)
    observation = observations_service.create_observation(
        db, current_user.institution_id, patient_id, data, current_user.external_subject
    )
    return ObservationRead.model_validate(observation)


@router.get("/{patient_id}/observations", response_model=list[ObservationRead])
def list_observations(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> list[ObservationRead]:
    require_patient_access(db, current_user, patient_id)
    observations = observations_service.list_observations(
        db, current_user.institution_id, patient_id
    )
    return [ObservationRead.model_validate(observation) for observation in observations]


@router.post(
    "/{patient_id}/clinical-support-summary",
    response_model=ClinicalSupportSummaryRead,
)
def generate_clinical_support_summary(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ClinicalSupportSummaryRead:
    """Apoio a analise clinica assistido por LLM (botao "Analisar dados
    clinicos" abaixo do painel de alertas de anomalia). Consolida series
    de observacoes e alertas de anomalia do paciente em um resumo com
    visao clinica, causas provaveis e direcionamento sugerido - sempre
    como apoio, nunca como diagnostico ou substituicao da analise do
    profissional responsavel (ver `app.clinical_support.service`)."""
    require_patient_access(db, current_user, patient_id)
    summary = clinical_support_service.generate_clinical_support_summary(
        db,
        current_user.institution_id,
        patient_id,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
    )
    return ClinicalSupportSummaryRead(
        summary_text=summary.summary_text,
        probable_causes=summary.probable_causes,
        suggested_next_steps=summary.suggested_next_steps,
        uncertainty_note=summary.uncertainty_note,
        provider=summary.provider,
        model=summary.model,
        prompt_version=summary.prompt_version,
        generated_at=summary.generated_at,
        observations_considered=summary.observations_considered,
        alerts_considered=summary.alerts_considered,
    )


@router.post(
    "/{patient_id}/break-glass", response_model=BreakGlassGrantRead, status_code=201
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
def create_break_glass_grant(
    request: Request,  # noqa: ARG001 - exigido pelo decorator do slowapi
    patient_id: uuid.UUID,
    data: BreakGlassRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> BreakGlassGrantRead:
    """Concede acesso de emergencia ao paciente por um prazo curto
    ("break glass"). Nunca silencioso: gera evento de auditoria
    AUTHORIZATION imediatamente e outro em cada acesso
    realizado sob o grant (ver `app.core.security.require_patient_access`).

    Limite de taxa mais restrito (`Settings.rate_limit_auth`, nao o
    `rate_limit_default` global): esta e a unica acao de elevacao de acesso
    exposta diretamente por esta API (o login/MFA em si acontece no
    Cognito, fora deste backend), entao e o alvo mais provavel de abuso por
    forca bruta/enumeracao de pacientes.
    """
    patients_service.get_patient(db, current_user.institution_id, patient_id)
    settings = get_settings()
    grant = identity_service.create_break_glass_grant(
        db,
        institution_id=current_user.institution_id,
        user_id=current_user.id,
        patient_id=patient_id,
        justification=data.justification,
        duration_seconds=min(data.duration_seconds, settings.session_max_age_seconds),
    )
    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.AUTHORIZATION,
        action="BREAK_GLASS_GRANTED",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
        justification=data.justification,
    )
    db.commit()
    db.refresh(grant)
    return BreakGlassGrantRead.model_validate(grant)


@router.post(
    "/{patient_id}/care-assignments",
    response_model=PatientCareAssignmentRead,
    status_code=201,
)
def create_care_assignment(
    patient_id: uuid.UUID,
    data: PatientCareAssignmentCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PatientCareAssignmentRead:
    """Cria o vinculo assistencial formal entre um profissional e um
    paciente. Restrito a administracao - o vinculo em si e uma decisao
    organizacional, nao clinica."""
    patients_service.get_patient(db, current_user.institution_id, patient_id)
    assignment = identity_service.create_patient_care_assignment(
        db,
        institution_id=current_user.institution_id,
        patient_id=patient_id,
        user_id=data.user_id,
        care_unit_id=data.care_unit_id,
        assigned_by=current_user.external_subject,
    )
    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.ADMINISTRATION,
        action="CARE_ASSIGNMENT_CREATE",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
        event_metadata={"user_id": str(data.user_id)},
    )
    db.commit()
    db.refresh(assignment)
    return PatientCareAssignmentRead.model_validate(assignment)


@router.delete(
    "/{patient_id}/care-assignments/{assignment_id}",
    response_model=PatientCareAssignmentRead,
)
def end_care_assignment(
    patient_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PatientCareAssignmentRead:
    patients_service.get_patient(db, current_user.institution_id, patient_id)
    assignment = identity_service.end_patient_care_assignment(db, assignment_id)
    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.ADMINISTRATION,
        action="CARE_ASSIGNMENT_END",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
    )
    db.commit()
    db.refresh(assignment)
    return PatientCareAssignmentRead.model_validate(assignment)
