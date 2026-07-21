"""Teste de integracao do processador AUDIO real (item 11 + secao 4.2).

Mesma estrategia de `tests/test_processors_image.py`: sobe um WAV PCM real
(senoide, simulando um sinal de voz continuo) pelo fluxo completo de
upload/aprovacao e chama `process_audio_modality` sobre o `MediaAsset`
resultante, verificando os achados de qualidade, analise acustica e
transcricao (LOCAL - sem motor de ASR, resultado UNAVAILABLE honesto).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import hashlib
import math
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
from app.processors.audio import process_audio_modality
from app.processors.models import ModalityFinding


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


def _sine_wav_bytes(*, sample_rate: int = 8000, seconds: float = 4.0) -> bytes:
    sample_count = int(sample_rate * seconds)
    samples = [
        int(20000 * math.sin(2 * math.pi * 220 * i / sample_rate)) for i in range(sample_count)
    ]
    data = b"".join(struct.pack("<h", max(-32768, min(32767, s))) for s in samples)

    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack(
            "<HHIIHH", 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample
        )
    )
    data_chunk = b"data" + struct.pack("<I", len(data)) + data
    riff_body = b"WAVE" + fmt_chunk + data_chunk
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


def _create_institution() -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": "Instituicao Audio"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID) -> str:
    session = SessionLocal()
    try:
        external_subject = f"audio-test-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name="Medico Teste Audio",
            role=UserRole.MEDICO.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


class TestAudioProcessorWithRealUpload:
    def test_real_wav_produces_quality_acoustic_and_transcription_findings(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id)}

        patient_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": f"MRN-AUD-{uuid.uuid4()}",
                "full_name": "Paciente Audio",
                "birth_date": "1975-03-20",
                "registered_sex": "feminino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        content = _sine_wav_bytes()
        checksum = hashlib.sha256(content).hexdigest()

        upload_response = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "AUDIO",
                "filename": "voz.wav",
                "mime_type": "audio/wav",
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
                modality_type="AUDIO",
                media_asset_id=media_asset.id,
                status="PENDING",
            )
            session.add(modality_state)
            session.flush()
            process_audio_modality(session, modality_state)
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

        # 1 qualidade (ORIGINAL_DATA) + 1 achado acustico (MODEL_OBSERVATION)
        # + 1 achado de status de transcricao (MODEL_OBSERVATION, UNAVAILABLE
        # com o adaptador LOCAL padrao) - sem hipotese de alteracao vocal,
        # pois a senoide continua nao cruza nenhum limiar heuristico.
        assert len(by_nature.get("ORIGINAL_DATA", [])) == 1
        model_observations = by_nature.get("MODEL_OBSERVATION", [])
        assert len(model_observations) == 2

        acoustic_finding = next(
            f for f in model_observations if "rms_energy_mean" in f.quality_metrics
        )
        assert acoustic_finding.quality_metrics["method"] == "acoustic_dsp_v1"

        transcription_finding = next(
            f for f in model_observations if "status" in f.quality_metrics
        )
        assert transcription_finding.quality_metrics["status"] == "UNAVAILABLE"
        assert transcription_finding.quality_metrics["provider"] == "local"

        # Senoide continua e alta nao cruza nenhum limiar heuristico de
        # alteracao vocal (ver test_acoustics_voice_analysis.py) - nenhuma
        # hipotese deve ser gerada so para preencher a secao do laudo.
        assert by_nature.get("ASSISTED_HYPOTHESIS", []) == []
