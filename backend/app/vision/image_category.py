"""Roteamento de imagem por categoria + area de interesse.

Imagens sao classificadas por categoria e encaminhadas ao processador
especifico apropriado - um unico modelo generico nao e adequado para
fotografia clinica, documento digitalizado e imagem radiologica ao
mesmo tempo.

Este modulo implementa um roteador REAL e determinístico baseado em
caracteristicas de cor/textura extraidas de pixels de fato (via Pillow) -
nao um stub, mas tambem nao um classificador clinico treinado. As
categorias sao distinguidas por:

- **fotografia clinica**: imagem colorida (baixo `grayscale_ratio`);
- **documento digitalizado**: quase sem cor e com histograma de
  intensidade fortemente concentrado nos extremos (preto/branco, tipico de
  texto escaneado) e poucas cores unicas;
- **imagem radiologica**: quase sem cor mas com histograma de intensidade
  mais continuo (tons de cinza distribuidos, tipico de raio-X/tomografia
  sem o padrao bimodal de um documento).

Limitacoes, disclosed explicitamente (nao escondidas):

- E um roteador por cor/textura, nao um classificador de conteudo clinico
  treinado - pode classificar erroneamente casos de fronteira (ex: uma
  fotografia em preto e branco pode ser roteada como documento ou
  radiologica).
- Nenhum modelo de reconhecimento de achado (lesao, ferida, fratura etc.)
  esta integrado - a saida e apenas a categoria, area de maior contraste
  local (como aproximacao heuristica de "area de interesse", sem
  significado clinico) e metadados de proveniencia.
- Imagens radiologicas de verdade (DICOM) nao sao o formato aceito hoje
  (`app.media.validation.ALLOWED_MIME_TYPES` so permite PNG/JPEG) - a
  categoria RADIOLOGICAL aqui cobre apenas a hipotese "imagem em tons de
  cinza com aparencia radiologica dentro de um arquivo PNG/JPEG", nao uma
  integracao DICOM/PACS real (deliberadamente fora do escopo atual).
- Categorias sem confianca suficiente (`UNSUPPORTED`) nunca recebem
  tentativa de classificacao ou diagnostico - categorias nao suportadas
  sao rejeitadas ou marcadas como inconclusivas, nunca tratadas com um
  diagnostico generico.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum

from PIL import Image

# Downsample fixo: torna a analise determinística e rapida independente da
# resolucao original, sem depender de numpy para varrer pixels em Python puro.
_ANALYSIS_SIZE = 64
_COLORLESS_CHANNEL_SPREAD = 12
_DARK_THRESHOLD = 64
_LIGHT_THRESHOLD = 192


class ImageCategory(str, Enum):
    PHOTOGRAPH = "PHOTOGRAPH"
    SCANNED_DOCUMENT = "SCANNED_DOCUMENT"
    RADIOLOGICAL = "RADIOLOGICAL"
    UNSUPPORTED = "UNSUPPORTED"


_CATEGORY_LIMITATIONS: dict[ImageCategory, list[str]] = {
    ImageCategory.PHOTOGRAPH: [
        "Roteamento heuristico por cor/textura, nao um classificador clinico treinado.",
        "Nenhum modelo de deteccao de achado (lesao, ferida etc.) esta integrado neste MVP.",
    ],
    ImageCategory.SCANNED_DOCUMENT: [
        "Roteamento heuristico; nenhum OCR ou extracao estruturada de documento esta "
        "integrado neste MVP.",
    ],
    ImageCategory.RADIOLOGICAL: [
        "Roteamento heuristico por cor/textura, nao um modelo radiologico validado.",
        "Integracao DICOM/PACS nao esta implementada - apenas PNG/JPEG sao aceitos hoje.",
    ],
    ImageCategory.UNSUPPORTED: [
        "Categoria nao determinada com confianca suficiente pelas heuristicas atuais - "
        "nenhuma tentativa de classificacao ou diagnostico foi feita para esta imagem.",
    ],
}

_CATEGORY_RECOMMENDATION = (
    "Encaminhar para revisao de profissional da especialidade correspondente - nenhuma "
    "conclusao diagnostica automatica foi gerada a partir desta imagem."
)


@dataclass(frozen=True)
class ImageCategoryClassification:
    category: ImageCategory
    method: str
    features: dict[str, float | int]
    limitations: list[str]
    recommendation: str


@dataclass(frozen=True)
class RegionOfInterest:
    """Aproximacao heuristica de "area/localizacao aproximada" da imagem:
    o quadrante com maior densidade de borda (maior variacao local de
    intensidade). Nao tem significado clinico proprio - e apenas o ponto de
    maior informacao visual da imagem, uma evidencia de baixo nivel."""

    quadrant: str
    bounding_box: dict[str, float]
    edge_density_score: float


def _open_rgb_thumbnail(image_bytes: bytes) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.convert("RGB").resize((_ANALYSIS_SIZE, _ANALYSIS_SIZE), Image.NEAREST)
    except Exception:  # noqa: BLE001 - decodificacao de arquivo hostil nunca deve propagar
        # `Exception` amplo (nao so UnidentifiedImageError/OSError/ValueError)
        # de proposito: quando o pacote opcional `ultralytics` (grupo
        # `vision`, worker de video) esta importado no MESMO processo, ele
        # aplica um monkey-patch GLOBAL em `PIL.Image.open` para tentar
        # registrar um plugin HEIF em caso de falha - e, sem `pip`
        # disponivel neste ambiente (gerenciado por `uv`), essa tentativa
        # de auto-instalacao levanta `ModuleNotFoundError` em vez da
        # excecao original do PIL para um arquivo corrompido. Esta funcao
        # e puramente defensiva (decodificar bytes nao confiaveis) e deve
        # permanecer honesta ("nao consegui decodificar" -> `None`)
        # independente de qual excecao uma biblioteca de terceiros (ou seu
        # monkey-patch) decidir levantar internamente.
        return None


def classify_image_category(image_bytes: bytes) -> ImageCategoryClassification | None:
    """Retorna `None` apenas quando a imagem nao pode ser decodificada (arquivo
    corrompido/formato inesperado) - nesse caso o chamador deve tratar como
    qualidade INVALID, nao como uma categoria."""
    thumbnail = _open_rgb_thumbnail(image_bytes)
    if thumbnail is None:
        return None

    pixel_map = thumbnail.load()
    pixels = [
        pixel_map[x, y] for y in range(_ANALYSIS_SIZE) for x in range(_ANALYSIS_SIZE)
    ]
    total = len(pixels)

    colorless_count = 0
    dark_count = 0
    light_count = 0
    unique_colors: set[tuple[int, int, int]] = set()
    for r, g, b in pixels:
        spread = max(r, g, b) - min(r, g, b)
        if spread <= _COLORLESS_CHANNEL_SPREAD:
            colorless_count += 1
        intensity = (r + g + b) / 3
        if intensity < _DARK_THRESHOLD:
            dark_count += 1
        elif intensity > _LIGHT_THRESHOLD:
            light_count += 1
        unique_colors.add((r, g, b))

    grayscale_ratio = colorless_count / total
    bimodal_intensity_ratio = (dark_count + light_count) / total
    unique_color_ratio = len(unique_colors) / total

    features: dict[str, float | int] = {
        "grayscale_ratio": round(grayscale_ratio, 4),
        "bimodal_intensity_ratio": round(bimodal_intensity_ratio, 4),
        "unique_color_ratio": round(unique_color_ratio, 4),
        "sample_size": total,
    }

    if grayscale_ratio < 0.85:
        category = ImageCategory.PHOTOGRAPH
    elif bimodal_intensity_ratio >= 0.7 and unique_color_ratio <= 0.15:
        category = ImageCategory.SCANNED_DOCUMENT
    elif bimodal_intensity_ratio < 0.7:
        category = ImageCategory.RADIOLOGICAL
    else:
        category = ImageCategory.UNSUPPORTED

    return ImageCategoryClassification(
        category=category,
        method="heuristic_color_texture_v1",
        features=features,
        limitations=_CATEGORY_LIMITATIONS[category],
        recommendation=_CATEGORY_RECOMMENDATION,
    )


def locate_region_of_interest(image_bytes: bytes) -> RegionOfInterest | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            grayscale = img.convert("L").resize((_ANALYSIS_SIZE, _ANALYSIS_SIZE), Image.NEAREST)
    except Exception:  # noqa: BLE001 - mesmo motivo de `_open_rgb_thumbnail` acima
        return None

    pixel_map = grayscale.load()
    half = _ANALYSIS_SIZE // 2
    quadrants = {
        "superior_esquerdo": (0, 0, half, half),
        "superior_direito": (half, 0, _ANALYSIS_SIZE, half),
        "inferior_esquerdo": (0, half, half, _ANALYSIS_SIZE),
        "inferior_direito": (half, half, _ANALYSIS_SIZE, _ANALYSIS_SIZE),
    }

    scores: dict[str, int] = {}
    for name, (x0, y0, x1, y1) in quadrants.items():
        score = 0
        for y in range(y0, y1 - 1):
            for x in range(x0, x1 - 1):
                current = pixel_map[x, y]
                score += abs(current - pixel_map[x + 1, y])
                score += abs(current - pixel_map[x, y + 1])
        scores[name] = score

    best_quadrant = max(scores, key=lambda name: scores[name])
    x0, y0, x1, y1 = quadrants[best_quadrant]
    total_score = sum(scores.values()) or 1

    return RegionOfInterest(
        quadrant=best_quadrant,
        bounding_box={
            "x0": round(x0 / _ANALYSIS_SIZE, 3),
            "y0": round(y0 / _ANALYSIS_SIZE, 3),
            "x1": round(x1 / _ANALYSIS_SIZE, 3),
            "y1": round(y1 / _ANALYSIS_SIZE, 3),
        },
        edge_density_score=round(scores[best_quadrant] / total_score, 4),
    )
