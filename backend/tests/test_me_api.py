"""Testes de `GET /me` (app.api.routes.me).

Cobre o caso de uso do frontend decidir quais itens de navegacao exibir de
acordo com o papel do usuario ativo (ESPECIFICACAO_FRONTEND.md secao 3):
qualquer papel autenticado consegue ler o proprio registro, sem exigir
`require_role` de administrador.

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI), mesmo criterio do restante da suite de identidade.
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
            {"id": str(institution_id), "name": "Instituicao Me API"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> str:
    session = SessionLocal()
    try:
        external_subject = f"me-api-test-{role.value.lower()}-{uuid.uuid4()}"
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


class TestGetMe:
    def test_returns_401_without_dev_subject_header(self, client: TestClient) -> None:
        response = client.get("/me")
        assert response.status_code == 401
        assert response.json()["code"] == "MISSING_AUTH_CONTEXT"

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.MEDICO,
            UserRole.ENFERMEIRO,
            UserRole.ADMINISTRADOR_TECNICO,
            UserRole.ADMINISTRADOR_CLINICO,
            UserRole.AUDITOR,
        ],
    )
    def test_returns_own_role_for_any_authenticated_role(
        self, client: TestClient, role: UserRole
    ) -> None:
        institution_id = _create_institution()
        external_subject = _create_user(institution_id, role)

        response = client.get("/me", headers={"X-Dev-Subject": external_subject})

        assert response.status_code == 200
        body = response.json()
        assert body["external_subject"] == external_subject
        assert body["role"] == role.value
        assert body["institution_id"] == str(institution_id)
