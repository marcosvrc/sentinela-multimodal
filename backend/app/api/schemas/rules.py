"""Contrato do endpoint de avaliacao manual do motor de regras (item 9)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome


class RuleEvaluationRequest(BaseModel):
    population: str = Field(default="adult", min_length=1, max_length=50)
    inputs: dict[str, bool | int | float | str] = Field(default_factory=dict)


class RuleEvaluationResponse(BaseModel):
    outcome: RuleEvaluationOutcome
    risk_level: int | None = None
    classification_label: str | None = None
    matched_rule_key: str | None = None
    other_matched_rule_keys: list[str] = Field(default_factory=list)
    inconclusive_reason: RuleEvaluationInconclusiveReason | None = None
    inconclusive_detail: str | None = None
    rule_set_id: uuid.UUID | None = None
    rule_set_version: str | None = None
