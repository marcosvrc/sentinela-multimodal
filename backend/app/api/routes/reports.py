"""Endpoints de relatorio de analise.

Mesmo criterio de acesso das demais rotas de analise (medico/enfermeiro -
`app.api.routes.media`); a confirmacao do relatorio e uma decisao clinica,
por isso exige o mesmo papel usado para submeter/revisar a analise (nao
ha um papel separado so para confirmacao de laudo neste MVP).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.schemas.reports import ReportRead
from app.core.db import get_db_session
from app.core.enums import UserRole
from app.core.security import AuthenticatedUser, require_patient_access, require_role
from app.media import service as media_service
from app.reports import service as reports_service
from app.storage import get_storage_adapter
from app.storage.base import StorageAdapter

router = APIRouter(tags=["reports"])

_require_clinical_staff = require_role(UserRole.MEDICO, UserRole.ENFERMEIRO)


def _get_storage() -> StorageAdapter:
    return get_storage_adapter()


@router.get("/analyses/{analysis_id}/report", response_model=ReportRead)
def get_report(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> ReportRead:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    report = reports_service.get_report(db, current_user.institution_id, analysis_id)
    return ReportRead.model_validate(report)


@router.post("/analyses/{analysis_id}/report/confirm", response_model=ReportRead)
def confirm_report(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    storage: StorageAdapter = Depends(_get_storage),
) -> ReportRead:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    report = reports_service.confirm_report(
        db, storage, current_user.institution_id, analysis_id, current_user.external_subject
    )
    return ReportRead.model_validate(report)


@router.get("/analyses/{analysis_id}/report/pdf")
def download_report_pdf(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    storage: StorageAdapter = Depends(_get_storage),
) -> Response:
    existing = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, existing.patient_id)
    pdf_bytes = reports_service.get_report_pdf(
        db, storage, current_user.institution_id, analysis_id
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="relatorio-{analysis_id}.pdf"'},
    )
