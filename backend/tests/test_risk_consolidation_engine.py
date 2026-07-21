"""Testes da combinacao de risco entre multiplos `code` (pure, sem banco)."""

from __future__ import annotations

from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome
from app.risk_consolidation.engine import CodeEvaluation, consolidate_code_evaluations
from app.rules_engine.engine import MatchedRule, RuleSetEvaluation


def _matched(code: str, risk_level: int, label: str) -> CodeEvaluation:
    return CodeEvaluation(
        code=code,
        evaluation=RuleSetEvaluation(
            outcome=RuleEvaluationOutcome.MATCHED,
            matched_rule=MatchedRule(
                rule_key=f"{code}_rule", risk_level=risk_level, classification_label=label
            ),
        ),
    )


def _inconclusive(
    code: str, reason: RuleEvaluationInconclusiveReason, detail: str
) -> CodeEvaluation:
    return CodeEvaluation(
        code=code,
        evaluation=RuleSetEvaluation(
            outcome=RuleEvaluationOutcome.INCONCLUSIVE,
            inconclusive_reason=reason,
            inconclusive_detail=detail,
        ),
    )


def test_no_evaluations_is_inconclusive() -> None:
    result = consolidate_code_evaluations([])
    assert result.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert result.matched_rule is None
    assert "Nenhuma entrada" in (result.inconclusive_detail or "")


def test_single_matched_code_wins() -> None:
    result = consolidate_code_evaluations([_matched("spo2", 4, "Hipoxemia")])
    assert result.outcome is RuleEvaluationOutcome.MATCHED
    assert result.matched_code == "spo2"
    assert result.risk_level == 4
    assert result.classification_label == "Hipoxemia"


def test_highest_risk_across_codes_wins() -> None:
    result = consolidate_code_evaluations(
        [
            _matched("spo2", 2, "Leve"),
            _matched("heart_rate", 6, "Critico"),
            _matched("temperature", 3, "Moderado"),
        ]
    )
    assert result.matched_code == "heart_rate"
    assert result.risk_level == 6
    other_codes = {code for code, _ in result.other_matches}
    assert other_codes == {"spo2", "temperature"}


def test_all_inconclusive_yields_inconclusive() -> None:
    result = consolidate_code_evaluations(
        [
            _inconclusive(
                "spo2", RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT, "faltou spo2"
            ),
        ]
    )
    assert result.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert result.inconclusive_reason is RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT
    assert result.inconclusive_detail == "faltou spo2"


def test_mixed_matched_and_inconclusive_ignores_inconclusive() -> None:
    result = consolidate_code_evaluations(
        [
            _inconclusive("temperature", RuleEvaluationInconclusiveReason.NO_RULE_MATCHED, "gap"),
            _matched("spo2", 1, "Normal"),
        ]
    )
    assert result.outcome is RuleEvaluationOutcome.MATCHED
    assert result.matched_code == "spo2"
    assert result.risk_level == 1
