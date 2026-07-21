"""Adaptador real de visao computacional: worker self-hosted OpenPose e/ou
YOLOv8 em CPU. Alternativas gerenciadas da AWS foram avaliadas e
descartadas porque o Amazon Rekognition nao oferece estimativa de pose,
requisito central desta modalidade.

Este adaptador NAO embute os modelos em si - orquestra tres colaboradores
injetados no construtor (mesmo padrao de injecao de dependencia do cliente
`boto3` falso em `AwsTranscribeAdapter`):

1. `FrameExtractor` - amostra `max_sample_frames` quadros do video (em
   producao, via `ffmpeg` instalado no container do worker).
   SEMPRE obrigatorio (sem quadros extraidos, nao ha o que analisar).
2. `PoseEngine` - estimativa de pose por quadro (em producao, OpenPose).
   OPCIONAL: `pose_engine=None` desliga a analise de pose sem afetar a
   deteccao de objetos - permite ligar YOLOv8 e OpenPose de forma
   independente via feature flags (banco, tela `/admin/feature-flags`,
   ver `app.integrations.vision.__init__`), sem exigir que o
   binario OpenPose (mais custoso de instalar/compilar) esteja disponivel
   so para testar o YOLOv8.
3. `DetectionEngine` - deteccao de objetos por quadro (em producao,
   YOLOv8 em CPU via `ultralytics`). OPCIONAL pelo mesmo motivo acima.

Pelo menos um dos dois motores (`pose_engine`/`detection_engine`) deve
estar presente - com os dois `None` a analise nao teria nenhum achado
possivel, e o adaptador falha explicitamente em vez de retornar um
resultado "completo" vazio.

Nenhum desses pacotes (ffmpeg, openpose, ultralytics) esta instalado neste
ambiente de desenvolvimento/sandbox - a orquestracao abaixo e codigo real e
e testada com colaboradores FALSOS injetados
(`tests/test_vision_adapters.py`), verificando agregacao de resultados e
tratamento de erro sem exercitar contra um video real, seguindo o mesmo
padrao de honestidade documentado no `AwsTranscribeAdapter`. Qualquer falha
de um colaborador (arquivo corrompido, modelo indisponivel, etc.) nunca
propaga cru - retorna `VisionAnalysisStatus.FAILED` com o motivo.
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.vision.base import (
    DetectionEngine,
    DetectionFrameFinding,
    FrameExtractor,
    PoseEngine,
    PoseFrameFinding,
    VideoAnalysisRequest,
    VideoAnalysisResult,
)

_POSE_MODEL_VERSION = "openpose-body25-cpu-v1"
_DETECTION_MODEL_VERSION = "yolov8n-cpu-v1"


class OpenPoseYoloVideoAdapter:
    def __init__(
        self,
        *,
        frame_extractor: FrameExtractor,
        pose_engine: PoseEngine | None,
        detection_engine: DetectionEngine | None,
    ) -> None:
        if pose_engine is None and detection_engine is None:
            raise ValueError(
                "OpenPoseYoloVideoAdapter exige ao menos um motor habilitado "
                "(pose_engine ou detection_engine) - com os dois desligados nao "
                "ha nenhum achado possivel de produzir."
            )
        self._frame_extractor = frame_extractor
        self._pose_engine = pose_engine
        self._detection_engine = detection_engine

    def analyze(self, request: VideoAnalysisRequest) -> VideoAnalysisResult:
        try:
            frames = self._frame_extractor.extract_sample_frames(
                request.video_bytes, max_frames=request.max_sample_frames
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(f"Falha ao extrair quadros do video: {exc}")

        if not frames:
            return self._failed_result("Nenhum quadro pode ser extraido do video.")

        pose_findings: list[PoseFrameFinding] = []
        detection_findings: list[DetectionFrameFinding] = []

        for frame_index, frame_jpeg in enumerate(frames):
            if self._pose_engine is not None:
                try:
                    persons = self._pose_engine.estimate(frame_jpeg)
                except Exception as exc:  # noqa: BLE001
                    return self._failed_result(
                        f"Falha na estimativa de pose no quadro {frame_index}: {exc}"
                    )

                confidences = [
                    p["mean_confidence"] for p in persons if p.get("mean_confidence") is not None
                ]
                pose_findings.append(
                    PoseFrameFinding(
                        frame_index=frame_index,
                        person_count=len(persons),
                        mean_keypoint_confidence=(
                            sum(confidences) / len(confidences) if confidences else None
                        ),
                        model_version=_POSE_MODEL_VERSION,
                    )
                )

            if self._detection_engine is not None:
                try:
                    detections = self._detection_engine.detect(frame_jpeg)
                except Exception as exc:  # noqa: BLE001
                    return self._failed_result(
                        f"Falha na deteccao de objetos no quadro {frame_index}: {exc}"
                    )

                for detection in detections:
                    detection_findings.append(
                        DetectionFrameFinding(
                            frame_index=frame_index,
                            label=str(detection["label"]),
                            confidence=float(detection["confidence"]),
                            model_version=_DETECTION_MODEL_VERSION,
                        )
                    )

        return VideoAnalysisResult(
            status=VisionAnalysisStatus.COMPLETED,
            provider="openpose_yolov8",
            frames_analyzed=len(frames),
            pose_enabled=self._pose_engine is not None,
            detection_enabled=self._detection_engine is not None,
            pose_findings=pose_findings,
            detection_findings=detection_findings,
        )

    def _failed_result(self, error: str) -> VideoAnalysisResult:
        return VideoAnalysisResult(
            status=VisionAnalysisStatus.FAILED,
            provider="openpose_yolov8",
            frames_analyzed=0,
            pose_enabled=self._pose_engine is not None,
            detection_enabled=self._detection_engine is not None,
            error=error[:500],
        )
