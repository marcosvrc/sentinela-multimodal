"""Testes de `app.vision.image_category` (secao 4.4 do escopo).

Gera imagens sinteticas reais (via Pillow) com propriedades conhecidas de
cor/textura e verifica que o roteador heuristico as classifica de forma
consistente com a categoria pretendida - nao testa contra imagens clinicas
reais (nao existem no MVP), mas exercita o algoritmo de ponta a ponta sobre
bytes de imagem de verdade, nao mocks.
"""

from __future__ import annotations

import io

from PIL import Image

from app.vision.image_category import (
    ImageCategory,
    classify_image_category,
    locate_region_of_interest,
)


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _colorful_photograph_bytes() -> bytes:
    """Simula uma fotografia clinica: gradiente colorido (pele/ambiente)."""
    image = Image.new("RGB", (200, 200))
    pixels = image.load()
    for y in range(200):
        for x in range(200):
            pixels[x, y] = (min(255, x + 30), min(255, y + 60), 120)
    return _png_bytes(image)


def _scanned_document_bytes() -> bytes:
    """Simula um documento escaneado: blocos solidos preto/branco (texto)."""
    image = Image.new("RGB", (200, 200), color=(255, 255, 255))
    pixels = image.load()
    # "Linhas de texto": faixas horizontais totalmente pretas.
    for y in list(range(20, 30)) + list(range(60, 70)) + list(range(100, 110)):
        for x in range(20, 180):
            pixels[x, y] = (0, 0, 0)
    return _png_bytes(image)


def _radiological_bytes() -> bytes:
    """Simula uma imagem radiologica: gradiente continuo de cinza (sem
    concentracao nos extremos, ao contrario do documento)."""
    image = Image.new("RGB", (200, 200))
    pixels = image.load()
    for y in range(200):
        for x in range(200):
            gray = int((x / 200) * 255)
            pixels[x, y] = (gray, gray, gray)
    return _png_bytes(image)


def _corrupted_bytes() -> bytes:
    return b"not-a-real-image-just-some-bytes"


def test_photograph_is_classified_as_photograph() -> None:
    result = classify_image_category(_colorful_photograph_bytes())
    assert result is not None
    assert result.category is ImageCategory.PHOTOGRAPH
    assert result.method == "heuristic_color_texture_v1"
    assert result.features["grayscale_ratio"] < 0.85


def test_scanned_document_is_classified_as_scanned_document() -> None:
    result = classify_image_category(_scanned_document_bytes())
    assert result is not None
    assert result.category is ImageCategory.SCANNED_DOCUMENT
    assert result.features["bimodal_intensity_ratio"] >= 0.7


def test_radiological_gradient_is_classified_as_radiological() -> None:
    result = classify_image_category(_radiological_bytes())
    assert result is not None
    assert result.category is ImageCategory.RADIOLOGICAL
    assert result.features["grayscale_ratio"] >= 0.85
    assert result.features["bimodal_intensity_ratio"] < 0.7


def test_undecodable_bytes_return_none_not_a_fake_category() -> None:
    assert classify_image_category(_corrupted_bytes()) is None


def test_every_category_only_recommends_specialist_review_never_a_diagnosis() -> None:
    """Toda categoria so recomenda revisao especializada, nunca uma
    conclusao diagnostica (requisito do escopo)."""
    expected = (
        "Encaminhar para revisao de profissional da especialidade correspondente - "
        "nenhuma conclusao diagnostica automatica foi gerada a partir desta imagem."
    )
    for image_bytes in (
        _colorful_photograph_bytes(),
        _scanned_document_bytes(),
        _radiological_bytes(),
    ):
        result = classify_image_category(image_bytes)
        assert result is not None
        assert result.recommendation == expected


def test_each_category_discloses_its_own_limitations() -> None:
    document_result = classify_image_category(_scanned_document_bytes())
    radiological_result = classify_image_category(_radiological_bytes())
    assert document_result is not None
    assert radiological_result is not None
    assert document_result.limitations != radiological_result.limitations
    assert len(document_result.limitations) > 0
    assert len(radiological_result.limitations) > 0


def test_region_of_interest_finds_the_high_contrast_quadrant() -> None:
    """Um quadrado de alto contraste isolado em um quadrante deve ser
    identificado como a area de maior densidade de borda."""
    image = Image.new("RGB", (200, 200), color=(128, 128, 128))
    pixels = image.load()
    # Padrao de tabuleiro de xadrez apenas no quadrante inferior-direito
    # (x,y >= 100) - maxima variacao pixel-a-pixel isolada ali.
    for y in range(100, 200):
        for x in range(100, 200):
            value = 0 if (x + y) % 2 == 0 else 255
            pixels[x, y] = (value, value, value)

    roi = locate_region_of_interest(_png_bytes(image))
    assert roi is not None
    assert roi.quadrant == "inferior_direito"
    assert roi.edge_density_score > 0.5


def test_region_of_interest_returns_none_for_undecodable_bytes() -> None:
    assert locate_region_of_interest(_corrupted_bytes()) is None
