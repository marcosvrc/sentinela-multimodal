"""Endpoint de avaliacao manual do motor de regras deterministico (item 9).

Utilitario para testar/inspecionar um conjunto de regras publicado contra
valores arbitrarios - util para validacao clinica antes de aprovar uma
versao e para depuracao. A execucao real das regras dentro do fluxo de
analise (paciente -> observacoes -> classificacao automatica) e conectada
pelo orquestrador (item 10) e pelos processadores de modalidade (item 11);
este endpoint nao depende deles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.rules import RuleEvaluationRequest, RuleEvaluationResponse
from app.audit import service as audit_service
from app.core.db import get_db_session
from app.core.enums import AuditCategory, AuditResult, UserRole
from app.core.security import AuthenticatedUser, require_role
from app.rules_engine import service as rules_service

router = APIRouter(prefix="/clinical-rules", tags=["clinical-rules"])

_require_rule_evaluation_access = require_role(
    UserRole.MEDICO, UserRole.ENFERMEIRO, UserRole.ADMINISTRADOR_CLINICO
)


@router.post("/{code}/evaluate", response_model=RuleEvaluationResponse)
def evaluate_rule_set(
    code: str,
    data: RuleEvaluationRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_rule_evaluation_access),
) -> RuleEvaluationResponse:
    evaluation, rule_set = rules_service.evaluate(db, code, data.population, data.inputs)

    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.ANALYSIS,
        action="RULE_SET_EVALUATION",
        resource_type="clinical_rule_set",
        resource_id=str(rule_set.id) if rule_set else None,
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
        event_metadata={
            "code": code,
            "population": data.population,
            "outcome": evaluation.outcome.value,
        },
    )
    db.commit()

    return RuleEvaluationResponse(
        outcome=evaluation.outcome,
        risk_level=evaluation.risk_level,
        classification_label=(
            evaluation.matched_rule.classification_label if evaluation.matched_rule else None
        ),
        matched_rule_key=(evaluation.matched_rule.rule_key if evaluation.matched_rule else None),
        other_matched_rule_keys=[rule.rule_key for rule in evaluation.other_matched_rules],
        inconclusive_reason=evaluation.inconclusive_reason,
        inconclusive_detail=evaluation.inconclusive_detail,
        rule_set_id=rule_set.id if rule_set else None,
        rule_set_version=rule_set.version if rule_set else None,
    )
