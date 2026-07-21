"""Teste de integracao do enriquecimento de analise de sentimento (Amazon
Comprehend) no processador TEXT, e da garantia de que o sentimento e
sempre CONTEXTUAL - nunca alcanca o prompt do LLM de consolidacao de risco
(ESCOPO_PROJETO.md secao 4.2).

Mesma estrategia de `tests/test_prompt_injection_security.py`: monta
`Patient`/`Analysis`/`AnalysisModalityState` direto via ORM (sem upload de
midia, que TEXT nao usa) e chama `process_text_modality` sobre o estado
resultante. O adaptador de sentimento e SUBSTITUIDO por um fake injetado
via monkeypatch (sem depender de credenciais/rede AWS real).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.enums import SentimentAnalysisStatus
from app.feature_flags.service import get_feature_flags, update_feature_flags
from app.integrations.sentiment_analysis.base import SentimentAnalysisResult, SentimentScore
from app.media import service as media_service
from app.orchestrator.models import AnalysisModalityState
from app.patients.models import Patient
from app.processors.models import ModalityFinding
from app.processors.text import process_text_modality
from app.risk_consolidation.service import consolidate_analysis_risk


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
def session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def _restore_sentiment_flag():
    """`FeatureFlags` e uma linha SINGLETON compartilhada por todo o banco
    de testes - ligar `sentiment_analysis_enabled` aqui sem desligar de
    volta no teardown vazaria estado para outros testes (mesmo cuidado de
    `tests/test_processors_image_clinical_relevance.py`)."""
    probe = SessionLocal()
    try:
        original = get_feature_flags(probe).sentiment_analysis_enabled
    finally:
        probe.close()

    yield

    cleanup = SessionLocal()
    try:
        update_feature_flags(
            cleanup,
            actor="test-teardown",
            actor_role="ADMINISTRADOR_TECNICO",
            sentiment_analysis_enabled=original,
        )
    finally:
        cleanup.close()


def _create_institution(session) -> uuid.UUID:
    institution_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
        {"id": str(institution_id), "name": "Instituicao Sentimento"},
    )
    session.commit()
    return institution_id


def _create_patient(session, institution_id: uuid.UUID) -> uuid.UUID:
    patient = Patient(
        institution_id=institution_id,
        medical_record_number=f"MRN-{uuid.uuid4()}",
        full_name="Paciente Teste Sentimento",
        birth_date=date(1990, 5, 10),
        registered_sex="feminino",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient.id


class _FakeSentimentAdapter:
    def __init__(self, sentiment: str, scores: SentimentScore):
        self._sentiment = sentiment
        self._scores = scores

    def detect_sentiment(self, request):  # noqa: ARG002 - assinatura do Protocol
        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.COMPLETED,
            provider="fake_comprehend",
            sentiment=self._sentiment,
            scores=self._scores,
        )


def test_sentiment_finding_is_recorded_when_flag_enabled(
    session, monkeypatch: pytest.MonkeyPatch, _restore_sentiment_flag
) -> None:
    update_feature_flags(
        session,
        actor="test-actor",
        actor_role="ADMINISTRADOR_TECNICO",
        sentiment_analysis_enabled=True,
    )

    fake_adapter = _FakeSentimentAdapter(
        "NEGATIVE", SentimentScore(positive=0.02, negative=0.88, neutral=0.08, mixed=0.02)
    )
    monkeypatch.setattr(
        "app.processors.text.get_sentiment_analysis_adapter", lambda db: fake_adapter
    )

    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    analysis = media_service.create_analysis(
        session,
        institution_id,
        patient_id,
        "test-actor",
        "Paciente relata muito desanimo e cansaco constante nos ultimos dias.",
    )

    modality_state = AnalysisModalityState(
        analysis_id=analysis.id, modality_type="TEXT", status="PENDING"
    )
    session.add(modality_state)
    session.flush()
    process_text_modality(session, modality_state)
    session.commit()

    findings = list(
        session.scalars(
            select(ModalityFinding).where(ModalityFinding.analysis_id == analysis.id)
        ).all()
    )
    sentiment_finding = next(f for f in findings if "sentiment" in f.quality_metrics)
    assert sentiment_finding.nature == "MODEL_OBSERVATION"
    assert sentiment_finding.quality_metrics["sentiment"] == "NEGATIVE"
    assert sentiment_finding.quality_metrics["scores"]["negative"] == 0.88
    assert "contextual" in sentiment_finding.summary.lower()
    assert "nao determina risco" in sentiment_finding.summary.lower()


def test_sentiment_never_reaches_llm_risk_consolidation_payload(
    session, monkeypatch: pytest.MonkeyPatch, _restore_sentiment_flag
) -> None:
    """Guardrail central do escopo (secao 4.2): sentimento e sempre
    contextual e NUNCA determina risco clinico - garantido aqui pelo fato
    de `consolidate_analysis_risk` so incluir achados `nature=
    ORIGINAL_DATA` no payload enviado ao LLM (MODEL_OBSERVATION, onde o
    sentimento e gravado, nunca entra)."""
    update_feature_flags(
        session,
        actor="test-actor",
        actor_role="ADMINISTRADOR_TECNICO",
        sentiment_analysis_enabled=True,
    )

    fake_adapter = _FakeSentimentAdapter(
        "NEGATIVE", SentimentScore(positive=0.01, negative=0.95, neutral=0.03, mixed=0.01)
    )
    monkeypatch.setattr(
        "app.processors.text.get_sentiment_analysis_adapter", lambda db: fake_adapter
    )

    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    analysis = media_service.create_analysis(
        session,
        institution_id,
        patient_id,
        "test-actor",
        "Paciente muito angustiado, relatando piora significativa do quadro.",
    )

    modality_state = AnalysisModalityState(
        analysis_id=analysis.id, modality_type="TEXT", status="PENDING"
    )
    session.add(modality_state)
    session.flush()
    process_text_modality(session, modality_state)
    session.commit()

    captured: list = []

    class _CapturingLlmAdapter:
        def summarize(self, request):
            captured.append(request)
            from app.integrations.llm.local import LocalTemplateLlmAdapter

            return LocalTemplateLlmAdapter().summarize(request)

    monkeypatch.setattr(
        "app.risk_consolidation.service.get_llm_adapter", lambda db: _CapturingLlmAdapter()
    )

    result = consolidate_analysis_risk(session, analysis)
    session.commit()

    assert len(captured) == 1
    sent_request = captured[0]
    # O unico resumo de modalidade enviado ao LLM e o de QUALIDADE
    # (ORIGINAL_DATA, "Texto com N caracteres...") - nunca o achado de
    # sentimento (MODEL_OBSERVATION).
    assert len(sent_request.modality_summaries) == 1
    assert "caracteres" in sent_request.modality_summaries[0].summary
    assert "NEGATIVE" not in repr(sent_request.modality_summaries[0].summary)
    assert result.outcome == "INCONCLUSIVE"
    # Nenhum evaluation baseado em codigo (sem structured_clinical_inputs)
    # - garante que o sentimento tambem nao influenciou o risco calculado.
    assert result.risk_level is None
