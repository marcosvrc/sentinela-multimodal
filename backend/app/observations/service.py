"""Regras de negocio de observacoes clinicas."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anomaly_detection.service import evaluate_and_create_alerts
from app.api.schemas.observations import ObservationCreate
from app.audit import service as audit_service
from app.core.enums import AuditCategory, AuditResult
from app.core.errors import ApiError
from app.observations.models import ClinicalObservation
from app.observations.validation import validate_observation
from app.patients.service import get_patient


def create_observation(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    data: ObservationCreate,
    actor: str,
) -> ClinicalObservation:
    # Garante que o paciente existe e pertence a instituicao do requisitante
    # antes de gravar a observacao (isolamento multi-tenant).
    get_patient(db, institution_id, patient_id)

    field_errors = validate_observation(data.observation_type, data.value, data.unit, data.context)
    if field_errors:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="Nao foi possivel registrar a observacao clinica.",
            status_code=422,
            field_errors=field_errors,
        )

    observation = ClinicalObservation(
        institution_id=institution_id,
        patient_id=patient_id,
        observation_type=data.observation_type.value,
        value=data.value,
        unit=data.unit,
        context=data.context,
        measured_at=data.measured_at,
        origin=data.origin,
        author=data.author,
        method=data.method,
        reading_quality=data.reading_quality.value,
    )
    db.add(observation)
    db.flush()

    # Deteccao de anomalia, mesma transacao: se o sinal recem-gravado for
    # anomalo em relacao ao historico recente
    # do paciente, o alerta e criado atomicamente com a observacao. Nunca
    # influencia a validacao/gravacao em si (falha na deteccao nao deveria
    # impedir o registro clinico) - mas por ora falhas aqui propagam como
    # qualquer outro erro de escrita, ja que a deteccao e uma leitura+
    # escrita simples sem dependencia externa.
    evaluate_and_create_alerts(db, institution_id, patient_id, observation)

    # Mesma transacao do INSERT: falha ao gravar o evento de auditoria
    # bloqueia a criacao da observacao, para nunca haver registro clinico
    # sem rastro de auditoria correspondente.
    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.DATA,
        action="OBSERVATION_CREATE",
        resource_type="clinical_observation",
        resource_id=str(observation.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=None,
        event_metadata={
            "observation_type": data.observation_type.value,
            "patient_id": str(patient_id),
        },
    )
    db.commit()
    db.refresh(observation)
    return observation


def list_observations(
    db: Session, institution_id: uuid.UUID, patient_id: uuid.UUID
) -> list[ClinicalObservation]:
    get_patient(db, institution_id, patient_id)
    return list(
        db.scalars(
            select(ClinicalObservation)
            .where(
                ClinicalObservation.institution_id == institution_id,
                ClinicalObservation.patient_id == patient_id,
            )
            .order_by(ClinicalObservation.measured_at.desc())
        ).all()
    )
