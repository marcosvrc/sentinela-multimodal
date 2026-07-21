"""Contrato do adaptador de reconhecimento de imagem (Azure AI Vision
Image Analysis - enriquecimento OPCIONAL do processamento de imagem).

Mesmo padrao arquitetural dos demais adaptadores (`app.integrations.llm`,
`app.integrations.transcription`, `app.integrations.vision`): o dominio
(`app.processors.image`) depende apenas deste Protocol, nunca do cliente
HTTP diretamente. `ImageRecognitionRequest` carrega os bytes da imagem
(`image_bytes`) - a Image Analysis do Azure recebe a imagem direto no
corpo da requisicao, sem exigir um storage intermediario. O processador
(`app.processors.image`) ja le os bytes do storage aprovado para extrair
dimensoes/categoria, entao reaproveita-los aqui nao adiciona nenhuma
leitura extra.

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
    """`storage_key` identifica o objeto de imagem ja aprovado (usado em
    logs/auditoria); `image_bytes` carrega o conteudo enviado diretamente
    no corpo da requisicao a Image Analysis do Azure."""

    storage_key: str
    min_confidence: float = 55.0
    image_bytes: bytes | None = None


@dataclass(frozen=True)
class ImageLabelFinding:
    """Um rotulo generico devolvido pelo servico de visao, com a
    confianca reportada - nunca reinterpretado como achado clinico."""

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
    testes) e `AzureVisionAdapter` (real)."""

    def detect_labels(self, request: ImageRecognitionRequest) -> ImageRecognitionResult: ...
