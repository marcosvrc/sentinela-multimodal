"""Selecao do adaptador de reconhecimento de video por feature flag (mesmo
padrao de `app.integrations.image_recognition`/`app.integrations.vision` -
decisao vem da linha singleton `app.feature_flags`, banco, mutavel em
runtime, nunca de `Settings`/`.env`). Por isso esta fabrica exige
`db: Session` e nunca usa `@lru_cache`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.feature_flags.service import get_feature_flags
from app.integrations.video_recognition.base import VideoRecognitionAdapter
from app.integrations.video_recognition.local import LocalUnavailableVideoRecognitionAdapter


def get_video_recognition_adapter(db: Session) -> VideoRecognitionAdapter:
    flags = get_feature_flags(db)

    if not flags.vision_rekognition_video_enabled:
        return LocalUnavailableVideoRecognitionAdapter()

    settings = get_settings()
    if not settings.s3_media_bucket:
        raise RuntimeError(
            "Feature flag vision_rekognition_video_enabled exige S3_MEDIA_BUCKET "
            "configurado no ambiente (o mesmo bucket usado pelo armazenamento de midia)."
        )

    import boto3

    from app.integrations.video_recognition.aws_rekognition_video import (
        AwsRekognitionVideoAdapter,
    )

    return AwsRekognitionVideoAdapter(
        rekognition_client=boto3.client("rekognition", region_name=settings.aws_region),
        media_bucket=settings.s3_media_bucket,
    )
