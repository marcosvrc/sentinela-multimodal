"""Teste de integracao do processador VIDEO real (item 11 + secao 4.1).

Mesma estrategia de `tests/test_processors_audio.py`: sobe um MP4 (ISO
BMFF) minimo real pelo fluxo completo de upload/aprovacao e chama
`process_video_modality` sobre o `MediaAsset` resultante. Com
`VISION_PROVIDER` no padrao (LOCAL, sem override neste ambiente), a
analise de visao computacional retorna honestamente UNAVAILABLE (sem
motor de pose/deteccao) - o teste verifica que os achados de qualidade e
de visao (status UNAVAILABLE) sao gravados corretamente, sem fabricar
pose/deteccao.

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import hashlib
import struct
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.media.models import MediaAsset
from app.orchestrator.models import AnalysisModalityState
from app.processors.models import ModalityFinding
from app.processors.video import process_video_modality


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        session.close()


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _build_box(box_type: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + box_type + body


def _minimal_mp4_bytes(*, timescale: int = 1000, duration: int = 6000) -> bytes:
    mvhd_body = (
        bytes([0])
        + bytes(3)  # version + flags
        + struct.pack(">II", 0, 0)  # creation/modification time
        + struct.pack(">II", timescale, duration)
        + bytes(80)  # resto do mvhd, irrelevante para o parser
    )
    mvhd = _build_box(b"mvhd", mvhd_body)
    moov = _build_box(b"moov", mvhd)
    ftyp = _build_box(b"ftyp", b"isom" + struct.pack(">I", 0) + b"isomiso2avc1mp41")
    return ftyp + moov


def _create_institution() -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": "Instituicao Video"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID) -> str:
    session = SessionLocal()
    try:
        external_subject = f"video-test-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name="Medico Teste Video",
            role=UserRole.MEDICO.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


class TestVideoProcessorWithRealUpload:
    def test_real_mp4_produces_quality_and_vision_unavailable_findings(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id)}

        patient_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": f"MRN-VID-{uuid.uuid4()}",
                "full_name": "Paciente Video",
                "birth_date": "1980-01-15",
                "registered_sex": "masculino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        content = _minimal_mp4_bytes()
        checksum = hashlib.sha256(content).hexdigest()

        upload_response = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "VIDEO",
                "filename": "sessao.mp4",
                "mime_type": "video/mp4",
                "size_bytes": len(content),
            },
        )
        media_id = upload_response.json()["media_id"]
        upload_url = upload_response.json()["upload_url"]

        assert client.put(upload_url, content=content).status_code == 204

        confirm_response = client.post(
            f"/analyses/{analysis_id}/media/{media_id}/confirm",
            headers=headers,
            json={"checksum_sha256": checksum},
        )
        assert confirm_response.json()["upload_state"] == "APPROVED"

        session = SessionLocal()
        try:
            media_asset = session.scalar(
                select(MediaAsset).where(MediaAsset.id == uuid.UUID(media_id))
            )
            modality_state = AnalysisModalityState(
                analysis_id=uuid.UUID(analysis_id),
                modality_type="VIDEO",
                media_asset_id=media_asset.id,
                status="PENDING",
            )
            session.add(modality_state)
            session.flush()
            process_video_modality(session, modality_state)
            session.commit()

            findings = list(
                session.scalars(
                    select(ModalityFinding).where(
                        ModalityFinding.analysis_id == uuid.UUID(analysis_id)
                    )
                ).all()
            )
        finally:
            session.close()

        by_nature: dict[str, list[ModalityFinding]] = {}
        for f in findings:
            by_nature.setdefault(f.nature, []).append(f)

        # 1 achado de qualidade estrutural (ORIGINAL_DATA, duracao real de
        # 6s lida do mvhd) + 2 achados MODEL_OBSERVATION: visao
        # computacional self-hosted (UNAVAILABLE com o adaptador LOCAL
        # padrao) e reconhecimento de video via Amazon Rekognition
        # (tambem UNAVAILABLE, pois a feature flag
        # `vision_rekognition_video_enabled` esta desligada por padrao) -
        # sem hipotese de ausencia de pessoa, pois o adaptador LOCAL nao
        # produz pose_findings (nenhum quadro real analisado).
        assert len(by_nature.get("ORIGINAL_DATA", [])) == 1
        quality_finding = by_nature["ORIGINAL_DATA"][0]
        assert quality_finding.quality_metrics["duration_seconds"] == 6.0

        model_observations = by_nature.get("MODEL_OBSERVATION", [])
        assert len(model_observations) == 2
        vision_finding = next(
            f for f in model_observations if "frames_analyzed" in f.quality_metrics
        )
        assert vision_finding.quality_metrics["status"] == "UNAVAILABLE"
        assert vision_finding.quality_metrics["provider"] == "local"

        recognition_finding = next(
            f for f in model_observations if "frames_analyzed" not in f.quality_metrics
        )
        assert recognition_finding.quality_metrics["status"] == "UNAVAILABLE"
        assert recognition_finding.quality_metrics["provider"] == "local"

        assert by_nature.get("ASSISTED_HYPOTHESIS", []) == []
