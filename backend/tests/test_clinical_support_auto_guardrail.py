"""Testes do guardrail de execucao automatica do apoio a analise clinica
(IA) - `app.clinical_support.service.should_run_automatic_clinical_support`
(feature flag `auto_clinical_support_enabled`, ver
`app.orchestrator.worker`). Testes da regra pura de relevancia clinica de
um achado individual (`app.processors.clinical_relevance.
is_clinically_relevant`) vivem em `test_processors_clinical_relevance.py`.

Precisa de Postgres real (analises/midias/achados sao persistidos);
pulado automaticamente quando indisponivel neste sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.clinical_support.service import should_run_automatic_clinical_support
from app.core.db import SessionLocal
from app.media import service as media_service
from app.orchestrator.models import AnalysisModalityState
from app.patients.models import Patient
from app.processors.models import ModalityFinding


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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_institution(session) -> uuid.UUID:
    institution_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
        {"id": str(institution_id), "name": "Instituicao Guardrail Auto"},
    )
    session.commit()
    return institution_id


def _create_patient(session, institution_id: uuid.UUID) -> uuid.UUID:
    patient = Patient(
        institution_id=institution_id,
        medical_record_number=f"MRN-{uuid.uuid4()}",
        full_name="Paciente Guardrail Auto",
        birth_date=date(1985, 3, 20),
        registered_sex="feminino",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient.id


def _create_modality_state(session, analysis_id: uuid.UUID) -> uuid.UUID:
    state = AnalysisModalityState(
        analysis_id=analysis_id, modality_type="IMAGE", status="COMPLETED"
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state.id


def _add_finding(
    session,
    analysis_id: uuid.UUID,
    modality_state_id: uuid.UUID,
    *,
    modality_type: str,
    nature: str,
    quality_metrics: dict,
) -> None:
    finding = ModalityFinding(
        analysis_id=analysis_id,
        modality_state_id=modality_state_id,
        modality_type=modality_type,
        nature=nature,
        quality_state="OK",
        quality_metrics=quality_metrics,
        quality_factors=[],
        summary="achado de teste",
    )
    session.add(finding)
    session.commit()


class TestShouldRunAutomaticClinicalSupport:
    def test_true_when_analysis_has_structured_clinical_inputs(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(
            session,
            institution_id,
            patient_id,
            "test-actor",
            structured_clinical_inputs={"spo2": {"spo2_percent": 98}},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is True

    def test_false_when_only_original_data_finding(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        state_id = _create_modality_state(session, analysis.id)
        _add_finding(
            session,
            analysis.id,
            state_id,
            modality_type="IMAGE",
            nature="ORIGINAL_DATA",
            quality_metrics={"width": 300, "height": 300},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is False

    def test_false_when_only_not_relevant_rekognition_finding(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        state_id = _create_modality_state(session, analysis.id)
        _add_finding(
            session,
            analysis.id,
            state_id,
            modality_type="IMAGE",
            nature="MODEL_OBSERVATION",
            quality_metrics={"clinical_relevance": "NOT_RELEVANT"},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is False

    def test_true_when_relevant_rekognition_finding(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        state_id = _create_modality_state(session, analysis.id)
        _add_finding(
            session,
            analysis.id,
            state_id,
            modality_type="IMAGE",
            nature="MODEL_OBSERVATION",
            quality_metrics={"clinical_relevance": "RELEVANT"},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is True

    def test_true_when_clinical_term_finding(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        state_id = _create_modality_state(session, analysis.id)
        _add_finding(
            session,
            analysis.id,
            state_id,
            modality_type="TEXT",
            nature="MODEL_OBSERVATION",
            quality_metrics={"term": "dor toracica"},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is True

    def test_false_when_only_sentiment_finding(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        state_id = _create_modality_state(session, analysis.id)
        _add_finding(
            session,
            analysis.id,
            state_id,
            modality_type="TEXT",
            nature="MODEL_OBSERVATION",
            quality_metrics={"sentiment": "NEUTRAL"},
        )
        assert should_run_automatic_clinical_support(session, analysis.id) is False

    def test_false_when_no_findings_and_no_structured_inputs(self, session) -> None:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        assert should_run_automatic_clinical_support(session, analysis.id) is False
