"""Contratos do modulo de administracao."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import EmployeeProfessionalType, UserRole


class MedicalSpecialtyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class MedicalSpecialtyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None


class MedicalSpecialtyRead(BaseModel):
    id: uuid.UUID
    name: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    cpf: str = Field(..., min_length=11, max_length=14)
    registration_number: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    specialty_id: uuid.UUID | None = None
    professional_type: EmployeeProfessionalType
    # Conta de acesso criada/vinculada junto com o funcionario (ver
    # app.administration.service.create_employee) - `role` deve ser
    # compativel com `professional_type`
    # (ALLOWED_ROLES_BY_PROFESSIONAL_TYPE); `external_subject` e o
    # identificador estavel da conta de acesso (ver app.core.security).
    role: UserRole
    external_subject: str = Field(..., min_length=1, max_length=255)


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    specialty_id: uuid.UUID | None = None
    active: bool | None = None
    # Atualiza o papel de acesso do usuario vinculado (com a mesma
    # validacao de compatibilidade com `professional_type` da criacao).
    role: UserRole | None = None


class EmployeeRead(BaseModel):
    id: uuid.UUID
    full_name: str
    cpf: str
    registration_number: str
    email: str
    specialty_id: uuid.UUID | None
    professional_type: str
    active: bool
    created_at: datetime
    updated_at: datetime
    # Dados da conta de acesso vinculada (podem ser None para funcionarios
    # legados sem vinculo - nunca deveria ocorrer em cadastros novos).
    user_id: uuid.UUID | None
    external_subject: str | None
    role: str | None

    model_config = {"from_attributes": True}


class AvailableRolesRead(BaseModel):
    """Papeis de acesso permitidos para um tipo profissional, selecionavel
    no cadastro de funcionario."""

    professional_type: EmployeeProfessionalType
    roles: list[UserRole]


class ClinicalRuleApprovalRead(BaseModel):
    id: uuid.UUID
    approver: str
    decision: str
    justification: str
    decided_at: datetime

    model_config = {"from_attributes": True}


class ClinicalRuleSetSummary(BaseModel):
    id: uuid.UUID
    code: str
    version: str
    population: str
    status: str
    effective_from: date
    effective_to: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClinicalRuleRead(BaseModel):
    """Regra individual dentro de um conjunto, incluindo a expressao
    `when` (armazenada em `ClinicalRuleCondition`, por isso nao vem direto
    de `from_attributes` - e montada explicitamente em
    `app.api.routes.administration._to_rule_set_detail`)."""

    id: uuid.UUID
    rule_key: str
    when: str
    risk_level: int
    classification_label: str
    notes: str | None
    position: int


class ClinicalRuleUpdate(BaseModel):
    """Edicao do conteudo de uma regra. Permitida apenas enquanto o
    conjunto estiver em `draft` (ver
    app.administration.service.update_rule). `when` e revalidado pelo
    parser seguro (`app.rules_engine.evaluator.compile_condition`) antes
    de ser persistido - nunca e avaliado com `eval()`."""

    when: str = Field(..., min_length=1, max_length=2000)
    risk_level: int = Field(..., ge=1, le=6)
    classification_label: str = Field(..., min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class ClinicalRuleActionRead(BaseModel):
    id: uuid.UUID
    risk_level: int
    description: str

    model_config = {"from_attributes": True}


class ClinicalRuleActionUpdate(BaseModel):
    description: str = Field(..., min_length=1, max_length=300)


class ClinicalRuleSetDetail(ClinicalRuleSetSummary):
    required_inputs: list[str]
    exclusions: list[str]
    content_hash: str
    approvals: list[ClinicalRuleApprovalRead]
    rules: list[ClinicalRuleRead]
    actions: list[ClinicalRuleActionRead]


class PublishRuleSetRequest(BaseModel):
    """`approver_employee_id` referencia um `Employee` cadastrado (nunca um
    nome digitado livremente): `app.administration.service.
    publish_rule_set` exige que seja um funcionario ativo com
    `professional_type=MEDICO` da mesma instituicao, e resolve o nome
    exibido na trilha de aprovacao a partir do cadastro."""

    approver_employee_id: uuid.UUID
    justification: str = Field(..., min_length=1)


class RollbackRuleSetRequest(BaseModel):
    approver_employee_id: uuid.UUID
    justification: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """`external_subject` e o identificador estavel da conta de acesso
    (provisionamento real de credencial fica fora deste sistema); este
    endpoint apenas registra o espelho local de instituicao/papel."""

    external_subject: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: UserRole


class UserUpdate(BaseModel):
    role: UserRole | None = None
    active: bool | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    external_subject: str
    full_name: str
    role: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
