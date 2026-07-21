"""Servico de relatorio: geracao (DRAFT), confirmacao e download em PDF (item 13).

`generate_report` e chamado pelo orquestrador (mesmo ponto que
`consolidate_analysis_risk`, item 12) sempre que ha algo consolidado para
mostrar - cria/atualiza um `Report` em `DRAFT`, sem gerar PDF ainda (o PDF
so e gerado no momento da confirmacao, para corresponder exatamente ao que
o profissional revisou - ver `app.reports.models.Report`).

`confirm_report` e chamado pelo profissional (endpoint HTTP): exige
`Analysis.status == WAITING_REVIEW`, gera o PDF a partir do conteudo atual,
grava no storage, marca `Report.state = CONFIRMED` e transiciona
`Analysis.status` para `COMPLETED` (unica transicao valida a partir de
WAITING_REVIEW - `ANALYSIS_STATUS_TRANSITIONS`).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.core.enums import AnalysisStatus, AuditCategory, AuditResult
from app.core.errors import ApiError
from app.media.models import Analysis
from app.orchestrator.state_machine import transition
from app.patients.service import get_patient
from app.processors.models import ModalityFinding
from app.reports.builder import (
    ReportAnalysisContext,
    ReportClinicalSupportSummary,
    ReportModalityFinding,
    ReportPatientContext,
    ReportProfessionalReview,
    ReportRiskConsolidation,
    build_report_content,
)
from app.reports.models import Report
from app.reports.pdf import render_report_pdf
from app.risk_consolidation.models import RiskConsolidation
from app.rules_engine.models import ClinicalRuleAction
from app.rules_engine.service import get_current_rule_set
from app.storage.base import StorageAdapter

_POPULATION = "adult"


def _report_storage_key(
    institution_id: uuid.UUID, analysis_id: uuid.UUID, report_id: uuid.UUID
) -> str:
    return f"{institution_id}/{analysis_id}/{report_id}.pdf"


def _protocol_conduct_description(db: Session, risk: RiskConsolidation | None) -> str | None:
    if risk is None or risk.outcome != "MATCHED" or risk.risk_level is None:
        return None

    matched_code = next(
        (
            item["code"]
            for item in risk.code_evaluations
            if item.get("risk_level") == risk.risk_level and item.get("outcome") == "MATCHED"
        ),
        None,
    )
    if matched_code is None:
        return None

    rule_set = get_current_rule_set(db, matched_code, _POPULATION)
    if rule_set is None:
        return None

    action = db.scalar(
        select(ClinicalRuleAction).where(
            ClinicalRuleAction.rule_set_id == rule_set.id,
            ClinicalRuleAction.risk_level == risk.risk_level,
        )
    )
    return action.description if action else None


def _build_content(
    db: Session,
    analysis: Analysis,
    review: ReportProfessionalReview,
    *,
    clinical_support_summary_raw: dict | None,
) -> dict:
    patient = get_patient(db, analysis.institution_id, analysis.patient_id)
    risk = db.scalar(select(RiskConsolidation).where(RiskConsolidation.analysis_id == analysis.id))
    findings = list(
        db.scalars(select(ModalityFinding).where(ModalityFinding.analysis_id == analysis.id)).all()
    )
    clinical_support_summary = (
        ReportClinicalSupportSummary(**clinical_support_summary_raw)
        if clinical_support_summary_raw
        else None
    )

    return build_report_content(
        patient=ReportPatientContext(
            patient_id=str(patient.id),
            medical_record_number=patient.medical_record_number,
            full_name=patient.full_name,
            birth_date=patient.birth_date.isoformat(),
        ),
        analysis=ReportAnalysisContext(
            analysis_id=str(analysis.id),
            institution_id=str(analysis.institution_id),
            status=analysis.status,
            created_at=analysis.created_at.isoformat(),
            created_by=analysis.created_by,
            additional_text=analysis.additional_text,
            structured_clinical_inputs=analysis.structured_clinical_inputs or {},
        ),
        risk=(
            ReportRiskConsolidation(
                outcome=risk.outcome,
                risk_level=risk.risk_level,
                classification_label=risk.classification_label,
                inconclusive_reason=risk.inconclusive_reason,
                inconclusive_detail=risk.inconclusive_detail,
                code_evaluations=risk.code_evaluations,
                llm_status=risk.llm_status,
                llm_summary=risk.llm_summary,
                llm_uncertainty_note=risk.llm_uncertainty_note,
                llm_provider=risk.llm_provider,
                llm_model=risk.llm_model,
                llm_prompt_version=risk.llm_prompt_version,
                llm_input_hash=risk.llm_input_hash,
                llm_output_hash=risk.llm_output_hash,
            )
            if risk
            else None
        ),
        modality_findings=[
            ReportModalityFinding(
                modality_type=finding.modality_type,
                nature=finding.nature,
                quality_state=finding.quality_state,
                quality_metrics=finding.quality_metrics,
                quality_factors=finding.quality_factors,
                summary=finding.summary,
                created_at=finding.created_at.isoformat(),
            )
            for finding in findings
        ],
        protocol_action_description=_protocol_conduct_description(db, risk),
        review=review,
        clinical_support_summary=clinical_support_summary,
    )


def generate_report(db: Session, analysis: Analysis) -> Report:
    """Cria/atualiza o relatorio em DRAFT a partir do estado atual (idempotente)."""
    existing = db.scalar(select(Report).where(Report.analysis_id == analysis.id))
    row = existing or Report(analysis_id=analysis.id, institution_id=analysis.institution_id)

    review = ReportProfessionalReview(
        state=row.state if existing else "DRAFT",
        confirmed_by=row.confirmed_by if existing else None,
        confirmed_at=row.confirmed_at.isoformat() if existing and row.confirmed_at else None,
    )
    row.content = _build_content(
        db,
        analysis,
        review,
        clinical_support_summary_raw=row.clinical_support_summary if existing else None,
    )

    if existing is None:
        db.add(row)
    db.flush()
    return row


def get_report(db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID) -> Report:
    report = db.scalar(
        select(Report).where(
            Report.analysis_id == analysis_id, Report.institution_id == institution_id
        )
    )
    if report is None:
        raise ApiError(
            code="REPORT_NOT_FOUND",
            message="Relatorio ainda nao disponivel para esta analise.",
            status_code=404,
        )
    return report


def confirm_report(
    db: Session,
    storage: StorageAdapter,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    actor: str,
) -> Report:
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.institution_id == institution_id
        )
    )
    if analysis is None:
        raise ApiError(
            code="ANALYSIS_NOT_FOUND", message="Analise nao encontrada.", status_code=404
        )

    report = get_report(db, institution_id, analysis_id)
    if report.state == "CONFIRMED":
        # Verificado antes do estado da analise: apos a primeira
        # confirmacao, `Analysis.status` ja e COMPLETED (nunca mais
        # WAITING_REVIEW), entao checar o estado da analise primeiro
        # tornaria este ramo codigo morto - uma segunda tentativa de
        # confirmar sempre cairia em ANALYSIS_NOT_AWAITING_REVIEW, que e
        # tecnicamente verdadeiro mas esconde a causa real (relatorio ja
        # confirmado) por tras de uma mensagem generica.
        raise ApiError(
            code="REPORT_ALREADY_CONFIRMED", message="Relatorio ja confirmado.", status_code=409
        )

    if AnalysisStatus(analysis.status) is not AnalysisStatus.WAITING_REVIEW:
        raise ApiError(
            code="ANALYSIS_NOT_AWAITING_REVIEW",
            message=f"Analise em estado '{analysis.status}' nao pode ter o relatorio confirmado.",
            status_code=409,
        )

    now = datetime.now(tz=timezone.utc)
    review = ReportProfessionalReview(
        state="CONFIRMED", confirmed_by=actor, confirmed_at=now.isoformat()
    )
    report.content = _build_content(
        db,
        analysis,
        review,
        clinical_support_summary_raw=report.clinical_support_summary,
    )
    report.state = "CONFIRMED"
    report.confirmed_by = actor
    report.confirmed_at = now

    pdf_bytes = render_report_pdf(report.content)
    storage_key = _report_storage_key(institution_id, analysis_id, report.id)
    storage.write_generated_object(
        generated_key=storage_key, content=pdf_bytes, content_type="application/pdf"
    )
    report.pdf_storage_key = storage_key
    report.pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    report.pdf_generated_at = now

    analysis.status = transition(AnalysisStatus.WAITING_REVIEW, AnalysisStatus.COMPLETED).value

    db.flush()

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.REVIEW,
        action="REPORT_CONFIRMED",
        resource_type="report",
        resource_id=str(report.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis_id),
        event_metadata={"pdf_sha256": report.pdf_sha256},
    )
    db.commit()
    db.refresh(report)
    return report


def get_report_pdf(
    db: Session, storage: StorageAdapter, institution_id: uuid.UUID, analysis_id: uuid.UUID
) -> bytes:
    report = get_report(db, institution_id, analysis_id)
    if report.state != "CONFIRMED" or not report.pdf_storage_key:
        raise ApiError(
            code="REPORT_NOT_CONFIRMED",
            message="O relatorio precisa ser confirmado antes do download em PDF.",
            status_code=409,
        )
    return storage.read_generated_object(report.pdf_storage_key)
