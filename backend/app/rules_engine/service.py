"""Carga de conjuntos de regras do banco e execucao via `app.rules_engine.engine`.

Selecao do conjunto vigente: entre os `ClinicalRuleSet` de um `code` e
`population` com `status == PUBLISHED`, escolhe o de `effective_from` mais
recente cuja vigencia inclua a data de referencia (`effective_from <=
as_of <= effective_to-ou-em-aberto`).

Antes da existencia do fluxo de publicacao formal (somente o
administrador clinico pode publicar regras clinicas), o campo `status`
(draft/publicado) NAO era filtrado aqui - nao havia ainda rota de
publicacao. Isso mudou: o filtro abaixo e o unico lugar do sistema que
decide "este conjunto conta como vigente", e agora exige `PUBLISHED` (ver
`app.administration.service.publish_rule_set`/`rollback_rule_set`).
Conjuntos `DRAFT` (ex.: recem-carregados por `make rules-seed`, ainda sem
aprovacao clinica formal) e `RETIRED` (substituidos/revertidos) nunca sao
considerados vigentes, mesmo com `effective_from` no passado - por
desenho: carregar o conteudo de uma regra e aprova-la para uso sao passos
distintos.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    ClinicalRuleSetStatus,
    RuleEvaluationInconclusiveReason,
    RuleEvaluationOutcome,
)
from app.rules_engine.engine import RuleDefinition, RuleSetEvaluation, evaluate_rule_set
from app.rules_engine.evaluator import Scalar
from app.rules_engine.models import ClinicalRule, ClinicalRuleSet


class NoRuleSetAvailableError(Exception):
    """Nenhum `ClinicalRuleSet` vigente foi encontrado para `code`/`population`."""


def get_current_rule_set(
    db: Session, code: str, population: str, as_of: date | None = None
) -> ClinicalRuleSet | None:
    reference_date = as_of or date.today()

    candidates = db.scalars(
        select(ClinicalRuleSet)
        .options(selectinload(ClinicalRuleSet.rules).selectinload(ClinicalRule.condition))
        .where(
            ClinicalRuleSet.code == code,
            ClinicalRuleSet.population == population,
            ClinicalRuleSet.status == ClinicalRuleSetStatus.PUBLISHED.value,
            ClinicalRuleSet.effective_from <= reference_date,
        )
        .order_by(ClinicalRuleSet.effective_from.desc(), ClinicalRuleSet.created_at.desc())
    ).all()

    for rule_set in candidates:
        if rule_set.effective_to is None or rule_set.effective_to >= reference_date:
            return rule_set
    return None


def evaluate(
    db: Session,
    code: str,
    population: str,
    inputs: dict[str, Scalar],
    as_of: date | None = None,
) -> tuple[RuleSetEvaluation, ClinicalRuleSet | None]:
    """Avalia `inputs` contra o conjunto vigente de `code`/`population`.

    Retorna a avaliacao junto com o `ClinicalRuleSet` usado (ou `None` se
    nenhum conjunto vigente existir), para que o chamador possa registrar
    rastreabilidade (qual versao da regra decidiu o resultado, para a
    classificacao deterministica de risco).
    """
    rule_set = get_current_rule_set(db, code, population, as_of)
    if rule_set is None:
        return (
            RuleSetEvaluation(
                outcome=RuleEvaluationOutcome.INCONCLUSIVE,
                inconclusive_reason=RuleEvaluationInconclusiveReason.NO_RULE_SET_AVAILABLE,
                inconclusive_detail=(
                    f"Nenhum conjunto de regras vigente para code={code!r}, "
                    f"population={population!r}."
                ),
            ),
            None,
        )

    rule_definitions = [
        RuleDefinition(
            rule_key=rule.rule_key,
            expression=rule.condition.expression,
            risk_level=rule.risk_level,
            classification_label=rule.classification_label,
            position=rule.position,
        )
        for rule in rule_set.rules
    ]
    evaluation = evaluate_rule_set(rule_definitions, list(rule_set.required_inputs), inputs)
    return evaluation, rule_set
