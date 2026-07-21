"""Endpoints do modulo de administracao.

Especialidade e funcionario sao administraveis por qualquer administrador
(tecnico ou clinico) - sao dados cadastrais, nao conteudo clinico. A
publicacao/rollback de conjuntos de regras clinicas e restrita ao
administrador clinico: somente ele pode publicar referencias e regras
clinicas.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.administration import service as administration_service
from app.api.schemas.administration import (
    AvailableRolesRead,
    ClinicalRuleActionRead,
    ClinicalRuleActionUpdate,
    ClinicalRuleApprovalRead,
    ClinicalRuleRead,
    ClinicalRuleSetDetail,
    ClinicalRuleSetSummary,
    ClinicalRuleUpdate,
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    MedicalSpecialtyCreate,
    MedicalSpecialtyRead,
    MedicalSpecialtyUpdate,
    PublishRuleSetRequest,
    RevokeSessionsRequest,
    RollbackRuleSetRequest,
    UserRead,
    UserUpdate,
)
from app.api.schemas.common import PageResponse
from app.api.schemas.feature_flags import FeatureFlagsRead, FeatureFlagsUpdate
from app.api.schemas.patients import CareUnitCreate, CareUnitRead, CareUnitUpdate
from app.core.db import get_db_session
from app.core.enums import EmployeeProfessionalType, UserRole
from app.core.security import AuthenticatedUser, require_role
from app.feature_flags import service as feature_flags_service
from app.identity import service as identity_service
from app.identity.models import User

router = APIRouter(prefix="/admin", tags=["administration"])

_require_admin = require_role(UserRole.ADMINISTRADOR_TECNICO, UserRole.ADMINISTRADOR_CLINICO)
_require_clinical_admin = require_role(UserRole.ADMINISTRADOR_CLINICO)


# --- Feature flags (IA/multimodalidade) -------------------------------------


@router.get("/feature-flags", response_model=FeatureFlagsRead)
def get_feature_flags(
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> FeatureFlagsRead:
    flags = feature_flags_service.get_feature_flags(db)
    return FeatureFlagsRead.model_validate(flags)


@router.patch("/feature-flags", response_model=FeatureFlagsRead)
def update_feature_flags(
    data: FeatureFlagsUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> FeatureFlagsRead:
    changes = data.model_dump(exclude_unset=True)
    for enum_field in (
        "llm_provider",
        "image_recognition_provider",
        "sentiment_analysis_provider",
    ):
        if enum_field in changes and changes[enum_field] is not None:
            changes[enum_field] = changes[enum_field].value
    flags = feature_flags_service.update_feature_flags(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        **changes,
    )
    return FeatureFlagsRead.model_validate(flags)


# --- Especialidade medica ---------------------------------------------------


@router.post("/specialties", response_model=MedicalSpecialtyRead, status_code=201)
def create_specialty(
    data: MedicalSpecialtyCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> MedicalSpecialtyRead:
    specialty = administration_service.create_specialty(
        db, current_user.institution_id, data, current_user.external_subject
    )
    return MedicalSpecialtyRead.model_validate(specialty)


@router.get("/specialties", response_model=PageResponse[MedicalSpecialtyRead])
def list_specialties(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=False),
    active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PageResponse[MedicalSpecialtyRead]:
    specialties, total_items = administration_service.list_specialties(
        db,
        current_user.institution_id,
        page,
        page_size,
        active_only=active_only,
        search=search,
        active=active,
    )
    return PageResponse.build(
        items=[MedicalSpecialtyRead.model_validate(s) for s in specialties],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.patch("/specialties/{specialty_id}", response_model=MedicalSpecialtyRead)
def update_specialty(
    specialty_id: uuid.UUID,
    data: MedicalSpecialtyUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> MedicalSpecialtyRead:
    specialty = administration_service.update_specialty(
        db,
        current_user.institution_id,
        specialty_id,
        name=data.name,
        active=data.active,
        actor=current_user.external_subject,
    )
    return MedicalSpecialtyRead.model_validate(specialty)


# --- Funcionarios -----------------------------------------------------------


def _to_employee_read(db: Session, employee) -> EmployeeRead:  # type: ignore[no-untyped-def]
    external_subject = None
    role = None
    if employee.user_id is not None:
        user = db.get(User, employee.user_id)
        if user is not None:
            external_subject = user.external_subject
            role = user.role
    return EmployeeRead(
        id=employee.id,
        full_name=employee.full_name,
        cpf=employee.cpf,
        registration_number=employee.registration_number,
        email=employee.email,
        specialty_id=employee.specialty_id,
        professional_type=employee.professional_type,
        active=employee.active,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
        user_id=employee.user_id,
        external_subject=external_subject,
        role=role,
    )


@router.post("/employees", response_model=EmployeeRead, status_code=201)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> EmployeeRead:
    employee = administration_service.create_employee(
        db, current_user.institution_id, data, current_user.external_subject
    )
    return _to_employee_read(db, employee)


@router.get("/employees", response_model=PageResponse[EmployeeRead])
def list_employees(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=False),
    active: bool | None = Query(default=None),
    search: str | None = Query(
        default=None, max_length=200, description="Substring do nome ou da matricula."
    ),
    professional_type: EmployeeProfessionalType | None = Query(default=None),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PageResponse[EmployeeRead]:
    employees, total_items = administration_service.list_employees(
        db,
        current_user.institution_id,
        page,
        page_size,
        active_only=active_only,
        search=search,
        professional_type=professional_type,
        active=active,
    )
    return PageResponse.build(
        items=[_to_employee_read(db, e) for e in employees],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.get("/employees/available-roles", response_model=AvailableRolesRead)
def get_available_roles(
    professional_type: EmployeeProfessionalType = Query(...),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> AvailableRolesRead:
    """Papeis de acesso selecionaveis no cadastro de funcionario, de
    acordo com o tipo profissional escolhido."""
    roles = administration_service.get_allowed_roles(professional_type)
    return AvailableRolesRead(professional_type=professional_type, roles=list(roles))


@router.get("/employees/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> EmployeeRead:
    employee = administration_service.get_employee(db, current_user.institution_id, employee_id)
    return _to_employee_read(db, employee)


@router.patch("/employees/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> EmployeeRead:
    employee = administration_service.update_employee(
        db, current_user.institution_id, employee_id, data, current_user.external_subject
    )
    return _to_employee_read(db, employee)


# --- Dados clinicos (publicacao/rollback de regras clinicas) ---------------


@router.get("/clinical-rule-sets", response_model=PageResponse[ClinicalRuleSetSummary])
def list_rule_sets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PageResponse[ClinicalRuleSetSummary]:
    rule_sets, total_items = administration_service.list_rule_sets(
        db, page, page_size, code=code, status=status
    )
    return PageResponse.build(
        items=[ClinicalRuleSetSummary.model_validate(rs) for rs in rule_sets],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


def _to_rule_set_detail(rule_set) -> ClinicalRuleSetDetail:  # type: ignore[no-untyped-def]
    """Monta o schema explicitamente em vez de um `model_validate`
    recursivo direto no objeto ORM: `ClinicalRule.when` nao e um atributo
    direto do modelo (vive em `ClinicalRuleCondition.expression`, tabela
    separada - ver docstring de `app.rules_engine.models.
    ClinicalRuleCondition`), e os schemas aninhados (`ClinicalRuleRead`/
    `ClinicalRuleActionRead`) nao tem `from_attributes` habilitado, o que
    faria `model_validate` falhar tentando converter os relacionamentos
    SQLAlchemy automaticamente."""
    return ClinicalRuleSetDetail(
        id=rule_set.id,
        code=rule_set.code,
        version=rule_set.version,
        population=rule_set.population,
        status=rule_set.status,
        effective_from=rule_set.effective_from,
        effective_to=rule_set.effective_to,
        created_at=rule_set.created_at,
        required_inputs=rule_set.required_inputs,
        exclusions=rule_set.exclusions,
        content_hash=rule_set.content_hash,
        approvals=[
            ClinicalRuleApprovalRead.model_validate(approval) for approval in rule_set.approvals
        ],
        rules=[
            ClinicalRuleRead(
                id=rule.id,
                rule_key=rule.rule_key,
                when=rule.condition.expression,
                risk_level=rule.risk_level,
                classification_label=rule.classification_label,
                notes=rule.notes,
                position=rule.position,
            )
            for rule in sorted(rule_set.rules, key=lambda r: r.position)
        ],
        actions=sorted(
            (
                ClinicalRuleActionRead(
                    id=action.id, risk_level=action.risk_level, description=action.description
                )
                for action in rule_set.actions
            ),
            key=lambda a: a.risk_level,
        ),
    )


@router.get("/clinical-rule-sets/{rule_set_id}", response_model=ClinicalRuleSetDetail)
def get_rule_set(
    rule_set_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> ClinicalRuleSetDetail:
    rule_set = administration_service.get_rule_set(db, rule_set_id)
    return _to_rule_set_detail(rule_set)


@router.post("/clinical-rule-sets/{rule_set_id}/publish", response_model=ClinicalRuleSetDetail)
def publish_rule_set(
    rule_set_id: uuid.UUID,
    data: PublishRuleSetRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_admin),
) -> ClinicalRuleSetDetail:
    rule_set = administration_service.publish_rule_set(
        db,
        rule_set_id,
        approver_employee_id=data.approver_employee_id,
        justification=data.justification,
        actor=current_user.external_subject,
        institution_id=current_user.institution_id,
    )
    return _to_rule_set_detail(administration_service.get_rule_set(db, rule_set.id))


@router.post("/clinical-rule-sets/{rule_set_id}/rollback", response_model=ClinicalRuleSetDetail)
def rollback_rule_set(
    rule_set_id: uuid.UUID,
    data: RollbackRuleSetRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_admin),
) -> ClinicalRuleSetDetail:
    rule_set = administration_service.rollback_rule_set(
        db,
        rule_set_id,
        approver_employee_id=data.approver_employee_id,
        justification=data.justification,
        actor=current_user.external_subject,
        institution_id=current_user.institution_id,
    )
    return _to_rule_set_detail(administration_service.get_rule_set(db, rule_set.id))


@router.patch(
    "/clinical-rule-sets/{rule_set_id}/rules/{rule_id}",
    response_model=ClinicalRuleSetDetail,
)
def update_rule(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ClinicalRuleUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_admin),
) -> ClinicalRuleSetDetail:
    """Edita uma regra individual (`when`, nivel de risco, rotulo, notas),
    restrito ao administrador clinico e apenas enquanto o conjunto estiver
    em `draft` (conjuntos publicados sao imutaveis)."""
    rule_set = administration_service.update_rule(
        db,
        rule_set_id,
        rule_id,
        data,
        actor=current_user.external_subject,
        institution_id=current_user.institution_id,
    )
    return _to_rule_set_detail(administration_service.get_rule_set(db, rule_set.id))


@router.patch(
    "/clinical-rule-sets/{rule_set_id}/actions/{action_id}",
    response_model=ClinicalRuleSetDetail,
)
def update_rule_action(
    rule_set_id: uuid.UUID,
    action_id: uuid.UUID,
    data: ClinicalRuleActionUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_clinical_admin),
) -> ClinicalRuleSetDetail:
    """Edita a descricao de conduta associada a um nivel de risco do
    conjunto (mesma restricao de `draft` de `update_rule`)."""
    rule_set = administration_service.update_rule_action(
        db,
        rule_set_id,
        action_id,
        data,
        actor=current_user.external_subject,
        institution_id=current_user.institution_id,
    )
    return _to_rule_set_detail(administration_service.get_rule_set(db, rule_set.id))


# --- Usuarios/papeis de acesso ---------------------------------------------
#
# Sem endpoint de criacao: a conta de acesso (`User`) e criada junto com o
# funcionario (POST /admin/employees) - esta tela agora e apenas
# consulta/gestao de papel e status de contas ja existentes.


@router.get("/users", response_model=PageResponse[UserRead])
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(
        default=None, max_length=255, description="Substring do identificador externo."
    ),
    role: UserRole | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PageResponse[UserRead]:
    users, total_items = administration_service.list_users(
        db,
        current_user.institution_id,
        page,
        page_size,
        search=search,
        role=role,
        active=active,
    )
    return PageResponse.build(
        items=[UserRead.model_validate(u) for u in users],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> UserRead:
    user = administration_service.get_user(db, current_user.institution_id, user_id)
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> UserRead:
    user = administration_service.update_user_role(
        db,
        current_user.institution_id,
        user_id,
        role=data.role,
        active=data.active,
        actor=current_user.external_subject,
    )
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/revoke-sessions", status_code=204)
def revoke_user_sessions(
    user_id: uuid.UUID,
    data: RevokeSessionsRequest,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> None:
    administration_service.revoke_user_sessions(
        db,
        current_user.institution_id,
        user_id,
        actor=current_user.external_subject,
        reason=data.reason,
    )


# --- Unidades assistenciais --------------------------------------------------


@router.post("/care-units", response_model=CareUnitRead, status_code=201)
def create_care_unit(
    data: CareUnitCreate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> CareUnitRead:
    unit = identity_service.create_care_unit(db, current_user.institution_id, data.name)
    db.commit()
    db.refresh(unit)
    return CareUnitRead.model_validate(unit)


@router.get("/care-units", response_model=PageResponse[CareUnitRead])
def list_care_units(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    active_only: bool = Query(default=False),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> PageResponse[CareUnitRead]:
    units, total_items = identity_service.list_care_units(
        db,
        current_user.institution_id,
        page,
        page_size,
        search=search,
        active_only=active_only,
        active=active,
    )
    return PageResponse.build(
        items=[CareUnitRead.model_validate(u) for u in units],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.patch("/care-units/{care_unit_id}", response_model=CareUnitRead)
def update_care_unit(
    care_unit_id: uuid.UUID,
    data: CareUnitUpdate,
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_admin),
) -> CareUnitRead:
    unit = identity_service.update_care_unit(
        db,
        current_user.institution_id,
        care_unit_id,
        name=data.name,
        active=data.active,
    )
    db.commit()
    db.refresh(unit)
    return CareUnitRead.model_validate(unit)
