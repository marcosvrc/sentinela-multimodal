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
