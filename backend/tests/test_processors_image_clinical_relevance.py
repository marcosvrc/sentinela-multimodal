"""Teste de integracao do guardrail de relevancia clinica (app.vision.
clinical_relevance) aplicado ao processador IMAGE quando o reconhecimento
via Amazon Rekognition esta habilitado.

Mesma estrategia de `tests/test_processors_image.py` (upload real via API,
processamento direto de `process_image_modality`), mas com o adaptador de
reconhecimento de imagem SUBSTITUIDO por um fake injetado via monkeypatch
(mesmo padrao de injecao usado em `test_image_recognition_adapters.py`),
para nao depender de credenciais/rede AWS real neste teste. Verifica que:

1. Rotulos claramente nao-clinicos (ex: "Mountain", "Car") geram um achado
   com aviso explicito e `clinical_relevance=NOT_RELEVANT`.
2. Esse achado e EXCLUIDO do payload enviado ao apoio a analise clinica
   (`app.clinical_support.service.generate_analysis_clinical_support_
   summary`), mas rotulos relevantes (ex: "Person", "Skin") continuam
   entrando normalmente.

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
from app.core.enums import UserRole, VisionAnalysisStatus
from app.feature_flags.service import get_feature_flags, update_feature_flags
from app.identity import service as identity_service
from app.integrations.image_recognition.base import ImageLabelFinding, ImageRecognitionResult
from app.main import create_app
from app.media.models import MediaAsset
from app.orchestrator.models import AnalysisModalityState
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


class _FakeRelevanceAdapter:
    """Adaptador fake com rotulos fixos, injetado no lugar do
    `AwsRekognitionImageAdapter` real (sem credenciais/rede)."""

    def __init__(self, labels: list[tuple[str, float]]):
        self._labels = labels

    def detect_labels(self, request):  # noqa: ARG002 - assinatura do Protocol
        return ImageRecognitionResult(
            status=VisionAnalysisStatus.COMPLETED,
            provider="fake_rekognition",
            labels=[ImageLabelFinding(label=name, confidence=conf) for name, conf in self._labels],
        )


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
            {"id": str(institution_id), "name": "Instituicao Relevancia Clinica"},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID) -> str:
    session = SessionLocal()
    try:
        external_subject = f"relevance-test-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name="Medico Teste Relevancia",
            role=UserRole.MEDICO.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


def _upload_and_approve_image(client: TestClient, headers: dict) -> tuple[str, str]:
    patient_response = client.post(
        "/patients",
        headers=headers,
        json={
            "medical_record_number": f"MRN-REL-{uuid.uuid4()}",
            "full_name": "Paciente Relevancia",
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
    assert client.put(upload_url, content=content).status_code == 204

    confirm_response = client.post(
        f"/analyses/{analysis_id}/media/{media_id}/confirm",
        headers=headers,
        json={"checksum_sha256": checksum},
    )
    assert confirm_response.json()["upload_state"] == "APPROVED"
    return analysis_id, media_id


@pytest.fixture
def _restore_image_recognition_flag():
    """`FeatureFlags` e uma linha SINGLETON compartilhada por todo o banco
    de testes (nao e criada/destruida por teste) - ligar
    `image_recognition_enabled` aqui sem desligar de volta no teardown
    vazaria estado para outros testes que dependem do padrao (desligado).
    Ver `app.feature_flags.service`."""
    session = SessionLocal()
    try:
        original = get_feature_flags(session).image_recognition_enabled
    finally:
        session.close()

    yield

    session = SessionLocal()
    try:
        update_feature_flags(
            session,
            actor="test-teardown",
            actor_role=UserRole.ADMINISTRADOR_TECNICO.value,
            image_recognition_enabled=original,
        )
    finally:
        session.close()


class TestImageProcessorClinicalRelevanceGuardrail:
    def test_non_clinical_labels_are_flagged_and_excluded_from_support_summary(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, _restore_image_recognition_flag
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id)}

        session = SessionLocal()
        try:
            update_feature_flags(
                session,
                actor="test-actor",
                actor_role=UserRole.ADMINISTRADOR_TECNICO.value,
                image_recognition_enabled=True,
            )
        finally:
            session.close()

        monkeypatch.setattr(
            "app.processors.image.get_image_recognition_adapter",
            lambda db: _FakeRelevanceAdapter([("Mountain", 95.0), ("Sky", 90.0)]),  # noqa: ARG005
        )

        analysis_id, media_id = _upload_and_approve_image(client, headers)

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

            from app.processors.image import process_image_modality

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

        recognition_finding = next(
            f for f in findings if "labels" in f.quality_metrics and f.quality_metrics["labels"]
        )
        assert recognition_finding.quality_metrics["clinical_relevance"] == "NOT_RELEVANT"
        assert "AVISO" in recognition_finding.summary
        assert "nao sera considerado" in recognition_finding.summary.lower() or (
            "não será considerado" in recognition_finding.summary.lower()
        )

        # O apoio a analise clinica sob demanda deve EXCLUIR este achado
        # das consideracoes finais.
        from app.clinical_support.service import generate_analysis_clinical_support_summary

        session = SessionLocal()
        try:
            summary = generate_analysis_clinical_support_summary(
                session,
                institution_id,
                uuid.UUID(analysis_id),
                actor="test-actor",
                actor_role=UserRole.MEDICO.value,
            )
        finally:
            session.close()

        # 1 achado de qualidade (ORIGINAL_DATA) + 1 categoria heuristica
        # (MODEL_OBSERVATION) entram; o achado de rotulos NAO-clinicos e
        # excluido - restam 2 dos 3 achados totais.
        assert summary.findings_considered == 2

    def test_clinically_relevant_labels_are_not_flagged(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, _restore_image_recognition_flag
    ) -> None:
        institution_id = _create_institution()
        headers = {"X-Dev-Subject": _create_user(institution_id)}

        session = SessionLocal()
        try:
            update_feature_flags(
                session,
                actor="test-actor",
                actor_role=UserRole.ADMINISTRADOR_TECNICO.value,
                image_recognition_enabled=True,
            )
        finally:
            session.close()

        monkeypatch.setattr(
            "app.processors.image.get_image_recognition_adapter",
            lambda db: _FakeRelevanceAdapter([("Person", 99.0), ("Skin", 97.0)]),  # noqa: ARG005
        )

        analysis_id, media_id = _upload_and_approve_image(client, headers)

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

            from app.processors.image import process_image_modality

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

        recognition_finding = next(
            f for f in findings if "labels" in f.quality_metrics and f.quality_metrics["labels"]
        )
        assert recognition_finding.quality_metrics["clinical_relevance"] == "RELEVANT"
        assert "AVISO" not in recognition_finding.summary
