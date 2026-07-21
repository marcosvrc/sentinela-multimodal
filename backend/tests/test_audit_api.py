"""Testes da API de auditoria (GET /audit/events).

Mesma estrategia das demais APIs: contrato HTTP sem banco (identidade
ausente) roda sempre; integracao real com banco e pulada quando Postgres
nao esta disponivel neste sandbox (roda no CI, que tem um servico Postgres).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        session.close()


def test_list_audit_events_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.get("/audit/events")
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_AUTH_CONTEXT"


@pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")
class TestAuditApiWithDatabase:
    """Exercita gravacao real de eventos (via criacao de paciente) e consulta."""

    def _create_institution(self) -> uuid.UUID:
        session = SessionLocal()
        try:
            institution_id = uuid.uuid4()
            session.execute(
                text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
                {"id": str(institution_id), "name": "Instituicao de Teste"},
            )
            session.commit()
            return institution_id
        finally:
            session.close()

    def _create_user(self, institution_id: uuid.UUID, role: UserRole) -> str:
        session = SessionLocal()
        try:
            external_subject = f"test-{role.value.lower()}-{uuid.uuid4()}"
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

    def _headers(self, institution_id: uuid.UUID, role: UserRole) -> dict:
        return {"X-Dev-Subject": self._create_user(institution_id, role)}

    def test_list_audit_events_rejects_page_size_above_max(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        response = client.get(
            "/audit/events",
            headers=self._headers(institution_id, UserRole.AUDITOR),
            params={"page_size": 1000},
        )
        assert response.status_code == 422

    def test_non_audit_role_is_forbidden(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        response = client.get(
            "/audit/events", headers=self._headers(institution_id, UserRole.MEDICO)
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"

    def test_patient_creation_generates_audit_event(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        clinical_headers = self._headers(institution_id, UserRole.MEDICO)

        create_response = client.post(
            "/patients",
            headers=clinical_headers,
            json={
                "medical_record_number": "MRN-AUDIT-1",
                "full_name": "Paciente Auditado",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        assert create_response.status_code == 201
        patient_id = create_response.json()["id"]

        audit_headers = self._headers(institution_id, UserRole.AUDITOR)
        events_response = client.get(
            "/audit/events",
            headers=audit_headers,
            params={"action": "PATIENT_CREATE", "resource_id": patient_id},
        )
        assert events_response.status_code == 200
        payload = events_response.json()
        assert payload["total_items"] == 1
        event = payload["items"][0]
        assert event["actor_role"] == "MEDICO"
        assert event["category"] == "DATA"
        assert event["result"] == "SUCCESS"
        assert event["resource_type"] == "patient"
        assert event["resource_id"] == patient_id

    def test_audit_query_itself_is_audited(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        clinical_headers = self._headers(institution_id, UserRole.MEDICO)
        audit_headers = self._headers(institution_id, UserRole.AUDITOR)

        # Gera pelo menos um evento para consultar.
        client.post(
            "/patients",
            headers=clinical_headers,
            json={
                "medical_record_number": "MRN-AUDIT-2",
                "full_name": "Paciente Auditado 2",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )

        first_query = client.get("/audit/events", headers=audit_headers)
        assert first_query.status_code == 200

        second_query = client.get(
            "/audit/events",
            headers=audit_headers,
            params={"action": "AUDIT_QUERY"},
        )
        assert second_query.status_code == 200
        payload = second_query.json()
        # A primeira consulta gerou um evento AUDIT_QUERY que a segunda deve
        # encontrar (Requirement 14.7 - consultas de auditoria sao auditadas).
        assert payload["total_items"] >= 1
        assert all(item["action"] == "AUDIT_QUERY" for item in payload["items"])

    def test_events_are_isolated_by_tenant(self, client: TestClient) -> None:
        institution_a = self._create_institution()
        institution_b = self._create_institution()

        client.post(
            "/patients",
            headers=self._headers(institution_a, UserRole.MEDICO),
            json={
                "medical_record_number": "MRN-TENANT-A",
                "full_name": "Paciente A",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )

        response_b = client.get(
            "/audit/events",
            headers=self._headers(institution_b, UserRole.AUDITOR),
            params={"action": "PATIENT_CREATE"},
        )
        assert response_b.status_code == 200
        assert response_b.json()["total_items"] == 0
