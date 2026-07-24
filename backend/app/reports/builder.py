"""Composicao pura do conteudo estruturado do relatorio.

Funcao pura (sem banco/rede): recebe dados ja carregados de outros modulos
(analise, consolidacao de risco, achados por modalidade, conduta do
protocolo) e monta o dict que sera persistido em `Report.content` e
renderizado em PDF (`app.reports.pdf`). A estrutura segue os 13 pontos da
estrutura minima do resultado exigida para o relatorio:

 1. Identificacao e contexto da analise
 2. Estado do relatorio
 3. Resumo assistido por IA
 4. Risco calculado pelo motor deterministico
 5. Achados deterministicos
 6. Observacoes derivadas dos modelos
 7. Hipoteses assistidas nao confirmadas
 8. Evidencias por modalidade e correlacao temporal
 9. Inconsistencias, dados ausentes ou desatualizados
10. Qualidade e limitacoes tecnicas
11. Condutas sistemicas previstas pelo protocolo
12. Revisao e decisao do profissional
13. Proveniencia e versoes

Pontos 6 ("observacoes derivadas dos modelos") e 7 ("hipoteses
assistidas") sao preenchidos a partir de `ModalityFinding.nature`
(`FindingNature.MODEL_OBSERVATION`/`ASSISTED_HYPOTHESIS`): ficam vazios
apenas quando nenhum processador daquela analise produziu achado dessa
natureza - nunca populados artificialmente. O processador de TEXT
(`app.processors.text`) produz observacoes reais de negacao/temporalidade/
certeza/experienciador (`app.clinical_nlp.text_analysis`); as demais
modalidades ainda dependem de integracao futura (visao computacional,
transcricao) para produzir achados dessa natureza.

Alem dos 13 pontos, `modality_attention` agrega os mesmos achados 6/7 POR
MODALIDADE em um `ModalityAttentionLevel`
(NONE/OBSERVATION/ATTENTION) - um indicador puramente visual para apoiar
a leitura rapida da tela de revisao, usando a MESMA regra de relevancia
clinica ja aplicada ao guardrail do apoio automatico (`app.processors.
clinical_relevance.is_clinically_relevant`). NUNCA e um calculo de risco
nem influencia `calculated_risk` - ver docstring de `ModalityAttentionLevel`
em `app.core.enums`.

`modality_summary` consolida em UMA UNICA linha por modalidade as
perguntas antes respondidas cruzando `modality_attention` (relevancia) com
`modality_evidence` (qualidade): qualidade agregada, relevancia clinica
(bool), resumo textual e se a modalidade entra no resumo final
correlacionado. `clinical_correlation_summary` e esse resumo final -
deterministico (sem LLM), correlacionando apenas as modalidades marcadas
como clinicamente relevantes em `modality_summary`. Ver `_compute_
modality_summary`/`_compute_clinical_correlation_summary` abaixo.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import FindingNature, ModalityAttentionLevel, ModalityType
from app.processors.clinical_relevance import is_clinically_relevant


@dataclass(frozen=True)
class ReportPatientContext:
    patient_id: str
    medical_record_number: str
    full_name: str
    birth_date: str


@dataclass(frozen=True)
class ReportAnalysisContext:
    analysis_id: str
    institution_id: str
    status: str
    created_at: str
    created_by: str
    additional_text: str | None
    structured_clinical_inputs: dict


@dataclass(frozen=True)
class ReportModalityFinding:
    modality_type: str
    nature: str
    quality_state: str
    quality_metrics: dict
    quality_factors: list[str]
    summary: str
    created_at: str


@dataclass(frozen=True)
class ReportRiskConsolidation:
    outcome: str
    risk_level: int | None
    classification_label: str | None
    inconclusive_reason: str | None
    inconclusive_detail: str | None
    code_evaluations: list[dict]
    llm_status: str
    llm_summary: str | None
    llm_uncertainty_note: str | None
    llm_provider: str | None
    llm_model: str | None
    llm_prompt_version: str | None
    llm_input_hash: str | None
    llm_output_hash: str | None


@dataclass(frozen=True)
class ReportProfessionalReview:
    state: str
    confirmed_by: str | None = None
    confirmed_at: str | None = None


def _compute_modality_attention(modality_findings: list[ReportModalityFinding]) -> list[dict]:
    """Agrega os achados por `modality_type`, aplicando a mesma regra de
    relevancia clinica do guardrail do apoio automatico (`app.processors.
    clinical_relevance.is_clinically_relevant`) para decidir o `level` de
    cada modalidade PRESENTE nesta analise:

    - `ATTENTION`: ha ao menos uma `ASSISTED_HYPOTHESIS` na modalidade.
    - `OBSERVATION`: sem hipotese, mas ha ao menos um `MODEL_OBSERVATION`
      clinicamente relevante confirmado.
    - `NONE`: nenhum achado relevante (so `ORIGINAL_DATA`, ou observacoes
      de modelo sem relevancia clinica confirmada).

    So inclui modalidades que de fato tem ao menos um achado nesta
    analise (`modality_findings` sempre tem pelo menos o `ORIGINAL_DATA`
    de qualidade quando a modalidade foi processada) - nunca lista uma
    modalidade ausente da analise. Ordem estavel: `ModalityType` (IMAGE,
    AUDIO, VIDEO, TEXT), nao a ordem de chegada dos achados no banco.
    """
    relevant_summaries_by_modality: dict[str, list[str]] = {}
    has_hypothesis_by_modality: dict[str, bool] = {}
    present_modalities: list[str] = []

    for finding in modality_findings:
        if finding.modality_type not in present_modalities:
            present_modalities.append(finding.modality_type)

        if finding.nature == FindingNature.ASSISTED_HYPOTHESIS.value:
            has_hypothesis_by_modality[finding.modality_type] = True
            relevant_summaries_by_modality.setdefault(finding.modality_type, []).append(
                finding.summary
            )
        elif finding.nature == FindingNature.MODEL_OBSERVATION.value and is_clinically_relevant(
            finding.nature, finding.quality_metrics
        ):
            relevant_summaries_by_modality.setdefault(finding.modality_type, []).append(
                finding.summary
            )

    # Ordem estavel pela enum, restrita as modalidades de fato presentes
    # nesta analise.
    ordered_modalities = [m.value for m in ModalityType if m.value in present_modalities]

    result: list[dict] = []
    for modality_type in ordered_modalities:
        if has_hypothesis_by_modality.get(modality_type):
            level = ModalityAttentionLevel.ATTENTION.value
        elif relevant_summaries_by_modality.get(modality_type):
            level = ModalityAttentionLevel.OBSERVATION.value
        else:
            level = ModalityAttentionLevel.NONE.value

        result.append(
            {
                "modality_type": modality_type,
                "level": level,
                "relevant_findings_count": len(
                    relevant_summaries_by_modality.get(modality_type, [])
                ),
                "summaries": relevant_summaries_by_modality.get(modality_type, []),
            }
        )
    return result


# Severidade de `ModalityQualityState` para agregar o pior estado dentre
# os achados `ORIGINAL_DATA` de uma mesma modalidade (uma analise pode ter
# mais de uma midia da mesma modalidade) - usado por
# `_compute_modality_summary`.
_QUALITY_STATE_SEVERITY = {
    "ADEQUATE": 0,
    "MODERATE": 1,
    "INSUFFICIENT": 2,
    "INVALID": 3,
}


def _compute_modality_summary(modality_findings: list[ReportModalityFinding]) -> list[dict]:
    """Consolida, em UMA linha por modalidade, as informacoes hoje
    espalhadas entre `modality_attention` (relevancia clinica) e
    `modality_evidence` (qualidade tecnica): qualidade agregada (pior
    estado entre os achados `ORIGINAL_DATA` da modalidade), relevancia
    clinica (mesma regra de `_compute_modality_attention`/`is_clinically_
    relevant`), um resumo textual e se a modalidade entra no resumo final
    correlacionado (`_compute_clinical_correlation_summary` abaixo).

    Fonte unica para a tabela "Resumo por modalidade" da tela de revisao -
    substitui a leitura fragmentada que antes exigia cruzar `modality_
    attention` (badges) com `modality_evidence` (tabela de achados) para
    responder as mesmas 4 perguntas por modalidade. So lista modalidades
    PRESENTES nesta analise (mesmo criterio de `_compute_modality_
    attention`)."""
    quality_state_by_modality: dict[str, str] = {}
    quality_summaries_by_modality: dict[str, list[str]] = {}
    present_modalities: list[str] = []

    for finding in modality_findings:
        if finding.modality_type not in present_modalities:
            present_modalities.append(finding.modality_type)
        if finding.nature != FindingNature.ORIGINAL_DATA.value:
            continue
        quality_summaries_by_modality.setdefault(finding.modality_type, []).append(
            finding.summary
        )
        current_state = quality_state_by_modality.get(finding.modality_type)
        if current_state is None or _QUALITY_STATE_SEVERITY.get(
            finding.quality_state, 0
        ) > _QUALITY_STATE_SEVERITY.get(current_state, 0):
            quality_state_by_modality[finding.modality_type] = finding.quality_state

    attention_by_modality = {
        item["modality_type"]: item for item in _compute_modality_attention(modality_findings)
    }

    ordered_modalities = [m.value for m in ModalityType if m.value in present_modalities]

    result: list[dict] = []
    for modality_type in ordered_modalities:
        attention = attention_by_modality.get(modality_type)
        clinically_relevant = bool(
            attention and attention["level"] != ModalityAttentionLevel.NONE.value
        )
        relevant_summary = "; ".join(attention["summaries"]) if attention else ""
        quality_summary = "; ".join(quality_summaries_by_modality.get(modality_type, []))
        result.append(
            {
                "modality_type": modality_type,
                "quality_state": quality_state_by_modality.get(modality_type),
                "clinically_relevant": clinically_relevant,
                "summary": (
                    relevant_summary
                    or quality_summary
                    or "Sem dados suficientes para resumo desta modalidade."
                ),
                # Criterio deliberadamente igual a `clinically_relevant`:
                # so modalidades com achado clinicamente relevante
                # confirmado entram no resumo final correlacionado
                # (`clinical_correlation_summary`) - qualidade tecnica
                # isolada (`ORIGINAL_DATA`) nunca e suficiente por si so.
                "used_in_final_analysis": clinically_relevant,
            }
        )
    return result


def _compute_clinical_correlation_summary(modality_summary: list[dict]) -> dict:
    """Resumo final determinístico (sem chamada de LLM - sempre
    disponivel, mesmo sem credencial de nuvem configurada) que
    correlaciona APENAS as modalidades marcadas em `modality_summary`
    como `used_in_final_analysis=True`. Distinto de `ai_summary`
    (automatico, baseado em achados `ORIGINAL_DATA` sem filtro de
    relevancia) e de `clinical_support_summary` (sob demanda, via LLM,
    com filtro de relevancia hoje restrito a rotulos de imagem) - este
    campo e a resposta direta ao "resumo final correlacionando apenas as
    modalidades com dados clinicos"."""
    included = [item for item in modality_summary if item["used_in_final_analysis"]]
    excluded = [item for item in modality_summary if not item["used_in_final_analysis"]]

    if not included:
        text = (
            "Nenhuma modalidade desta analise apresentou dados clinicamente "
            "relevantes para correlacao."
        )
    else:
        parts = [f"{item['modality_type']}: {item['summary']}" for item in included]
        text = "Correlacao entre modalidades com dados clinicos - " + " | ".join(parts)

    return {
        "included_modality_types": [item["modality_type"] for item in included],
        "excluded_modality_types": [item["modality_type"] for item in excluded],
        "text": text,
    }


