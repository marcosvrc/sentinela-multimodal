"""Orquestrador: consome a fila e avanca a maquina de estados.

`process_next_message` e a unidade de trabalho de um worker stateless:
cada chamada abre sua propria sessao de banco e nao guarda estado entre
execucoes. Dispara um `ModalityProcessor` por modalidade pendente da
analise. Os processadores reais vivem em `app.processors.registry.
PROCESSORS` e sao passados explicitamente pelo chamador (ver
`scripts/run_orchestrator_worker.py`); quando nenhum processador esta
registrado para uma modalidade, ela termina em `FAILED_RETRYABLE` com um
motivo explicito, em vez de fingir um resultado clinico. Este modulo
permanece agnostico de quais processadores existem: o dict `processors` e
quem cresce.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.clinical_support import service as clinical_support_service
from app.core.enums import AnalysisStatus, AuditCategory, AuditResult, ModalityType
from app.feature_flags.service import get_feature_flags
from app.media.models import Analysis
from app.orchestrator.models import AnalysisModalityState
from app.orchestrator.state_machine import transition
from app.queue.base import QueueAdapter
from app.reports.service import generate_report
from app.risk_consolidation.service import consolidate_analysis_risk

NO_PROCESSOR_REGISTERED_MESSAGE = (
    "Nenhum processador registrado para esta modalidade (ainda nao implementado)."
)


class ModalityProcessor(Protocol):
    """Contrato que cada processador de modalidade real implementa."""

    def __call__(self, db: Session, modality_state: AnalysisModalityState) -> None: ...


@dataclass(frozen=True)
class ModalityStateResult:
    """Resultado de UM `AnalysisModalityState` processado - `modality_type`
    nao e mais uma chave unica desde que uma analise passou a aceitar
    multiplas midias da mesma modalidade (ver `app.orchestrator.service.
    submit_analysis`); por isso o resultado e uma lista, nao um dict
    chaveado por `modality_type` (que colidiria/perderia entradas)."""

    modality_state_id: uuid.UUID
    modality_type: str
    media_asset_id: uuid.UUID | None
    status: str


@dataclass(frozen=True)
class ProcessingOutcome:
    analysis_id: uuid.UUID
    final_status: AnalysisStatus
    modality_results: list[ModalityStateResult]


def process_next_message(
    db: Session,
    queue: QueueAdapter,
    processors: dict[ModalityType, ModalityProcessor] | None = None,
) -> ProcessingOutcome | None:
    """Processa uma mensagem da fila, se houver. Retorna `None` se a fila estiver vazia."""
    processors = processors or {}

    messages = queue.receive(max_messages=1)
    if not messages:
        return None

    message = messages[0]
    analysis_id = uuid.UUID(message.body["analysis_id"])

    analysis = db.scalar(select(Analysis).where(Analysis.id == analysis_id))
    if analysis is None:
        # Mensagem orfa (analise excluida entre o enqueue e o consumo); nao
        # ha nada a processar. Descarta a mensagem para nao girar em loop.
        queue.delete(message.receipt_handle)
        return None

    current_status = AnalysisStatus(analysis.status)
    if current_status is AnalysisStatus.QUEUED:
        analysis.status = transition(current_status, AnalysisStatus.PROCESSING).value
        db.flush()
    elif current_status is not AnalysisStatus.PROCESSING:
        # Mensagem duplicada/atrasada para uma analise que ja saiu de
        # QUEUED/PROCESSING (ex: foi cancelada) - descarta sem reprocessar.
        queue.delete(message.receipt_handle)
        return None

    modality_states = list(
        db.scalars(
            select(AnalysisModalityState).where(
                AnalysisModalityState.analysis_id == analysis.id,
                AnalysisModalityState.status == "PENDING",
            )
        ).all()
    )

    for modality_state in modality_states:
        modality_state.started_at = datetime.now(tz=timezone.utc)
        processor = processors.get(ModalityType(modality_state.modality_type))
        if processor is None:
            modality_state.status = "FAILED_RETRYABLE"
            modality_state.error_message = NO_PROCESSOR_REGISTERED_MESSAGE
            modality_state.completed_at = datetime.now(tz=timezone.utc)
            continue

        try:
            processor(db, modality_state)
            modality_state.status = "COMPLETED"
        except Exception as exc:  # noqa: BLE001
            modality_state.status = "FAILED_RETRYABLE"
            modality_state.error_message = str(exc)[:500]
        modality_state.completed_at = datetime.now(tz=timezone.utc)

    db.flush()

    all_states = list(
        db.scalars(
            select(AnalysisModalityState).where(AnalysisModalityState.analysis_id == analysis.id)
        ).all()
    )
    final_status = _decide_final_status(all_states)
    analysis.status = transition(AnalysisStatus.PROCESSING, final_status).value

    if final_status in (AnalysisStatus.WAITING_REVIEW, AnalysisStatus.PARTIALLY_COMPLETED):
        # Consolida o risco deterministico sempre que houver ao menos uma
        # modalidade concluida - mesmo em PARTIALLY_COMPLETED, para nao
        # ocultar um alerta ja identificado so porque outra modalidade
        # falhou. Falha do LLM e tratada dentro de
        # `consolidate_analysis_risk` e nunca propaga.
        consolidate_analysis_risk(db, analysis)
        # Relatorio em DRAFT: fica pronto para revisao assim que ha
        # consolidacao de risco, sem gerar PDF ainda (isso so acontece na
        # confirmacao - ver app.reports.service.confirm_report).
        generate_report(db, analysis)
        # Apoio a analise clinica (IA) AUTOMATICO - substitui o botao
        # manual "Analisar dados clinicos" quando a feature flag
        # `auto_clinical_support_enabled` esta ligada (tela `/admin/
        # feature-flags`). Desligada, nenhuma chamada automatica ocorre
        # (equivalente a nunca clicar o botao manual). Mesmo com a flag
        # ligada, so executa quando ha conteudo clinicamente relevante
        # identificado nesta analise (ver `app.clinical_support.service.
        # should_run_automatic_clinical_support`) - nunca chama o LLM so
        # porque ha midia, se essa midia nao tiver sinal clinico
        # confirmado. Falha do LLM aqui nunca deve interromper o
        # processamento do worker (mesmo principio de `consolidate_
        # analysis_risk` - falha de IA nunca bloqueia o registro clinico
        # ja calculado).
        _maybe_run_automatic_clinical_support(db, analysis)

    audit_service.record_event(
        db,
        actor="system-orchestrator",
        category=AuditCategory.ANALYSIS,
        action="ANALYSIS_PROCESSING_COMPLETED",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS,
        institution_id=analysis.institution_id,
        analysis_id=str(analysis.id),
        event_metadata={
            "final_status": final_status.value,
            "modality_results": [
                {
                    "modality_state_id": str(state.id),
                    "modality_type": state.modality_type,
                    "media_asset_id": str(state.media_asset_id) if state.media_asset_id else None,
                    "status": state.status,
                }
                for state in all_states
            ],
        },
    )
    db.commit()
    queue.delete(message.receipt_handle)

    return ProcessingOutcome(
        analysis_id=analysis.id,
        final_status=final_status,
        modality_results=[
            ModalityStateResult(
                modality_state_id=state.id,
                modality_type=state.modality_type,
                media_asset_id=state.media_asset_id,
                status=state.status,
            )
            for state in all_states
        ],
    )


def _maybe_run_automatic_clinical_support(db: Session, analysis: Analysis) -> None:
    flags = get_feature_flags(db)
    if not flags.auto_clinical_support_enabled:
        return

    if not clinical_support_service.should_run_automatic_clinical_support(db, analysis.id):
        return

    try:
        clinical_support_service.generate_analysis_clinical_support_summary(
            db,
            analysis.institution_id,
            analysis.id,
            actor="system-orchestrator",
            actor_role=None,
        )
    except Exception:  # noqa: BLE001 - falha de IA nunca bloqueia o processamento
        # `generate_analysis_clinical_support_summary` ja registra seu
        # proprio evento de auditoria ANALYSIS_CLINICAL_SUPPORT_SUMMARY_
        # FAILED e comita antes de levantar `ApiError` - nada adicional a
        # fazer aqui alem de engolir a excecao e seguir o processamento
        # normal do worker (consolidacao de risco/relatorio ja gravados
        # continuam validos independente deste apoio opcional).
        pass


def _decide_final_status(states: list[AnalysisModalityState]) -> AnalysisStatus:
    if not states:
        # Analise submetida com APENAS dados clinicos estruturados (sem
        # midia nem texto adicional - ver `app.orchestrator.service.
        # submit_analysis`): nao ha nenhum `AnalysisModalityState` a
        # processar, mas isso e um caso valido, nao um bug. O motor de
        # regras deterministico + resumo do LLM (`consolidate_analysis_
        # risk`, disparado pelo chamador quando o status final e
        # WAITING_REVIEW) e o unico conteudo desta analise.
        return AnalysisStatus.WAITING_REVIEW

    statuses = {state.status for state in states}
    if statuses == {"COMPLETED"}:
        return AnalysisStatus.WAITING_REVIEW
    if "COMPLETED" in statuses:
        return AnalysisStatus.PARTIALLY_COMPLETED
    return AnalysisStatus.FAILED_RETRYABLE
