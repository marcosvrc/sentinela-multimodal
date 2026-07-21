"""Testes da API de avaliacao manual de regras (POST /clinical-rules/{code}/evaluate)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.rules_engine.models import ClinicalRule, ClinicalRuleCondition, ClinicalRuleSet


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


def test_evaluate_without_auth_header_returns_401(client: TestClient) -> None:
    response = client.post("/clinical-rules/spo2/evaluate", json={"inputs": {}})
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_AUTH_CONTEXT"


@pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")
class TestRulesApiWithDatabase:
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

    def _headers(self, institution_id: uuid.UUID, role: UserRole = UserRole.MEDICO) -> dict:
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
            return {"X-Dev-Subject": external_subject}
        finally:
            session.close()

    def _seed_rule_set(self, code: str) -> None:
        session = SessionLocal()
        try:
            from datetime import date

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
                rule_key="normal",
                risk_level=1,
                classification_label="Normal",
                position=0,
            )
            session.add(rule)
            session.flush()
            session.add(ClinicalRuleCondition(rule_id=rule.id, expression="spo2_percent >= 96"))
            session.commit()
        finally:
            session.close()

    def test_evaluate_matched(self, client: TestClient) -> None:
        code = f"test-spo2-{uuid.uuid4()}"
        self._seed_rule_set(code)
        institution_id = self._create_institution()

        response = client.post(
            f"/clinical-rules/{code}/evaluate",
            headers=self._headers(institution_id),
            json={"inputs": {"spo2_percent": 99}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "MATCHED"
        assert body["matched_rule_key"] == "normal"
        assert body["risk_level"] == 1

    def test_evaluate_inconclusive_for_unknown_code(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        response = client.post(
            f"/clinical-rules/does-not-exist-{uuid.uuid4()}/evaluate",
            headers=self._headers(institution_id),
            json={"inputs": {}},
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "INCONCLUSIVE"
        assert response.json()["inconclusive_reason"] == "NO_RULE_SET_AVAILABLE"

    def test_evaluate_forbidden_for_non_clinical_role(self, client: TestClient) -> None:
        institution_id = self._create_institution()
        response = client.post(
            "/clinical-rules/spo2/evaluate",
            headers=self._headers(institution_id, role=UserRole.AUDITOR),
            json={"inputs": {}},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"
