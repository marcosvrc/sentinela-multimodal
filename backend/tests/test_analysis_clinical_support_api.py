"""Testes de integracao do apoio a analise clinica assistido por LLM para
UMA analise multimodal especifica (botao "Analisar dados clinicos" da
tela de revisao da analise - `app.clinical_support.service.
generate_analysis_clinical_support_summary`).

Mesmo padrao de `test_clinical_support_api.py` (que testa o apoio em nivel
de paciente): usa o adaptador LOCAL (template deterministico, sem chamada
de rede) para exercitar o endpoint de ponta a ponta sem depender de
credenciais OpenAI. Precisa de Postgres real; pulado automaticamente
quando indisponivel neste sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.orchestrator.worker import process_next_message
from app.processors.registry import PROCESSORS
from app.queue import get_queue_adapter
from app.rules_engine.models import ClinicalRule, ClinicalRuleCondition, ClinicalRuleSet


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
def client() -> TestClient:
    return TestClient(create_app())


def _create_institution(name: str) -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": name},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> str:
    session = SessionLocal()
    try:
        external_subject = f"acs-test-{role.value.lower()}-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name=f"Usuario Teste {role.value}",
            role=role.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


def _headers(subject: str) -> dict:
    return {"X-Dev-Subject": subject}


def _seed_rule_set(code: str) -> None:
    session = SessionLocal()
    try:
        rule_set = ClinicalRuleSet(
            code=code,
            version="0.1.0-acs",
            population="adult",
            status="published",
            effective_from=date.today(),
            effective_to=None,
            required_inputs=["spo2_percent"],
            exclusions=[],
            content_hash=f"acs-hash-{uuid.uuid4()}",
        )
        session.add(rule_set)
        session.flush()
        severe = ClinicalRule(
            rule_set_id=rule_set.id,
            rule_key="severe",
            risk_level=6,
            classification_label="Hipoxemia grave",
            position=0,
        )
        session.add(severe)
        session.flush()
        session.add(ClinicalRuleCondition(rule_id=severe.id, expression="spo2_percent <= 91"))
        session.commit()
    finally:
        session.close()


def _drain_queue_to_terminal_state() -> None:
    queue = get_queue_adapter()
    for _ in range(10):
        session = SessionLocal()
        try:
            outcome = process_next_message(session, queue, processors=PROCESSORS)
        finally:
            session.close()
        if outcome is None:
            return


class TestAnalysisClinicalSupportSummary:
    def test_generates_summary_from_analysis_findings_and_calculated_risk(
        self, client: TestClient
    ) -> None:
        code = f"acs-spo2-{uuid.uuid4()}"
        _seed_rule_set(code)

        institution_id = _create_institution("Hospital Apoio Analise")
        clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-ACS-{uuid.uuid4()}",
                "full_name": "Paciente Apoio Analise",
                "birth_date": "1978-02-10",
                "registered_sex": "masculino",
            },
        )
        assert patient_response.status_code == 201
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={
                "patient_id": patient_id,
                "additional_text": "Paciente nega dor toracica.",
                "structured_clinical_inputs": {code: {"spo2_percent": 85}},
            },
        )
        assert analysis_response.status_code == 201
        analysis_id = analysis_response.json()["id"]

        submit_response = client.post(f"/analyses/{analysis_id}/submit", headers=clinician_headers)
        assert submit_response.status_code == 200

        _drain_queue_to_terminal_state()

        status_response = client.get(f"/analyses/{analysis_id}", headers=clinician_headers)
        assert status_response.json()["status"] == "WAITING_REVIEW"

        summary_response = client.post(
            f"/analyses/{analysis_id}/clinical-support-summary", headers=clinician_headers
        )
        assert summary_response.status_code == 200
        body = summary_response.json()
        assert body["summary_text"]
        assert body["probable_causes"]
        assert body["suggested_next_steps"]
        assert "nao substitui" in body["uncertainty_note"].lower()
        assert body["provider"] == "local"
        # Ao menos os achados ORIGINAL_DATA (item 11) do processador TEXT e
        # o achado MODEL_OBSERVATION do termo "dor toracica" (secao 4.3).
        assert body["findings_considered"] >= 2
        assert "Hipoxemia grave" in body["summary_text"]

    def test_requires_patient_access(self, client: TestClient) -> None:
        institution_id = _create_institution("Hospital Apoio Analise RBAC")
        clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))
        other_clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-ACS-RBAC-{uuid.uuid4()}",
                "full_name": "Paciente Apoio Analise RBAC",
                "birth_date": "1990-01-01",
                "registered_sex": "feminino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={"patient_id": patient_id, "additional_text": "Texto qualquer."},
        )
        analysis_id = analysis_response.json()["id"]

        response = client.post(
            f"/analyses/{analysis_id}/clinical-support-summary", headers=other_clinician_headers
        )
        assert response.status_code == 403
        assert response.json()["code"] == "NO_CARE_ASSIGNMENT"

    def test_non_clinical_role_cannot_call_endpoint(self, client: TestClient) -> None:
        institution_id = _create_institution("Hospital Apoio Analise Auditor")
        clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))
        auditor_headers = _headers(_create_user(institution_id, UserRole.AUDITOR))

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-ACS-AUD-{uuid.uuid4()}",
                "full_name": "Paciente Apoio Analise Auditor",
                "birth_date": "1988-06-20",
                "registered_sex": "masculino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={"patient_id": patient_id, "additional_text": "Texto qualquer."},
        )
        analysis_id = analysis_response.json()["id"]

        response = client.post(
            f"/analyses/{analysis_id}/clinical-support-summary", headers=auditor_headers
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"
