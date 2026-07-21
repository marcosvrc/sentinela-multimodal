"""Testes de `app.orchestrator.service` e `app.orchestrator.worker` (item 10).

Precisam de Postgres real (analises, midias e fila sao todas persistidas);
pulados automaticamente quando indisponivel neste sandbox (roda no CI).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import AnalysisStatus, MediaUploadState, ModalityType
from app.core.errors import ApiError
from app.media import service as media_service
from app.media.models import MediaAsset
from app.orchestrator import service as orchestrator_service
from app.orchestrator.worker import NO_PROCESSOR_REGISTERED_MESSAGE, process_next_message
from app.patients.models import Patient
from app.queue.local import LocalDbQueueAdapter


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


@pytest.fixture(autouse=True)
def _clean_queue_table():
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM analysis_queue_messages"))
        session.commit()
    finally:
        session.close()
    yield


@pytest.fixture
def queue() -> LocalDbQueueAdapter:
    return LocalDbQueueAdapter()


def _create_institution(session) -> uuid.UUID:
    institution_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
        {"id": str(institution_id), "name": "Instituicao de Teste"},
    )
    session.commit()
    return institution_id


def _create_patient(session, institution_id: uuid.UUID) -> uuid.UUID:
    patient = Patient(
        institution_id=institution_id,
        medical_record_number=f"MRN-{uuid.uuid4()}",
        full_name="Paciente Orquestrador",
        birth_date=date(1990, 6, 15),
        registered_sex="feminino",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient.id


def _approve_media_asset(
    session, institution_id: uuid.UUID, analysis_id: uuid.UUID, *, filename: str = "foto.png"
) -> MediaAsset:
    """Insere diretamente um `MediaAsset` ja `APPROVED` (bypassa o fluxo de upload,
    que ja e testado em tests/test_media_api.py; aqui so precisamos do estado final)."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    asset = MediaAsset(
        institution_id=institution_id,
        analysis_id=analysis_id,
        modality_type=ModalityType.IMAGE.value,
        upload_state=MediaUploadState.APPROVED.value,
        storage_key="test/key",
        original_filename=filename,
        declared_mime_type="image/png",
        declared_size_bytes=len(content),
        detected_mime_type="image/png",
        actual_size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        created_by="test-actor",
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@pytest.fixture
def analysis_with_approved_image(queue):
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        _approve_media_asset(session, institution_id, analysis.id)
        return institution_id, analysis.id
    finally:
        session.close()


def test_submit_analysis_transitions_to_queued_and_enqueues(
    analysis_with_approved_image, queue
) -> None:
    institution_id, analysis_id = analysis_with_approved_image
    session = SessionLocal()
    try:
        analysis = orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
        assert analysis.status == AnalysisStatus.QUEUED.value

        messages = queue.receive(max_messages=1)
        assert len(messages) == 1
        assert messages[0].body["analysis_id"] == str(analysis_id)
    finally:
        session.close()


def test_submit_analysis_without_content_returns_422(queue) -> None:
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")

        with pytest.raises(ApiError) as exc_info:
            orchestrator_service.submit_analysis(
                session, queue, institution_id, analysis.id, "test-actor"
            )
        assert exc_info.value.code == "NO_MODALITY_AVAILABLE"
    finally:
        session.close()


def test_submit_analysis_with_only_additional_text_succeeds(queue) -> None:
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(
            session, institution_id, patient_id, "test-actor", "Paciente relata tontura."
        )

        result = orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis.id, "test-actor"
        )
        assert result.status == AnalysisStatus.QUEUED.value
    finally:
        session.close()


def test_submit_analysis_with_only_structured_clinical_inputs_succeeds(queue) -> None:
    """Etapa "Dados clinicos" da tela de nova analise permite submeter sem
    nenhuma midia nem texto adicional - o motor de regras + resumo do LLM
    (`consolidate_analysis_risk`) e conteudo valido por si so."""
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(
            session,
            institution_id,
            patient_id,
            "test-actor",
            structured_clinical_inputs={"spo2": {"spo2_percent": 98}},
        )

        result = orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis.id, "test-actor"
        )
        assert result.status == AnalysisStatus.QUEUED.value
    finally:
        session.close()


