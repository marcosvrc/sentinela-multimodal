"""Leitura/atualizacao da linha singleton de feature flags (tela
`/admin/feature-flags`, acesso restrito a administrador).

Mesma disciplina de auditoria do restante do sistema: toda atualizacao
grava um evento categoria ADMINISTRATION com o antes/depois dos campos
alterados (nunca um "flag mudou" generico sem rastro do que mudou).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.core.enums import AuditCategory, AuditResult
from app.feature_flags.models import FeatureFlags

_SINGLETON_ID = 1


def get_feature_flags(db: Session) -> FeatureFlags:
    """A linha e semeada pela migration 0017 - `scalar_one()` falha alto
    (em vez de criar uma linha por baixo dos panos) se ela nao existir,
    mesmo padrao de `app.audit.service.record_event` para
    `AuditChainState`."""
    return db.execute(
        select(FeatureFlags).where(FeatureFlags.id == _SINGLETON_ID)
    ).scalar_one()


_EDITABLE_FIELDS = (
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
    "auto_clinical_support_enabled",
)


def update_feature_flags(
    db: Session,
    *,
    actor: str,
    actor_role: str | None,
    **changes: object,
) -> FeatureFlags:
    """Atualiza somente os campos presentes em `changes` (schema de update
    parcial - ver `app.api.schemas.feature_flags.FeatureFlagsUpdate`).
    Rejeita qualquer chave fora de `_EDITABLE_FIELDS` para nunca permitir
    que um campo novo passe a ser gravavel sem revisao explicita deste
    modulo."""
    unknown = set(changes) - set(_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Campos desconhecidos para feature flags: {sorted(unknown)}")

    flags = get_feature_flags(db)
    before = {field: getattr(flags, field) for field in changes}

    for field, value in changes.items():
        if value is not None:
            setattr(flags, field, value)

    flags.updated_by = actor
    db.flush()

    after = {field: getattr(flags, field) for field in changes}

    audit_service.record_event(
        db,
        actor=actor,
        actor_role=actor_role,
        category=AuditCategory.ADMINISTRATION,
        action="FEATURE_FLAGS_UPDATED",
        resource_type="feature_flags",
        resource_id=str(_SINGLETON_ID),
        result=AuditResult.SUCCESS,
        event_metadata={"before": before, "after": after},
    )
    db.commit()
    db.refresh(flags)
    return flags
