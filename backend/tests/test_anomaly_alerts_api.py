"""Teste de integracao ponta a ponta da deteccao de anomalia + fluxo de
alerta (ESCOPO_PROJETO.md secao 4.5): observacoes clinicas reais via API
disparando `ClinicalAlert`, e o ciclo reconhecer -> escalar -> encerrar via
`/alerts/*`.

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app


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
            {"id": str(institution_id), "name": "Instituicao Alertas"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> tuple[str, uuid.UUID]:
    session = SessionLocal()
    try:
        external_subject = f"alerts-test-{role.value.lower()}-{uuid.uuid4()}"
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
        patient_id = uuid.uuid4()
        session.execute(
            text(
                "INSERT INTO patients "
                "(id, institution_id, medical_record_number, full_name, birth_date, "
                "registered_sex, created_by, created_at, updated_at) "
                "VALUES (:id, :institution_id, :mrn, :name, '1985-05-05', 'M', "
                "'seed', now(), now())"
            ),
            {
                "id": str(patient_id),
                "institution_id": str(institution_id),
                "mrn": f"MRN-ALERT-{uuid.uuid4().hex[:10]}",
                "name": "Paciente Teste Alertas",
            },
        )
        session.commit()
        return patient_id
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


class TestAnomalyAlertLifecycle:
    def test_stable_readings_then_spike_creates_alert_visible_in_list(
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

        spike_time = base_time + timedelta(hours=5, minutes=45)
        spike_response = _post_heart_rate(client, medico_headers, patient_id, 180, spike_time)
        assert spike_response.status_code == 201

        alerts_response = client.get(f"/patients/{patient_id}/alerts", headers=medico_headers)
        assert alerts_response.status_code == 200
        alerts = alerts_response.json()["items"]
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["signal_key"] == "HEART_RATE"
        assert alert["severity"] == "CRITICAL"
        assert alert["status"] == "OPEN"
        assert alert["evidence"]["baseline_deviation"] is not None

        alert_id = alert["id"]

        ack_response = client.post(
            f"/alerts/{alert_id}/acknowledge", headers=medico_headers
        )
        assert ack_response.status_code == 200
        assert ack_response.json()["status"] == "ACKNOWLEDGED"
        assert ack_response.json()["acknowledged_by"] == medico_subject

        escalate_response = client.post(
            f"/alerts/{alert_id}/escalate",
            headers=medico_headers,
            json={"escalated_to": "Medico plantonista", "reason": "Taquicardia subita, avaliar."},
        )
        assert escalate_response.status_code == 200
        assert escalate_response.json()["status"] == "ESCALATED"

        resolve_response = client.post(
            f"/alerts/{alert_id}/resolve",
            headers=medico_headers,
            json={"notes": "Paciente reavaliado, sinal estabilizado apos intervencao."},
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "RESOLVED"

        double_resolve = client.post(
            f"/alerts/{alert_id}/resolve",
            headers=medico_headers,
            json={"notes": "Tentativa duplicada."},
        )
        assert double_resolve.status_code == 409
        assert double_resolve.json()["code"] == "ALERT_ALREADY_RESOLVED"

    def test_stable_readings_do_not_create_alerts(self, client: TestClient) -> None:
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
        for i, value in enumerate([78, 80, 79, 81, 80, 79]):
            response = _post_heart_rate(
                client, medico_headers, patient_id, value, base_time + timedelta(hours=i)
            )
            assert response.status_code == 201

        alerts_response = client.get(f"/patients/{patient_id}/alerts", headers=medico_headers)
        assert alerts_response.status_code == 200
        assert alerts_response.json()["items"] == []

    def test_alert_actions_require_patient_access(self, client: TestClient) -> None:
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
        assigned_headers = {"X-Dev-Subject": assigned_subject}
        unassigned_headers = {"X-Dev-Subject": unassigned_subject}

        base_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
        for i, value in enumerate([78, 80, 79, 81, 80]):
            _post_heart_rate(
                client, assigned_headers, patient_id, value, base_time + timedelta(hours=i)
            )
        _post_heart_rate(
            client, assigned_headers, patient_id, 180, base_time + timedelta(hours=5, minutes=45)
        )

        alert_id = client.get(f"/patients/{patient_id}/alerts", headers=assigned_headers).json()[
            "items"
        ][0]["id"]

        denied = client.post(f"/alerts/{alert_id}/acknowledge", headers=unassigned_headers)
        assert denied.status_code == 403
        assert denied.json()["code"] == "NO_CARE_ASSIGNMENT"

    def test_alerts_summary_counts_by_severity(self, client: TestClient) -> None:
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
            _post_heart_rate(
                client, medico_headers, patient_id, value, base_time + timedelta(hours=i)
            )
        # Spike critico (>= critical_sd de desvio do baseline estavel acima).
        _post_heart_rate(
            client, medico_headers, patient_id, 180, base_time + timedelta(hours=5, minutes=45)
        )

        summary_response = client.get(
            f"/patients/{patient_id}/alerts/summary", headers=medico_headers
        )
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["critical"] == 1
        assert summary["high"] == 0
        assert summary["moderate"] == 0

        severity_filtered = client.get(
            f"/patients/{patient_id}/alerts",
            headers=medico_headers,
            params={"severity": "CRITICAL"},
        )
        assert severity_filtered.status_code == 200
        assert severity_filtered.json()["total_items"] == 1

        no_match = client.get(
            f"/patients/{patient_id}/alerts",
            headers=medico_headers,
            params={"severity": "MODERATE"},
        )
        assert no_match.status_code == 200
        assert no_match.json()["total_items"] == 0
