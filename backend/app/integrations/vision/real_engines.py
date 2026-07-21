"""Motores reais de pose (OpenPose) e deteccao de objetos (YOLOv8) - worker
de video self-hosted.

Ambos importam suas dependencias de forma tardia (dentro do metodo, nao no
topo do modulo) para que o restante da aplicacao (API, demais workers) nao
precise instalar bibliotecas pesadas de visao computacional que so o
worker de video usa - mesma logica de isolamento por processo/IAM Role ja
aplicada na infraestrutura (cada processo tem sua propria IAM Role: API,
worker de audio, worker de video/imagem etc. nao compartilham permissoes
amplas).

- `YoloV8DetectionEngine` usa `ultralytics.YOLO` (pacote `ultralytics`,
  grupo de dependencias opcional `vision` do worker de video) com um modelo
  pre-treinado generico (`yolov8n.pt`, COCO) em CPU.
- `OpenPosePoseEngine` chama o binario oficial do OpenPose (compilado na
  imagem Docker do worker de video, nao distribuido via `pip`) via
  subprocess, com saida em JSON (`--write_json`), e parseia os keypoints do
  formato BODY_25.

**Nenhum dos dois foi exercitado neste ambiente** (sem `ultralytics`
instalado, sem o binario do OpenPose compilado, sem GPU/CPU dedicada para
rodar um modelo de verdade) - documentado explicitamente, mesmo padrao de
honestidade do restante do projeto. A orquestracao que os consome
(`OpenPoseYoloVideoAdapter`) e testada com engines FALSAS injetadas.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

_YOLO_MODEL_WEIGHTS = "yolov8n.pt"
_YOLO_CONFIDENCE_THRESHOLD = 0.4


class YoloV8DetectionEngine:
    def __init__(self, *, model_weights: str = _YOLO_MODEL_WEIGHTS) -> None:
        self._model_weights = model_weights
        self._model = None

    def _load_model(self):
        if self._model is None:
            from ultralytics import YOLO  # dependencia pesada, so no worker de video

            self._model = YOLO(self._model_weights)
        return self._model

    def detect(self, frame_jpeg: bytes) -> list[dict]:
        import numpy as np
        from PIL import Image

        model = self._load_model()
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            tmp_file.write(frame_jpeg)
            tmp_file.flush()
            image = np.array(Image.open(tmp_file.name).convert("RGB"))
            results = model.predict(image, device="cpu", verbose=False)

        detections: list[dict] = []
        for result in results:
            for box in result.boxes:
                confidence = float(box.conf[0])
                if confidence < _YOLO_CONFIDENCE_THRESHOLD:
                    continue
                label = result.names[int(box.cls[0])]
                detections.append({"label": label, "confidence": confidence})
        return detections


class OpenPosePoseEngine:
    def __init__(self, *, openpose_binary: str = "openpose.bin") -> None:
        self._openpose_binary = openpose_binary

    def estimate(self, frame_jpeg: bytes) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_dir = tmp_path / "image"
            output_dir = tmp_path / "output"
            image_dir.mkdir()
            output_dir.mkdir()
            (image_dir / "frame.jpg").write_bytes(frame_jpeg)

            subprocess.run(
                [
                    self._openpose_binary,
                    "--image_dir",
                    str(image_dir),
                    "--write_json",
                    str(output_dir),
                    "--display",
                    "0",
                    "--render_pose",
                    "0",
                    "--model_pose",
                    "BODY_25",
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )

            json_files = sorted(output_dir.glob("*.json"))
            if not json_files:
                return []
            payload = json.loads(json_files[0].read_text())

        persons: list[dict] = []
        for person in payload.get("people", []):
            keypoints = person.get("pose_keypoints_2d", [])
            # BODY_25: triplas (x, y, confianca); a confianca e o terceiro
            # valor de cada tripla.
            confidences = keypoints[2::3]
            valid_confidences = [c for c in confidences if c > 0]
            persons.append(
                {
                    "mean_confidence": (
                        sum(valid_confidences) / len(valid_confidences)
                        if valid_confidences
                        else None
                    )
                }
            )
        return persons
