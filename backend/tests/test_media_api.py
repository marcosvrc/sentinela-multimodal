"""Testes da API de analise/upload de midia (item 8 do backlog).

Mesma estrategia das demais APIs: contrato HTTP sem banco roda sempre;
integracao real (com banco, exercitando tambem o adaptador de storage
local de ponta a ponta) e pulada quando Postgres nao esta disponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

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


def test_create_analysis_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post("/analyses", json={"patient_id": str(uuid.uuid4())})
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_AUTH_CONTEXT"


@pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")
class TestMediaApiWithDatabase:
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

    def _create_user(self, institution_id: uuid.UUID, role: UserRole = UserRole.MEDICO) -> str:
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

    def _headers(self, institution_id: uuid.UUID, role: UserRole = UserRole.MEDICO) -> dict:
        return {"X-Dev-Subject": self._create_user(institution_id, role)}

    def _create_user_with_employee(
        self, institution_id: uuid.UUID, role: UserRole, registration_number: str
    ) -> str:
        """Cria um usuario clinico com um `Employee` vinculado (matricula
        informada), para testar o enriquecimento de `registration_number`
        em `GET /analyses/professionals`."""
        session = SessionLocal()
        try:
            external_subject = f"test-{role.value.lower()}-{uuid.uuid4()}"
            user = identity_service.get_or_create_user(
                session,
                institution_id=institution_id,
                external_subject=external_subject,
                full_name=f"Usuario Teste {role.value}",
                role=role.value,
            )
            session.execute(
                text(
                    "INSERT INTO employees "
                    "(id, institution_id, user_id, full_name, cpf, registration_number, "
                    "email, professional_type, active) "
                    "VALUES (:id, :institution_id, :user_id, :full_name, :cpf, "
                    ":registration_number, :email, :professional_type, true)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "institution_id": str(institution_id),
                    "user_id": str(user.id),
                    "full_name": user.full_name,
                    "cpf": str(uuid.uuid4().int)[:11],
                    "registration_number": registration_number,
                    "email": f"{external_subject}@example.com",
                    "professional_type": "MEDICO" if role == UserRole.MEDICO else "ENFERMEIRO",
                },
            )
            session.commit()
            return external_subject
        finally:
            session.close()

    def _create_patient(
        self,
        client: TestClient,
        headers: dict,
        *,
        full_name: str = "Paciente Midia",
        medical_record_number: str | None = None,
    ) -> str:
        response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": medical_record_number or f"MRN-{uuid.uuid4()}",
                "full_name": full_name,
                "birth_date": "1990-06-15",
                "registered_sex": "feminino",
            },
        )
        assert response.status_code == 201
        return response.json()["id"]

    def test_create_analysis(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)

        response = client.post(
            "/analyses",
            headers=headers,
            json={"patient_id": patient_id, "additional_text": "Paciente relata tontura."},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "CREATED"
        assert body["patient_id"] == patient_id

    def test_list_analyses_returns_only_own_institution_most_recent_first(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)

        first = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id, "additional_text": "a"}
        )
        second = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id, "additional_text": "b"}
        )
        assert first.status_code == 201
        assert second.status_code == 201

        other_institution_id = self._create_institution()
        other_headers = self._headers(other_institution_id)
        other_patient_id = self._create_patient(client, other_headers)
        client.post(
            "/analyses",
            headers=other_headers,
            json={"patient_id": other_patient_id, "additional_text": "outra instituicao"},
        )

        response = client.get("/analyses", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 2
        returned_ids = [item["id"] for item in body["items"]]
        assert returned_ids == [second.json()["id"], first.json()["id"]]

    def test_list_analyses_filters_by_patient_id(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_a = self._create_patient(client, headers)
        patient_b = self._create_patient(client, headers)

        client.post("/analyses", headers=headers, json={"patient_id": patient_a})
        client.post("/analyses", headers=headers, json={"patient_id": patient_b})

        response = client.get("/analyses", headers=headers, params={"patient_id": patient_a})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["patient_id"] == patient_a

    def test_full_upload_flow_approves_valid_png(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)

        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        checksum = hashlib.sha256(content).hexdigest()

        upload_response = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "IMAGE",
                "filename": "foto.png",
                "mime_type": "image/png",
                "size_bytes": len(content),
            },
        )
        assert upload_response.status_code == 201
        upload_body = upload_response.json()
        media_id = upload_body["media_id"]

        # A analise deve ter transicionado para UPLOADING.
        analysis_after = client.get(f"/analyses/{analysis_id}", headers=headers).json()
        assert analysis_after["status"] == "UPLOADING"

        put_response = client.put(upload_body["upload_url"], content=content)
        assert put_response.status_code == 204

        confirm_response = client.post(
            f"/analyses/{analysis_id}/media/{media_id}/confirm",
            headers=headers,
            json={"checksum_sha256": checksum},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed["upload_state"] == "APPROVED"
        assert confirmed["detected_mime_type"] == "image/png"

    def test_confirm_rejects_checksum_mismatch(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)
        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        upload_body = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "IMAGE",
                "filename": "foto.png",
                "mime_type": "image/png",
                "size_bytes": len(content),
            },
        ).json()
        client.put(upload_body["upload_url"], content=content)

        confirm_response = client.post(
            f"/analyses/{analysis_id}/media/{upload_body['media_id']}/confirm",
            headers=headers,
            json={"checksum_sha256": "0" * 64},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["upload_state"] == "REJECTED"
        assert "checksum" in confirm_response.json()["rejection_reason"].lower()

    def test_confirm_rejects_mime_signature_mismatch(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)
        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        # Declara PNG mas envia bytes que tem assinatura de JPEG.
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        checksum = hashlib.sha256(content).hexdigest()
        upload_body = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "IMAGE",
                "filename": "foto.png",
                "mime_type": "image/png",
                "size_bytes": len(content),
            },
        ).json()
        client.put(upload_body["upload_url"], content=content)

        confirm_response = client.post(
            f"/analyses/{analysis_id}/media/{upload_body['media_id']}/confirm",
            headers=headers,
            json={"checksum_sha256": checksum},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["upload_state"] == "REJECTED"

    def test_request_upload_url_rejects_disallowed_mime(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)
        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        response = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "IMAGE",
                "filename": "documento.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1000,
            },
        )
        assert response.status_code == 422
        assert "mime_type" in response.json()["field_errors"]

    def test_request_upload_url_rejects_disabled_modality(self, client: TestClient) -> None:
        """Feature flag `modality_image_enabled=false` (tela /admin/
        feature-flags) bloqueia novos uploads dessa modalidade com 422 -
        ver `app.media.service._is_modality_enabled`. Restaura a flag no
        teardown para nao afetar outros testes que dependem dela."""
        from app.core.db import SessionLocal
        from app.feature_flags.service import update_feature_flags

        db = SessionLocal()
        try:
            update_feature_flags(
                db, actor="test-setup", actor_role=None, modality_image_enabled=False
            )
        finally:
            db.close()

        try:
            institution_id = self._create_institution()
            headers = self._headers(institution_id)
            patient_id = self._create_patient(client, headers)
            analysis_id = client.post(
                "/analyses", headers=headers, json={"patient_id": patient_id}
            ).json()["id"]

            response = client.post(
                f"/analyses/{analysis_id}/media",
                headers=headers,
                json={
                    "modality_type": "IMAGE",
                    "filename": "foto.png",
                    "mime_type": "image/png",
                    "size_bytes": 1000,
                },
            )
            assert response.status_code == 422
            assert response.json()["code"] == "MODALITY_DISABLED"
        finally:
            db = SessionLocal()
            try:
                update_feature_flags(
                    db, actor="test-teardown", actor_role=None, modality_image_enabled=True
                )
            finally:
                db.close()

    def test_non_clinical_role_is_forbidden(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id, role=UserRole.AUDITOR)

        response = client.post("/analyses", headers=headers, json={"patient_id": str(uuid.uuid4())})
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"

    def test_list_analyses_resolves_created_by_full_name(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)
        client.post("/analyses", headers=headers, json={"patient_id": patient_id})

        response = client.get("/analyses", headers=headers)
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["created_by_full_name"] == "Usuario Teste MEDICO"

    def test_list_analyses_filters_by_created_by(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers_medico = self._headers(institution_id, role=UserRole.MEDICO)
        headers_enfermeiro = self._headers(institution_id, role=UserRole.ENFERMEIRO)
        patient_id = self._create_patient(client, headers_medico)

        client.post("/analyses", headers=headers_medico, json={"patient_id": patient_id})
        client.post("/analyses", headers=headers_enfermeiro, json={"patient_id": patient_id})

        medico_subject = headers_medico["X-Dev-Subject"]
        response = client.get(
            "/analyses", headers=headers_medico, params={"created_by": medico_subject}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["created_by"] == medico_subject

    def test_list_analyses_filters_by_date_range(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(client, headers)
        client.post("/analyses", headers=headers, json={"patient_id": patient_id})

        today = date.today().isoformat()

        in_range = client.get(
            "/analyses",
            headers=headers,
            params={"created_from": today, "created_to": today},
        )
        assert in_range.status_code == 200
        assert in_range.json()["total_items"] == 1

        out_of_range = client.get(
            "/analyses",
            headers=headers,
            params={"created_from": "2000-01-01", "created_to": "2000-01-02"},
        )
        assert out_of_range.status_code == 200
        assert out_of_range.json()["total_items"] == 0

    def test_list_analyses_includes_patient_name_and_medical_record_number(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_id = self._create_patient(
            client, headers, full_name="Ana Beatriz Souza", medical_record_number="MRN-0099"
        )
        client.post("/analyses", headers=headers, json={"patient_id": patient_id})

        response = client.get("/analyses", headers=headers)
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["patient_full_name"] == "Ana Beatriz Souza"
        assert item["patient_medical_record_number"] == "MRN-0099"

    def test_list_analyses_filters_by_patient_name(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_a = self._create_patient(client, headers, full_name="Ana Beatriz Souza")
        patient_b = self._create_patient(client, headers, full_name="Carlos Eduardo Lima")
        client.post("/analyses", headers=headers, json={"patient_id": patient_a})
        client.post("/analyses", headers=headers, json={"patient_id": patient_b})

        response = client.get("/analyses", headers=headers, params={"patient_name": "beatriz"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["patient_full_name"] == "Ana Beatriz Souza"

    def test_list_analyses_filters_by_patient_medical_record_number(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        patient_a = self._create_patient(client, headers, medical_record_number="MRN-1234")
        patient_b = self._create_patient(client, headers, medical_record_number="MRN-5678")
        client.post("/analyses", headers=headers, json={"patient_id": patient_a})
        client.post("/analyses", headers=headers, json={"patient_id": patient_b})

        response = client.get(
            "/analyses", headers=headers, params={"patient_medical_record_number": "1234"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_items"] == 1
        assert body["items"][0]["patient_medical_record_number"] == "MRN-1234"

    def test_list_analysis_professionals_returns_only_clinical_staff(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        self._create_user(institution_id, role=UserRole.ENFERMEIRO)
        self._create_user(institution_id, role=UserRole.ADMINISTRADOR_TECNICO)

        response = client.get("/analyses/professionals", headers=headers)
        assert response.status_code == 200
        roles_present = {item["full_name"] for item in response.json()}
        assert any("MEDICO" in name for name in roles_present)
        assert any("ENFERMEIRO" in name for name in roles_present)
        assert not any("ADMINISTRADOR" in name for name in roles_present)

    def test_list_analysis_professionals_includes_registration_number_when_linked(
        self, client: TestClient
    ) -> None:
        institution_id = self._create_institution()
        headers = self._headers(institution_id)
        linked_subject = self._create_user_with_employee(
            institution_id, UserRole.MEDICO, registration_number="MAT-0001"
        )

        response = client.get("/analyses/professionals", headers=headers)
        assert response.status_code == 200
        by_subject = {item["external_subject"]: item for item in response.json()}

        assert by_subject[linked_subject]["registration_number"] == "MAT-0001"
        # O usuario criado por `_headers`/`self._create_user` acima nao tem
        # `Employee` vinculado - deve aparecer com `registration_number=None`,
        # nunca quebrar a resposta.
        caller_subject = headers["X-Dev-Subject"]
        assert by_subject[caller_subject]["registration_number"] is None

    def test_cross_tenant_analysis_access_returns_404(self, client: TestClient) -> None:
        institution_a = self._create_institution()
        institution_b = self._create_institution()
        headers_a = self._headers(institution_a)
        patient_id = self._create_patient(client, headers_a)

        analysis_id = client.post(
            "/analyses", headers=headers_a, json={"patient_id": patient_id}
        ).json()["id"]

        headers_b = self._headers(institution_b)
        response = client.get(f"/analyses/{analysis_id}", headers=headers_b)
        assert response.status_code == 404
