"""Testes de integracao da API de feature flags (`/admin/feature-flags`,
acesso restrito a administrador - ver `app.feature_flags`).

Precisa de Postgres real; pulado automaticamente quando indisponivel
neste sandbox (roda no CI).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.feature_flags.service import update_feature_flags
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


@pytest.fixture(autouse=True)
def restore_feature_flags():
    """Toda mutacao feita pelos testes deste arquivo e revertida no
    teardown - `update_feature_flags` commita direto (linha singleton
    compartilhada entre testes/processos)."""
    db = SessionLocal()
    try:
        from app.feature_flags.service import get_feature_flags

        original = {
            field: getattr(get_feature_flags(db), field)
            for field in (
                "llm_provider_enabled",
                "llm_provider",
                "llm_openai_model",
                "llm_gemini_model",
                "modality_audio_enabled",
                "modality_video_enabled",
                "modality_image_enabled",
                "vision_detection_enabled",
                "vision_pose_enabled",
                "image_recognition_enabled",
                "sentiment_analysis_enabled",
            )
        }
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        update_feature_flags(db, actor="test-teardown", actor_role=None, **original)
    finally:
        db.close()


def _create_institution() -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": "Instituicao Feature Flags"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> str:
    session = SessionLocal()
    try:
        external_subject = f"ff-test-{role.value.lower()}-{uuid.uuid4()}"
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


class TestFeatureFlagsApi:
    def test_admin_technical_can_read_flags(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_headers = _headers(_create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO))

        response = client.get("/admin/feature-flags", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert "llm_provider_enabled" in body
        assert "modality_audio_enabled" in body
        assert body["gemini_implemented"] is False
        assert any(opt["value"] == "gpt-4o-mini" for opt in body["openai_model_options"])
        assert any(opt["value"] == "gemini-1.5-flash" for opt in body["gemini_model_options"])

    def test_admin_clinical_can_update_flags(self, client: TestClient) -> None:
        institution_id = _create_institution()
        admin_headers = _headers(_create_user(institution_id, UserRole.ADMINISTRADOR_CLINICO))

        response = client.patch(
            "/admin/feature-flags",
            headers=admin_headers,
            json={"llm_provider_enabled": True, "llm_provider": "OPENAI"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["llm_provider_enabled"] is True
        assert body["llm_provider"] == "OPENAI"

        # Persistiu de fato - uma nova leitura reflete o valor atualizado.
        follow_up = client.get("/admin/feature-flags", headers=admin_headers)
        assert follow_up.json()["llm_provider_enabled"] is True

    def test_update_accepts_gemini_selection_even_though_unimplemented(
        self, client: TestClient
    ) -> None:
        """A tela permite escolher Gemini como PLANEJAMENTO (ver
        app.integrations.llm.gemini_adapter) - a falha so ocorre quando o
        LLM e de fato chamado, nunca ao salvar a preferencia."""
        institution_id = _create_institution()
        admin_headers = _headers(_create_user(institution_id, UserRole.ADMINISTRADOR_TECNICO))

        response = client.patch(
            "/admin/feature-flags",
            headers=admin_headers,
            json={
                "llm_provider_enabled": True,
                "llm_provider": "GEMINI",
                "llm_gemini_model": "gemini-2.0-flash",
            },
        )
        assert response.status_code == 200
        assert response.json()["llm_provider"] == "GEMINI"

    def test_non_admin_role_cannot_read_flags(self, client: TestClient) -> None:
        institution_id = _create_institution()
        medico_headers = _headers(_create_user(institution_id, UserRole.MEDICO))

        response = client.get("/admin/feature-flags", headers=medico_headers)
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"

    def test_non_admin_role_cannot_update_flags(self, client: TestClient) -> None:
        institution_id = _create_institution()
        auditor_headers = _headers(_create_user(institution_id, UserRole.AUDITOR))

        response = client.patch(
            "/admin/feature-flags",
            headers=auditor_headers,
            json={"modality_video_enabled": False},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN_ROLE"

    def test_unauthenticated_request_returns_401(self, client: TestClient) -> None:
        response = client.get("/admin/feature-flags")
        assert response.status_code == 401
