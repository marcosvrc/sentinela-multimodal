"""Contrato do apoio a analise clinica assistido por LLM.

Ver `app.clinical_support.service` - o resumo nunca e persistido (gerado
sob demanda a cada chamada), por isso este schema nao tem `from_attributes`
(nao vem de uma linha do banco).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ClinicalSupportSummaryRead(BaseModel):
    summary_text: str
    probable_causes: str
    suggested_next_steps: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    generated_at: datetime
    observations_considered: int
    alerts_considered: int


class AnalysisClinicalSupportSummaryRead(BaseModel):
    """Mesmo contrato acima, mas para o apoio a analise clinica de UMA
    analise multimodal especifica (ver `app.clinical_support.service.
    generate_analysis_clinical_support_summary`)."""

    summary_text: str
    probable_causes: str
    suggested_next_steps: str
    uncertainty_note: str
    provider: str
    model: str
    prompt_version: str
    generated_at: datetime
    findings_considered: int
