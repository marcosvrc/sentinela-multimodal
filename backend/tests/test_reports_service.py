"""Testes de `app.reports.service` (item 13).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI). Usa `LocalFilesystemStorageAdapter` em um diretorio
temporario para exercitar a escrita/leitura real do PDF gerado.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import AnalysisStatus
from app.core.errors import ApiError
from app.media import service as media_service
from app.orchestrator.state_machine import transition
from app.patients.models import Patient
from app.reports import service as reports_service
from app.risk_consolidation.service import consolidate_analysis_risk
from app.rules_engine.models import (
    ClinicalRule,
    ClinicalRuleAction,
    ClinicalRuleCondition,
    ClinicalRuleSet,
)
from app.storage.local import LocalFilesystemStorageAdapter


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        session.close()


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")


@pytest.fixture
def session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield LocalFilesystemStorageAdapter(
            storage_root=tmp_dir, upload_secret="test-secret", upload_url_ttl_seconds=900
        )


def _create_institution(session) -> uuid.UUID:
    institution_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
        {"id": str(institution_id), "name": "Instituicao de Teste"},
    )
    session.commit()
    return institution_id


def _create_patient(session, institution_id: uuid.UUID) -> uuid.UUID:
    patient = Patient(
        institution_id=institution_id,
        medical_record_number=f"MRN-{uuid.uuid4()}",
        full_name="Paciente Relatorio",
        birth_date=date(1978, 11, 2),
        registered_sex="feminino",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient.id


def _create_rule_set_with_action(session, *, code: str) -> None:
    rule_set = ClinicalRuleSet(
        code=code,
        version="0.1.0-test",
        population="adult",
        status="published",
        effective_from=date.today(),
        effective_to=None,
        required_inputs=["spo2_percent"],
        exclusions=[],
        content_hash=f"test-hash-{uuid.uuid4()}",
    )
    session.add(rule_set)
    session.flush()
    rule = ClinicalRule(
        rule_set_id=rule_set.id,
        rule_key="severe",
        risk_level=6,
        classification_label="Hipoxemia grave",
        position=0,
    )
    session.add(rule)
    session.flush()
    session.add(ClinicalRuleCondition(rule_id=rule.id, expression="spo2_percent <= 91"))
    session.add(
        ClinicalRuleAction(
            rule_set_id=rule_set.id, risk_level=6, description="Seguir protocolo de emergencia."
        )
    )
    session.commit()


def _create_analysis_at_waiting_review(session, code: str):
    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    _create_rule_set_with_action(session, code=code)

    analysis = media_service.create_analysis(
        session,
        institution_id,
        patient_id,
        "test-actor",
        None,
        {code: {"spo2_percent": 85}},
    )
    consolidate_analysis_risk(session, analysis)
    analysis.status = transition(AnalysisStatus.CREATED, AnalysisStatus.UPLOADING).value
    analysis.status = transition(AnalysisStatus.UPLOADING, AnalysisStatus.QUEUED).value
    analysis.status = transition(AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING).value
    analysis.status = transition(AnalysisStatus.PROCESSING, AnalysisStatus.WAITING_REVIEW).value
    session.commit()
    session.refresh(analysis)
    return institution_id, analysis


def test_generate_report_is_draft_with_protocol_conduct(session) -> None:
    code = f"test-spo2-report-{uuid.uuid4()}"
    institution_id, analysis = _create_analysis_at_waiting_review(session, code)

    report = reports_service.generate_report(session, analysis)
    session.commit()

    assert report.state == "DRAFT"
    assert report.content["calculated_risk"]["risk_level"] == 6
    assert report.content["protocol_conduct"] == "Seguir protocolo de emergencia."
    assert report.pdf_storage_key is None


def test_confirm_report_generates_pdf_and_completes_analysis(session, storage) -> None:
    code = f"test-spo2-confirm-{uuid.uuid4()}"
    institution_id, analysis = _create_analysis_at_waiting_review(session, code)
    reports_service.generate_report(session, analysis)
    session.commit()

    confirmed = reports_service.confirm_report(
        session, storage, institution_id, analysis.id, "dr-confirmador"
    )
    session.commit()

    assert confirmed.state == "CONFIRMED"
    assert confirmed.confirmed_by == "dr-confirmador"
    assert confirmed.pdf_storage_key is not None
    assert confirmed.pdf_sha256 is not None

    session.refresh(analysis)
    assert analysis.status == AnalysisStatus.COMPLETED.value

    pdf_bytes = reports_service.get_report_pdf(session, storage, institution_id, analysis.id)
    assert pdf_bytes[:5] == b"%PDF-"


def test_confirm_report_twice_fails(session, storage) -> None:
    code = f"test-spo2-double-{uuid.uuid4()}"
    institution_id, analysis = _create_analysis_at_waiting_review(session, code)
    reports_service.generate_report(session, analysis)
    session.commit()

    reports_service.confirm_report(session, storage, institution_id, analysis.id, "dr-confirmador")
    session.commit()

    with pytest.raises(ApiError) as exc_info:
        reports_service.confirm_report(
            session, storage, institution_id, analysis.id, "dr-confirmador"
        )
    assert exc_info.value.code == "REPORT_ALREADY_CONFIRMED"


def test_download_pdf_before_confirmation_fails(session, storage) -> None:
    code = f"test-spo2-nodownload-{uuid.uuid4()}"
    institution_id, analysis = _create_analysis_at_waiting_review(session, code)
    reports_service.generate_report(session, analysis)
    session.commit()

    with pytest.raises(ApiError) as exc_info:
        reports_service.get_report_pdf(session, storage, institution_id, analysis.id)
    assert exc_info.value.code == "REPORT_NOT_CONFIRMED"
