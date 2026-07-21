"""Endpoints de submissao/cancelamento/retentativa da analise.

Mesmo criterio de acesso das demais rotas de analise/paciente: medico ou
enfermeiro.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.media import AnalysisRead
from app.api.schemas.orchestrator import AnalysisModalityStateRead
from app.core.db import get_db_session
from app.core.enums import UserRole
from app.core.security import AuthenticatedUser, require_patient_access, require_role
from app.media import service as media_service
from app.orchestrator import service as orchestrator_service
from app.queue import get_queue_adapter
from app.queue.base import QueueAdapter

router = APIRouter(prefix="/analyses", tags=["orchestrator"])

_require_clinical_staff = require_role(UserRole.MEDICO, UserRole.ENFERMEIRO)


def _get_queue() -> QueueAdapter:
    return get_queue_adapter()


@router.post("/{analysis_id}/submit", response_model=AnalysisRead)
def submit_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    queue: QueueAdapter = Depends(_get_queue),
) -> AnalysisRead:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    analysis = orchestrator_service.submit_analysis(
        db, queue, current_user.institution_id, analysis_id, current_user.external_subject
    )
    return AnalysisRead.model_validate(analysis)


@router.post("/{analysis_id}/cancel", response_model=AnalysisRead)
def cancel_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AnalysisRead:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    analysis = orchestrator_service.cancel_analysis(
        db, current_user.institution_id, analysis_id, current_user.external_subject
    )
    return AnalysisRead.model_validate(analysis)


@router.post("/{analysis_id}/retry", response_model=AnalysisRead)
def retry_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    queue: QueueAdapter = Depends(_get_queue),
) -> AnalysisRead:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    analysis = orchestrator_service.retry_analysis(
        db, queue, current_user.institution_id, analysis_id, current_user.external_subject
    )
    return AnalysisRead.model_validate(analysis)


@router.get("/{analysis_id}/modalities", response_model=list[AnalysisModalityStateRead])
def list_modality_states(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> list[AnalysisModalityStateRead]:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    states = orchestrator_service.list_modality_states(db, current_user.institution_id, analysis_id)
    return [AnalysisModalityStateRead.model_validate(state) for state in states]
