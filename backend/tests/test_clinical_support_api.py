"""Testes de integracao do apoio a analise clinica assistido por LLM
(botao "Analisar dados clinicos" - `app.clinical_support.service`).

Usa o adaptador LOCAL (template deterministico, sem chamada de rede -
configuracao padrao de teste) para exercitar o endpoint de ponta a ponta
sem depender de credenciais OpenAI.

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.patients.models import Patient


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


def _create_institution() -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": "Instituicao Apoio Clinico"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> tuple[str, uuid.UUID]:
    session = SessionLocal()
    try:
        external_subject = f"clinical-support-test-{role.value.lower()}-{uuid.uuid4()}"
        user = identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name=f"Usuario Teste {role.value}",
            role=role.value,
        )
        session.commit()
        return external_subject, user.id
    finally:
        session.close()


def _create_patient(institution_id: uuid.UUID) -> uuid.UUID:
    session = SessionLocal()
    try:
        patient = Patient(
            institution_id=institution_id,
            medical_record_number=f"MRN-SUPPORT-{uuid.uuid4().hex[:10]}",
            full_name="Paciente Teste Apoio Clinico",
            birth_date=date(1960, 3, 10),
            registered_sex="F",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return patient.id
    finally:
        session.close()


def _post_heart_rate(
    client: TestClient, headers: dict, patient_id: uuid.UUID, value: float, measured_at: datetime
):
    return client.post(
        f"/patients/{patient_id}/observations",
        headers=headers,
        json={
            "observation_type": "HEART_RATE",
            "value": {"value": value},
            "unit": "bpm",
            "context": {},
            "measured_at": measured_at.isoformat(),
            "origin": "manual",
            "author": "Enfermeira Teste",
            "reading_quality": "VALID",
        },
    )


class TestClinicalSupportSummary:
    def test_generates_summary_from_patient_observations_and_alerts(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        medico_subject, medico_id = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": admin_subject},
            json={"user_id": str(medico_id)},
        )
        medico_headers = {"X-Dev-Subject": medico_subject}

        base_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
        for i, value in enumerate([78, 80, 79, 81, 80]):
            response = _post_heart_rate(
                client, medico_headers, patient_id, value, base_time + timedelta(hours=i)
            )
            assert response.status_code == 201
        # Spike que dispara um alerta de anomalia (mesmo cenario de
        # test_anomaly_alerts_api.py).
        spike_response = _post_heart_rate(
            client, medico_headers, patient_id, 180, base_time + timedelta(hours=5, minutes=45)
        )
        assert spike_response.status_code == 201

        summary_response = client.post(
            f"/patients/{patient_id}/clinical-support-summary", headers=medico_headers
        )
        assert summary_response.status_code == 200
        body = summary_response.json()
        assert body["summary_text"]
        assert body["probable_causes"]
        assert body["suggested_next_steps"]
        assert "nao substitui" in body["uncertainty_note"].lower()
        assert body["provider"] == "local"
        assert body["observations_considered"] >= 1
        assert body["alerts_considered"] >= 1

    def test_generates_summary_even_without_any_clinical_data(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        medico_subject, medico_id = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": admin_subject},
            json={"user_id": str(medico_id)},
        )
        medico_headers = {"X-Dev-Subject": medico_subject}

        response = client.post(
            f"/patients/{patient_id}/clinical-support-summary", headers=medico_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["observations_considered"] == 0
        assert body["alerts_considered"] == 0

    def test_requires_care_assignment(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        assigned_subject, assigned_id = _create_user(institution_id, UserRole.MEDICO)
        unassigned_subject, _ = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": admin_subject},
            json={"user_id": str(assigned_id)},
        )

        response = client.post(
            f"/patients/{patient_id}/clinical-support-summary",
            headers={"X-Dev-Subject": unassigned_subject},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "NO_CARE_ASSIGNMENT"

    def test_administrator_role_cannot_call_endpoint(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        patient_id = _create_patient(institution_id)

        response = client.post(
            f"/patients/{patient_id}/clinical-support-summary",
            headers={"X-Dev-Subject": admin_subject},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"
