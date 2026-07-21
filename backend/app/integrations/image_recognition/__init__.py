"""Selecao do adaptador de reconhecimento de imagem por feature flag (mesmo
padrao de `app.integrations.vision` - a decisao de ligar/desligar vem da
linha singleton `app.feature_flags`, banco, mutavel em runtime via tela
`/admin/feature-flags`, nunca de `Settings`/`.env`). Por isso esta fabrica
exige `db: Session` e nunca usa `@lru_cache`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ImageRecognitionProvider
from app.feature_flags.service import get_feature_flags
from app.integrations.image_recognition.base import ImageRecognitionAdapter
from app.integrations.image_recognition.local import LocalUnavailableImageRecognitionAdapter


def get_image_recognition_adapter(db: Session) -> ImageRecognitionAdapter:
    flags = get_feature_flags(db)

    if not flags.image_recognition_enabled:
        return LocalUnavailableImageRecognitionAdapter()

    settings = get_settings()
    provider = ImageRecognitionProvider(flags.image_recognition_provider)

    if provider is ImageRecognitionProvider.AWS_REKOGNITION:
        if not settings.s3_media_bucket:
            raise RuntimeError(
                "Feature flag image_recognition_enabled=AWS_REKOGNITION exige "
                "S3_MEDIA_BUCKET configurado no ambiente (o mesmo bucket usado pelo "
                "armazenamento de midia)."
            )

        import boto3

        from app.integrations.image_recognition.aws_rekognition import AwsRekognitionImageAdapter

        return AwsRekognitionImageAdapter(
            rekognition_client=boto3.client("rekognition", region_name=settings.aws_region),
            media_bucket=settings.s3_media_bucket,
        )

    if provider is ImageRecognitionProvider.AZURE_VISION:
        if not settings.azure_vision_key or not settings.azure_vision_endpoint:
            raise RuntimeError(
                "Feature flag image_recognition_provider=AZURE_VISION exige "
                "AZURE_VISION_KEY e AZURE_VISION_ENDPOINT configurados."
            )

        import httpx

        from app.integrations.image_recognition.azure_vision import AzureVisionAdapter

        return AzureVisionAdapter(
            http_client=httpx.Client(timeout=30.0),  # type: ignore[arg-type]
            subscription_key=settings.azure_vision_key,
            endpoint=settings.azure_vision_endpoint,
        )

    raise RuntimeError(f"Provedor de reconhecimento de imagem desconhecido: {provider}")
