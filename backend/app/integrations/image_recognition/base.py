"""Contrato do adaptador de reconhecimento de imagem (Amazon Rekognition
Image - enriquecimento OPCIONAL do processamento de imagem).

Mesmo padrao arquitetural dos demais adaptadores (`app.integrations.llm`,
`app.integrations.transcription`, `app.integrations.vision`): o dominio
(`app.processors.image`) depende apenas deste Protocol, nunca de `boto3`
diretamente. `ImageRecognitionRequest` carrega apenas a referencia ao
objeto ja aprovado no S3 (nunca bytes inline) - `DetectLabels` aceita uma
referencia `S3Object` direta, entao nem o worker precisa reenviar os
bytes que ja leu do storage (diferente do adaptador de video, que chama um
worker self-hosted no mesmo processo).

Este adaptador NUNCA substitui a heuristica de categoria/regiao de
interesse existente (`app.vision.image_category`) - apenas adiciona
rotulos genericos (ex.: "X-Ray", "Person", "Document") como achado
complementar, sempre como enriquecimento opcional, nunca como
substituicao da classificacao principal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import VisionAnalysisStatus


@dataclass(frozen=True)
class ImageRecognitionRequest:
    """Referencia ao objeto de imagem ja aprovado (`storage_key`, usado
    pelo adaptador AWS que referencia o objeto direto no S3) mais,
    opcionalmente, os bytes (`image_bytes`, usado apenas pelo adaptador
    Azure - Image Analysis recebe a imagem direto no corpo da
    requisicao). O processador (`app.processors.image`) ja le os bytes do
    storage aprovado para extrair dimensoes/categoria, entao reaproveita-
    los aqui nao adiciona nenhuma leitura extra."""

    storage_key: str
    min_confidence: float = 55.0
    image_bytes: bytes | None = None


@dataclass(frozen=True)
class ImageLabelFinding:
    """Um rotulo generico devolvido pelo Rekognition, com a confianca
    reportada pelo servico - nunca reinterpretado como achado clinico."""

    label: str
    confidence: float


@dataclass(frozen=True)
class ImageRecognitionResult:
    status: VisionAnalysisStatus
    provider: str
    labels: list[ImageLabelFinding] = field(default_factory=list)
    error: str | None = None


class ImageRecognitionAdapter(Protocol):
    """Implementado por `LocalUnavailableImageRecognitionAdapter` (dev/
    testes) e `AwsRekognitionImageAdapter` (real)."""

    def detect_labels(self, request: ImageRecognitionRequest) -> ImageRecognitionResult: ...
