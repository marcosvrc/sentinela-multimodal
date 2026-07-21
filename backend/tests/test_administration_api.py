"""Testes de integracao da API de administracao (item 5.3).

Cobre os tres CRUDs da secao 5.3 do escopo: especialidade medica,
funcionario, e o fluxo de publicacao/rollback de `ClinicalRuleSet`
(que passa a ser o unico caminho para um conjunto de regras se tornar
vigente - ver `app/rules_engine/service.py`).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.administration.models import Employee
from app.core.db import SessionLocal
from app.core.enums import EmployeeProfessionalType, UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.rules_engine.models import (
    ClinicalRule,
    ClinicalRuleAction,
    ClinicalRuleCondition,
    ClinicalRuleSet,
)


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
            {"id": str(institution_id), "name": "Instituicao Admin"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> str:
    session = SessionLocal()
    try:
        external_subject = f"admin-test-{role.value.lower()}-{uuid.uuid4()}"
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


def _create_approver_employee(institution_id: uuid.UUID) -> uuid.UUID:
    """Medico ativo cadastrado, usado como `approver_employee_id` nas
    chamadas de publish/rollback - o endpoint nao aceita mais um nome de
    aprovador digitado livremente (ver `app.administration.service.
    get_active_doctor_for_approval`)."""
    session = SessionLocal()
    try:
        employee = Employee(
            institution_id=institution_id,
            full_name="Dr. Aprovador Teste",
            cpf=f"{uuid.uuid4().int % 10**11:011d}",
            registration_number=f"CRM-{uuid.uuid4().hex[:8]}",
            email=f"aprovador-{uuid.uuid4()}@example.com",
            professional_type=EmployeeProfessionalType.MEDICO.value,
            active=True,
        )
        session.add(employee)
        session.commit()
        return employee.id
    finally:
        session.close()


def _seed_draft_rule_set(code: str) -> uuid.UUID:
    session = SessionLocal()
    try:
        rule_set = ClinicalRuleSet(
            code=code,
            version=f"0.{uuid.uuid4().hex[:12]}",
            population="adult",
            status="draft",
            effective_from=date.today(),
            effective_to=None,
            required_inputs=["spo2_percent"],
            exclusions=[],
            content_hash=f"admin-test-hash-{uuid.uuid4()}",
        )
        session.add(rule_set)
        session.flush()
        rule = ClinicalRule(
            rule_set_id=rule_set.id,
            rule_key="normal",
            risk_level=1,
            classification_label="Normal",
            position=0,
        )
        session.add(rule)
        session.flush()
        session.add(ClinicalRuleCondition(rule_id=rule.id, expression="spo2_percent >= 96"))
        session.add(
            ClinicalRuleAction(rule_set_id=rule_set.id, risk_level=1, description="Rotina.")
        )
        session.commit()
        return rule_set.id
    finally:
        session.close()


class TestSpecialtyAndEmployeeCrud:
    def test_admin_tecnico_creates_specialty_and_employee(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}

        specialty_response = client.post(
            "/admin/specialties", headers=headers, json={"name": "Cardiologia"}
        )
        assert specialty_response.status_code == 201
        specialty_id = specialty_response.json()["id"]

        employee_response = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Dra. Ana Souza",
                "cpf": "111.444.777-35",
                "registration_number": "CRM-12345",
                "email": "ana.souza@example.com",
                "specialty_id": specialty_id,
                "professional_type": "MEDICO",
                "role": "MEDICO",
                "external_subject": f"employee-{uuid.uuid4()}",
            },
        )
        assert employee_response.status_code == 201
        body = employee_response.json()
        assert body["cpf"] == "11144477735"
        assert body["specialty_id"] == specialty_id
        assert body["active"] is True
        assert body["professional_type"] == "MEDICO"
        assert body["role"] == "MEDICO"
        assert body["external_subject"] is not None

        list_response = client.get("/admin/employees", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()["total_items"] == 1

    def test_created_employee_can_authenticate_with_its_own_role(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}
        external_subject = f"employee-me-{uuid.uuid4()}"

        employee_response = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Dr. Login Direto",
                "cpf": "111.444.777-35",
                "registration_number": "CRM-77777",
                "email": "login.direto@example.com",
                "professional_type": "MEDICO",
                "role": "ADMINISTRADOR_CLINICO",
                "external_subject": external_subject,
            },
        )
        assert employee_response.status_code == 201

        me_response = client.get("/me", headers={"X-Dev-Subject": external_subject})
        assert me_response.status_code == 200
        assert me_response.json()["role"] == "ADMINISTRADOR_CLINICO"

    def test_nurse_employee_can_only_receive_nurse_role(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}

        response = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Enf. Papel Invalido",
                "cpf": "111.444.777-35",
                "registration_number": "COREN-1",
                "email": "enf.invalido@example.com",
                "professional_type": "ENFERMEIRO",
                "role": "ADMINISTRADOR_TECNICO",
                "external_subject": f"employee-{uuid.uuid4()}",
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "ROLE_NOT_ALLOWED_FOR_PROFESSIONAL_TYPE"

    def test_get_available_roles_for_nurse_returns_only_nurse_role(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}

        response = client.get(
            "/admin/employees/available-roles",
            headers=headers,
            params={"professional_type": "ENFERMEIRO"},
        )
        assert response.status_code == 200
        assert response.json()["roles"] == ["ENFERMEIRO"]

    def test_get_available_roles_for_doctor_includes_admin_and_auditor(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}

        response = client.get(
            "/admin/employees/available-roles",
            headers=headers,
            params={"professional_type": "MEDICO"},
        )
        assert response.status_code == 200
        roles = set(response.json()["roles"])
        assert roles == {"MEDICO", "ADMINISTRADOR_TECNICO", "ADMINISTRADOR_CLINICO", "AUDITOR"}

    def test_create_employee_with_invalid_cpf_returns_422(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}

        response = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Dr. Invalido",
                "cpf": "111.111.111-11",
                "registration_number": "CRM-99999",
                "email": "invalido@example.com",
                "professional_type": "MEDICO",
                "role": "MEDICO",
                "external_subject": f"employee-{uuid.uuid4()}",
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_CPF"

    def test_duplicate_cpf_in_same_institution_returns_409(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}
        payload = {
            "full_name": "Dr. Duplicado",
            "cpf": "111.444.777-35",
            "registration_number": "CRM-11111",
            "email": "duplicado@example.com",
            "professional_type": "MEDICO",
            "role": "MEDICO",
            "external_subject": f"employee-{uuid.uuid4()}",
        }
        first = client.post("/admin/employees", headers=headers, json=payload)
        assert first.status_code == 201

        second = client.post(
            "/admin/employees",
            headers=headers,
            json={
                **payload,
                "registration_number": "CRM-22222",
                "external_subject": f"employee-{uuid.uuid4()}",
            },
        )
        assert second.status_code == 409
        assert second.json()["code"] == "DUPLICATE_EMPLOYEE"

    def test_duplicate_external_subject_returns_409(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}
        shared_subject = f"employee-{uuid.uuid4()}"
        first = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Dr. Primeiro",
                "cpf": "111.444.777-35",
                "registration_number": "CRM-30000",
                "email": "primeiro@example.com",
                "professional_type": "MEDICO",
                "role": "MEDICO",
                "external_subject": shared_subject,
            },
        )
        assert first.status_code == 201

        second = client.post(
            "/admin/employees",
            headers=headers,
            json={
                "full_name": "Dr. Segundo",
                "cpf": "529.982.247-25",
                "registration_number": "CRM-30001",
                "email": "segundo@example.com",
                "professional_type": "MEDICO",
                "role": "MEDICO",
                "external_subject": shared_subject,
            },
        )
        assert second.status_code == 409
        assert second.json()["code"] == "DUPLICATE_USER"

    def test_medico_role_cannot_manage_administration(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.MEDICO)}

        response = client.post("/admin/specialties", headers=headers, json={"name": "Pediatria"})
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"


class TestClinicalRuleSetPublicationWorkflow:
    def test_draft_rule_set_is_not_evaluated_until_published(self, client: TestClient) -> None:
        institution_id = _create_institution()
        clinical_admin_headers = {
            "X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)
        }
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-spo2-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        # Ainda em draft: o motor de regras nao considera o conjunto vigente.
        evaluate_headers = {
            "X-Dev-Subject": _create_user(institution_id, UserRole.MEDICO)
        }
        evaluate_before = client.post(
            f"/clinical-rules/{code}/evaluate",
            headers=evaluate_headers,
            json={"population": "adult", "inputs": {"spo2_percent": 98}},
        )
        assert evaluate_before.status_code == 200
        assert evaluate_before.json()["outcome"] == "INCONCLUSIVE"

        publish_response = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=clinical_admin_headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Revisado e aprovado para uso.",
            },
        )
        assert publish_response.status_code == 200
        assert publish_response.json()["status"] == "published"

        evaluate_after = client.post(
            f"/clinical-rules/{code}/evaluate",
            headers=evaluate_headers,
            json={"population": "adult", "inputs": {"spo2_percent": 98}},
        )
        assert evaluate_after.status_code == 200
        assert evaluate_after.json()["outcome"] == "MATCHED"

    def test_publish_twice_returns_conflict(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-publish-twice-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        first = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Primeira publicacao.",
            },
        )
        assert first.status_code == 200

        second = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Segunda tentativa.",
            },
        )
        assert second.status_code == 409
        assert second.json()["code"] == "RULE_SET_NOT_DRAFT"

    def test_medico_cannot_publish_rule_set(self, client: TestClient) -> None:
        institution_id = _create_institution()
        medico_headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.MEDICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-forbidden-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        response = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=medico_headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Tentativa nao autorizada.",
            },
        )
        assert response.status_code == 403

    def test_publish_rejects_approver_that_is_not_a_doctor(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        code = f"admin-test-approver-nurse-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        session = SessionLocal()
        try:
            nurse = Employee(
                institution_id=institution_id,
                full_name="Enf. Nao Aprovador",
                cpf=f"{uuid.uuid4().int % 10**11:011d}",
                registration_number=f"COREN-{uuid.uuid4().hex[:8]}",
                email=f"enfermeiro-{uuid.uuid4()}@example.com",
                professional_type=EmployeeProfessionalType.ENFERMEIRO.value,
                active=True,
            )
            session.add(nurse)
            session.commit()
            nurse_id = nurse.id
        finally:
            session.close()

        response = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=headers,
            json={"approver_employee_id": str(nurse_id), "justification": "Tentativa invalida."},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "APPROVER_MUST_BE_DOCTOR"

    def test_publish_rejects_unknown_approver(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        code = f"admin-test-approver-unknown-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        response = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(uuid.uuid4()),
                "justification": "Tentativa invalida.",
            },
        )
        assert response.status_code == 404
        assert response.json()["code"] == "APPROVER_NOT_FOUND"

    def test_publishing_new_version_retires_previous_published_version(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-supersede-{uuid.uuid4()}"

        old_version_id = _seed_draft_rule_set(code)
        client.post(
            f"/admin/clinical-rule-sets/{old_version_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Versao inicial.",
            },
        )

        new_version_id = _seed_draft_rule_set(code)
        publish_new = client.post(
            f"/admin/clinical-rule-sets/{new_version_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Nova versao substitui a antiga.",
            },
        )
        assert publish_new.status_code == 200
        assert publish_new.json()["status"] == "published"

        old_after_new_publish = client.get(
            f"/admin/clinical-rule-sets/{old_version_id}", headers=headers
        )
        assert old_after_new_publish.json()["status"] == "retired"

    def test_rollback_restores_previous_version_and_retires_current(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-rollback-{uuid.uuid4()}"

        old_version_id = _seed_draft_rule_set(code)
        client.post(
            f"/admin/clinical-rule-sets/{old_version_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Versao inicial.",
            },
        )
        new_version_id = _seed_draft_rule_set(code)
        client.post(
            f"/admin/clinical-rule-sets/{new_version_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Nova versao substitui a antiga.",
            },
        )
        # Neste ponto: old_version = retired, new_version = published
        # (efeito colateral automatico do publish acima).

        rollback_response = client.post(
            f"/admin/clinical-rule-sets/{old_version_id}/rollback",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Nova versao apresentou problema; revertendo.",
            },
        )
        assert rollback_response.status_code == 200
        assert rollback_response.json()["status"] == "published"

        new_after_rollback = client.get(
            f"/admin/clinical-rule-sets/{new_version_id}", headers=headers
        )
        assert new_after_rollback.json()["status"] == "retired"

    def test_rollback_on_non_retired_rule_set_returns_conflict(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-rollback-invalid-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        response = client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/rollback",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Tentativa invalida em draft.",
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "RULE_SET_NOT_RETIRED"


class TestClinicalRuleEditing:
    def test_get_rule_set_detail_exposes_rules_and_actions(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO)}
        code = f"admin-test-detail-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        response = client.get(f"/admin/clinical-rule-sets/{rule_set_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body["rules"]) == 1
        assert body["rules"][0]["when"] == "spo2_percent >= 96"
        assert body["rules"][0]["risk_level"] == 1
        assert body["rules"][0]["classification_label"] == "Normal"

    def test_clinical_admin_edits_draft_rule(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        code = f"admin-test-edit-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)

        detail = client.get(f"/admin/clinical-rule-sets/{rule_set_id}", headers=headers).json()
        rule_id = detail["rules"][0]["id"]
        original_hash = detail["content_hash"]

        response = client.patch(
            f"/admin/clinical-rule-sets/{rule_set_id}/rules/{rule_id}",
            headers=headers,
            json={
                "when": "spo2_percent >= 97",
                "risk_level": 2,
                "classification_label": "Normal ajustado",
                "notes": "Ajuste de limiar.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rules"][0]["when"] == "spo2_percent >= 97"
        assert body["rules"][0]["risk_level"] == 2
        assert body["rules"][0]["classification_label"] == "Normal ajustado"
        assert body["content_hash"] != original_hash

    def test_edit_rule_rejects_unsafe_expression(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        code = f"admin-test-unsafe-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)
        detail = client.get(f"/admin/clinical-rule-sets/{rule_set_id}", headers=headers).json()
        rule_id = detail["rules"][0]["id"]

        response = client.patch(
            f"/admin/clinical-rule-sets/{rule_set_id}/rules/{rule_id}",
            headers=headers,
            json={
                "when": "__import__('os').system('echo hi')",
                "risk_level": 1,
                "classification_label": "Normal",
                "notes": None,
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "UNSAFE_RULE_EXPRESSION"

    def test_edit_rule_rejected_when_rule_set_is_published(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        approver_employee_id = _create_approver_employee(institution_id)
        code = f"admin-test-edit-published-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)
        detail = client.get(f"/admin/clinical-rule-sets/{rule_set_id}", headers=headers).json()
        rule_id = detail["rules"][0]["id"]

        client.post(
            f"/admin/clinical-rule-sets/{rule_set_id}/publish",
            headers=headers,
            json={
                "approver_employee_id": str(approver_employee_id),
                "justification": "Publicado para o teste.",
            },
        )

        response = client.patch(
            f"/admin/clinical-rule-sets/{rule_set_id}/rules/{rule_id}",
            headers=headers,
            json={
                "when": "spo2_percent >= 90",
                "risk_level": 1,
                "classification_label": "Normal",
                "notes": None,
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "RULE_SET_NOT_DRAFT"

    def test_medico_cannot_edit_rule(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_headers = {
            "X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)
        }
        medico_headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.MEDICO)}
        code = f"admin-test-forbidden-edit-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)
        detail = client.get(
            f"/admin/clinical-rule-sets/{rule_set_id}", headers=admin_headers
        ).json()
        rule_id = detail["rules"][0]["id"]

        response = client.patch(
            f"/admin/clinical-rule-sets/{rule_set_id}/rules/{rule_id}",
            headers=medico_headers,
            json={
                "when": "spo2_percent >= 90",
                "risk_level": 1,
                "classification_label": "Normal",
                "notes": None,
            },
        )
        assert response.status_code == 403

    def test_edit_rule_action_description(self, client: TestClient) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO)}
        code = f"admin-test-edit-action-{uuid.uuid4()}"
        rule_set_id = _seed_draft_rule_set(code)
        detail = client.get(f"/admin/clinical-rule-sets/{rule_set_id}", headers=headers).json()
        action_id = detail["actions"][0]["id"]

        response = client.patch(
            f"/admin/clinical-rule-sets/{rule_set_id}/actions/{action_id}",
            headers=headers,
            json={"description": "Conduta revisada para nivel 1."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["actions"][0]["description"] == "Conduta revisada para nivel 1."
