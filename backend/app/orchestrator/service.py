"""Submissao, cancelamento e nova tentativa de analise.

Fecha o fluxo tecnico ate o ponto em que o orquestrador
(`app.orchestrator.worker`) assume: valida que ha conteudo
aprovado para processar, cria uma linha de estado por modalidade
(`AnalysisModalityState`), publica a mensagem na fila e transiciona
`Analysis.status` conforme `app.orchestrator.state_machine`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.core.enums import AnalysisStatus, AuditCategory, AuditResult, MediaUploadState
from app.core.errors import ApiError
from app.media.models import Analysis, MediaAsset
from app.media.service import get_analysis
from app.orchestrator.models import AnalysisModalityState
from app.orchestrator.state_machine import InvalidTransitionError, transition
from app.queue.base import QueueAdapter


def _current_status(analysis: Analysis) -> AnalysisStatus:
    return AnalysisStatus(analysis.status)


def submit_analysis(
    db: Session,
    queue: QueueAdapter,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    actor: str,
) -> Analysis:
    analysis = get_analysis(db, institution_id, analysis_id)
    current_status = _current_status(analysis)

    if current_status not in (AnalysisStatus.CREATED, AnalysisStatus.UPLOADING):
        raise ApiError(
            code="ANALYSIS_NOT_SUBMITTABLE",
            message=f"Analise em estado '{analysis.status}' nao pode ser submetida.",
            status_code=409,
        )

    media_assets = list(
        db.scalars(
            select(MediaAsset).where(
                MediaAsset.analysis_id == analysis_id,
                MediaAsset.institution_id == institution_id,
            )
        ).all()
    )

    unresolved = [
        asset
        for asset in media_assets
        if asset.upload_state
        in (MediaUploadState.AWAITING_UPLOAD.value, MediaUploadState.QUARANTINED.value)
    ]
    if unresolved:
        raise ApiError(
            code="PENDING_UPLOADS",
            message=(
                "Existem midias com upload nao confirmado. Confirme ou aguarde a "
                "resolucao de todas antes de submeter a analise."
            ),
            status_code=409,
        )

    # Um `AnalysisModalityState` por MIDIA aprovada (nao mais um por
    # modalidade): uma analise pode ter mais de uma imagem/audio/video, e
    # cada arquivo e processado e rastreado independentemente (cada
    # processador le o `MediaAsset` associado a cada estado via
    # `media_asset_id`, nunca por `modality_type` - ver
    # `app.processors.base.load_approved_media_asset`). Mantem a ordem de
    # criacao do upload para previsibilidade.
    approved_assets = [
        asset for asset in media_assets if asset.upload_state == MediaUploadState.APPROVED.value
    ]

    has_text = bool(analysis.additional_text and analysis.additional_text.strip())
    # Dados clinicos estruturados (`Analysis.structured_clinical_inputs`,
    # preenchidos na etapa "Dados clinicos" da tela de nova analise) sao um
    # conteudo valido por si so - avaliados pelo motor de regras
    # deterministico e resumidos pelo LLM em `consolidate_analysis_risk`,
    # mesmo sem nenhuma midia ou texto adicional (caso "apenas dados
    # clinicos" do fluxo de nova analise).
    has_structured_clinical_inputs = bool(analysis.structured_clinical_inputs)

    if not approved_assets and not has_text and not has_structured_clinical_inputs:
        raise ApiError(
            code="NO_MODALITY_AVAILABLE",
            message=(
                "A analise precisa de ao menos uma midia aprovada, texto adicional ou "
                "dado clinico estruturado para ser submetida."
            ),
            status_code=422,
        )

    # CREATED so pode ir direto a UPLOADING; uma analise submetida sem
    # nunca ter solicitado upload (somente texto adicional)
    # passa por UPLOADING de forma instantanea antes de QUEUED, para nao
    # exigir uma transicao CREATED->QUEUED que a tabela nao permite.
    if current_status is AnalysisStatus.CREATED:
        analysis.status = transition(current_status, AnalysisStatus.UPLOADING).value
        current_status = AnalysisStatus.UPLOADING

    analysis.status = transition(current_status, AnalysisStatus.QUEUED).value

    for media_asset in approved_assets:
        db.add(
            AnalysisModalityState(
                analysis_id=analysis.id,
                modality_type=media_asset.modality_type,
                media_asset_id=media_asset.id,
                status="PENDING",
            )
        )
    if has_text:
        db.add(
            AnalysisModalityState(
                analysis_id=analysis.id,
                modality_type="TEXT",
                media_asset_id=None,
                status="PENDING",
            )
        )

    db.flush()
    queue.enqueue({"analysis_id": str(analysis.id), "institution_id": str(institution_id)})

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ANALYSIS,
        action="ANALYSIS_SUBMIT",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis.id),
        event_metadata={
            "modalities": [asset.modality_type for asset in approved_assets]
            + (["TEXT"] if has_text else []),
            "media_asset_count": len(approved_assets),
        },
    )
    db.commit()
    db.refresh(analysis)
    return analysis


_CANCELLABLE_STATES = (
    AnalysisStatus.CREATED,
    AnalysisStatus.UPLOADING,
    AnalysisStatus.QUEUED,
    AnalysisStatus.PROCESSING,
    AnalysisStatus.PARTIALLY_COMPLETED,
)


def cancel_analysis(
    db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID, actor: str
) -> Analysis:
    analysis = get_analysis(db, institution_id, analysis_id)
    current_status = _current_status(analysis)

    try:
        analysis.status = transition(current_status, AnalysisStatus.CANCELLED).value
    except InvalidTransitionError as exc:
        raise ApiError(
            code="ANALYSIS_NOT_CANCELLABLE",
            message=f"Analise em estado '{analysis.status}' nao pode ser cancelada.",
            status_code=409,
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ANALYSIS,
        action="ANALYSIS_CANCEL",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis.id),
    )
    db.commit()
    db.refresh(analysis)
    return analysis


def retry_analysis(
    db: Session,
    queue: QueueAdapter,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    actor: str,
) -> Analysis:
    analysis = get_analysis(db, institution_id, analysis_id)
    current_status = _current_status(analysis)

    try:
        analysis.status = transition(current_status, AnalysisStatus.QUEUED).value
    except InvalidTransitionError as exc:
        raise ApiError(
            code="ANALYSIS_NOT_RETRYABLE",
            message=f"Analise em estado '{analysis.status}' nao pode ser reprocessada.",
            status_code=409,
        ) from exc

    # Modalidades que falharam de forma retentavel voltam a PENDING; as
    # que ja completaram (analise PARCIALMENTE concluida) sao preservadas.
    failed_states = list(
        db.scalars(
            select(AnalysisModalityState).where(
                AnalysisModalityState.analysis_id == analysis.id,
                AnalysisModalityState.status == "FAILED_RETRYABLE",
            )
        ).all()
    )
    for state in failed_states:
        state.status = "PENDING"
        state.error_message = None
        state.started_at = None
        state.completed_at = None

    db.flush()
    queue.enqueue({"analysis_id": str(analysis.id), "institution_id": str(institution_id)})

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ANALYSIS,
        action="ANALYSIS_RETRY",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis.id),
        event_metadata={"retried_modalities": [state.modality_type for state in failed_states]},
    )
    db.commit()
    db.refresh(analysis)
    return analysis


def list_modality_states(
    db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID
) -> list[AnalysisModalityState]:
    get_analysis(db, institution_id, analysis_id)
    return list(
        db.scalars(
            select(AnalysisModalityState)
            .where(AnalysisModalityState.analysis_id == analysis_id)
            .order_by(AnalysisModalityState.created_at)
        ).all()
    )
