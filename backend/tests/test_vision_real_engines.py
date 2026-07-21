"""Teste de integracao do motor real YOLOv8 (`app.integrations.vision.
real_engines.YoloV8DetectionEngine`) - complementa `tests/test_vision_
adapters.py` (que testa a ORQUESTRACAO `OpenPoseYoloVideoAdapter` com
engines FALSOS injetados) validando que o motor REAL de fato funciona
quando o grupo opcional `vision` (`ultralytics`) esta instalado.

Pulado automaticamente quando `ultralytics` nao esta instalado neste
ambiente (mesmo padrao de skip por dependencia ausente usado no restante
do projeto) - roda apenas quando `uv sync --group vision` foi executado.
`OpenPosePoseEngine` NAO e testado aqui: o binario do OpenPose e compilado
fora do pip (imagem Docker do worker de video), sem equivalente instalavel
localmente.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "ultralytics", reason="grupo opcional 'vision' nao instalado (uv sync --group vision)"
)

from ultralytics.utils import ASSETS  # noqa: E402

from app.integrations.vision.real_engines import YoloV8DetectionEngine  # noqa: E402


def test_yolov8_detects_known_objects_in_bundled_sample_image() -> None:
    """`bus.jpg` e uma imagem de amostra distribuida com o proprio pacote
    `ultralytics` (nao um arquivo do repositorio) - contem um onibus e
    varias pessoas, um caso de teste estavel e conhecido pela comunidade
    para validar que a inferencia YOLOv8 esta funcionando de ponta a
    ponta (download do modelo pre-treinado + forward pass real em CPU)."""
    engine = YoloV8DetectionEngine()
    image_bytes = (ASSETS / "bus.jpg").read_bytes()

    detections = engine.detect(image_bytes)

    labels = {d["label"] for d in detections}
    assert "person" in labels
    assert "bus" in labels
    assert all(0.0 <= d["confidence"] <= 1.0 for d in detections)


def test_yolov8_returns_empty_list_for_random_noise_image() -> None:
    """Imagem sem nenhum objeto reconhecivel (ruido aleatorio) nao deve
    gerar deteccoes fabricadas - o motor real deve retornar lista vazia
    (ou apenas deteccoes abaixo do limiar de confianca, ja filtradas)."""
    from io import BytesIO

    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed=42)
    noise = rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
    buffer = BytesIO()
    Image.fromarray(noise).save(buffer, format="JPEG")

    engine = YoloV8DetectionEngine()
    detections = engine.detect(buffer.getvalue())

    assert detections == []
