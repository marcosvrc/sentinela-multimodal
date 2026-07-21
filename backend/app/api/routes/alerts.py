"""Endpoints de alerta de anomalia.

Restrito a papeis assistenciais (medico, enfermeiro): mesmo raciocinio de
`app/api/routes/patients.py` - administradores/auditores nao acompanham
prontuario clinico identificado. Todo alerta e sempre de um paciente
especifico, entao toda rota passa por `require_patient_access` (vinculo
assistencial ou break glass) depois de confirmar o isolamento
multi-tenant.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.anomaly_detection import service as alerts_service
from app.api.schemas.alerts import (
    AlertSeverityCounts,
    ClinicalAlertRead,
    EscalateAlertRequest,
    ResolveAlertRequest,
)
from app.api.schemas.common import PageResponse
from app.core.db import get_db_session
from app.core.enums import AlertSeverity, AlertStatus, UserRole
from app.core.security import AuthenticatedUser, require_patient_access, require_role

router = APIRouter(tags=["alerts"])

_require_clinical_staff = require_role(UserRole.MEDICO, UserRole.ENFERMEIRO)


@router.get(
    "/patients/{patient_id}/alerts/summary",
    response_model=AlertSeverityCounts,
)
def get_patient_alerts_summary(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AlertSeverityCounts:
    """Contagem de alertas por severidade, usada nos "big numbers" do
    painel de alertas antes de escolher uma severidade para ver o
    detalhe paginado."""
    require_patient_access(db, current_user, patient_id)
    counts = alerts_service.count_alerts_by_severity(db, current_user.institution_id, patient_id)
    return AlertSeverityCounts(**counts)


@router.get("/patients/{patient_id}/alerts", response_model=PageResponse[ClinicalAlertRead])
def list_patient_alerts(
    patient_id: uuid.UUID,
    status: AlertStatus | None = Query(default=None),
    severity: AlertSeverity | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PageResponse[ClinicalAlertRead]:
    require_patient_access(db, current_user, patient_id)
    alerts, total_items = alerts_service.list_alerts(
        db,
        current_user.institution_id,
        patient_id=patient_id,
        status=status,
        severity=severity,
        page=page,
        page_size=page_size,
    )
    return PageResponse.build(
        items=[ClinicalAlertRead.model_validate(a) for a in alerts],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=ClinicalAlertRead)
def acknowledge_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ClinicalAlertRead:
    alert = alerts_service.get_alert(db, current_user.institution_id, alert_id)
    require_patient_access(db, current_user, alert.patient_id)
    updated = alerts_service.acknowledge_alert(
        db, current_user.institution_id, alert_id, actor=current_user.external_subject
    )
    return ClinicalAlertRead.model_validate(updated)


@router.post("/alerts/{alert_id}/escalate", response_model=ClinicalAlertRead)
def escalate_alert(
    alert_id: uuid.UUID,
    data: EscalateAlertRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ClinicalAlertRead:
    alert = alerts_service.get_alert(db, current_user.institution_id, alert_id)
    require_patient_access(db, current_user, alert.patient_id)
    updated = alerts_service.escalate_alert(
        db,
        current_user.institution_id,
        alert_id,
        actor=current_user.external_subject,
        escalated_to=data.escalated_to,
        reason=data.reason,
    )
    return ClinicalAlertRead.model_validate(updated)


@router.post("/alerts/{alert_id}/resolve", response_model=ClinicalAlertRead)
def resolve_alert(
    alert_id: uuid.UUID,
    data: ResolveAlertRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ClinicalAlertRead:
    alert = alerts_service.get_alert(db, current_user.institution_id, alert_id)
    require_patient_access(db, current_user, alert.patient_id)
    updated = alerts_service.resolve_alert(
        db,
        current_user.institution_id,
        alert_id,
        actor=current_user.external_subject,
        notes=data.notes,
    )
    return ClinicalAlertRead.model_validate(updated)