def test_worker_processes_analysis_with_only_structured_clinical_inputs(queue) -> None:
    """Sem nenhum `AnalysisModalityState` (nenhuma midia/texto), o worker
    deve concluir em WAITING_REVIEW - nao FAILED_FINAL - e ainda assim
    rodar a consolidacao de risco (motor de regras + LLM) sobre os dados
    clinicos estruturados."""
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(
            session,
            institution_id,
            patient_id,
            "test-actor",
            structured_clinical_inputs={"spo2": {"spo2_percent": 98}},
        )
        analysis_id = analysis.id
        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    session = SessionLocal()
    try:
        outcome = process_next_message(session, queue)
        assert outcome is not None
        assert outcome.final_status is AnalysisStatus.WAITING_REVIEW
        assert outcome.modality_results == []

        risk = session.scalar(
            text("SELECT outcome FROM risk_consolidations WHERE analysis_id = :id"),
            {"id": str(analysis_id)},
        )
        assert risk is not None
    finally:
        session.close()


def test_submit_analysis_blocks_when_upload_unresolved(queue) -> None:
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        storage = _fake_storage()
        media_service.request_upload_url(
            session,
            storage,
            institution_id,
            analysis.id,
            "test-actor",
            ModalityType.IMAGE,
            "foto.png",
            "image/png",
            100,
        )

        with pytest.raises(ApiError) as exc_info:
            orchestrator_service.submit_analysis(
                session, queue, institution_id, analysis.id, "test-actor"
            )
        assert exc_info.value.code == "PENDING_UPLOADS"
    finally:
        session.close()


def _fake_storage():
    import tempfile

    from app.storage.local import LocalFilesystemStorageAdapter

    return LocalFilesystemStorageAdapter(
        storage_root=tempfile.mkdtemp(), upload_secret="test-secret", upload_url_ttl_seconds=900
    )


def test_worker_processes_message_with_no_processors_marks_failed_retryable(
    analysis_with_approved_image, queue
) -> None:
    institution_id, analysis_id = analysis_with_approved_image
    session = SessionLocal()
    try:
        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    session = SessionLocal()
    try:
        outcome = process_next_message(session, queue)
        assert outcome is not None
        assert outcome.final_status is AnalysisStatus.FAILED_RETRYABLE
        assert [(r.modality_type, r.status) for r in outcome.modality_results] == [
            ("IMAGE", "FAILED_RETRYABLE")
        ]
    finally:
        session.close()

    # Mensagem deve ter sido consumida (ack) - fila vazia agora.
    assert queue.receive(max_messages=1) == []


def test_worker_records_no_processor_error_message(analysis_with_approved_image, queue) -> None:
    institution_id, analysis_id = analysis_with_approved_image
    session = SessionLocal()
    try:
        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    session = SessionLocal()
    try:
        process_next_message(session, queue)

        states = orchestrator_service.list_modality_states(session, institution_id, analysis_id)
        assert len(states) == 1
        assert states[0].error_message == NO_PROCESSOR_REGISTERED_MESSAGE
    finally:
        session.close()


def test_worker_returns_none_when_queue_empty(queue) -> None:
    session = SessionLocal()
    try:
        assert process_next_message(session, queue) is None
    finally:
        session.close()


def test_submit_analysis_creates_one_modality_state_per_media_asset_of_same_type(
    queue,
) -> None:
    """Uma analise com DUAS imagens deve gerar DOIS `AnalysisModalityState`
    (um por midia), nao um so - ver `app.orchestrator.service.
    submit_analysis`. Cobre a mudanca de "1 estado por modalidade" para "1
    estado por midia aprovada"."""
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        first_asset = _approve_media_asset(
            session, institution_id, analysis.id, filename="foto1.png"
        )
        second_asset = _approve_media_asset(
            session, institution_id, analysis.id, filename="foto2.png"
        )

        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis.id, "test-actor"
        )

        states = orchestrator_service.list_modality_states(session, institution_id, analysis.id)
        assert len(states) == 2
        assert {state.modality_type for state in states} == {"IMAGE"}
        media_asset_ids = {state.media_asset_id for state in states}
        assert media_asset_ids == {first_asset.id, second_asset.id}
        assert all(state.status == "PENDING" for state in states)
    finally:
        session.close()


