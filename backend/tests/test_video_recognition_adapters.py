"""Testes dos adaptadores de reconhecimento de video (Amazon Rekognition
Video, ADR 0016 "atualizacao").

O adaptador LOCAL e testado diretamente (sem rede). O adaptador AWS real
(`AwsRekognitionVideoAdapter`) e testado com um cliente `boto3` FALSO
injetado no construtor (mesmo padrao de injecao de dependencia usado em
`test_transcription_adapters.py`).
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.video_recognition.aws_rekognition_video import (
    AwsRekognitionVideoAdapter,
)
from app.integrations.video_recognition.base import VideoRecognitionRequest
from app.integrations.video_recognition.local import LocalUnavailableVideoRecognitionAdapter

_REQUEST = VideoRecognitionRequest(
    storage_key="institution-1/analysis-1/video.mp4",
    job_name="analysis-1-video-rekognition",
)


def test_local_adapter_always_returns_unavailable_never_fake_labels() -> None:
    adapter = LocalUnavailableVideoRecognitionAdapter()
    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.UNAVAILABLE
    assert result.labels == []
    assert result.provider == "local"
    assert result.error is not None


class _FakeRekognitionVideoClient:
    def __init__(self, *, final_status: str = "SUCCEEDED", labels: list[dict] | None = None):
        self.final_status = final_status
        self.labels = labels if labels is not None else [
            {"Label": {"Name": "Person", "Confidence": 88.0}, "Timestamp": 1200},
            {"Label": {"Name": "Bed", "Confidence": 71.4}, "Timestamp": 3400},
        ]
        self.start_calls: list[dict] = []
        self.poll_count = 0

    def start_label_detection(self, **kwargs):
        self.start_calls.append(kwargs)
        return {"JobId": "job-123"}

    def get_label_detection(self, **kwargs):
        self.poll_count += 1
        return {"JobStatus": self.final_status, "Labels": self.labels}


def test_aws_adapter_starts_job_with_approved_prefix() -> None:
    client = _FakeRekognitionVideoClient()
    adapter = AwsRekognitionVideoAdapter(
        rekognition_client=client, media_bucket="sentinelhealth-media", poll_interval_seconds=0
    )

    adapter.detect_labels(_REQUEST)

    assert len(client.start_calls) == 1
    call = client.start_calls[0]
    assert call["Video"]["S3Object"]["Bucket"] == "sentinelhealth-media"
    assert call["Video"]["S3Object"]["Name"] == "approved/institution-1/analysis-1/video.mp4"


def test_aws_adapter_returns_completed_result_with_parsed_labels_and_timestamps() -> None:
    adapter = AwsRekognitionVideoAdapter(
        rekognition_client=_FakeRekognitionVideoClient(),
        media_bucket="bucket",
        poll_interval_seconds=0,
    )

    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.provider == "aws_rekognition_video"
    assert len(result.labels) == 2
    assert result.labels[0].label == "Person"
    assert result.labels[0].timestamp_millis == 1200
    assert result.labels[1].label == "Bed"


def test_aws_adapter_returns_failed_result_when_job_fails() -> None:
    adapter = AwsRekognitionVideoAdapter(
        rekognition_client=_FakeRekognitionVideoClient(final_status="FAILED"),
        media_bucket="bucket",
        poll_interval_seconds=0,
    )

    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.FAILED
    assert result.labels == []
    assert result.error is not None


def test_aws_adapter_never_raises_when_client_errors() -> None:
    class _RaisingClient:
        def start_label_detection(self, **kwargs):
            raise RuntimeError("credenciais invalidas")

    adapter = AwsRekognitionVideoAdapter(
        rekognition_client=_RaisingClient(), media_bucket="bucket", poll_interval_seconds=0
    )

    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.FAILED
    assert "credenciais invalidas" in result.error
