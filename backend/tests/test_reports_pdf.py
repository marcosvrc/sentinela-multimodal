"""Testes de `app.reports.pdf.render_report_pdf` (pure, sem banco/rede)."""

from __future__ import annotations

from app.reports.builder import (
    ReportAnalysisContext,
    ReportPatientContext,
    ReportProfessionalReview,
    ReportRiskConsolidation,
    build_report_content,
)
from app.reports.pdf import render_report_pdf


def _content(risk_outcome: str = "MATCHED") -> dict:
    risk = ReportRiskConsolidation(
        outcome=risk_outcome,
        risk_level=6 if risk_outcome == "MATCHED" else None,
        classification_label="Hipoxemia grave" if risk_outcome == "MATCHED" else None,
        inconclusive_reason=None if risk_outcome == "MATCHED" else "MISSING_REQUIRED_INPUT",
        inconclusive_detail=None if risk_outcome == "MATCHED" else "faltou dado",
        code_evaluations=(
            [
                {
                    "code": "spo2",
                    "outcome": "MATCHED",
                    "risk_level": 6,
                    "classification_label": "Hipoxemia grave",
                    "inconclusive_reason": None,
                }
            ]
            if risk_outcome == "MATCHED"
            else []
        ),
        llm_status="SUCCESS",
        llm_summary="Resumo de teste.",
        llm_uncertainty_note="Nota de incerteza.",
        llm_provider="local",
        llm_model="local-template",
        llm_prompt_version="local-template-v1",
        llm_input_hash="a" * 64,
        llm_output_hash="b" * 64,
    )
    return build_report_content(
        patient=ReportPatientContext(
            patient_id="patient-1",
            medical_record_number="MRN-1",
            full_name="Paciente Teste",
            birth_date="1990-01-01",
        ),
        analysis=ReportAnalysisContext(
            analysis_id="analysis-1",
            institution_id="institution-1",
            status="WAITING_REVIEW",
            created_at="2026-07-11T10:00:00+00:00",
            created_by="dr-teste",
            additional_text=None,
            structured_clinical_inputs={},
        ),
        risk=risk,
        modality_findings=[],
        protocol_action_description="Alertar equipe assistencial.",
        review=ReportProfessionalReview(state="DRAFT"),
    )


def test_render_report_pdf_produces_valid_pdf_bytes() -> None:
    pdf_bytes = render_report_pdf(_content())
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_render_report_pdf_handles_inconclusive_risk() -> None:
    pdf_bytes = render_report_pdf(_content(risk_outcome="INCONCLUSIVE"))
    assert pdf_bytes[:5] == b"%PDF-"
