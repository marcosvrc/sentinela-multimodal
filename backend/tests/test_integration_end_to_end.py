"""Teste de integracao ponta a ponta (item 16 do backlog).

Diferente dos demais arquivos `test_*_api.py`, que testam uma rota/modulo
isoladamente, este arquivo percorre o fluxo completo pela API HTTP tal como
um cliente real faria: cadastro de paciente -> criacao de analise com
entradas clinicas estruturadas -> submissao -> processamento pelo worker
(fila real, processadores reais do item 11) -> consolidacao de risco ->
geracao do laudo DRAFT -> confirmacao -> download do PDF -> verificacao da
cadeia de auditoria. Tambem cobre, no mesmo fluxo, os dois eixos de
seguranca exigidos pela secao 7/8 do escopo: isolamento entre instituicoes
(multi-tenant) e autorizacao por papel (RBAC).

Marcado `@pytest.mark.integration` (`make test-integration` / `pytest -m
integration`). Precisa de Postgres real; pulado automaticamente quando
indisponivel neste sandbox (roda no CI, que sobe Postgres via Compose).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.audit.hashing import verify_chain
from app.audit.models import AuditEvent
from app.core.db import SessionLocal
from app.core.enums import UserRole
from app.identity import service as identity_service
from app.main import create_app
from app.orchestrator.worker import process_next_message
from app.processors.registry import PROCESSORS
from app.queue import get_queue_adapter
from app.rules_engine.models import (
    ClinicalRule,
    ClinicalRuleCondition,
    ClinicalRuleSet,
)


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        session.close()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente"),
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _create_institution(name: str) -> uuid.UUID:
    session = SessionLocal()
    try:
        institution_id = uuid.uuid4()
        session.execute(
            text("INSERT INTO institutions (id, name) VALUES (:id, :name)"),
            {"id": str(institution_id), "name": name},
        )
        session.commit()
        return institution_id
    finally:
        session.close()


def _create_user(institution_id: uuid.UUID, role: UserRole) -> str:
    session = SessionLocal()
    try:
        external_subject = f"e2e-{role.value.lower()}-{uuid.uuid4()}"
        identity_service.get_or_create_user(
            session,
            institution_id=institution_id,
            external_subject=external_subject,
            full_name=f"Usuario E2E {role.value}",
            role=role.value,
        )
        session.commit()
        return external_subject
    finally:
        session.close()


def _headers(subject: str) -> dict:
    return {"X-Dev-Subject": subject}


def _seed_rule_set(code: str) -> None:
    """Regra minima de SpO2 - mesma estrategia dos demais testes DB-gated."""
    session = SessionLocal()
    try:
        rule_set = ClinicalRuleSet(
            code=code,
            version="0.1.0-e2e",
            population="adult",
            # PUBLISHED: desde o item 5.3, get_current_rule_set so considera
            # conjuntos publicados vigentes (ver app/rules_engine/service.py).
            status="published",
            effective_from=date.today(),
            effective_to=None,
            required_inputs=["spo2_percent"],
            exclusions=[],
            content_hash=f"e2e-hash-{uuid.uuid4()}",
        )
        session.add(rule_set)
        session.flush()
        severe = ClinicalRule(
            rule_set_id=rule_set.id,
            rule_key="severe",
            risk_level=6,
            classification_label="Hipoxemia grave",
            position=0,
        )
        session.add(severe)
        session.flush()
        session.add(ClinicalRuleCondition(rule_id=severe.id, expression="spo2_percent <= 91"))
        session.commit()
    finally:
        session.close()


def _drain_queue_to_terminal_state() -> None:
    """Roda o worker ate a fila esvaziar (mesma unidade de trabalho de producao)."""
    queue = get_queue_adapter()
    for _ in range(10):
        session = SessionLocal()
        try:
            outcome = process_next_message(session, queue, processors=PROCESSORS)
        finally:
            session.close()
        if outcome is None:
            return


class TestFullClinicalPipeline:
    def test_analysis_flows_from_creation_to_confirmed_report_with_audit_trail(
        self, client: TestClient
    ) -> None:
        code = f"e2e-spo2-{uuid.uuid4()}"
        _seed_rule_set(code)

        institution_id = _create_institution("Hospital E2E")
        clinician = _create_user(institution_id, UserRole.MEDICO)
        auditor = _create_user(institution_id, UserRole.AUDITOR)
        clinician_headers = _headers(clinician)

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-E2E-{uuid.uuid4()}",
                "full_name": "Paciente Fluxo Completo",
                "birth_date": "1978-02-10",
                "registered_sex": "masculino",
            },
        )
        assert patient_response.status_code == 201
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={
                "patient_id": patient_id,
                "additional_text": "Paciente com dessaturacao referida pela equipe.",
                "structured_clinical_inputs": {code: {"spo2_percent": 85}},
            },
        )
        assert analysis_response.status_code == 201
        analysis_id = analysis_response.json()["id"]

        submit_response = client.post(f"/analyses/{analysis_id}/submit", headers=clinician_headers)
        assert submit_response.status_code == 200
        assert submit_response.json()["status"] == "QUEUED"

        _drain_queue_to_terminal_state()

        status_response = client.get(f"/analyses/{analysis_id}", headers=clinician_headers)
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "WAITING_REVIEW"

        report_response = client.get(f"/analyses/{analysis_id}/report", headers=clinician_headers)
        assert report_response.status_code == 200
        report_body = report_response.json()
        assert report_body["state"] == "DRAFT"
        assert report_body["content"]["calculated_risk"]["risk_level"] == 6
        assert report_body["content"]["calculated_risk"]["classification_label"] == (
            "Hipoxemia grave"
        )
        # A partir da secao 4.3, o processador de texto roda NLP clinico
        # real (app.clinical_nlp) e populariza "model_observations" quando
        # ha termo do lexico no texto - o additional_text usado aqui nao
        # contem nenhum termo do lexico atual, entao a secao permanece
        # vazia por ausencia de achado, nunca por omissao artificial
        # (mesmo principio de "nunca preencher com dado inventado").
        assert report_body["content"]["model_observations"] == []
        assert report_body["content"]["assisted_hypotheses"] == []

        confirm_response = client.post(
            f"/analyses/{analysis_id}/report/confirm", headers=clinician_headers
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["state"] == "CONFIRMED"

        final_status_response = client.get(f"/analyses/{analysis_id}", headers=clinician_headers)
        assert final_status_response.json()["status"] == "COMPLETED"

        pdf_response = client.get(f"/analyses/{analysis_id}/report/pdf", headers=clinician_headers)
        assert pdf_response.status_code == 200
        assert pdf_response.content[:5] == b"%PDF-"

        # --- Cadeia de auditoria integra e verificavel de ponta a ponta ---
        session = SessionLocal()
        try:
            events = session.scalars(
                select(AuditEvent)
                .where(AuditEvent.institution_id == institution_id)
                .order_by(AuditEvent.sequence)
            ).all()
        finally:
            session.close()
        assert len(events) >= 5  # paciente, analise, submissao, IA, laudo confirmado
        # Mesmo conjunto de campos usado por `app.audit.service.record_event`
        # ao calcular o hash original (`_HASHED_FIELDS`) - reconstruir com um
        # subconjunto diferente faria `verify_chain` acusar violacao mesmo
        # com a cadeia intacta.
        chain = [
            {
                "sequence": e.sequence,
                "prev_hash": e.prev_hash,
                "event_hash": e.event_hash,
                "fields": {
                    "institution_id": str(e.institution_id) if e.institution_id else None,
                    "actor": e.actor,
                    "actor_role": e.actor_role,
                    "unit": e.unit,
                    "category": e.category,
                    "action": e.action,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "result": e.result,
                    "justification": e.justification,
                    "request_id": e.request_id,
                    "analysis_id": e.analysis_id,
                    "workflow_id": e.workflow_id,
                    "job_id": e.job_id,
                    "event_metadata": e.event_metadata,
                },
            }
            for e in events
        ]
        assert verify_chain(chain) == []

        audit_response = client.get(
            "/audit/events", headers=_headers(auditor), params={"page_size": 50}
        )
        assert audit_response.status_code == 200
        assert audit_response.json()["total_items"] >= len(events)

    def test_text_clinical_nlp_populates_model_observations_in_confirmed_report(
        self, client: TestClient
    ) -> None:
        """Secao 4.3 do escopo, ponta a ponta: um termo do lexico clinico no
        `additional_text` deve virar achado MODEL_OBSERVATION real, visivel
        no laudo, sem afetar o risco calculado deterministicamente."""
        code = f"e2e-nlp-spo2-{uuid.uuid4()}"
        _seed_rule_set(code)

        institution_id = _create_institution("Hospital NLP")
        clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-NLP-{uuid.uuid4()}",
                "full_name": "Paciente NLP",
                "birth_date": "1982-04-15",
                "registered_sex": "feminino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={
                "patient_id": patient_id,
                "additional_text": (
                    "Paciente nega dor toracica. Familiar relata confusao mental ontem."
                ),
                "structured_clinical_inputs": {code: {"spo2_percent": 85}},
            },
        )
        analysis_id = analysis_response.json()["id"]
        client.post(f"/analyses/{analysis_id}/submit", headers=clinician_headers)
        _drain_queue_to_terminal_state()

        report_response = client.get(
            f"/analyses/{analysis_id}/report", headers=clinician_headers
        )
        observations = report_response.json()["content"]["model_observations"]
        # A partir do enriquecimento de sentimento (Amazon Comprehend,
        # `sentiment_analysis_enabled` - desligado por padrao neste teste),
        # o processador de TEXT tambem grava um achado MODEL_OBSERVATION
        # "indisponivel" honesto (mesmo padrao do Rekognition Image) -
        # filtra apenas os achados de termo clinico (secao 4.3) aqui.
        nlp_observations = [obs for obs in observations if "term" in obs["details"]]
        assert len(nlp_observations) == 2
        terms = {obs["details"]["term"] for obs in nlp_observations}
        assert terms == {"dor toracica", "confusao mental"}
        by_term = {obs["details"]["term"]: obs["details"] for obs in nlp_observations}
        assert by_term["dor toracica"]["negation"] == "NEGATED"
        assert by_term["confusao mental"]["negation"] == "AFFIRMED"
        assert by_term["confusao mental"]["temporality"] == "PAST"

        sentiment_observation = next(obs for obs in observations if "sentiment" in obs["details"])
        assert sentiment_observation["details"]["status"] == "UNAVAILABLE"

        # O risco continua vindo exclusivamente do motor deterministico -
        # os achados de NLP nao entram na consolidacao de risco (ver
        # app.risk_consolidation.service, filtro por nature=ORIGINAL_DATA).
        assert report_response.json()["content"]["calculated_risk"]["risk_level"] == 6

    def test_second_institution_cannot_see_or_act_on_first_institutions_analysis(
        self, client: TestClient
    ) -> None:
        code = f"e2e-spo2-isolated-{uuid.uuid4()}"
        _seed_rule_set(code)

        institution_a = _create_institution("Hospital A")
        institution_b = _create_institution("Hospital B")
        clinician_a = _headers(_create_user(institution_a, UserRole.MEDICO))
        clinician_b = _headers(_create_user(institution_b, UserRole.MEDICO))

        patient_response = client.post(
            "/patients",
            headers=clinician_a,
            json={
                "medical_record_number": f"MRN-ISO-{uuid.uuid4()}",
                "full_name": "Paciente Instituicao A",
                "birth_date": "1990-01-01",
                "registered_sex": "feminino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_a,
            json={
                "patient_id": patient_id,
                "additional_text": "Texto restrito a instituicao A.",
                "structured_clinical_inputs": {code: {"spo2_percent": 85}},
            },
        )
        analysis_id = analysis_response.json()["id"]
        client.post(f"/analyses/{analysis_id}/submit", headers=clinician_a)
        _drain_queue_to_terminal_state()
        client.post(f"/analyses/{analysis_id}/report/confirm", headers=clinician_a)

        # Instituicao B nao enxerga nada do fluxo da instituicao A: resposta
        # indistinguivel de "nao existe" (404), nunca 403 (que revelaria a
        # existencia do recurso a um tenant nao relacionado).
        assert client.get(f"/patients/{patient_id}", headers=clinician_b).status_code == 404
        assert client.get(f"/analyses/{analysis_id}", headers=clinician_b).status_code == 404
        assert client.get(f"/analyses/{analysis_id}/report", headers=clinician_b).status_code == 404
        assert (
            client.get(f"/analyses/{analysis_id}/report/pdf", headers=clinician_b).status_code
            == 404
        )
        assert (
            client.post(f"/analyses/{analysis_id}/report/confirm", headers=clinician_b).status_code
            == 404
        )

    def test_non_clinical_role_cannot_submit_or_confirm_report(self, client: TestClient) -> None:
        institution_id = _create_institution("Hospital RBAC")
        clinician_headers = _headers(_create_user(institution_id, UserRole.MEDICO))
        auditor_headers = _headers(_create_user(institution_id, UserRole.AUDITOR))

        patient_response = client.post(
            "/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": f"MRN-RBAC-{uuid.uuid4()}",
                "full_name": "Paciente RBAC",
                "birth_date": "1995-05-05",
                "registered_sex": "masculino",
            },
        )
        patient_id = patient_response.json()["id"]

        analysis_response = client.post(
            "/analyses",
            headers=clinician_headers,
            json={"patient_id": patient_id, "additional_text": "Texto qualquer."},
        )
        analysis_id = analysis_response.json()["id"]

        # Um auditor pode consultar auditoria, mas nao e papel clinico:
        # nao pode submeter nem confirmar laudos (secao 5.2 do escopo).
        assert (
            client.post(f"/analyses/{analysis_id}/submit", headers=auditor_headers).status_code
            == 403
        )
        assert (
            client.post(
                f"/analyses/{analysis_id}/report/confirm", headers=auditor_headers
            ).status_code
            == 403
        )
        assert (
            client.post(f"/analyses/{analysis_id}/submit", headers=clinician_headers).status_code
            == 200
        )
