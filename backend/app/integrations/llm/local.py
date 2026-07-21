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
    LlmSummaryRequest,
    LlmSummaryResult,
)

PROMPT_VERSION = "local-template-v1"
CLINICAL_SUPPORT_PROMPT_VERSION = "local-clinical-support-template-v1"
ANALYSIS_CLINICAL_SUPPORT_PROMPT_VERSION = "local-analysis-clinical-support-template-v1"


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
                "modality_summaries": [
                    {
                        "modality_type": item.modality_type,
                        "quality_state": item.quality_state,
                        "summary": item.summary,
                    }
                    for item in request.modality_summaries
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