def test_worker_processes_each_media_asset_of_same_modality_independently(queue) -> None:
    """Registra um processador de teste que so falha para um dos dois
    arquivos IMAGE - confirma que cada `AnalysisModalityState` e processado
    de forma independente (nao ha deduplicacao por `modality_type`)."""
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        good_asset_id = _approve_media_asset(
            session, institution_id, analysis.id, filename="ok.png"
        ).id
        bad_asset_id = _approve_media_asset(
            session, institution_id, analysis.id, filename="bad.png"
        ).id
        analysis_id = analysis.id

        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    def _processor(db, modality_state) -> None:  # noqa: ANN001
        if modality_state.media_asset_id == bad_asset_id:
            raise ValueError("falha simulada para este arquivo especifico")

    session = SessionLocal()
    try:
        outcome = process_next_message(
            session, queue, processors={ModalityType.IMAGE: _processor}
        )
        assert outcome is not None
        assert outcome.final_status is AnalysisStatus.PARTIALLY_COMPLETED
        results_by_asset = {r.media_asset_id: r.status for r in outcome.modality_results}
        assert results_by_asset[good_asset_id] == "COMPLETED"
        assert results_by_asset[bad_asset_id] == "FAILED_RETRYABLE"
    finally:
        session.close()


def test_cancel_analysis_from_created(queue) -> None:
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")

        cancelled = orchestrator_service.cancel_analysis(
            session, institution_id, analysis.id, "test-actor"
        )
        assert cancelled.status == AnalysisStatus.CANCELLED.value
    finally:
        session.close()


def test_cancel_analysis_from_terminal_state_returns_409(queue) -> None:
    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")
        orchestrator_service.cancel_analysis(session, institution_id, analysis.id, "test-actor")

        with pytest.raises(ApiError) as exc_info:
            orchestrator_service.cancel_analysis(session, institution_id, analysis.id, "test-actor")
        assert exc_info.value.code == "ANALYSIS_NOT_CANCELLABLE"
    finally:
        session.close()


def test_retry_requeues_failed_retryable_analysis(analysis_with_approved_image, queue) -> None:
    institution_id, analysis_id = analysis_with_approved_image
    session = SessionLocal()
    try:
        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    session = SessionLocal()
    try:
        process_next_message(session, queue)
    finally:
        session.close()

    session = SessionLocal()
    try:
        retried = orchestrator_service.retry_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
        assert retried.status == AnalysisStatus.QUEUED.value

        states = orchestrator_service.list_modality_states(session, institution_id, analysis_id)
        assert all(state.status == "PENDING" for state in states)
    finally:
        session.close()

    messages = queue.receive(max_messages=1)
    assert len(messages) == 1


def test_worker_runs_automatic_clinical_support_when_flag_enabled_and_content_relevant(
    queue,
) -> None:
    """Flag `auto_clinical_support_enabled` ligada + analise com dados
    clinicos estruturados (conteudo relevante por definicao, ver
    `app.clinical_support.service.should_run_automatic_clinical_support`):
    o worker deve gerar e persistir o resumo automaticamente no relatorio,
    sem nenhum clique no botao manual."""
    from app.feature_flags.service import get_feature_flags, update_feature_flags

    probe = SessionLocal()
    try:
        original_flag = get_feature_flags(probe).auto_clinical_support_enabled
    finally:
        probe.close()

    toggle = SessionLocal()
    try:
        update_feature_flags(
            toggle, actor="test-actor", actor_role=None, auto_clinical_support_enabled=True
        )
    finally:
        toggle.close()

    try:
        session = SessionLocal()
        try:
            institution_id = _create_institution(session)
            patient_id = _create_patient(session, institution_id)
            analysis = media_service.create_analysis(
                session,
                institution_id,
                patient_id,
                "test-actor",
                structured_clinical_inputs={"spo2": {"spo2_percent": 98}},
            )
            analysis_id = analysis.id
            orchestrator_service.submit_analysis(
                session, queue, institution_id, analysis_id, "test-actor"
            )
        finally:
            session.close()

        session = SessionLocal()
        try:
            outcome = process_next_message(session, queue)
            assert outcome is not None
            assert outcome.final_status is AnalysisStatus.WAITING_REVIEW

            report = session.scalar(
                text("SELECT clinical_support_summary FROM reports WHERE analysis_id = :id"),
                {"id": str(analysis_id)},
            )
            assert report is not None
            assert report["summary_text"]
        finally:
            session.close()
    finally:
        cleanup = SessionLocal()
        try:
            update_feature_flags(
                cleanup,
                actor="test-teardown",
                actor_role=None,
                auto_clinical_support_enabled=original_flag,
            )
        finally:
            cleanup.close()