@dataclass(frozen=True)
class ReportClinicalSupportSummary:
    """Ultimo resultado do botao "Analisar dados clinicos" (apoio a
    analise clinica assistido por LLM, `app.clinical_support.service.
    generate_analysis_clinical_support_summary`), persistido em
    `Report.clinical_support_summary`. Distinto do "Resumo assistido por
    IA" do ponto 3 da estrutura minima (`ai_summary`, sempre gerado
    automaticamente na consolidacao de risco) - este e SOB DEMANDA e pode
    nunca ter sido gerado (`None` no chamador quando o profissional nunca
    clicou no botao)."""

    summary_text: str
    probable_causes: str
    suggested_next_steps: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    generated_at: str
    findings_considered: int


def build_report_content(
    *,
    patient: ReportPatientContext,
    analysis: ReportAnalysisContext,
    risk: ReportRiskConsolidation | None,
    modality_findings: list[ReportModalityFinding],
    protocol_action_description: str | None,
    review: ReportProfessionalReview,
    clinical_support_summary: ReportClinicalSupportSummary | None = None,
) -> dict:
    inconsistencies: list[str] = []
    if risk is None or risk.outcome == "INCONCLUSIVE":
        detail = risk.inconclusive_detail if risk else "Nenhuma consolidacao de risco disponivel."
        inconsistencies.append(detail or "Resultado inconclusivo.")
    for finding in modality_findings:
        if finding.quality_state in ("INSUFFICIENT", "INVALID"):
            inconsistencies.append(
                f"Modalidade {finding.modality_type}: qualidade {finding.quality_state} "
                f"({', '.join(finding.quality_factors) or 'sem fator especifico'})."
            )

    provenance = {
        "rule_codes_evaluated": [item["code"] for item in (risk.code_evaluations if risk else [])],
        "llm_provider": risk.llm_provider if risk else None,
        "llm_model": risk.llm_model if risk else None,
        "llm_prompt_version": risk.llm_prompt_version if risk else None,
        "llm_input_hash": risk.llm_input_hash if risk else None,
        "llm_output_hash": risk.llm_output_hash if risk else None,
    }

    modality_summary = _compute_modality_summary(modality_findings)

    return {
        "identification": {
            "analysis_id": analysis.analysis_id,
            "institution_id": analysis.institution_id,
            "patient": {
                "patient_id": patient.patient_id,
                "medical_record_number": patient.medical_record_number,
                "full_name": patient.full_name,
                "birth_date": patient.birth_date,
            },
            "created_by": analysis.created_by,
            "created_at": analysis.created_at,
            "additional_text": analysis.additional_text,
            "structured_clinical_inputs": analysis.structured_clinical_inputs,
        },
        "report_state": review.state,
        "ai_summary": {
            "text": risk.llm_summary if risk else None,
            "uncertainty_note": risk.llm_uncertainty_note if risk else None,
            "status": risk.llm_status if risk else "SKIPPED",
        },
        # Apoio a analise clinica SOB DEMANDA (botao "Analisar dados
        # clinicos") - distinto de `ai_summary` acima (automatico, sempre
        # gerado). `None` se o profissional nunca clicou no botao para
        # esta analise antes da confirmacao do relatorio.
        "clinical_support_summary": (
            {
                "summary_text": clinical_support_summary.summary_text,
                "probable_causes": clinical_support_summary.probable_causes,
                "suggested_next_steps": clinical_support_summary.suggested_next_steps,
                "uncertainty_note": clinical_support_summary.uncertainty_note,
                "provider": clinical_support_summary.provider,
                "model": clinical_support_summary.model,
                "prompt_version": clinical_support_summary.prompt_version,
                "generated_at": clinical_support_summary.generated_at,
                "findings_considered": clinical_support_summary.findings_considered,
            }
            if clinical_support_summary is not None
            else None
        ),
        "calculated_risk": {
            "outcome": risk.outcome if risk else "INCONCLUSIVE",
            "risk_level": risk.risk_level if risk else None,
            "classification_label": risk.classification_label if risk else None,
            "inconclusive_reason": risk.inconclusive_reason if risk else None,
            "inconclusive_detail": risk.inconclusive_detail if risk else None,
        },
        "deterministic_findings": risk.code_evaluations if risk else [],
        "model_observations": [
            {
                "modality_type": finding.modality_type,
                "summary": finding.summary,
                "details": finding.quality_metrics,
                "observed_at": finding.created_at,
            }
            for finding in modality_findings
            if finding.nature == "MODEL_OBSERVATION"
        ],
        "assisted_hypotheses": [
            {
                "modality_type": finding.modality_type,
                "summary": finding.summary,
                "details": finding.quality_metrics,
                "observed_at": finding.created_at,
            }
            for finding in modality_findings
            if finding.nature == "ASSISTED_HYPOTHESIS"
        ],
        # "Nivel de atencao por modalidade" - NUNCA e
        # risco clinico (ver docstring do modulo e de `ModalityAttentionLevel`
        # em app.core.enums); e um indicador puramente visual derivado dos
        # mesmos achados de `model_observations`/`assisted_hypotheses`
        # acima, agregados por modalidade, para apoiar a leitura rapida da
        # tela de revisao.
        "modality_attention": _compute_modality_attention(modality_findings),
        # Tabela consolidada "Resumo por modalidade": uma linha por
        # modalidade com qualidade + relevancia clinica + resumo + se
        # entra no resumo final correlacionado - substitui a necessidade
        # de cruzar `modality_attention` com `modality_evidence` na UI
        # para responder as mesmas perguntas.
        "modality_summary": modality_summary,
        # Resumo final deterministico correlacionando APENAS as
        # modalidades marcadas em `modality_summary` como
        # `used_in_final_analysis=True` - ver docstring de
        # `_compute_clinical_correlation_summary`.
        "clinical_correlation_summary": _compute_clinical_correlation_summary(modality_summary),
        # Evidencia por modalidade e qualidade tecnica unificadas em uma
        # unica lista/tabela (uma linha por achado, com todas as colunas
        # juntas) - antes eram duas secoes separadas repetindo a mesma
        # `modality_type` para cada achado; a UI agora renderiza isso como
        # uma tabela paginada de 5 em 5 (`AnalysisReviewPage`).
        "modality_evidence": [
            {
                "modality_type": finding.modality_type,
                "summary": finding.summary,
                "observed_at": finding.created_at,
                "quality_state": finding.quality_state,
                "quality_factors": finding.quality_factors,
            }
            for finding in modality_findings
        ],
        "inconsistencies": inconsistencies,
        "protocol_conduct": protocol_action_description,
        "professional_review": {
            "state": review.state,
            "confirmed_by": review.confirmed_by,
            "confirmed_at": review.confirmed_at,
        },
        "provenance": provenance,
    }
