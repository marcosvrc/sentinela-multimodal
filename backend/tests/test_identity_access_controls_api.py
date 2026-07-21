"""Testes de integracao do eixo "unidade + vinculo assistencial" (secao 5.2)
e do CRUD de usuarios/papeis de acesso (secao 5.3, fechado por
`app.administration.service.create_user`/etc).

Cobre o que `docs/governance/VALIDACAO_ESCOPO.md` disclosed como faltante
antes desta rodada de reconciliacao: `require_patient_access` (vinculo
assistencial + break glass), CRUD de `PatientCareAssignment`/`CareUnit`, e
CRUD de `User` (criacao, listagem, atualizacao de papel/ativacao, revogacao
de sessoes).

Nao cobre o adaptador COGNITO em si (exigiria um JWKS real - ver
`app/integrations/identity/cognito.py` e seus proprios testes unitarios com
chave RSA gerada em memoria); aqui o foco e a autorizacao que roda **depois**
de qualquer identidade ja resolvida (LOCAL nestes testes, como em todo o
resto da suite HTTP).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
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
            {"id": str(institution_id), "name": "Instituicao Identidade"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> tuple[str, uuid.UUID]:
    session = SessionLocal()
    try:
        external_subject = f"identity-test-{role.value.lower()}-{uuid.uuid4()}"
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
                "VALUES (:id, :institution_id, :mrn, :name, '1990-01-01', 'F', "
                "'seed', now(), now())"
            ),
            {
                "id": str(patient_id),
                "institution_id": str(institution_id),
                "mrn": f"MRN-{uuid.uuid4().hex[:10]}",
                "name": "Paciente Teste Identidade",
            },
        )
        session.commit()
        return patient_id
    finally:
        session.close()


class TestPatientAccessRequiresCareAssignment:
    def test_medico_without_assignment_gets_403_no_care_assignment(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        medico_subject, _ = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        response = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert response.status_code == 403
        assert response.json()["code"] == "NO_CARE_ASSIGNMENT"

    def test_admin_creates_assignment_then_medico_gains_access(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        medico_subject, medico_id = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        denied = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert denied.status_code == 403

        assignment_response = client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": admin_subject},
            json={"user_id": str(medico_id)},
        )
        assert assignment_response.status_code == 201
        assignment_id = assignment_response.json()["id"]
        assert assignment_response.json()["active"] is True

        allowed = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert allowed.status_code == 200

        ended = client.delete(
            f"/patients/{patient_id}/care-assignments/{assignment_id}",
            headers={"X-Dev-Subject": admin_subject},
        )
        assert ended.status_code == 200
        assert ended.json()["active"] is False

        denied_again = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert denied_again.status_code == 403

    def test_medico_cannot_create_care_assignment(self, client: TestClient) -> None:
        institution_id = _create_institution()
        medico_subject, medico_id = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        response = client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": medico_subject},
            json={"user_id": str(medico_id)},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"


class TestBreakGlass:
    def test_break_glass_grant_allows_immediate_access_and_is_audited(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        medico_subject, _ = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        denied = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert denied.status_code == 403

        grant_response = client.post(
            f"/patients/{patient_id}/break-glass",
            headers={"X-Dev-Subject": medico_subject},
            json={"justification": "Emergencia: paciente em choque, sem vinculo formal ainda."},
        )
        assert grant_response.status_code == 201
        assert grant_response.json()["patient_id"] == str(patient_id)

        allowed = client.get(
            f"/patients/{patient_id}", headers={"X-Dev-Subject": medico_subject}
        )
        assert allowed.status_code == 200

    def test_break_glass_requires_justification_with_minimum_length(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        medico_subject, _ = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        response = client.post(
            f"/patients/{patient_id}/break-glass",
            headers={"X-Dev-Subject": medico_subject},
            json={"justification": "curta"},
        )
        assert response.status_code == 422


class TestCareUnitCrud:
    def test_admin_creates_care_unit_and_assigns_it(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        _, medico_id = _create_user(institution_id, UserRole.MEDICO)
        patient_id = _create_patient(institution_id)

        unit_response = client.post(
            "/admin/care-units",
            headers={"X-Dev-Subject": admin_subject},
            json={"name": "UTI Adulto"},
        )
        assert unit_response.status_code == 201
        unit_id = unit_response.json()["id"]
        assert unit_response.json()["active"] is True

        assignment_response = client.post(
            f"/patients/{patient_id}/care-assignments",
            headers={"X-Dev-Subject": admin_subject},
            json={"user_id": str(medico_id), "care_unit_id": unit_id},
        )
        assert assignment_response.status_code == 201
        assert assignment_response.json()["care_unit_id"] == unit_id


class TestUserCrud:
    """Nao ha mais `POST /admin/users`: a conta de acesso e criada junto
    com o funcionario (`POST /admin/employees`, ver
    test_administration_api.py::test_created_employee_can_authenticate_with_its_own_role).
    Esta classe cobre apenas consulta (com filtros) e gestao (papel/status/
    revogacao de sessao) de contas ja existentes."""

    def test_admin_lists_and_updates_user(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        _, medico_user_id = _create_user(institution_id, UserRole.MEDICO)

        list_response = client.get("/admin/users", headers={"X-Dev-Subject": admin_subject})
        assert list_response.status_code == 200
        assert list_response.json()["total_items"] >= 2  # admin + medico

        update_response = client.patch(
            f"/admin/users/{medico_user_id}",
            headers={"X-Dev-Subject": admin_subject},
            json={"active": False},
        )
        assert update_response.status_code == 200
        assert update_response.json()["active"] is False

    def test_list_users_filters_by_search_role_and_active(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        auditor_subject, auditor_id = _create_user(institution_id, UserRole.AUDITOR)

        by_search = client.get(
            "/admin/users",
            headers={"X-Dev-Subject": admin_subject},
            params={"search": auditor_subject},
        )
        assert by_search.status_code == 200
        assert by_search.json()["total_items"] == 1
        assert by_search.json()["items"][0]["external_subject"] == auditor_subject

        by_role = client.get(
            "/admin/users",
            headers={"X-Dev-Subject": admin_subject},
            params={"role": "AUDITOR"},
        )
        assert by_role.status_code == 200
        assert all(item["role"] == "AUDITOR" for item in by_role.json()["items"])

        client.patch(
            f"/admin/users/{auditor_id}",
            headers={"X-Dev-Subject": admin_subject},
            json={"active": False},
        )
        by_active = client.get(
            "/admin/users",
            headers={"X-Dev-Subject": admin_subject},
            params={"active": "false"},
        )
        assert by_active.status_code == 200
        inactive_subjects = [item["external_subject"] for item in by_active.json()["items"]]
        assert auditor_subject in inactive_subjects

    def test_medico_cannot_manage_users(self, client: TestClient) -> None:
        institution_id = _create_institution()
        medico_subject, _ = _create_user(institution_id, UserRole.MEDICO)

        response = client.get("/admin/users", headers={"X-Dev-Subject": medico_subject})
        assert response.status_code == 403

    def test_revoke_sessions_endpoint_returns_204(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_subject, _ = _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)
        _, target_user_id = _create_user(institution_id, UserRole.MEDICO)

        response = client.post(
            f"/admin/users/{target_user_id}/revoke-sessions",
            headers={"X-Dev-Subject": admin_subject},
            json={"reason": "Suspeita de compartilhamento de credencial."},
        )
        assert response.status_code == 204


class TestLoginLockout:
    def test_is_locked_out_after_threshold_and_resets_outside_window(self) -> None:
        # Testa `app.identity.service.is_locked_out` diretamente (a unica
        # forma de exercitar bloqueio sem um token Cognito real - ver
        # docstring do modulo sobre o escopo dos testes de COGNITO).
        session = SessionLocal()
        try:
            from app.core.config import get_settings

            settings = get_settings()
            subject = f"lockout-test-{uuid.uuid4()}"

            assert identity_service.is_locked_out(session, subject) is False

            for _ in range(settings.login_max_failed_attempts):
                identity_service.record_failed_attempt(session, subject, reason="bad_token")
            session.commit()

            assert identity_service.is_locked_out(session, subject) is True
        finally:
            session.close()