def test_worker_does_not_run_automatic_clinical_support_when_flag_disabled(queue) -> None:
    """Flag desligada (default): mesmo com dados clinicos estruturados
    (conteudo relevante), o worker nunca deve gerar o resumo automatico -
    `Report.clinical_support_summary` permanece `None`."""
    from app.feature_flags.service import get_feature_flags

    probe = SessionLocal()
    try:
        assert get_feature_flags(probe).auto_clinical_support_enabled is False
    finally:
        probe.close()

    session = SessionLocal()
    try:
        institution_id = _create_institution(session)
        patient_id = _create_patient(session, institution_id)
        analysis = media_service.create_analysis(
            session,
            institution_id,
            patient_id,
            "test-actor",
            structured_clinical_inputs={"spo2": {"spo2_percent": 98}},
        )
        analysis_id = analysis.id
        orchestrator_service.submit_analysis(
            session, queue, institution_id, analysis_id, "test-actor"
        )
    finally:
        session.close()

    session = SessionLocal()
    try:
        outcome = process_next_message(session, queue)
        assert outcome is not None
        assert outcome.final_status is AnalysisStatus.WAITING_REVIEW

        summary = session.scalar(
            text("SELECT clinical_support_summary FROM reports WHERE analysis_id = :id"),
            {"id": str(analysis_id)},
        )
        assert summary is None
    finally:
        session.close()


def test_worker_does_not_run_automatic_clinical_support_without_relevant_content(
    analysis_with_approved_image, queue
) -> None:
    """Flag ligada, mas SEM nenhum dado clinico estruturado nem achado
    relevante (so a imagem aprovada, sem processador registrado - fixture
    `analysis_with_approved_image` termina em FAILED_RETRYABLE sem gerar
    nenhum `ModalityFinding`): o apoio automatico nao deve ser chamado."""
    from app.feature_flags.service import get_feature_flags, update_feature_flags

    probe = SessionLocal()
    try:
        original_flag = get_feature_flags(probe).auto_clinical_support_enabled
    finally:
        probe.close()

    toggle = SessionLocal()
    try:
        update_feature_flags(
            toggle, actor="test-actor", actor_role=None, auto_clinical_support_enabled=True
        )
    finally:
        toggle.close()

    try:
        institution_id, analysis_id = analysis_with_approved_image
        session = SessionLocal()
        try:
            orchestrator_service.submit_analysis(
                session, queue, institution_id, analysis_id, "test-actor"
            )
        finally:
            session.close()

        session = SessionLocal()
        try:
            outcome = process_next_message(session, queue)
            assert outcome is not None
            # Sem processador registrado para IMAGE nesta suite -> FAILED_RETRYABLE,
            # nunca chega a WAITING_REVIEW/PARTIALLY_COMPLETED, entao nem o
            # relatorio nem o apoio automatico sao gerados.
            assert outcome.final_status is AnalysisStatus.FAILED_RETRYABLE

            report_exists = session.scalar(
                text("SELECT 1 FROM reports WHERE analysis_id = :id"), {"id": str(analysis_id)}
            )
            assert report_exists is None
        finally:
            session.close()
    finally:
        cleanup = SessionLocal()
        try:
            update_feature_flags(
                cleanup,
                actor="test-teardown",
                actor_role=None,
                auto_clinical_support_enabled=original_flag,
            )
        finally:
            cleanup.close()
