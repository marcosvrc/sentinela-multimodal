"""Teste de integracao do processador IMAGE real (item 11 + secao 4.4).

Diferente de `tests/test_vision_image_category.py` (que testa a heuristica
de classificacao isoladamente, sem banco/storage), este arquivo percorre o
fluxo real de upload (via API, adaptador de storage local) e chama
`process_image_modality` sobre um `MediaAsset` de verdade, verificando que
o achado de qualidade (ORIGINAL_DATA) e o achado de categoria
(MODEL_OBSERVATION, secao 4.4) sao gravados corretamente e aparecem no
laudo.

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import hashlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.media.models import MediaAsset
from app.orchestrator.models import AnalysisModalityState
from app.processors.image import process_image_modality
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


def _colorful_photograph_png_bytes() -> bytes:
    image = Image.new("RGB", (300, 300))
    pixels = image.load()
    for y in range(300):
        for x in range(300):
            pixels[x, y] = (min(255, x), min(255, y), 150)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _create_institution() -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": "Instituicao Imagem"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID) -> str:
    session = SessionLocal()
    try:
        external_subject = f"img-test-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name="Medico Teste Imagem",
            role=UserRole.MEDICO.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


class TestImageProcessorWithRealUpload:
    def test_real_photograph_produces_quality_and_category_findings(
        self, client: TestClient
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id)}

        patient_response = client.post(
            "/patients",
            headers=headers,
            json={
                "medical_record_number": f"MRN-IMG-{uuid.uuid4()}",
                "full_name": "Paciente Imagem",
                "birth_date": "1988-09-09",
                "registered_sex": "masculino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_id = client.post(
            "/analyses", headers=headers, json={"patient_id": patient_id}
        ).json()["id"]

        content = _colorful_photograph_png_bytes()
        checksum = hashlib.sha256(content).hexdigest()

        upload_response = client.post(
            f"/analyses/{analysis_id}/media",
            headers=headers,
            json={
                "modality_type": "IMAGE",
                "filename": "foto.png",
                "mime_type": "image/png",
                "size_bytes": len(content),
            },
        )
        media_id = upload_response.json()["media_id"]
        upload_url = upload_response.json()["upload_url"]

        put_response = client.put(upload_url, content=content)
        assert put_response.status_code == 204

        confirm_response = client.post(
            f"/analyses/{analysis_id}/media/{media_id}/confirm",
            headers=headers,
            json={"checksum_sha256": checksum},
        )
        assert confirm_response.json()["upload_state"] == "APPROVED"

        # Processa a modalidade diretamente (mesma unidade de trabalho que o
        # worker real executaria - ver app.orchestrator.worker).
        session = SessionLocal()
        try:
            media_asset = session.scalar(
                select(MediaAsset).where(MediaAsset.id == uuid.UUID(media_id))
            )
            modality_state = AnalysisModalityState(
                analysis_id=uuid.UUID(analysis_id),
                modality_type="IMAGE",
                media_asset_id=media_asset.id,
                status="PENDING",
            )
            session.add(modality_state)
            session.flush()
            process_image_modality(session, modality_state)
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

        # 1 achado de qualidade estrutural (ORIGINAL_DATA) + 2 achados
        # MODEL_OBSERVATION: categoria heuristica (sempre roda) e
        # reconhecimento de imagem via Amazon Rekognition (roda com o
        # adaptador LOCAL padrao, retornando UNAVAILABLE honesto, pois a
        # feature flag `image_recognition_enabled` esta desligada por
        # padrao neste ambiente).
        assert len(findings) == 3
        by_nature: dict[str, list[ModalityFinding]] = {}
        for f in findings:
            by_nature.setdefault(f.nature, []).append(f)
        assert len(by_nature.get("ORIGINAL_DATA", [])) == 1
        assert len(by_nature.get("MODEL_OBSERVATION", [])) == 2

        quality_finding = by_nature["ORIGINAL_DATA"][0]
        assert quality_finding.quality_metrics["width"] == 300
        assert quality_finding.quality_metrics["height"] == 300

        model_observations = by_nature["MODEL_OBSERVATION"]
        category_finding = next(
            f for f in model_observations if "category" in f.quality_metrics
        )
        assert category_finding.quality_metrics["category"] == "PHOTOGRAPH"
        assert category_finding.quality_metrics["method"] == "heuristic_color_texture_v1"
        assert "region_of_interest" in category_finding.quality_metrics
        assert len(category_finding.quality_metrics["limitations"]) > 0

        recognition_finding = next(
            f for f in model_observations if "provider" in f.quality_metrics
        )
        assert recognition_finding.quality_metrics["status"] == "UNAVAILABLE"
        assert recognition_finding.quality_metrics["provider"] == "local"
