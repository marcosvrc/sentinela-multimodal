"""Helper compartilhado pelos processadores de modalidade (item 11)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import FindingNature, ModalityQualityState, ModalityType
from app.media.models import MediaAsset
from app.orchestrator.models import AnalysisModalityState
from app.processors.models import ModalityFinding


class MediaAssetMissingError(Exception):
    """`media_asset_id` ausente ou aponta para um asset inexistente/nao aprovado."""


def load_approved_media_asset(db: Session, modality_state: AnalysisModalityState) -> MediaAsset:
    if modality_state.media_asset_id is None:
        raise MediaAssetMissingError(
            f"Estado de modalidade {modality_state.modality_type} sem media_asset_id associado."
        )
    media_asset = db.scalar(
        select(MediaAsset).where(MediaAsset.id == modality_state.media_asset_id)
    )
    if media_asset is None or media_asset.upload_state != "APPROVED":
        raise MediaAssetMissingError("Media asset ausente ou nao aprovado para processamento.")
    return media_asset


def record_finding(
    *,
    modality_state: AnalysisModalityState,
    modality_type: ModalityType,
    quality_state: ModalityQualityState,
    quality_metrics: dict,
    quality_factors: list[str],
    summary: str,
    nature: FindingNature = FindingNature.ORIGINAL_DATA,
) -> ModalityFinding:
    return ModalityFinding(
        analysis_id=modality_state.analysis_id,
        modality_state_id=modality_state.id,
        modality_type=modality_type.value,
        nature=nature.value,
        quality_state=quality_state.value,
        quality_metrics=quality_metrics,
        quality_factors=quality_factors,
        summary=summary,
    )
