"""Testes de `app.risk_consolidation.service.consolidate_analysis_risk` (item 12).

Precisa de Postgres real (grava `Analysis`, `ClinicalRuleSet`,
`RiskConsolidation`, evento de auditoria); pulado automaticamente quando
indisponivel neste sandbox (roda no CI). Usa o adaptador LOCAL de LLM (sem
rede) - `llm_provider` fica em LOCAL por padrao em `Settings`.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.enums import LlmCallStatus, RuleEvaluationOutcome
from app.media import service as media_service
from app.patients.models import Patient
from app.risk_consolidation.models import RiskConsolidation
from app.risk_consolidation.service import consolidate_analysis_risk
from app.rules_engine.models import ClinicalRule, ClinicalRuleCondition, ClinicalRuleSet


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
        full_name="Paciente Consolidador",
        birth_date=date(1985, 3, 20),
        registered_sex="masculino",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient.id


def _create_rule_set(session, *, code: str, required_inputs: list[str], rules) -> None:
    rule_set = ClinicalRuleSet(
        code=code,
        version="0.1.0-test",
        population="adult",
        status="published",
        effective_from=date.today(),
        effective_to=None,
        required_inputs=required_inputs,
        exclusions=[],
        content_hash=f"test-hash-{uuid.uuid4()}",
    )
    session.add(rule_set)
    session.flush()
    for position, (rule_key, expression, risk_level, label) in enumerate(rules):
        clinical_rule = ClinicalRule(
            rule_set_id=rule_set.id,
            rule_key=rule_key,
            risk_level=risk_level,
            classification_label=label,
            position=position,
        )
        session.add(clinical_rule)
        session.flush()
        session.add(ClinicalRuleCondition(rule_id=clinical_rule.id, expression=expression))
    session.commit()


def test_consolidate_matches_rule_and_generates_local_summary(session) -> None:
    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    code = f"test-spo2-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        required_inputs=["spo2_percent"],
        rules=[
            ("normal", "spo2_percent >= 96", 1, "Normal"),
            ("severe", "spo2_percent <= 91", 6, "Hipoxemia grave"),
        ],
    )

    analysis = media_service.create_analysis(
        session,
        institution_id,
        patient_id,
        "test-actor",
        None,
        {code: {"spo2_percent": 85}},
    )

    result = consolidate_analysis_risk(session, analysis)
    session.commit()

    assert result.outcome == RuleEvaluationOutcome.MATCHED.value
    assert result.risk_level == 6
    assert result.classification_label == "Hipoxemia grave"
    assert result.llm_status == LlmCallStatus.SUCCESS.value
    assert result.llm_summary is not None
    assert "6" in result.llm_summary

    stored = session.scalar(
        select(RiskConsolidation).where(RiskConsolidation.analysis_id == analysis.id)
    )
    assert stored is not None
    assert stored.id == result.id


def test_consolidate_without_structured_inputs_is_inconclusive(session) -> None:
    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    analysis = media_service.create_analysis(session, institution_id, patient_id, "test-actor")

    result = consolidate_analysis_risk(session, analysis)
    session.commit()

    assert result.outcome == RuleEvaluationOutcome.INCONCLUSIVE.value
    assert result.risk_level is None
    assert result.llm_status == LlmCallStatus.SUCCESS.value
    assert result.llm_summary is not None


def test_consolidate_is_idempotent_upsert(session) -> None:
    institution_id = _create_institution(session)
    patient_id = _create_patient(session, institution_id)
    code = f"test-hr-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        required_inputs=["heart_rate_bpm"],
        rules=[("normal", "60 <= heart_rate_bpm <= 100", 1, "Normal")],
    )
    analysis = media_service.create_analysis(
        session, institution_id, patient_id, "test-actor", None, {code: {"heart_rate_bpm": 75}}
    )

    first = consolidate_analysis_risk(session, analysis)
    session.commit()
    second = consolidate_analysis_risk(session, analysis)
    session.commit()

    assert first.id == second.id

    all_rows = list(
        session.scalars(
            select(RiskConsolidation).where(RiskConsolidation.analysis_id == analysis.id)
        ).all()
    )
    assert len(all_rows) == 1
