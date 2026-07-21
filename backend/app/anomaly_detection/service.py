"""Orquestracao de deteccao de anomalia + ciclo de vida do alerta.

`evaluate_and_create_alerts` e chamado por
`app.observations.service.create_observation` na MESMA transacao (antes do
commit final): se uma nova leitura for anomala em relacao ao historico
recente do paciente para o mesmo sinal, um `ClinicalAlert` e criado
atomicamente junto com a observacao. Cobre os sinais vitais numericos com
faixa fisiologica ja validada - batimentos, pressao arterial, oxigenacao,
frequencia respiratoria, temperatura e debito urinario (`URINE_OUTPUT`) -
configurados em `app.anomaly_detection.detection`. Prescricoes e
"movimentacao do paciente" permanecem fora do escopo desta deteccao: a
analise de prescricoes exigiria definicao de fontes farmacologicas,
interacoes, doses, alergias e validacao farmaceutica/clinica, nenhuma das
quais existe neste sistema; e deteccao de padrao de movimentacao exigiria
agregar achados de pose entre MULTIPLAS analises de video do mesmo
paciente ao longo do tempo, um mecanismo de agregacao longitudinal que
ainda nao existe. Ambas permanecem como lacunas conhecidas em vez de
fingidas aqui.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anomaly_detection.detection import (
    DETECTOR_VERSION,
    VitalSignSample,
    detect_vital_sign_anomaly,
)
from app.anomaly_detection.models import ClinicalAlert
from app.audit import service as audit_service
from app.core.enums import AlertSeverity, AlertStatus, AuditCategory, AuditResult
from app.core.errors import ApiError
from app.observations.models import ClinicalObservation

# Mapa observation_type -> lista de (signal_key, extrator do campo numerico
# dentro de `ClinicalObservation.value`). Pressao arterial produz DOIS
# sinais independentes a partir de uma unica observacao.
_SIGNAL_EXTRACTORS: dict[str, list[tuple[str, str]]] = {
    "HEART_RATE": [("HEART_RATE", "value")],
    "RESPIRATORY_RATE": [("RESPIRATORY_RATE", "value")],
    "SPO2": [("SPO2", "value")],
    "TEMPERATURE": [("TEMPERATURE", "value")],
    "BLOOD_PRESSURE": [
        ("BLOOD_PRESSURE_SYSTOLIC", "systolic"),
        ("BLOOD_PRESSURE_DIASTOLIC", "diastolic"),
    ],
    "URINE_OUTPUT": [("URINE_OUTPUT", "value")],
}

_EXPECTED_ACTION_BY_SEVERITY: dict[AlertSeverity, str] = {
    AlertSeverity.MODERATE: (
        "Reavaliar o paciente e registrar nova afericao deste sinal em ate 1 hora."
    ),
    AlertSeverity.HIGH: (
        "Notificar a equipe assistencial responsavel e reavaliar o paciente prontamente."
    ),
    AlertSeverity.CRITICAL: (
        "Acionar a equipe assistencial imediatamente; considerar avaliacao medica urgente."
    ),
}


def evaluate_and_create_alerts(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    observation: ClinicalObservation,
) -> list[ClinicalAlert]:
    """Roda a deteccao para cada sinal extraivel de `observation` e cria um
    `ClinicalAlert` por sinal anomalo. Nao faz commit (mesma transacao do
    chamador - `app.observations.service.create_observation`)."""
    extractors = _SIGNAL_EXTRACTORS.get(observation.observation_type)
    if not extractors:
        return []

    created: list[ClinicalAlert] = []
    for signal_key, field_name in extractors:
        raw_value = observation.value.get(field_name)
        if not isinstance(raw_value, int | float):
            continue

        history = _load_signal_history(
            db, institution_id, patient_id, observation.observation_type, field_name, observation
        )
        new_sample = VitalSignSample(measured_at=observation.measured_at, value=float(raw_value))
        result = detect_vital_sign_anomaly(signal_key, history, new_sample)
        if not result.is_anomalous:
            continue

        assert result.severity is not None  # is_anomalous=True sempre traz severity
        alert = ClinicalAlert(
            institution_id=institution_id,
            patient_id=patient_id,
            observation_id=observation.id,
            signal_key=signal_key,
            severity=result.severity.value,
            status=AlertStatus.OPEN.value,
            detector_source=DETECTOR_VERSION,
            confidence=result.confidence,
            evidence=result.evidence,
            expected_action=_EXPECTED_ACTION_BY_SEVERITY[result.severity],
            detected_at=observation.measured_at,
        )
        db.add(alert)
        db.flush()
        created.append(alert)

        audit_service.record_event(
            db,
            actor="system:anomaly_detection",
            category=AuditCategory.ANALYSIS,
            action="CLINICAL_ALERT_CREATED",
            resource_type="clinical_alert",
            resource_id=str(alert.id),
            result=AuditResult.SUCCESS,
            institution_id=institution_id,
            event_metadata={
                "patient_id": str(patient_id),
                "signal": signal_key,
                "severity": result.severity.value,
                "triggered_by": list(result.triggered_by),
            },
        )

    return created


def _load_signal_history(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    observation_type: str,
    field_name: str,
    current_observation: ClinicalObservation,
) -> list[VitalSignSample]:
    rows = db.scalars(
        select(ClinicalObservation)
        .where(
            ClinicalObservation.institution_id == institution_id,
            ClinicalObservation.patient_id == patient_id,
            ClinicalObservation.observation_type == observation_type,
            ClinicalObservation.id != current_observation.id,
            ClinicalObservation.measured_at < current_observation.measured_at,
        )
        .order_by(ClinicalObservation.measured_at.desc())
        .limit(20)
    ).all()

    samples: list[VitalSignSample] = []
    for row in rows:
        raw = row.value.get(field_name)
        if isinstance(raw, int | float):
            samples.append(VitalSignSample(measured_at=row.measured_at, value=float(raw)))
    return samples


def list_alerts(
    db: Session,
    institution_id: uuid.UUID,
    *,
    patient_id: uuid.UUID | None,
    status: AlertStatus | None,
    severity: AlertSeverity | None = None,
    page: int,
    page_size: int,
) -> tuple[list[ClinicalAlert], int]:
    from sqlalchemy import func as sa_func

    filters = [ClinicalAlert.institution_id == institution_id]
    if patient_id is not None:
        filters.append(ClinicalAlert.patient_id == patient_id)
    if status is not None:
        filters.append(ClinicalAlert.status == status.value)
    if severity is not None:
        filters.append(ClinicalAlert.severity == severity.value)

    total_items = db.scalar(select(sa_func.count()).select_from(ClinicalAlert).where(*filters))
    items = db.scalars(
        select(ClinicalAlert)
        .where(*filters)
        .order_by(ClinicalAlert.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def count_alerts_by_severity(
    db: Session, institution_id: uuid.UUID, patient_id: uuid.UUID
) -> dict[str, int]:
    """Quantidade de alertas do paciente por severidade (todos os status),
    usada nos "big numbers" do painel de alertas
    (`GET /patients/{id}/alerts/summary`). Sempre devolve as tres chaves,
    mesmo com contagem zero, para o frontend nao precisar tratar ausencia
    de chave."""
    from sqlalchemy import func as sa_func

    rows = db.execute(
        select(ClinicalAlert.severity, sa_func.count())
        .where(
            ClinicalAlert.institution_id == institution_id,
            ClinicalAlert.patient_id == patient_id,
        )
        .group_by(ClinicalAlert.severity)
    ).all()
    counts_by_severity = {severity: count for severity, count in rows}
    return {
        "critical": counts_by_severity.get(AlertSeverity.CRITICAL.value, 0),
        "high": counts_by_severity.get(AlertSeverity.HIGH.value, 0),
        "moderate": counts_by_severity.get(AlertSeverity.MODERATE.value, 0),
    }


def get_alert(db: Session, institution_id: uuid.UUID, alert_id: uuid.UUID) -> ClinicalAlert:
    alert = db.scalar(
        select(ClinicalAlert).where(
            ClinicalAlert.id == alert_id, ClinicalAlert.institution_id == institution_id
        )
    )
    if alert is None:
        raise ApiError(code="ALERT_NOT_FOUND", message="Alerta nao encontrado.", status_code=404)
    return alert


def acknowledge_alert(
    db: Session, institution_id: uuid.UUID, alert_id: uuid.UUID, *, actor: str
) -> ClinicalAlert:
    alert = get_alert(db, institution_id, alert_id)
    if alert.status != AlertStatus.OPEN.value:
        raise ApiError(
            code="ALERT_NOT_OPEN",
            message="Somente alertas em aberto podem ser reconhecidos.",
            status_code=409,
        )
    alert.status = AlertStatus.ACKNOWLEDGED.value
    alert.acknowledged_by = actor
    alert.acknowledged_at = datetime.now(tz=timezone.utc)
    _audit_alert_transition(db, alert, actor, "CLINICAL_ALERT_ACKNOWLEDGED")
    db.commit()
    db.refresh(alert)
    return alert


def escalate_alert(
    db: Session,
    institution_id: uuid.UUID,
    alert_id: uuid.UUID,
    *,
    actor: str,
    escalated_to: str,
    reason: str,
) -> ClinicalAlert:
    alert = get_alert(db, institution_id, alert_id)
    if alert.status == AlertStatus.RESOLVED.value:
        raise ApiError(
            code="ALERT_ALREADY_RESOLVED",
            message="Um alerta encerrado nao pode ser escalado.",
            status_code=409,
        )
    alert.status = AlertStatus.ESCALATED.value
    alert.escalated_to = escalated_to
    alert.escalated_at = datetime.now(tz=timezone.utc)
    alert.escalation_reason = reason
    _audit_alert_transition(
        db, alert, actor, "CLINICAL_ALERT_ESCALATED", event_metadata={"escalated_to": escalated_to}
    )
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(
    db: Session, institution_id: uuid.UUID, alert_id: uuid.UUID, *, actor: str, notes: str
) -> ClinicalAlert:
    alert = get_alert(db, institution_id, alert_id)
    if alert.status == AlertStatus.RESOLVED.value:
        raise ApiError(
            code="ALERT_ALREADY_RESOLVED", message="Este alerta ja foi encerrado.", status_code=409
        )
    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_by = actor
    alert.resolved_at = datetime.now(tz=timezone.utc)
    alert.resolution_notes = notes
    _audit_alert_transition(db, alert, actor, "CLINICAL_ALERT_RESOLVED")
    db.commit()
    db.refresh(alert)
    return alert


def _audit_alert_transition(
    db: Session,
    alert: ClinicalAlert,
    actor: str,
    action: str,
    *,
    event_metadata: dict | None = None,
) -> None:
    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ANALYSIS,
        action=action,
        resource_type="clinical_alert",
        resource_id=str(alert.id),
        result=AuditResult.SUCCESS,
        institution_id=alert.institution_id,
        event_metadata={"patient_id": str(alert.patient_id), **(event_metadata or {})},
    )
