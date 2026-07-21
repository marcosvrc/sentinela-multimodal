"""Testes do servico de feature flags (`app.feature_flags.service`) - tela
`/admin/feature-flags`.

Precisa de Postgres real (a linha singleton e semeada pela migration
0017); pulado automaticamente quando indisponivel neste sandbox (roda no
CI). `update_feature_flags` faz `db.commit()` internamente (mesma
necessidade de visibilidade imediata de qualquer flag ligada/desligada,
sem depender de uma transacao aberta) - por isso os testes que MUTAM a
linha singleton restauram o estado original explicitamente no teardown,
em vez de confiar em `rollback()` (que nao desfaz o que ja foi commitado).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.audit.models import AuditEvent
from app.core.db import SessionLocal
from app.feature_flags.models import FeatureFlags
from app.feature_flags.service import (
    _EDITABLE_FIELDS,
    get_feature_flags,
    update_feature_flags,
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
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def restore_flags(session):
    """Guarda o estado atual da linha singleton e restaura no teardown -
    necessario porque `update_feature_flags` commita direto (ver docstring
    do modulo)."""
    original = {field: getattr(get_feature_flags(session), field) for field in _EDITABLE_FIELDS}
    yield
    db = SessionLocal()
    try:
        update_feature_flags(db, actor="test-teardown", actor_role=None, **original)
    finally:
        db.close()


def test_get_feature_flags_returns_the_singleton_row(session) -> None:
    flags = get_feature_flags(session)
    assert flags.id == 1
    # Defaults semeados pela migration 0017 - seguro por padrao (mesma
    # convencao de LLM_PROVIDER=LOCAL/VISION_PROVIDER=LOCAL em .env).
    assert flags.llm_provider_enabled is False
    assert flags.modality_audio_enabled is True
    assert flags.modality_video_enabled is True
    assert flags.modality_image_enabled is True
    assert flags.vision_detection_enabled is False
    assert flags.vision_pose_enabled is False


def test_update_feature_flags_changes_only_provided_fields(session, restore_flags) -> None:
    before = get_feature_flags(session)
    original_audio = before.modality_audio_enabled

    updated = update_feature_flags(
        session,
        actor="admin-test",
        actor_role="ADMINISTRADOR_TECNICO",
        llm_provider_enabled=True,
        llm_provider="OPENAI",
    )

    assert updated.llm_provider_enabled is True
    assert updated.llm_provider == "OPENAI"
    # Campo nao enviado no update permanece inalterado.
    assert updated.modality_audio_enabled == original_audio
    assert updated.updated_by == "admin-test"


def test_update_feature_flags_rejects_unknown_field(session) -> None:
    with pytest.raises(ValueError, match="Campos desconhecidos"):
        update_feature_flags(
            session,
            actor="admin-test",
            actor_role="ADMINISTRADOR_TECNICO",
            not_a_real_field=True,
        )


def test_update_feature_flags_records_audit_event_with_before_after(
    session, restore_flags
) -> None:
    update_feature_flags(
        session,
        actor="admin-audit-test",
        actor_role="ADMINISTRADOR_CLINICO",
        modality_video_enabled=False,
    )

    event = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.action == "FEATURE_FLAGS_UPDATED", AuditEvent.actor == "admin-audit-test")
        .order_by(AuditEvent.sequence.desc())
    )
    assert event is not None
    assert event.event_metadata["before"]["modality_video_enabled"] is True
    assert event.event_metadata["after"]["modality_video_enabled"] is False


def test_editable_fields_match_model_columns() -> None:
    """Trava de seguranca: `_EDITABLE_FIELDS` (allowlist de campos
    gravaveis) nunca deve divergir silenciosamente das colunas reais do
    modelo - qualquer coluna nova exige atualizar esta lista de proposito."""
    model_fields = {
        column.name
        for column in FeatureFlags.__table__.columns
        if column.name not in ("id", "updated_at", "updated_by")
    }
    assert set(_EDITABLE_FIELDS) == model_fields
