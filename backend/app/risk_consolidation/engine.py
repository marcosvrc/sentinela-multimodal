"""Combinacao pura de avaliacoes de multiplos conjuntos de regras (item 12).

`app.rules_engine.engine.evaluate_rule_set` decide o risco DENTRO de um
unico conjunto (ex: "spo2"). Uma analise pode ter entradas estruturadas
para varios conjuntos ao mesmo tempo (spo2 + heart_rate + ...); esta funcao
aplica a MESMA politica conservadora ja usada dentro de um conjunto
(vence o `risk_level` mais alto; INCONCLUSIVO so quando TODOS os conjuntos
avaliados forem inconclusivos) para combina-los em um unico resultado por
analise. Nao acessa banco nem OpenAI - funcao pura, testavel sem I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome
from app.rules_engine.engine import MatchedRule, RuleSetEvaluation


@dataclass(frozen=True)
class CodeEvaluation:
    """Uma avaliacao de rule set identificada pelo `code` que a produziu."""

    code: str
    evaluation: RuleSetEvaluation


@dataclass(frozen=True)
class ConsolidatedRisk:
    outcome: RuleEvaluationOutcome
    matched_code: str | None = None
    matched_rule: MatchedRule | None = None
    other_matches: tuple[tuple[str, MatchedRule], ...] = field(default_factory=tuple)
    inconclusive_reason: RuleEvaluationInconclusiveReason | None = None
    inconclusive_detail: str | None = None

    @property
    def risk_level(self) -> int | None:
        return self.matched_rule.risk_level if self.matched_rule else None

    @property
    def classification_label(self) -> str | None:
        return self.matched_rule.classification_label if self.matched_rule else None


def consolidate_code_evaluations(evaluations: list[CodeEvaluation]) -> ConsolidatedRisk:
    if not evaluations:
        return ConsolidatedRisk(
            outcome=RuleEvaluationOutcome.INCONCLUSIVE,
            inconclusive_reason=RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT,
            inconclusive_detail=(
                "Nenhuma entrada clinica estruturada foi fornecida para esta analise."
            ),
        )

    matches: list[tuple[str, MatchedRule]] = []
    for item in evaluations:
        if (
            item.evaluation.outcome is RuleEvaluationOutcome.MATCHED
            and item.evaluation.matched_rule
        ):
            matches.append((item.code, item.evaluation.matched_rule))

    if not matches:
        # Todos inconclusivos: reporta o primeiro motivo/detalhe encontrado
        # (todos sao igualmente validos para exibir; nao ha um "vencedor"
        # entre motivos de inconclusividade).
        first = evaluations[0].evaluation
        return ConsolidatedRisk(
            outcome=RuleEvaluationOutcome.INCONCLUSIVE,
            inconclusive_reason=first.inconclusive_reason,
            inconclusive_detail=first.inconclusive_detail,
        )

    matches.sort(key=lambda pair: pair[1].risk_level, reverse=True)
    (winner_code, winner_rule), *rest = matches
    return ConsolidatedRisk(
        outcome=RuleEvaluationOutcome.MATCHED,
        matched_code=winner_code,
        matched_rule=winner_rule,
        other_matches=tuple(rest),
    )
