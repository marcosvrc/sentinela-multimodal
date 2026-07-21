"""Endpoints de analise e upload de midia.

Acesso as rotas de negocio restrito a medico/enfermeiro, mesmo criterio
usado em app/api/routes/patients.py (usuarios so acessam pacientes e
funcoes autorizadas para seu papel).

A rota `PUT /media/local-storage/{token}` e a implementacao do upload
direto do adaptador de armazenamento local (app/storage/local.py) - nao
usa `require_role` porque quem autentica o upload e a assinatura da
propria URL pre-assinada (token HMAC), nao uma sessao de usuario.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.administration import service as administration_service
from app.api.schemas.clinical_support import AnalysisClinicalSupportSummaryRead
from app.api.schemas.common import PageResponse
from app.api.schemas.media import (
    AnalysisCreate,
    AnalysisRead,
    AnalysisStatsRead,
    MediaAssetRead,
    MediaConfirmRequest,
    MediaUploadRequest,
    MediaUploadResponse,
    ProfessionalRead,
)
from app.clinical_support import service as clinical_support_service
from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.core.security import AuthenticatedUser, require_patient_access, require_role
from app.identity import service as identity_service
from app.media import service as media_service
from app.media.models import Analysis
from app.patients import service as patients_service
from app.patients.models import Patient
from app.risk_consolidation import service as risk_consolidation_service
from app.storage import get_storage_adapter
from app.storage.base import StorageAdapter
from app.storage.local import (
    LocalFilesystemStorageAdapter,
    LocalUploadTokenError,
    decode_local_upload_token,
)

router = APIRouter(tags=["media"])

_require_clinical_staff = require_role(UserRole.MEDICO, UserRole.ENFERMEIRO)


def _to_analysis_read(
    analysis: Analysis,
    full_name_by_subject: dict[str, str],
    patients_by_id: dict[uuid.UUID, Patient] | None = None,
) -> AnalysisRead:
    patient = (patients_by_id or {}).get(analysis.patient_id)
    return AnalysisRead(
        id=analysis.id,
        patient_id=analysis.patient_id,
        status=analysis.status,
        additional_text=analysis.additional_text,
        structured_clinical_inputs=analysis.structured_clinical_inputs,
        created_by=analysis.created_by,
        created_by_full_name=full_name_by_subject.get(analysis.created_by),
        patient_full_name=patient.full_name if patient else None,
        patient_medical_record_number=patient.medical_record_number if patient else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


def _get_storage() -> StorageAdapter:
    return get_storage_adapter()


@router.post("/analyses", response_model=AnalysisRead, status_code=201)
def create_analysis(
    data: AnalysisCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AnalysisRead:
    require_patient_access(db, current_user, data.patient_id)
    analysis = media_service.create_analysis(
        db,
        current_user.institution_id,
        data.patient_id,
        current_user.external_subject,
        data.additional_text,
        data.structured_clinical_inputs,
    )
    return AnalysisRead.model_validate(analysis)


@router.get("/analyses", response_model=PageResponse[AnalysisRead])
def list_analyses(
    patient_id: uuid.UUID | None = Query(default=None),
    created_by: str | None = Query(
        default=None, description="external_subject exato do profissional (filtro 'Medico')."
    ),
    created_from: date | None = Query(
        default=None, description="Data inicial (inclusiva) de criacao da analise."
    ),
    created_to: date | None = Query(
        default=None, description="Data final (inclusiva) de criacao da analise."
    ),
    patient_name: str | None = Query(
        default=None, description="Filtro por nome do paciente (substring, case-insensitive)."
    ),
    patient_medical_record_number: str | None = Query(
        default=None,
        description="Filtro por numero de prontuario do paciente (substring, case-insensitive).",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> PageResponse[AnalysisRead]:
    if patient_id is not None:
        require_patient_access(db, current_user, patient_id)

    created_from_dt = (
        datetime.combine(created_from, time.min, tzinfo=timezone.utc)
        if created_from is not None
        else None
    )
    created_to_dt = (
        datetime.combine(created_to, time.max, tzinfo=timezone.utc)
        if created_to is not None
        else None
    )

    analyses, total_items = media_service.list_analyses(
        db,
        current_user.institution_id,
        patient_id,
        page,
        page_size,
        created_by=created_by,
        created_from=created_from_dt,
        created_to=created_to_dt,
        patient_name=patient_name,
        patient_medical_record_number=patient_medical_record_number,
    )

    full_name_by_subject = {
        user.external_subject: user.full_name
        for user in identity_service.get_users_by_external_subjects(
            db, current_user.institution_id, {analysis.created_by for analysis in analyses}
        ).values()
    }
    patients_by_id = patients_service.get_patients_by_ids(
        db, current_user.institution_id, {analysis.patient_id for analysis in analyses}
    )

    return PageResponse.build(
        items=[
            _to_analysis_read(analysis, full_name_by_subject, patients_by_id)
            for analysis in analyses
        ],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.get("/analyses/stats", response_model=AnalysisStatsRead)
def get_analysis_stats(
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AnalysisStatsRead:
    """Estatisticas agregadas de todas as analises da instituicao com
    consolidacao de risco ja gravada (percentual de analises conclusivas -
    ver `app.risk_consolidation.service.get_analysis_consolidation_stats`),
    usadas nos "big numbers" da tela de revisao da analise."""
    stats = risk_consolidation_service.get_analysis_consolidation_stats(
        db, current_user.institution_id
    )
    return AnalysisStatsRead(
        total_analyses_consolidated=stats.total_analyses_consolidated,
        conclusive_count=stats.conclusive_count,
        conclusive_rate_percent=stats.conclusive_rate_percent,
    )


@router.get("/analyses/professionals", response_model=list[ProfessionalRead])
def list_analysis_professionals(
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> list[ProfessionalRead]:
    """Opcoes do filtro "Medico" do historico de analises e do campo
    pesquisavel de funcionario no popup de observacao clinica (matricula +
    nome)."""
    professionals = identity_service.list_clinical_staff(db, current_user.institution_id)
    registration_by_user_id = administration_service.get_registration_numbers_by_user_id(
        db, current_user.institution_id, {user.id for user in professionals}
    )
    return [
        ProfessionalRead(
            external_subject=user.external_subject,
            full_name=user.full_name,
            registration_number=registration_by_user_id.get(user.id),
        )
        for user in professionals
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
def get_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AnalysisRead:
    analysis = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, analysis.patient_id)
    return AnalysisRead.model_validate(analysis)


@router.post(
    "/analyses/{analysis_id}/clinical-support-summary",
    response_model=AnalysisClinicalSupportSummaryRead,
)
def generate_analysis_clinical_support_summary(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> AnalysisClinicalSupportSummaryRead:
    """Apoio a analise clinica assistido por LLM para esta analise
    multimodal especifica (botao "Analisar dados clinicos" da tela de
    revisao/relatorio da analise). Consolida os achados JA PRODUZIDOS pelos
    processadores de modalidade (imagem/audio/video/texto) e o risco JA
    CALCULADO deterministicamente em um resumo com visao clinica, causas
    provaveis e direcionamento sugerido - sempre como apoio, nunca como
    diagnostico ou substituicao da analise do profissional responsavel
    (ver `app.clinical_support.service.
    generate_analysis_clinical_support_summary`)."""
    analysis = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, analysis.patient_id)
    summary = clinical_support_service.generate_analysis_clinical_support_summary(
        db,
        current_user.institution_id,
        analysis_id,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
    )
    return AnalysisClinicalSupportSummaryRead(
        summary_text=summary.summary_text,
        probable_causes=summary.probable_causes,
        suggested_next_steps=summary.suggested_next_steps,
        uncertainty_note=summary.uncertainty_note,
        provider=summary.provider,
        model=summary.model,
        prompt_version=summary.prompt_version,
        generated_at=summary.generated_at,
        findings_considered=summary.findings_considered,
    )


@router.post("/analyses/{analysis_id}/media", response_model=MediaUploadResponse, status_code=201)
def request_upload_url(
    analysis_id: uuid.UUID,
    data: MediaUploadRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    storage: StorageAdapter = Depends(_get_storage),
) -> MediaUploadResponse:
    analysis = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, analysis.patient_id)
    media_asset, presigned = media_service.request_upload_url(
        db,
        storage,
        current_user.institution_id,
        analysis_id,
        current_user.external_subject,
        data.modality_type,
        data.filename,
        data.mime_type,
        data.size_bytes,
    )
    return MediaUploadResponse(
        media_id=media_asset.id,
        upload_url=presigned.url,
        upload_method=presigned.method,
        upload_headers=presigned.headers,
        expires_at=presigned.expires_at,
    )


@router.post("/analyses/{analysis_id}/media/{media_id}/confirm", response_model=MediaAssetRead)
def confirm_upload(
    analysis_id: uuid.UUID,
    media_id: uuid.UUID,
    data: MediaConfirmRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
    storage: StorageAdapter = Depends(_get_storage),
) -> MediaAssetRead:
    analysis = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, analysis.patient_id)
    media_asset = media_service.confirm_upload(
        db,
        storage,
        current_user.institution_id,
        analysis_id,
        media_id,
        current_user.external_subject,
        data.checksum_sha256,
    )
    return MediaAssetRead.model_validate(media_asset)


@router.get("/analyses/{analysis_id}/media", response_model=list[MediaAssetRead])
def list_media_assets(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_staff),
) -> list[MediaAssetRead]:
    analysis = media_service.get_analysis(db, current_user.institution_id, analysis_id)
    require_patient_access(db, current_user, analysis.patient_id)
    media_assets = media_service.list_media_assets(db, current_user.institution_id, analysis_id)
    return [MediaAssetRead.model_validate(media_asset) for media_asset in media_assets]


@router.put("/media/local-storage/{token}", status_code=204)
async def upload_to_local_storage(token: str, request: Request) -> Response:
    settings = get_settings()
    try:
        decoded = decode_local_upload_token(token, secret=settings.media_local_upload_secret)
    except LocalUploadTokenError as exc:
        raise ApiError(code="INVALID_UPLOAD_TOKEN", message=str(exc), status_code=403) from exc

    storage = get_storage_adapter()
    assert isinstance(storage, LocalFilesystemStorageAdapter)

    body = await request.body()
    storage.write_quarantined_object(decoded.quarantine_key, body)
    return Response(status_code=204)
