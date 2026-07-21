"""Testes de `app.rules_engine.service` (carga do conjunto vigente + execucao).

Precisa de Postgres real (grava/le `ClinicalRuleSet`/`ClinicalRule`); pulado
automaticamente quando indisponivel neste sandbox (roda no CI).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome
from app.rules_engine import service as rules_service
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


def _create_rule_set(
    session,
    *,
    code: str,
    population: str = "adult",
    status: str = "published",
    version: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    required_inputs: list[str] | None = None,
    rules: list[tuple[str, str, int, str]],
) -> ClinicalRuleSet:
    rule_set = ClinicalRuleSet(
        code=code,
        version=version or f"0.{uuid.uuid4().hex[:12]}",
        population=population,
        status=status,
        effective_from=effective_from or date.today(),
        effective_to=effective_to,
        required_inputs=required_inputs or [],
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
    session.refresh(rule_set)
    return rule_set


@pytest.fixture
def session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_get_current_rule_set_finds_matching_code_and_population(session) -> None:
    code = f"test-spo2-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        required_inputs=["spo2_percent"],
        rules=[("normal", "spo2_percent >= 96", 1, "Normal")],
    )

    found = rules_service.get_current_rule_set(session, code, "adult")
    assert found is not None
    assert found.code == code


def test_get_current_rule_set_returns_none_when_not_yet_effective(session) -> None:
    code = f"test-future-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        effective_from=date.today() + timedelta(days=30),
        rules=[("normal", "value >= 1", 1, "Normal")],
    )

    assert rules_service.get_current_rule_set(session, code, "adult") is None


def test_get_current_rule_set_returns_none_when_expired(session) -> None:
    code = f"test-expired-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        effective_from=date.today() - timedelta(days=60),
        effective_to=date.today() - timedelta(days=1),
        rules=[("normal", "value >= 1", 1, "Normal")],
    )

    assert rules_service.get_current_rule_set(session, code, "adult") is None


def test_evaluate_matches_rule(session) -> None:
    code = f"test-hr-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        required_inputs=["heart_rate_bpm"],
        rules=[
            ("normal", "60 <= heart_rate_bpm <= 100", 1, "Normal"),
            ("tachycardia", "heart_rate_bpm > 100", 4, "Taquicardia"),
        ],
    )

    evaluation, rule_set = rules_service.evaluate(session, code, "adult", {"heart_rate_bpm": 75})
    assert evaluation.outcome is RuleEvaluationOutcome.MATCHED
    assert evaluation.matched_rule.rule_key == "normal"
    assert rule_set is not None
    assert rule_set.code == code


def test_evaluate_returns_inconclusive_when_no_rule_set_exists(session) -> None:
    evaluation, rule_set = rules_service.evaluate(
        session, f"does-not-exist-{uuid.uuid4()}", "adult", {"x": 1}
    )
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.NO_RULE_SET_AVAILABLE
    assert rule_set is None


def test_get_current_rule_set_ignores_draft_status(session) -> None:
    # Item 5.3: um conjunto recem-carregado (seed/YAML) fica em "draft" ate
    # ser publicado por um administrador clinico - nunca conta como vigente
    # so por ter effective_from no passado.
    code = f"test-draft-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        status="draft",
        required_inputs=["value"],
        rules=[("normal", "value >= 0", 1, "Normal")],
    )

    assert rules_service.get_current_rule_set(session, code, "adult") is None


def test_get_current_rule_set_ignores_retired_status(session) -> None:
    # Uma versao revertida/substituida ("retired") tambem nunca conta como
    # vigente, mesmo com effective_from no passado.
    code = f"test-retired-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        status="retired",
        required_inputs=["value"],
        rules=[("normal", "value >= 0", 1, "Normal")],
    )

    assert rules_service.get_current_rule_set(session, code, "adult") is None


def test_evaluate_picks_most_recent_effective_version(session) -> None:
    code = f"test-versions-{uuid.uuid4()}"
    _create_rule_set(
        session,
        code=code,
        effective_from=date.today() - timedelta(days=100),
        required_inputs=["value"],
        rules=[("old", "value >= 0", 1, "Antiga")],
    )
    _create_rule_set(
        session,
        code=code,
        effective_from=date.today() - timedelta(days=1),
        required_inputs=["value"],
        rules=[("new", "value >= 0", 2, "Nova")],
    )

    evaluation, rule_set = rules_service.evaluate(session, code, "adult", {"value": 5})
    assert evaluation.matched_rule.rule_key == "new"
