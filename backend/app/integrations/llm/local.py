"""Adaptador LOCAL de LLM: template deterministico, sem chamada de rede.

TEMPORARIO (mesmo padrao dos adaptadores locais de storage/queue/identidade
- ver `app.storage.local`, `app.queue.local`): usado em dev/testes para
exercitar o fluxo de consolidacao de ponta a ponta sem depender de
credenciais OpenAI. Produz um resumo textual fixo e auditavel a partir dos
mesmos campos que o adaptador real receberia - nunca inventa achados,
apenas formata o que ja foi calculado deterministicamente.
"""

from __future__ import annotations

import hashlib
import json

from app.integrations.llm.base import (
    LlmAnalysisClinicalSupportRequest,
    LlmClinicalSupportRequest,
    LlmClinicalSupportResult,
    LlmModalityRiskAssessmentRequest,
    LlmModalityRiskAssessmentResult,
    LlmSummaryRequest,
    LlmSummaryResult,
    LlmTextRelevanceCheckRequest,
    LlmTextRelevanceCheckResult,
)

PROMPT_VERSION = "local-template-v1"
CLINICAL_SUPPORT_PROMPT_VERSION = "local-clinical-support-template-v1"
ANALYSIS_CLINICAL_SUPPORT_PROMPT_VERSION = "local-analysis-clinical-support-template-v1"
MODALITY_RISK_PROMPT_VERSION = "local-modality-risk-template-v1"


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LocalTemplateLlmAdapter:
    def summarize(self, request: LlmSummaryRequest) -> LlmSummaryResult:
        input_payload = json.dumps(
            {
                "risk_outcome": request.risk_outcome,
                "risk_level": request.risk_level,
                "risk_classification_label": request.risk_classification_label,
                "inconclusive_reason": request.inconclusive_reason,
                "matched_rule_codes": list(request.matched_rule_codes),
                "structured_inputs": request.structured_inputs,
                "modality_summaries": [
                    {
                        "modality_type": item.modality_type,
                        "quality_state": item.quality_state,
                        "summary": item.summary,
                    }
                    for item in request.modality_summaries
                ],
                "clinical_findings": [
                    {"modality_type": item.modality_type, "summary": item.summary}
                    for item in request.clinical_findings
                ],
            },
            sort_keys=True,
        )

        if request.risk_outcome == "MATCHED":
            summary_text = (
                f"Classificacao deterministica: nivel {request.risk_level} "
                f"({request.risk_classification_label}), a partir de "
                f"{', '.join(request.matched_rule_codes) or 'regra nao identificada'}."
            )
            # Adiciona valores clínicos estruturados
            if request.structured_inputs:
                inputs_notes = "; ".join(
                    f"{code}: {vals}" for code, vals in request.structured_inputs.items()
                )
                summary_text += f" Valores informados: {inputs_notes}."
        else:
            summary_text = (
                "Classificacao inconclusiva: "
                f"{request.inconclusive_reason or 'motivo nao especificado'}."
            )

        if request.modality_summaries:
            modality_notes = "; ".join(
                f"{item.modality_type}={item.quality_state} ({item.summary})"
                for item in request.modality_summaries
            )
            summary_text += f" Modalidades: {modality_notes}."

        if request.clinical_findings:
            findings_notes = "; ".join(
                f"{item.modality_type}: {item.summary}" for item in request.clinical_findings[:5]
            )
            summary_text += f" Achados multimodais relevantes: {findings_notes}."

        uncertainty_note = (
            "Resumo gerado por template local (sem LLM real); nao substitui revisao profissional."
            if request.risk_outcome == "MATCHED"
            else "Resultado inconclusivo exige avaliacao adicional pelo profissional responsavel."
        )

        return LlmSummaryResult(
            summary_text=summary_text,
            uncertainty_note=uncertainty_note,
            provider="local",
            model="local-template",
            prompt_version=PROMPT_VERSION,
            input_hash=_hash(input_payload),
            output_hash=_hash(summary_text + uncertainty_note),
        )

    def generate_clinical_support_summary(
        self, request: LlmClinicalSupportRequest
    ) -> LlmClinicalSupportResult:
        input_payload = json.dumps(
            {
                "patient_age": request.patient_age,
                "patient_sex": request.patient_sex,
                "observations": [
                    {
                        "observation_type": item.observation_type,
                        "unit": item.unit,
                        "recent_values": list(item.recent_values),
                    }
                    for item in request.observations
                ],
                "alerts": [
                    {
                        "signal_key": item.signal_key,
                        "severity": item.severity,
                        "status": item.status,
                        "expected_action": item.expected_action,
                        "detected_at": item.detected_at,
                    }
                    for item in request.alerts
                ],
            },
            sort_keys=True,
        )

        if request.observations:
            observation_notes = "; ".join(
                f"{item.observation_type} ({len(item.recent_values)} registro(s) recente(s))"
                for item in request.observations
            )
            summary_text = (
                f"Paciente com {request.patient_age} anos ({request.patient_sex}). "
                f"Dados clinicos disponiveis: {observation_notes}."
            )
        else:
            summary_text = (
                f"Paciente com {request.patient_age} anos ({request.patient_sex}). "
                "Nenhuma observacao clinica registrada ainda."
            )

        if request.alerts:
            alert_notes = "; ".join(
                f"{item.signal_key} ({item.severity}, status {item.status})"
                for item in request.alerts
            )
            probable_causes = (
                f"Alertas de anomalia registrados: {alert_notes}. Resumo gerado por template "
                "local (sem LLM real) - nao identifica causa clinica real."
            )
        else:
            probable_causes = (
                "Nenhum alerta de anomalia registrado no periodo avaliado. Resumo gerado por "
                "template local (sem LLM real)."
            )

        suggested_next_steps = (
            "Revisar a serie temporal completa de cada sinal e correlacionar com o quadro "
            "clinico do paciente antes de qualquer decisao (template local, sem LLM real)."
        )
        uncertainty_note = (
            "Este e um apoio a analise clinica gerado automaticamente (template local, sem "
            "LLM real) - nao e um diagnostico e nao substitui a avaliacao do profissional "
            "responsavel, que deve sempre realizar sua propria analise."
        )

        output_text = summary_text + probable_causes + suggested_next_steps + uncertainty_note
        return LlmClinicalSupportResult(
            summary_text=summary_text,
            probable_causes=probable_causes,
            suggested_next_steps=suggested_next_steps,
            uncertainty_note=uncertainty_note,
            provider="local",
            model="local-template",
            prompt_version=CLINICAL_SUPPORT_PROMPT_VERSION,
            input_hash=_hash(input_payload),
            output_hash=_hash(output_text),
        )

    def generate_analysis_clinical_support_summary(
        self, request: LlmAnalysisClinicalSupportRequest
    ) -> LlmClinicalSupportResult:
        input_payload = json.dumps(
            {
                "patient_age": request.patient_age,
                "patient_sex": request.patient_sex,
                "risk_outcome": request.risk_outcome,
                "risk_level": request.risk_level,
                "risk_classification_label": request.risk_classification_label,
                "structured_inputs": [
                    {"code": item.code, "inputs": item.inputs} for item in request.structured_inputs
                ],
                "findings": [
                    {
                        "modality_type": item.modality_type,
                        "nature": item.nature,
                        "quality_state": item.quality_state,
                        "summary": item.summary,
                    }
                    for item in request.findings
                ],
            },
            sort_keys=True,
        )

        risk_note = (
            f"risco {request.risk_classification_label} (nivel {request.risk_level})"
            if request.risk_outcome == "MATCHED"
            else "risco inconclusivo"
        )
        summary_text = (
            f"Paciente com {request.patient_age} anos ({request.patient_sex}). "
            f"Analise multimodal com {risk_note}."
        )

        if request.structured_inputs:
            structured_notes = "; ".join(
                f"{item.code}: {item.inputs}" for item in request.structured_inputs
            )
            summary_text += f" Dados clinicos estruturados: {structured_notes}."

        if request.findings:
            findings_notes = "; ".join(
                f"{item.modality_type} ({item.nature.lower()}): {item.summary}"
                for item in request.findings
            )
            summary_text += f" Achados por modalidade: {findings_notes}."
            probable_causes = (
                "Achados consolidados a partir das modalidades enviadas nesta analise, "
                "correlacionados com os dados clinicos estruturados quando disponiveis. "
                "Resumo gerado por template local (sem LLM real) - nao identifica causa "
                "clinica real."
            )
        else:
            probable_causes = (
                "Nenhum achado de modalidade disponivel nesta analise. Resumo gerado por "
                "template local (sem LLM real)."
            )

        suggested_next_steps = (
            "Revisar cada achado por modalidade e correlacionar com o quadro clinico do "
            "paciente antes de qualquer decisao (template local, sem LLM real)."
        )
        uncertainty_note = (
            "Este e um apoio a analise clinica desta analise multimodal, gerado "
            "automaticamente (template local, sem LLM real) - nao e um diagnostico e nao "
            "substitui a avaliacao do profissional responsavel, que deve sempre realizar "
            "sua propria analise."
        )

        output_text = summary_text + probable_causes + suggested_next_steps + uncertainty_note
        return LlmClinicalSupportResult(
            summary_text=summary_text,
            probable_causes=probable_causes,
            suggested_next_steps=suggested_next_steps,
            uncertainty_note=uncertainty_note,
            provider="local",
            model="local-template",
            prompt_version=ANALYSIS_CLINICAL_SUPPORT_PROMPT_VERSION,
            input_hash=_hash(input_payload),
            output_hash=_hash(output_text),
        )

    def assess_modality_risk(
        self, request: LlmModalityRiskAssessmentRequest
    ) -> LlmModalityRiskAssessmentResult:
        input_payload = json.dumps(
            {
                "findings": [
                    {
                        "modality_type": f.modality_type,
                        "nature": f.nature,
                        "quality_state": f.quality_state,
                        "summary": f.summary,
                    }
                    for f in request.findings
                ],
                "deterministic_risk_outcome": request.deterministic_risk_outcome,
                "deterministic_risk_level": request.deterministic_risk_level,
            },
            sort_keys=True,
        )

        # Heuristica local simples: achados ASSISTED_HYPOTHESIS presentes
        # sugerem risco moderado (3); achados MODEL_OBSERVATION relevantes
        # sem hipotese sugerem risco leve (2); nada relevante = baixo (1).
        has_hypothesis = any(f.nature == "ASSISTED_HYPOTHESIS" for f in request.findings)
        has_observation = any(f.nature == "MODEL_OBSERVATION" for f in request.findings)

        if has_hypothesis:
            risk_level = 3
            classification_label = "Risco moderado (hipotese assistida identificada)"
        elif has_observation:
            risk_level = 2
            classification_label = "Risco leve (observacao de modelo identificada)"
        else:
            risk_level = 1
            classification_label = "Risco baixo (sem achado clinico relevante nas modalidades)"

        justification = (
            f"Avaliacao assistida baseada em {len(request.findings)} achado(s) multimodal(is). "
            f"Template local (sem LLM real) - heuristica simplificada."
        )
        uncertainty_note = (
            "Risco assistido por IA (template local) - sugestao, nao classificacao definitiva. "
            "O profissional deve avaliar os achados individualmente."
        )

        output_text = f"{risk_level}|{classification_label}|{justification}|{uncertainty_note}"
        return LlmModalityRiskAssessmentResult(
            risk_level=risk_level,
            classification_label=classification_label,
            justification=justification,
            uncertainty_note=uncertainty_note,
            provider="local",
            model="local-template",
            prompt_version=MODALITY_RISK_PROMPT_VERSION,
            input_hash=_hash(input_payload),
            output_hash=_hash(output_text),
        )

    def check_text_clinical_relevance(
        self, request: LlmTextRelevanceCheckRequest
    ) -> LlmTextRelevanceCheckResult:
        """Heuristica local simples: verifica se o texto contem ao menos
        um termo do vocabulario clinico curado (mesma lista usada pelo
        extrator NegEx/ConText). Sem LLM real."""
        from app.clinical_nlp.text_analysis import analyze_clinical_text

        mentions = list(analyze_clinical_text(request.text))
        word_count = len(request.text.split())
        # Relevante se encontrar ao menos 1 termo clinico num texto com
        # palavras suficientes (>= 3 palavras)
        is_relevant = len(mentions) > 0 and word_count >= 3
        pct = min(100, int((len(mentions) / max(word_count, 1)) * 100 * 10))

        return LlmTextRelevanceCheckResult(
            is_clinically_relevant=is_relevant,
            relevance_percent=pct,
            reason=(
                f"{len(mentions)} termo(s) clinico(s) em {word_count} palavras (template local)"
                if is_relevant
                else f"Nenhum termo clinico identificado em {word_count} palavras (template local)"
            ),
            provider="local",
            model="local-template",
        )

    def extract_clinical_terms(self, text: str) -> list[dict]:
        """Fallback local: usa o NegEx/ConText determinístico."""
        from app.clinical_nlp.text_analysis import analyze_clinical_text

        mentions = analyze_clinical_text(text)
        return [
            {
                "term": m.term,
                "negation": m.negation.value,
                "temporality": m.temporality.value,
                "certainty": m.certainty.value,
                "experiencer": m.experiencer.value,
            }
            for m in mentions
        ]
