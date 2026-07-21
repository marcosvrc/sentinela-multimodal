"""Testes da API de pacientes/observacoes.

Duas camadas:
1. Contrato HTTP (sem banco): ausencia de identidade - a resolucao de
   `X-Dev-Subject` nem chega a consultar o banco quando o cabecalho esta
   ausente, entao este caso nao exige Postgres.
2. Integracao real (com banco): marcados e pulados automaticamente quando
   Postgres nao esta acessivel (este sandbox de desenvolvimento nao tem
   Postgres instalado; o CI tem um servico dedicado - ver .github/workflows/ci.yml).
   Exercitam tambem a resolucao de identidade (usuario/papel) e o RBAC,
   ja que ambos dependem de uma consulta real ao banco.
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


def test_create_patient_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post(
        "/patients",
        json={
            "medical_record_number": "MRN-1",
            "full_name": "Paciente Teste",
            "birth_date": "1990-01-01",
            "registered_sex": "feminino",
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_AUTH_CONTEXT"


@pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")
class TestPatientsApiWithDatabase:
    """Exercita o fluxo completo contra um Postgres real (roda no CI)."""

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
        """Cria um usuario e retorna o `external_subject` (valor de X-Dev-Subject)."""
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

    def _clinical_headers(
        self, institution_id: uuid.UUID, role: UserRole = UserRole.MEDICO
    ) -> dict:
        subject = self._create_user(institution_id, role)
        return {"X-Dev-Subject": subject}

    def test_create_patient_with_unknown_subject_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/patients",
            headers={"X-Dev-Subject": f"nao-existe-{uuid.uuid4()}"},
            json={
                "medical_record_number": "MRN-1",
                "full_name": "Paciente Teste",
                "birth_date": "1990-01-01",
                "registered_sex": "feminino",
            },
        )
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_AUTH_CONTEXT"

    def test_create_patient_with_non_clinical_role_returns_403(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id, role=UserRole.AUDITOR)

        response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-1",
                "full_name": "Paciente Teste",
                "birth_date": "1990-01-01",
                "registered_sex": "feminino",
            },
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"

    def test_create_patient_with_future_birth_date_returns_422(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-1",
                "full_name": "Paciente Teste",
                "birth_date": "2099-01-01",
                "registered_sex": "feminino",
            },
        )
        assert response.status_code == 422

    def test_create_patient_missing_required_field_returns_422(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        response = client.post("/patients", headers=headers, json={"full_name": "Sem prontuario"})
        assert response.status_code == 422

    def test_create_and_fetch_patient(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-100",
                "full_name": "Paciente Integracao",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        assert create_response.status_code == 201
        patient = create_response.json()
        assert patient["age"] >= 0

        get_response = client.get(f"/patients/{patient['id']}", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["medical_record_number"] == "MRN-100"

    def test_create_patient_with_height_cm(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-HEIGHT-1",
                "full_name": "Paciente Com Altura",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
                "height_cm": 165.5,
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["height_cm"] == 165.5

    def test_create_patient_with_out_of_range_height_returns_422(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-HEIGHT-2",
                "full_name": "Paciente Altura Invalida",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
                "height_cm": 999,
            },
        )
        assert response.status_code == 422

    def test_update_patient_height_cm(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-HEIGHT-3",
                "full_name": "Paciente Para Editar Altura",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = create_response.json()["id"]
        assert create_response.json()["height_cm"] is None

        patch_response = client.patch(
            f"/patients/{patient_id}", headers=headers, json={"height_cm": 178.0}
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["height_cm"] == 178.0

        get_response = client.get(f"/patients/{patient_id}", headers=headers)
        assert get_response.json()["height_cm"] == 178.0

    def test_update_patient_full_record(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-EDIT-1",
                "full_name": "Nome Original",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = create_response.json()["id"]

        patch_response = client.patch(
            f"/patients/{patient_id}",
            headers=headers,
            json={
                "medical_record_number": "MRN-EDIT-1-NOVO",
                "full_name": "Nome Editado",
                "birth_date": "1991-07-20",
                "registered_sex": "masculino",
                "email": "editado@example.com",
                "height_cm": 180.0,
            },
        )
        assert patch_response.status_code == 200
        body = patch_response.json()
        assert body["medical_record_number"] == "MRN-EDIT-1-NOVO"
        assert body["full_name"] == "Nome Editado"
        assert body["birth_date"] == "1991-07-20"
        assert body["registered_sex"] == "masculino"
        assert body["email"] == "editado@example.com"
        assert body["height_cm"] == 180.0

    def test_deactivate_and_reactivate_patient(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)

        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-DEACT-1",
                "full_name": "Paciente Para Desativar",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = create_response.json()["id"]
        assert create_response.json()["active"] is True

        deactivate_response = client.patch(
            f"/patients/{patient_id}", headers=headers, json={"active": False}
        )
        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["active"] is False

        # Paciente desativado nao aparece na listagem padrao (active=True implicito).
        list_response = client.get("/patients", headers=headers, params={"search": "MRN-DEACT-1"})
        assert list_response.json()["total_items"] == 0

        # Mas aparece ao filtrar explicitamente por inativos.
        inactive_list_response = client.get(
            "/patients", headers=headers, params={"search": "MRN-DEACT-1", "active": "false"}
        )
        assert inactive_list_response.json()["total_items"] == 1

        reactivate_response = client.patch(
            f"/patients/{patient_id}", headers=headers, json={"active": True}
        )
        assert reactivate_response.status_code == 200
        assert reactivate_response.json()["active"] is True

    def test_duplicate_medical_record_number_returns_409(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        payload = {
            "medical_record_number": "MRN-DUP",
            "full_name": "Paciente Duplicado",
            "birth_date": "1990-06-15",
            "registered_sex": "feminino",
        }

        first = client.post("/patients", headers=headers, json=payload)
        assert first.status_code == 201

        second = client.post("/patients", headers=headers, json=payload)
        assert second.status_code == 409
        assert second.json()["code"] == "DUPLICATE_MEDICAL_RECORD_NUMBER"

    def test_cross_tenant_patient_access_returns_404(self, client: TestClient) -> None:
        institution_a = self._create_institution()
        institution_b = self._create_institution()

        create_response = client.post(
            "/patients",
            headers=self._clinical_headers(institution_a),
            json={
                "medical_record_number": "MRN-ISOLATED",
                "full_name": "Paciente Isolado",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = create_response.json()["id"]

        cross_tenant_response = client.get(
            f"/patients/{patient_id}", headers=self._clinical_headers(institution_b)
        )
        assert cross_tenant_response.status_code == 404

    def test_list_patients_search_by_name_matches_case_insensitive_substring(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-SEARCH-1",
                "full_name": "Fulano da Silva Souza",
                "birth_date": "1990-06-15",
                "registered_sex": "masculino",
            },
        )
        client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-SEARCH-2",
                "full_name": "Beltrana Pereira",
                "birth_date": "1985-03-20",
                "registered_sex": "feminino",
            },
        )

        response = client.get("/patients", headers=headers, params={"search": "silva"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["full_name"] == "Fulano da Silva Souza"

    def test_list_patients_search_by_medical_record_number(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-UNIQUE-999",
                "full_name": "Paciente Prontuario",
                "birth_date": "1990-06-15",
                "registered_sex": "masculino",
            },
        )

        response = client.get("/patients", headers=headers, params={"search": "unique-999"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["medical_record_number"] == "MRN-UNIQUE-999"

    def test_list_patients_search_without_match_returns_empty_page(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-NOMATCH",
                "full_name": "Paciente Qualquer",
                "birth_date": "1990-06-15",
                "registered_sex": "masculino",
            },
        )

        response = client.get(
            "/patients", headers=headers, params={"search": "nome-que-nao-existe"}
        )
        assert response.status_code == 200
        assert response.json()["total_items"] == 0

    def test_list_patients_includes_has_analyses_flag(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        with_analysis = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-WITH-ANALYSIS",
                "full_name": "Paciente Com Analise",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        ).json()["id"]
        without_analysis = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-WITHOUT-ANALYSIS",
                "full_name": "Paciente Sem Analise",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        ).json()["id"]
        client.post("/analyses", headers=headers, json={"patient_id": with_analysis})

        response = client.get("/patients", headers=headers)
        assert response.status_code == 200
        by_id = {item["id"]: item for item in response.json()["items"]}
        assert by_id[with_analysis]["has_analyses"] is True
        assert by_id[without_analysis]["has_analyses"] is False

    def test_list_patients_filters_by_has_analyses_true(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        with_analysis = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-FILTER-YES",
                "full_name": "Paciente Filtro Com Analise",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        ).json()["id"]
        client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-FILTER-NO",
                "full_name": "Paciente Filtro Sem Analise",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        client.post("/analyses", headers=headers, json={"patient_id": with_analysis})

        response = client.get("/patients", headers=headers, params={"has_analyses": "true"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["id"] == with_analysis

    def test_list_patients_filters_by_has_analyses_false(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        with_analysis = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-FILTER-YES-2",
                "full_name": "Paciente Filtro Com Analise 2",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        ).json()["id"]
        without_analysis = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-FILTER-NO-2",
                "full_name": "Paciente Filtro Sem Analise 2",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        ).json()["id"]
        client.post("/analyses", headers=headers, json={"patient_id": with_analysis})

        response = client.get("/patients", headers=headers, params={"has_analyses": "false"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["id"] == without_analysis

    def test_glycemia_observation_without_context_returns_422(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-GLY",
                "full_name": "Paciente Glicemia",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = create_response.json()["id"]

        observation_response = client.post(
            f"/patients/{patient_id}/observations",
            headers=headers,
            json={
                "observation_type": "GLYCEMIA",
                "value": {"value": 90},
                "unit": "mg/dL",
                "measured_at": "2026-07-11T10:00:00Z",
                "origin": "dispositivo",
                "author": "enfermeiro-1",
            },
        )
        assert observation_response.status_code == 422
        assert "moment" in observation_response.json()["field_errors"]

    def test_weight_observation_create_and_list(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._clinical_headers(institution_id)
        create_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-WEIGHT",
                "full_name": "Paciente Peso",
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
                "height_cm": 170.0,
            },
        )
        patient_id = create_response.json()["id"]

        observation_response = client.post(
            f"/patients/{patient_id}/observations",
            headers=headers,
            json={
                "observation_type": "WEIGHT",
                "value": {"value": 68.4},
                "unit": "kg",
                "measured_at": "2026-07-11T10:00:00Z",
                "origin": "dispositivo",
                "author": "enfermeiro-1",
            },
        )
        assert observation_response.status_code == 201
        assert observation_response.json()["value"]["value"] == 68.4

        list_response = client.get(f"/patients/{patient_id}/observations", headers=headers)
        assert list_response.status_code == 200
        weight_entries = [
            o for o in list_response.json() if o["observation_type"] == "WEIGHT"
        ]
        assert len(weight_entries) == 1
