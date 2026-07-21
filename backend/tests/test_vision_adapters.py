"""Testes dos adaptadores de visao computacional (secao 4.1/6.2 do escopo;
ADR 0016).

O adaptador LOCAL e testado diretamente (sem dependencias externas). O
adaptador real (`OpenPoseYoloVideoAdapter`) e testado com colaboradores
FALSOS injetados (`FrameExtractor`, `PoseEngine`, `DetectionEngine`) - mesmo
padrao de injecao de dependencia usado em `test_transcription_adapters.py`
com o cliente `boto3` falso - verifica agregacao de resultados e
tratamento de erro sem exercitar `ffmpeg`/OpenPose/YOLOv8 reais, que nao
estao disponiveis neste sandbox.
"""

from __future__ import annotations

import pytest

from app.core.enums import VisionAnalysisStatus
from app.integrations.vision.base import VideoAnalysisRequest
from app.integrations.vision.local import LocalUnavailableVisionAdapter
from app.integrations.vision.openpose_yolo import OpenPoseYoloVideoAdapter

_REQUEST = VideoAnalysisRequest(
    storage_key="institution-1/analysis-1/video.mp4",
    media_format="mp4",
    max_sample_frames=4,
    video_bytes=b"fake-mp4-bytes",
)


def test_local_adapter_always_returns_unavailable_never_fake_findings() -> None:
    adapter = LocalUnavailableVisionAdapter()
    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.UNAVAILABLE
    assert result.frames_analyzed == 0
    assert result.pose_findings == []
    assert result.detection_findings == []
    assert result.error is not None


class _FakeFrameExtractor:
    def __init__(self, *, frames: list[bytes] | None = None):
        self.frames = frames if frames is not None else [b"frame-0", b"frame-1"]
        self.calls: list[dict] = []

    def extract_sample_frames(self, video_bytes: bytes, *, max_frames: int) -> list[bytes]:
        self.calls.append({"video_bytes": video_bytes, "max_frames": max_frames})
        return self.frames[:max_frames]


class _FakePoseEngine:
    def __init__(self, *, persons_per_frame: list[list[dict]] | None = None):
        # Por padrao, uma pessoa detectada por quadro com confianca fixa.
        self.persons_per_frame = persons_per_frame
        self.calls: list[bytes] = []

    def estimate(self, frame_jpeg: bytes) -> list[dict]:
        self.calls.append(frame_jpeg)
        if self.persons_per_frame is not None:
            return self.persons_per_frame[len(self.calls) - 1]
        return [{"mean_confidence": 0.8}]


class _FakeDetectionEngine:
    def __init__(self, *, detections_per_frame: list[list[dict]] | None = None):
        self.detections_per_frame = detections_per_frame
        self.calls: list[bytes] = []

    def detect(self, frame_jpeg: bytes) -> list[dict]:
        self.calls.append(frame_jpeg)
        if self.detections_per_frame is not None:
            return self.detections_per_frame[len(self.calls) - 1]
        return [{"label": "leito", "confidence": 0.9}]


def test_real_adapter_extracts_frames_and_aggregates_pose_and_detection() -> None:
    frame_extractor = _FakeFrameExtractor()
    pose_engine = _FakePoseEngine()
    detection_engine = _FakeDetectionEngine()
    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=frame_extractor,
        pose_engine=pose_engine,
        detection_engine=detection_engine,
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.provider == "openpose_yolov8"
    assert result.frames_analyzed == 2
    assert len(result.pose_findings) == 2
    assert all(p.person_count == 1 for p in result.pose_findings)
    assert all(p.mean_keypoint_confidence == 0.8 for p in result.pose_findings)
    assert len(result.detection_findings) == 2
    assert all(d.label == "leito" for d in result.detection_findings)

    # `max_sample_frames` da requisicao foi propagado ao extrator.
    assert frame_extractor.calls[0]["max_frames"] == 4


def test_real_adapter_returns_failed_when_no_frames_extracted() -> None:
    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=_FakeFrameExtractor(frames=[]),
        pose_engine=_FakePoseEngine(),
        detection_engine=_FakeDetectionEngine(),
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.FAILED
    assert result.frames_analyzed == 0
    assert result.error is not None


def test_real_adapter_never_raises_when_pose_engine_errors() -> None:
    class _RaisingPoseEngine:
        def estimate(self, frame_jpeg: bytes) -> list[dict]:
            raise RuntimeError("modelo de pose indisponivel")

    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=_FakeFrameExtractor(),
        pose_engine=_RaisingPoseEngine(),
        detection_engine=_FakeDetectionEngine(),
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.FAILED
    assert "modelo de pose indisponivel" in result.error


def test_real_adapter_aggregates_zero_persons_across_frames() -> None:
    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=_FakeFrameExtractor(),
        pose_engine=_FakePoseEngine(persons_per_frame=[[], []]),
        detection_engine=_FakeDetectionEngine(detections_per_frame=[[], []]),
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert all(p.person_count == 0 for p in result.pose_findings)
    assert all(p.mean_keypoint_confidence is None for p in result.pose_findings)
    assert result.detection_findings == []


def test_adapter_requires_at_least_one_engine_enabled() -> None:
    """Os dois motores desligados (feature flags vision_detection_enabled/
    vision_pose_enabled ambas false) nao produz nenhum achado possivel - a
    fabrica (app.integrations.vision) ja falha antes de chegar aqui, mas o
    adaptador tambem se protege contra ser instanciado diretamente dessa
    forma."""
    with pytest.raises(ValueError, match="ao menos um motor habilitado"):
        OpenPoseYoloVideoAdapter(
            frame_extractor=_FakeFrameExtractor(),
            pose_engine=None,
            detection_engine=None,
        )


def test_adapter_with_only_detection_engine_never_calls_pose_engine() -> None:
    """vision_pose_enabled=false, vision_detection_enabled=true - permite
    considerar YOLOv8 isoladamente sem exigir o binario OpenPose."""
    detection_engine = _FakeDetectionEngine()
    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=_FakeFrameExtractor(),
        pose_engine=None,
        detection_engine=detection_engine,
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.pose_enabled is False
    assert result.detection_enabled is True
    assert result.pose_findings == []
    assert len(result.detection_findings) == 2
    assert len(detection_engine.calls) == 2


def test_adapter_with_only_pose_engine_never_calls_detection_engine() -> None:
    """vision_detection_enabled=false, vision_pose_enabled=true - permite
    considerar OpenPose isoladamente, sem YOLOv8."""
    pose_engine = _FakePoseEngine()
    adapter = OpenPoseYoloVideoAdapter(
        frame_extractor=_FakeFrameExtractor(),
        pose_engine=pose_engine,
        detection_engine=None,
    )

    result = adapter.analyze(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.pose_enabled is True
    assert result.detection_enabled is False
    assert result.detection_findings == []
    assert len(result.pose_findings) == 2
    assert len(pose_engine.calls) == 2
