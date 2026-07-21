"""Motor de regras deterministico: execucao real das condicoes (item 9).

Ate aqui (`app.rules_engine.models` + `clinical_rules/seeding.py`), as
condicoes de regra eram persistidas como texto mas nunca executadas contra
um valor real — a classificacao de risco ainda nao existia de fato. Este
modulo fecha essa lacuna com uma funcao pura: dado um conjunto de regras ja
carregado (nao acessa o banco - isso e responsabilidade de
`app.rules_engine.service`) e os valores observados de um paciente, produz
um `RuleSetEvaluation` determinístico.

Principios:

- Nunca adivinha um risco quando falta informacao: entradas obrigatorias
  ausentes ou de tipo incompativel produzem `INCONCLUSIVE`, nunca um
  `risk_level` "seguro" por padrao.
- Nunca escolhe silenciosamente entre regras conflitantes: se mais de uma
  regra do conjunto casar com os mesmos valores (nao deveria acontecer em
  um conjunto bem desenhado, mas o motor nao assume isso), vence o
  `risk_level` mais alto (postura conservadora de seguranca do paciente) e
  o resultado registra TODAS as regras que casaram, para auditoria e para
  expor o gap no conjunto de regras a quem o publica.
- Zero regras casando com entradas completas e validas tambem e
  `INCONCLUSIVE` (gap de cobertura na tabela), nao um erro silencioso.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome
from app.rules_engine.evaluator import (
    MissingVariableError,
    Scalar,
    UnsafeExpressionError,
    compile_condition,
)


@dataclass(frozen=True)
class RuleDefinition:
    """Uma regra ja carregada do banco (ou de um YAML validado), pronta pra avaliar."""

    rule_key: str
    expression: str
    risk_level: int
    classification_label: str
    position: int = 0


@dataclass(frozen=True)
class MatchedRule:
    rule_key: str
    risk_level: int
    classification_label: str


@dataclass(frozen=True)
class RuleSetEvaluation:
    outcome: RuleEvaluationOutcome
    matched_rule: MatchedRule | None = None
    other_matched_rules: tuple[MatchedRule, ...] = field(default_factory=tuple)
    inconclusive_reason: RuleEvaluationInconclusiveReason | None = None
    inconclusive_detail: str | None = None

    @property
    def risk_level(self) -> int | None:
        return self.matched_rule.risk_level if self.matched_rule else None


def evaluate_rule_set(
    rules: list[RuleDefinition],
    required_inputs: list[str],
    inputs: dict[str, Scalar],
) -> RuleSetEvaluation:
    """Avalia um conjunto de regras contra os valores de um paciente.

    `required_inputs` e conferido primeiro e por completo (mesmo que uma
    regra individual nao use todas as variaveis) porque a ausencia de um
    dado exigido pelo protocolo publicado e, por si so, motivo de
    inconclusividade - independente de qual regra teria ou nao casado.
    """
    missing = [name for name in required_inputs if name not in inputs or inputs[name] is None]
    if missing:
        return RuleSetEvaluation(
            outcome=RuleEvaluationOutcome.INCONCLUSIVE,
            inconclusive_reason=RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT,
            inconclusive_detail=f"Entradas obrigatorias ausentes: {', '.join(missing)}.",
        )

    matches: list[MatchedRule] = []
    for rule in sorted(rules, key=lambda r: r.position):
        try:
            condition = compile_condition(rule.expression)
            is_match = condition.evaluate(inputs)
        except MissingVariableError as exc:
            return RuleSetEvaluation(
                outcome=RuleEvaluationOutcome.INCONCLUSIVE,
                inconclusive_reason=RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT,
                inconclusive_detail=(
                    f"Regra '{rule.rule_key}' referencia variavel nao informada: "
                    f"{exc.variable_name}."
                ),
            )
        except UnsafeExpressionError as exc:
            return RuleSetEvaluation(
                outcome=RuleEvaluationOutcome.INCONCLUSIVE,
                inconclusive_reason=RuleEvaluationInconclusiveReason.INVALID_INPUT,
                inconclusive_detail=(f"Nao foi possivel avaliar a regra '{rule.rule_key}': {exc}"),
            )

        if is_match:
            matches.append(
                MatchedRule(
                    rule_key=rule.rule_key,
                    risk_level=rule.risk_level,
                    classification_label=rule.classification_label,
                )
            )

    if not matches:
        return RuleSetEvaluation(
            outcome=RuleEvaluationOutcome.INCONCLUSIVE,
            inconclusive_reason=RuleEvaluationInconclusiveReason.NO_RULE_MATCHED,
            inconclusive_detail="Nenhuma regra do conjunto correspondeu aos valores informados.",
        )

    matches.sort(key=lambda m: m.risk_level, reverse=True)
    winner, *rest = matches
    return RuleSetEvaluation(
        outcome=RuleEvaluationOutcome.MATCHED,
        matched_rule=winner,
        other_matched_rules=tuple(rest),
    )
