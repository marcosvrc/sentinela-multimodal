"""Extracao real de quadros via `ffmpeg` (worker de video self-hosted).

Nao ha decodificador de video puro-Python neste projeto (H.264 exige uma
biblioteca nativa) - o binario `ffmpeg` e instalado na imagem Docker do
worker de video (analogo ao worker Docker que executa OpenPose/YOLO em
CPU sobre amostras pequenas), nunca no processo da API nem nos demais
workers.

Amostragem uniforme: `max_frames` quadros igualmente espacados ao longo do
video (nao os primeiros `N` quadros), usando o filtro `fps` do proprio
`ffmpeg` calculado a partir da duracao real (`parse_isobmff_duration_seconds`,
ja usado pelo processador de video para a avaliacao de qualidade estrutural).

**Nao exercitado contra um binario `ffmpeg` real neste ambiente** (nao
instalado no sandbox de desenvolvimento) - a orquestracao que consome esta
classe (`OpenPoseYoloVideoAdapter`) e testada com uma implementacao FALSA
de `FrameExtractor` injetada (`tests/test_vision_adapters.py`), seguindo o
mesmo padrao de honestidade dos demais adaptadores reais do projeto.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.processors.media_analysis import parse_isobmff_duration_seconds


class FfmpegFrameExtractor:
    def __init__(self, *, ffmpeg_binary: str = "ffmpeg") -> None:
        self._ffmpeg_binary = ffmpeg_binary

    def extract_sample_frames(self, video_bytes: bytes, *, max_frames: int) -> list[bytes]:
        if max_frames <= 0:
            return []

        duration_seconds = parse_isobmff_duration_seconds(video_bytes) or 0.0
        # fps do filtro = quantos quadros por segundo amostrar para obter
        # aproximadamente `max_frames` quadros distribuidos ao longo do
        # video inteiro (nunca so o inicio).
        fps = max_frames / duration_seconds if duration_seconds > 1.0 else 1.0

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.mp4"
            input_path.write_bytes(video_bytes)
            output_pattern = tmp_path / "frame_%03d.jpg"

            subprocess.run(
                [
                    self._ffmpeg_binary,
                    "-y",
                    "-i",
                    str(input_path),
                    "-vf",
                    f"fps={fps}",
                    "-frames:v",
                    str(max_frames),
                    "-qscale:v",
                    "2",
                    str(output_pattern),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )

            return [
                path.read_bytes() for path in sorted(tmp_path.glob("frame_*.jpg"))
            ][:max_frames]
