"""Consolidador de risco de uma analise.

`consolidate_analysis_risk` e chamado pelo orquestrador
(`app.orchestrator.worker`) apos o processamento das modalidades. Ele:

1. Avalia `Analysis.structured_clinical_inputs` (entradas ja conhecidas
   pelo profissional, ver `app.media.models.Analysis`) contra o motor de
   regras deterministico (`app.rules_engine`), um `code` por vez, e combina
   os resultados pela mesma politica conservadora do motor (`app.risk_
   consolidation.engine`: risco mais alto vence, INCONCLUSIVO se nenhum
   `code` casar).
2. Pede ao adaptador de LLM configurado (`app.integrations.llm`) um resumo
   textual explicativo - usando SOMENTE uma allowlist de campos ja
   minimizados (nunca o texto adicional bruto do paciente). Falha do LLM
   (rede, credencial, timeout, resposta invalida) e capturada e registrada
   como `llm_status=FAILED`; NUNCA impede a gravacao do resultado
   deterministico - falhas de um provedor de IA externo nao podem impedir
   o registro clinico nem ocultar alertas deterministicos ja identificados.
3. Persiste (upsert) uma linha em `RiskConsolidation` e um evento de
   auditoria categoria IA (fornecedor, regiao, modelo, versao do prompt,
   hash de entrada/saida e resultado).

Populacao fixada em "adult": adulto e a populacao suportada no MVP;
excecoes exigem um protocolo proprio ainda nao implementado - nao e uma
simplificacao improvisada, e uma delimitacao deliberada do escopo atual.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.core.enums import AuditCategory, AuditResult, LlmCallStatus
from app.integrations.llm import get_llm_adapter
from app.integrations.llm.base import LlmModalitySummaryInput, LlmSummaryRequest
from app.media.models import Analysis
from app.processors.models import ModalityFinding
from app.risk_consolidation.engine import CodeEvaluation, consolidate_code_evaluations
from app.risk_consolidation.models import RiskConsolidation
from app.rules_engine import service as rules_service

_POPULATION = "adult"


@dataclass(frozen=True)
class AnalysisConsolidationStats:
    total_analyses_consolidated: int
    conclusive_count: int
    conclusive_rate_percent: float


def get_analysis_consolidation_stats(
    db: Session, institution_id: uuid.UUID
) -> AnalysisConsolidationStats:
    """Estatisticas agregadas de todas as analises da instituicao com
    consolidacao de risco ja gravada - alimenta o "big number" de
    percentual de analises conclusivas (`MATCHED`) na tela de revisao da
    analise. Junta com `Analysis` para restringir por `institution_id`
    (multi-tenant - `RiskConsolidation` nao tem a coluna direto)."""
    total = db.scalar(
        select(func.count())
        .select_from(RiskConsolidation)
        .join(Analysis, Analysis.id == RiskConsolidation.analysis_id)
        .where(Analysis.institution_id == institution_id)
    )
    conclusive = db.scalar(
        select(func.count())
        .select_from(RiskConsolidation)
        .join(Analysis, Analysis.id == RiskConsolidation.analysis_id)
        .where(
            Analysis.institution_id == institution_id,
            RiskConsolidation.outcome == "MATCHED",
        )
    )
    total = int(total or 0)
    conclusive = int(conclusive or 0)
    rate = round((conclusive / total) * 100, 1) if total > 0 else 0.0
    return AnalysisConsolidationStats(
        total_analyses_consolidated=total,
        conclusive_count=conclusive,
        conclusive_rate_percent=rate,
    )


def consolidate_analysis_risk(db: Session, analysis: Analysis) -> RiskConsolidation:
    code_evaluations: list[CodeEvaluation] = []
    for code, inputs in (analysis.structured_clinical_inputs or {}).items():
        evaluation, _rule_set = rules_service.evaluate(db, code, _POPULATION, inputs)
        code_evaluations.append(CodeEvaluation(code=code, evaluation=evaluation))

    consolidated = consolidate_code_evaluations(code_evaluations)

    # Apenas o achado de qualidade original por modalidade (`ORIGINAL_DATA`)
    # alimenta o resumo do LLM - achados `MODEL_OBSERVATION` (ex.: mencoes
    # individuais de termo clinico extraidas pelo processador de texto)
    # sao conteudo mais granular, de volume variavel, que nao
    # faz parte da allowlist minimizada enviada ao LLM (app.integrations.
    # llm.base.LlmSummaryRequest); eles aparecem no laudo via
    # `model_observations` (app.reports.builder), nao aqui.
    findings = list(
        db.scalars(
            select(ModalityFinding).where(
                ModalityFinding.analysis_id == analysis.id,
                ModalityFinding.nature == "ORIGINAL_DATA",
            )
        ).all()
    )

    llm_request = LlmSummaryRequest(
        risk_outcome=consolidated.outcome.value,
        risk_level=consolidated.risk_level,
        risk_classification_label=consolidated.classification_label,
        inconclusive_reason=(
            consolidated.inconclusive_reason.value if consolidated.inconclusive_reason else None
        ),
        matched_rule_codes=(
            tuple([consolidated.matched_code] if consolidated.matched_code else [])
        ),
        modality_summaries=tuple(
            LlmModalitySummaryInput(
                modality_type=finding.modality_type,
                quality_state=finding.quality_state,
                summary=finding.summary,
            )
            for finding in findings
        ),
    )

    llm_status = LlmCallStatus.SUCCESS
    llm_summary = None
    llm_uncertainty_note = None
    llm_error = None
    llm_provider = None
    llm_model = None
    llm_prompt_version = None
    llm_input_hash = None
    llm_output_hash = None

    try:
        adapter = get_llm_adapter(db)
        result = adapter.summarize(llm_request)
        llm_summary = result.summary_text
        llm_uncertainty_note = result.uncertainty_note
        llm_provider = result.provider
        llm_model = result.model
        llm_prompt_version = result.prompt_version
        llm_input_hash = result.input_hash
        llm_output_hash = result.output_hash
    except Exception as exc:  # noqa: BLE001 - falha de LLM nunca deve propagar
        llm_status = LlmCallStatus.FAILED
        llm_error = str(exc)[:500]

    existing = db.scalar(
        select(RiskConsolidation).where(RiskConsolidation.analysis_id == analysis.id)
    )
    row = existing or RiskConsolidation(analysis_id=analysis.id)

    row.outcome = consolidated.outcome.value
    row.risk_level = consolidated.risk_level
    row.classification_label = consolidated.classification_label
    row.inconclusive_reason = (
        consolidated.inconclusive_reason.value if consolidated.inconclusive_reason else None
    )
    row.inconclusive_detail = consolidated.inconclusive_detail
    row.code_evaluations = [
        {
            "code": item.code,
            "outcome": item.evaluation.outcome.value,
            "risk_level": item.evaluation.risk_level,
            "classification_label": (
                item.evaluation.matched_rule.classification_label
                if item.evaluation.matched_rule
                else None
            ),
            "inconclusive_reason": (
                item.evaluation.inconclusive_reason.value
                if item.evaluation.inconclusive_reason
                else None
            ),
        }
        for item in code_evaluations
    ]
    row.llm_status = llm_status.value
    row.llm_summary = llm_summary
    row.llm_uncertainty_note = llm_uncertainty_note
    row.llm_error = llm_error
    row.llm_provider = llm_provider
    row.llm_model = llm_model
    row.llm_prompt_version = llm_prompt_version
    row.llm_input_hash = llm_input_hash
    row.llm_output_hash = llm_output_hash

    if existing is None:
        db.add(row)
    db.flush()

    audit_service.record_event(
        db,
        actor="system-risk-consolidator",
        category=AuditCategory.AI,
        action="ANALYSIS_RISK_CONSOLIDATED",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS if llm_status != LlmCallStatus.FAILED else AuditResult.ERROR,
        institution_id=analysis.institution_id,
        analysis_id=str(analysis.id),
        event_metadata={
            "outcome": row.outcome,
            "risk_level": row.risk_level,
            "llm_status": row.llm_status,
            "llm_provider": row.llm_provider,
            "llm_model": row.llm_model,
            "llm_prompt_version": row.llm_prompt_version,
            "llm_input_hash": row.llm_input_hash,
            "llm_output_hash": row.llm_output_hash,
        },
    )

    return row
