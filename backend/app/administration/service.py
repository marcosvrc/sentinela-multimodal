"""Regras de negocio do modulo de administracao.

Tres blocos:

1. Especialidade medica (`MedicalSpecialty`) - CRUD simples por instituicao.
2. Funcionarios/medicos (`Employee`) - CRUD por instituicao, com CPF e
   matricula unicos por instituicao, vinculo opcional a especialidade e a
   um `User` (conta de acesso).
3. Dados clinicos (`ClinicalRuleSet`, ja existente) - nao e um CRUD de
   conteudo (a estrutura de regra continua vindo do fluxo
   YAML -> validacao -> seed); o que faltava era o fluxo de
   publicacao formal: somente o administrador clinico pode publicar
   referencias e regras clinicas, e toda mudanca deve possuir versao,
   justificativa, fonte, aprovador, vigencia e possibilidade de rollback -
   `publish_rule_set`/`rollback_rule_set` fecham exatamente essa lacuna,
   documentada em `app.rules_engine.service`.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.administration.models import Employee, MedicalSpecialty
from app.api.schemas.administration import (
    ClinicalRuleActionUpdate,
    ClinicalRuleUpdate,
    EmployeeCreate,
    EmployeeUpdate,
    MedicalSpecialtyCreate,
)
from app.audit import service as audit_service
from app.core.enums import (
    AuditCategory,
    AuditResult,
    ClinicalRuleSetStatus,
    EmployeeProfessionalType,
    UserRole,
)
from app.core.errors import ApiError
from app.identity import service as identity_service
from app.identity.models import User
from app.rules_engine.evaluator import UnsafeExpressionError, compile_condition
from app.rules_engine.models import ClinicalRuleApproval, ClinicalRuleSet
from clinical_rules.seeding import compute_content_hash

# Papeis de acesso permitidos por tipo profissional: um Enfermeiro so pode
# ocupar o papel ENFERMEIRO; um Medico pode ocupar o papel clinico MEDICO ou
# qualquer papel administrativo/de auditoria - a instituicao NAO tem um
# quadro separado de "administradores" sem formacao medica neste MVP.
ALLOWED_ROLES_BY_PROFESSIONAL_TYPE: dict[EmployeeProfessionalType, tuple[UserRole, ...]] = {
    EmployeeProfessionalType.MEDICO: (
        UserRole.MEDICO,
        UserRole.ADMINISTRADOR_TECNICO,
        UserRole.ADMINISTRADOR_CLINICO,
        UserRole.AUDITOR,
    ),
    EmployeeProfessionalType.ENFERMEIRO: (UserRole.ENFERMEIRO,),
}


def get_allowed_roles(professional_type: EmployeeProfessionalType) -> tuple[UserRole, ...]:
    return ALLOWED_ROLES_BY_PROFESSIONAL_TYPE[professional_type]


def _validate_role_for_professional_type(
    professional_type: EmployeeProfessionalType, role: UserRole
) -> None:
    allowed = ALLOWED_ROLES_BY_PROFESSIONAL_TYPE[professional_type]
    if role not in allowed:
        raise ApiError(
            code="ROLE_NOT_ALLOWED_FOR_PROFESSIONAL_TYPE",
            message=(
                f"O papel '{role.value}' nao e permitido para o tipo profissional "
                f"'{professional_type.value}'. Papeis permitidos: "
                f"{', '.join(r.value for r in allowed)}."
            ),
            status_code=422,
            field_errors={"role": "Papel incompativel com o tipo profissional."},
        )

# --- Especialidade medica ---------------------------------------------------


def create_specialty(
    db: Session, institution_id: uuid.UUID, data: MedicalSpecialtyCreate, actor: str
) -> MedicalSpecialty:
    specialty = MedicalSpecialty(institution_id=institution_id, name=data.name.strip())
    db.add(specialty)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_SPECIALTY_NAME",
            message="Ja existe uma especialidade com este nome nesta instituicao.",
            status_code=409,
            field_errors={"name": "Especialidade ja cadastrada."},
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="SPECIALTY_CREATE",
        resource_type="medical_specialty",
        resource_id=str(specialty.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
    )
    db.commit()
    db.refresh(specialty)
    return specialty


def list_specialties(
    db: Session,
    institution_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    active_only: bool = False,
    search: str | None = None,
    active: bool | None = None,
) -> tuple[list[MedicalSpecialty], int]:
    """`active` e um filtro tri-state explicito (None = qualquer status,
    True/False = so ativas/inativas) - `active_only` e mantido por
    compatibilidade com chamadores existentes, mas `active` tem
    precedencia quando informado."""
    tenant_filter = [MedicalSpecialty.institution_id == institution_id]
    if active is not None:
        tenant_filter.append(MedicalSpecialty.active.is_(active))
    elif active_only:
        tenant_filter.append(MedicalSpecialty.active.is_(True))
    if search:
        tenant_filter.append(MedicalSpecialty.name.ilike(f"%{search.strip()}%"))

    total_items = db.scalar(
        select(func.count()).select_from(MedicalSpecialty).where(*tenant_filter)
    )
    items = db.scalars(
        select(MedicalSpecialty)
        .where(*tenant_filter)
        .order_by(MedicalSpecialty.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def _get_specialty(
    db: Session, institution_id: uuid.UUID, specialty_id: uuid.UUID
) -> MedicalSpecialty:
    specialty = db.scalar(
        select(MedicalSpecialty).where(
            MedicalSpecialty.id == specialty_id,
            MedicalSpecialty.institution_id == institution_id,
        )
    )
    if specialty is None:
        raise ApiError(
            code="SPECIALTY_NOT_FOUND",
            message="Especialidade nao encontrada.",
            status_code=404,
        )
    return specialty


def update_specialty(
    db: Session,
    institution_id: uuid.UUID,
    specialty_id: uuid.UUID,
    *,
    name: str | None,
    active: bool | None,
    actor: str,
) -> MedicalSpecialty:
    specialty = _get_specialty(db, institution_id, specialty_id)
    if name is not None:
        specialty.name = name.strip()
    if active is not None:
        specialty.active = active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_SPECIALTY_NAME",
            message="Ja existe uma especialidade com este nome nesta instituicao.",
            status_code=409,
            field_errors={"name": "Especialidade ja cadastrada."},
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="SPECIALTY_UPDATE",
        resource_type="medical_specialty",
        resource_id=str(specialty.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
    )
    db.commit()
    db.refresh(specialty)
    return specialty


# --- Funcionarios (medicos) -------------------------------------------------

# Validacao de formato (11 digitos, apos remover mascara) + digitos
# verificadores do CPF (algoritmo publico, modulo 11) - nao consulta a
# Receita Federal nem confirma que o CPF existe/pertence a pessoa; apenas
# rejeita valores estruturalmente invalidos antes de persistir.
_CPF_DIGITS_RE = re.compile(r"\D")


def _cpf_digits(cpf: str) -> str:
    return _CPF_DIGITS_RE.sub("", cpf)


def is_valid_cpf(cpf: str) -> bool:
    digits = _cpf_digits(cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    for check_position in (9, 10):
        total = sum(
            int(digit) * weight
            for digit, weight in zip(
                digits[:check_position], range(check_position + 1, 1, -1), strict=True
            )
        )
        expected = (total * 10) % 11
        expected = 0 if expected == 10 else expected
        if expected != int(digits[check_position]):
            return False
    return True


def create_employee(
    db: Session, institution_id: uuid.UUID, data: EmployeeCreate, actor: str
) -> Employee:
    """Cadastra o funcionario E a conta de acesso (`User`) vinculada na
    mesma operacao: cadastrar o funcionario passou a exigir escolher o
    papel de acesso dele, em vez de criar o usuario separadamente pela
    tela de Usuarios. O papel deve ser compativel com `professional_type`
    (`ALLOWED_ROLES_BY_PROFESSIONAL_TYPE`) - um Enfermeiro nunca pode
    receber um papel administrativo."""
    if not is_valid_cpf(data.cpf):
        raise ApiError(
            code="INVALID_CPF",
            message="CPF invalido.",
            status_code=422,
            field_errors={"cpf": "Numero de CPF invalido."},
        )

    _validate_role_for_professional_type(data.professional_type, data.role)

    if data.specialty_id is not None:
        _get_specialty(db, institution_id, data.specialty_id)

    if identity_service.get_user_by_external_subject(db, data.external_subject) is not None:
        raise ApiError(
            code="DUPLICATE_USER",
            message="Ja existe um usuario com este identificador externo.",
            status_code=409,
            field_errors={"external_subject": "Identificador ja cadastrado."},
        )

    user = User(
        institution_id=institution_id,
        external_subject=data.external_subject,
        full_name=data.full_name.strip(),
        role=data.role.value,
    )
    db.add(user)
    db.flush()

    employee = Employee(
        institution_id=institution_id,
        user_id=user.id,
        specialty_id=data.specialty_id,
        full_name=data.full_name.strip(),
        cpf=_cpf_digits(data.cpf),
        registration_number=data.registration_number.strip(),
        email=data.email,
        professional_type=data.professional_type.value,
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_EMPLOYEE",
            message="Ja existe um funcionario com este CPF ou matricula nesta instituicao.",
            status_code=409,
            field_errors={"cpf": "CPF ou matricula ja cadastrados nesta instituicao."},
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="EMPLOYEE_CREATE",
        resource_type="employee",
        resource_id=str(employee.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={"role": data.role.value, "professional_type": data.professional_type.value},
    )
    db.commit()
    db.refresh(employee)
    return employee


def list_employees(
    db: Session,
    institution_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    active_only: bool = False,
    search: str | None = None,
    professional_type: EmployeeProfessionalType | None = None,
    active: bool | None = None,
) -> tuple[list[Employee], int]:
    """`search` casa por substring (case-insensitive) em nome OU matricula -
    a mesma caixa de busca serve para os dois campos (mesmo padrao de
    `patients_service.list_patients`). `active` e um filtro tri-state
    explicito (None = qualquer status); `active_only` fica mantido por
    compatibilidade, mas `active` tem precedencia quando informado."""
    tenant_filter = [Employee.institution_id == institution_id]
    if active is not None:
        tenant_filter.append(Employee.active.is_(active))
    elif active_only:
        tenant_filter.append(Employee.active.is_(True))
    if professional_type is not None:
        tenant_filter.append(Employee.professional_type == professional_type.value)
    if search:
        pattern = f"%{search.strip()}%"
        tenant_filter.append(
            Employee.full_name.ilike(pattern) | Employee.registration_number.ilike(pattern)
        )

    total_items = db.scalar(select(func.count()).select_from(Employee).where(*tenant_filter))
    items = db.scalars(
        select(Employee)
        .where(*tenant_filter)
        .order_by(Employee.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def get_registration_numbers_by_user_id(
    db: Session, institution_id: uuid.UUID, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Mapa `User.id` -> `Employee.registration_number` (matricula) para o
    conjunto de usuarios informado, usado para exibir "matricula - nome"
    no campo de funcionario pesquisavel (registro de observacao clinica) e
    em outras listas que hoje so tem o nome do usuario disponivel. Usuarios
    sem funcionario administrativo vinculado simplesmente nao aparecem no
    mapa retornado."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(Employee.user_id, Employee.registration_number).where(
            Employee.institution_id == institution_id,
            Employee.user_id.in_(user_ids),
        )
    ).all()
    return {user_id: registration_number for user_id, registration_number in rows}


def get_active_doctor_for_approval(
    db: Session, institution_id: uuid.UUID, employee_id: uuid.UUID
) -> Employee:
    """Resolve o funcionario que assina como aprovador de uma publicacao/
    rollback de conjunto de regras clinicas (`publish_rule_set`/
    `rollback_rule_set`). So aceita medico ativo cadastrado nesta
    instituicao - nunca um nome digitado livremente: somente o
    administrador clinico pode publicar regras clinicas, mas quem *assina*
    a aprovacao clinica no texto e um medico do quadro, nao necessariamente
    quem clicou no botao."""
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.institution_id == institution_id,
        )
    )
    if employee is None:
        raise ApiError(
            code="APPROVER_NOT_FOUND",
            message="Aprovador nao encontrado.",
            status_code=404,
            field_errors={"approver_employee_id": "Funcionario nao encontrado."},
        )
    if employee.professional_type != EmployeeProfessionalType.MEDICO.value:
        raise ApiError(
            code="APPROVER_MUST_BE_DOCTOR",
            message="Apenas medicos cadastrados podem ser selecionados como aprovador.",
            status_code=422,
            field_errors={"approver_employee_id": "Selecione um medico cadastrado."},
        )
    if not employee.active:
        raise ApiError(
            code="APPROVER_INACTIVE",
            message="O medico selecionado como aprovador esta inativo.",
            status_code=422,
            field_errors={"approver_employee_id": "Selecione um medico ativo."},
        )
    return employee


def get_employee(db: Session, institution_id: uuid.UUID, employee_id: uuid.UUID) -> Employee:
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.institution_id == institution_id
        )
    )
    if employee is None:
        raise ApiError(
            code="EMPLOYEE_NOT_FOUND", message="Funcionario nao encontrado.", status_code=404
        )
    return employee


def update_employee(
    db: Session,
    institution_id: uuid.UUID,
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    actor: str,
) -> Employee:
    employee = get_employee(db, institution_id, employee_id)

    if data.full_name is not None:
        employee.full_name = data.full_name.strip()
    if data.email is not None:
        employee.email = data.email
    if data.specialty_id is not None:
        _get_specialty(db, institution_id, data.specialty_id)
        employee.specialty_id = data.specialty_id
    if data.active is not None:
        employee.active = data.active

    if data.role is not None:
        professional_type = EmployeeProfessionalType(employee.professional_type)
        _validate_role_for_professional_type(professional_type, data.role)
        if employee.user_id is not None:
            update_user_role(
                db,
                institution_id,
                employee.user_id,
                role=data.role,
                active=None,
                actor=actor,
            )

    # Desativar o funcionario tambem desativa a conta de acesso vinculada
    # (nao ha motivo assistencial para um funcionario inativo continuar
    # autenticando); reativar o funcionario NAO reativa o acesso
    # automaticamente - isso exige uma decisao explicita na tela de
    # Usuarios, para nao reabrir acesso silenciosamente.
    if data.active is False and employee.user_id is not None:
        update_user_role(
            db, institution_id, employee.user_id, role=None, active=False, actor=actor
        )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_EMPLOYEE",
            message="Ja existe um funcionario com este CPF ou matricula nesta instituicao.",
            status_code=409,
        ) from exc

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="EMPLOYEE_UPDATE",
        resource_type="employee",
        resource_id=str(employee.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
    )
    db.commit()
    db.refresh(employee)
    return employee


# --- Dados clinicos (publicacao/rollback de ClinicalRuleSet) ---------------


def list_rule_sets(
    db: Session,
    page: int,
    page_size: int,
    *,
    code: str | None = None,
    status: str | None = None,
) -> tuple[list[ClinicalRuleSet], int]:
    filters = []
    if code:
        filters.append(ClinicalRuleSet.code == code)
    if status:
        filters.append(ClinicalRuleSet.status == status)

    total_items = db.scalar(
        select(func.count()).select_from(ClinicalRuleSet).where(*filters)
    )
    items = db.scalars(
        select(ClinicalRuleSet)
        .where(*filters)
        .order_by(ClinicalRuleSet.code, ClinicalRuleSet.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def get_rule_set(db: Session, rule_set_id: uuid.UUID) -> ClinicalRuleSet:
    rule_set = db.scalar(
        select(ClinicalRuleSet)
        .options(
            selectinload(ClinicalRuleSet.sources),
            selectinload(ClinicalRuleSet.approvals),
            selectinload(ClinicalRuleSet.rules),
            selectinload(ClinicalRuleSet.actions),
        )
        .where(ClinicalRuleSet.id == rule_set_id)
    )
    if rule_set is None:
        raise ApiError(
            code="RULE_SET_NOT_FOUND",
            message="Conjunto de regras clinicas nao encontrado.",
            status_code=404,
        )
    return rule_set


def _rule_set_content_for_hash(rule_set: ClinicalRuleSet) -> dict:
    """Serializacao canonica do conteudo do conjunto, no mesmo formato
    usado pelo seed (`clinical_rules.seeding.compute_content_hash`), mas
    lendo direto das linhas ja persistidas em vez do YAML original -
    usada para recalcular `content_hash` apos uma edicao via UI mantendo
    o mesmo criterio de hash que o `cli.py seed` usa para detectar
    conflito. Inclui apenas os campos que tambem entram no hash do YAML
    (code, version, population, rules) - sources/status/vigencia nao
    fazem parte do conteudo hasheado no seed original."""
    return {
        "code": rule_set.code,
        "version": rule_set.version,
        "population": rule_set.population,
        "required_inputs": sorted(rule_set.required_inputs),
        "exclusions": sorted(rule_set.exclusions),
        "rules": [
            {
                "id": rule.rule_key,
                "when": rule.condition.expression,
                "risk_level": rule.risk_level,
                "classification_label": rule.classification_label,
                "notes": rule.notes,
            }
            for rule in sorted(rule_set.rules, key=lambda r: r.position)
        ],
    }


def update_rule(
    db: Session,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ClinicalRuleUpdate,
    *,
    actor: str,
    institution_id: uuid.UUID,
) -> ClinicalRuleSet:
    """Edita o conteudo de uma regra (`when`, nivel de risco, rotulo,
    notas), permitido apenas enquanto o conjunto estiver em `draft`
    (conjuntos publicados sao imutaveis - mesma invariante de
    `publish_rule_set`). A expressao `when` e revalidada pelo parser
    seguro antes de ser salva (nunca confiar em texto vindo da UI sem
    reparsear); `content_hash` e recalculado a cada edicao, mantendo
    consistente a detecao de divergencia do `cli.py seed` (rodar o seed
    de novo depois de uma edicao via UI vai apontar CONFLITO ao inves de
    SEM MUDANCA - esperado, pois o conteudo realmente diverge do YAML)."""
    rule_set = get_rule_set(db, rule_set_id)
    if rule_set.status != ClinicalRuleSetStatus.DRAFT.value:
        raise ApiError(
            code="RULE_SET_NOT_DRAFT",
            message=(
                f"Conjunto esta em status '{rule_set.status}'; apenas conjuntos em "
                "'draft' podem ter regras editadas."
            ),
            status_code=409,
        )

    rule = next((r for r in rule_set.rules if r.id == rule_id), None)
    if rule is None:
        raise ApiError(
            code="RULE_NOT_FOUND",
            message="Regra nao encontrada neste conjunto.",
            status_code=404,
        )

    try:
        compile_condition(data.when)
    except UnsafeExpressionError as exc:
        raise ApiError(
            code="UNSAFE_RULE_EXPRESSION",
            message="Expressao da condicao (when) invalida ou nao permitida.",
            status_code=422,
            field_errors={"when": str(exc)},
        ) from exc

    rule.condition.expression = data.when
    rule.risk_level = data.risk_level
    rule.classification_label = data.classification_label.strip()
    rule.notes = data.notes.strip() if data.notes else None
    db.flush()

    rule_set.content_hash = compute_content_hash(_rule_set_content_for_hash(rule_set))

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="CLINICAL_RULE_UPDATE",
        resource_type="clinical_rule",
        resource_id=str(rule.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={"rule_set_id": str(rule_set.id), "rule_key": rule.rule_key},
    )
    db.commit()
    db.refresh(rule_set)
    return rule_set


def update_rule_action(
    db: Session,
    rule_set_id: uuid.UUID,
    action_id: uuid.UUID,
    data: ClinicalRuleActionUpdate,
    *,
    actor: str,
    institution_id: uuid.UUID,
) -> ClinicalRuleSet:
    """Edita a descricao de conduta associada a um nivel de risco do
    conjunto. Mesma restricao de imutabilidade apos publicacao que
    `update_rule` - a conduta nao entra no `content_hash` (nao faz parte
    do YAML original, e derivada de `risk_levels.meaning`), por isso essa
    edicao nao recalcula o hash."""
    rule_set = get_rule_set(db, rule_set_id)
    if rule_set.status != ClinicalRuleSetStatus.DRAFT.value:
        raise ApiError(
            code="RULE_SET_NOT_DRAFT",
            message=(
                f"Conjunto esta em status '{rule_set.status}'; apenas conjuntos em "
                "'draft' podem ter condutas editadas."
            ),
            status_code=409,
        )

    action = next((a for a in rule_set.actions if a.id == action_id), None)
    if action is None:
        raise ApiError(
            code="RULE_ACTION_NOT_FOUND",
            message="Conduta nao encontrada neste conjunto.",
            status_code=404,
        )

    action.description = data.description.strip()
    db.flush()

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="CLINICAL_RULE_ACTION_UPDATE",
        resource_type="clinical_rule_action",
        resource_id=str(action.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={"rule_set_id": str(rule_set.id), "risk_level": action.risk_level},
    )
    db.commit()
    db.refresh(rule_set)
    return rule_set


def publish_rule_set(
    db: Session,
    rule_set_id: uuid.UUID,
    *,
    approver_employee_id: uuid.UUID,
    justification: str,
    actor: str,
    institution_id: uuid.UUID,
) -> ClinicalRuleSet:
    """Publica um conjunto em `draft`, tornando-o candidato a vigente para
    seu `code`/`population` (`app.rules_engine.service.get_current_rule_set`
    so considera conjuntos `PUBLISHED`). Nao altera o conteudo do
    conjunto - ele permanece imutavel (mesmo `content_hash`); apenas o
    `status` muda, e a decisao entra na trilha de aprovacao
    (`ClinicalRuleApproval`).

    `approver_employee_id` precisa ser um medico ativo cadastrado nesta
    instituicao (`get_active_doctor_for_approval`) - nunca um nome de
    texto livre, para que a trilha de aprovacao sempre referencie um
    profissional real e verificavel.

    Qualquer outro conjunto hoje `PUBLISHED` para o mesmo `code`/
    `population` e automaticamente aposentado (`RETIRED`): so uma versao
    fica vigente por vez, e a anterior nunca e apagada nem reescrita -
    apenas transiciona de estado, o que tambem e o que torna
    `rollback_rule_set` possivel (ele exige um alvo `RETIRED`)."""
    approver_employee = get_active_doctor_for_approval(db, institution_id, approver_employee_id)
    approver = f"{approver_employee.full_name} ({approver_employee.registration_number})"
    rule_set = get_rule_set(db, rule_set_id)
    if rule_set.status != ClinicalRuleSetStatus.DRAFT.value:
        raise ApiError(
            code="RULE_SET_NOT_DRAFT",
            message=(
                f"Conjunto esta em status '{rule_set.status}'; apenas conjuntos em "
                "'draft' podem ser publicados."
            ),
            status_code=409,
        )

    previously_published = db.scalars(
        select(ClinicalRuleSet).where(
            ClinicalRuleSet.code == rule_set.code,
            ClinicalRuleSet.population == rule_set.population,
            ClinicalRuleSet.status == ClinicalRuleSetStatus.PUBLISHED.value,
        )
    ).all()
    for superseded in previously_published:
        superseded.status = ClinicalRuleSetStatus.RETIRED.value
        db.add(
            ClinicalRuleApproval(
                rule_set_id=superseded.id,
                approver=approver,
                decision="retired_by_new_publication",
                justification=justification,
            )
        )

    rule_set.status = ClinicalRuleSetStatus.PUBLISHED.value
    db.add(
        ClinicalRuleApproval(
            rule_set_id=rule_set.id,
            approver=approver,
            decision="published",
            justification=justification,
        )
    )

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="CLINICAL_RULE_SET_PUBLISH",
        resource_type="clinical_rule_set",
        resource_id=str(rule_set.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        justification=justification,
    )
    db.commit()
    db.refresh(rule_set)
    return rule_set


def rollback_rule_set(
    db: Session,
    rule_set_id: uuid.UUID,
    *,
    approver_employee_id: uuid.UUID,
    justification: str,
    actor: str,
    institution_id: uuid.UUID,
) -> ClinicalRuleSet:
    """Restaura um conjunto `retired` (anteriormente publicado e depois
    substituido) de volta a `published`, e aposenta (`RETIRED`) o conjunto
    hoje publicado para o mesmo `code`/`population`, se houver algum. Nunca
    apaga nem reescreve conteudo - apenas transiciona `status`, preservando
    ambas as versoes e a trilha de aprovacao completa, garantindo a
    possibilidade de rollback. Mesma validacao de aprovador de
    `publish_rule_set`: `approver_employee_id` precisa ser um medico
    ativo cadastrado."""
    approver_employee = get_active_doctor_for_approval(db, institution_id, approver_employee_id)
    approver = f"{approver_employee.full_name} ({approver_employee.registration_number})"
    target = get_rule_set(db, rule_set_id)
    if target.status != ClinicalRuleSetStatus.RETIRED.value:
        raise ApiError(
            code="RULE_SET_NOT_RETIRED",
            message=(
                f"Conjunto esta em status '{target.status}'; apenas conjuntos 'retired' "
                "podem ser restaurados por rollback."
            ),
            status_code=409,
        )

    currently_published = db.scalars(
        select(ClinicalRuleSet).where(
            ClinicalRuleSet.code == target.code,
            ClinicalRuleSet.population == target.population,
            ClinicalRuleSet.status == ClinicalRuleSetStatus.PUBLISHED.value,
        )
    ).all()
    for rule_set in currently_published:
        rule_set.status = ClinicalRuleSetStatus.RETIRED.value
        db.add(
            ClinicalRuleApproval(
                rule_set_id=rule_set.id,
                approver=approver,
                decision="retired_by_rollback",
                justification=justification,
            )
        )

    target.status = ClinicalRuleSetStatus.PUBLISHED.value
    db.add(
        ClinicalRuleApproval(
            rule_set_id=target.id,
            approver=approver,
            decision="rollback",
            justification=justification,
        )
    )

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="CLINICAL_RULE_SET_ROLLBACK",
        resource_type="clinical_rule_set",
        resource_id=str(target.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        justification=justification,
    )
    db.commit()
    db.refresh(target)
    return target


# --- Usuarios/papeis de acesso ----------------------------------------------
#
# Fecha a lacuna do CRUD de usuarios/papeis de acesso propriamente dito. O
# provisionamento real de CREDENCIAL (senha/MFA) continua no Cognito, fora
# deste modulo - aqui vive apenas o espelho local (`app.identity.models.User`)
# que determina instituicao/papel para autorizacao, mesma tabela que
# `app.core.security.get_current_user` sempre consultou. Criar o usuario
# aqui e o equivalente a "AdminCreateUser" do Cognito (ver
# `admin_create_user_config.allow_admin_create_user_only = true` no modulo
# Terraform de identidade) - o restante do provisionamento de credencial
# (convite, senha temporaria, MFA) acontece no proprio Cognito.


def create_user(
    db: Session,
    institution_id: uuid.UUID,
    *,
    external_subject: str,
    full_name: str,
    role: UserRole,
    actor: str,
) -> User:
    existing = identity_service.get_user_by_external_subject(db, external_subject)
    if existing is not None:
        raise ApiError(
            code="DUPLICATE_USER",
            message="Ja existe um usuario com este identificador externo.",
            status_code=409,
            field_errors={"external_subject": "Identificador ja cadastrado."},
        )

    user = User(
        institution_id=institution_id,
        external_subject=external_subject,
        full_name=full_name.strip(),
        role=role.value,
    )
    db.add(user)
    db.flush()

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="USER_CREATE",
        resource_type="user",
        resource_id=str(user.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={"role": role.value},
    )
    db.commit()
    db.refresh(user)
    return user


def list_users(
    db: Session,
    institution_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    search: str | None = None,
    role: UserRole | None = None,
    active: bool | None = None,
) -> tuple[list[User], int]:
    """`search` casa por substring (case-insensitive) no identificador
    externo - a tela de Usuarios nao exibe mais nome (essa informacao vive
    no cadastro de Funcionario)."""
    filters = [User.institution_id == institution_id]
    if search:
        filters.append(User.external_subject.ilike(f"%{search.strip()}%"))
    if role is not None:
        filters.append(User.role == role.value)
    if active is not None:
        filters.append(User.active.is_(active))

    total_items = db.scalar(select(func.count()).select_from(User).where(*filters))
    items = db.scalars(
        select(User)
        .where(*filters)
        .order_by(User.external_subject)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def get_user(db: Session, institution_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = db.scalar(
        select(User).where(User.id == user_id, User.institution_id == institution_id)
    )
    if user is None:
        raise ApiError(code="USER_NOT_FOUND", message="Usuario nao encontrado.", status_code=404)
    return user


def update_user_role(
    db: Session,
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    role: UserRole | None,
    active: bool | None,
    actor: str,
) -> User:
    """Altera papel e/ou desativa um usuario. Desativar um usuario nunca o
    apaga (auditoria/analises passadas continuam apontando para o mesmo
    `external_subject`); apenas impede novas autenticacoes
    (`app.core.security._get_current_user_cognito` rejeita `active=False`).
    Qualquer mudanca de papel revoga TODAS as sessoes ativas do usuario -
    a autorizacao de uma sessao ja aberta nunca deve ficar defasada em
    relacao ao papel atual: sessoes devem ser revogaveis centralmente.
    """
    user = get_user(db, institution_id, user_id)
    role_changed = role is not None and role.value != user.role

    if role is not None:
        user.role = role.value
    if active is not None:
        user.active = active

    if role_changed or active is False:
        identity_service.revoke_all_sessions_for_user(
            db,
            user_id,
            revoked_by=actor,
            reason="Papel alterado ou usuario desativado pela administracao.",
        )

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ADMINISTRATION,
        action="USER_UPDATE",
        resource_type="user",
        resource_id=str(user.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        event_metadata={"role": user.role, "active": user.active},
    )
    db.commit()
    db.refresh(user)
    return user


def revoke_user_sessions(
    db: Session, institution_id: uuid.UUID, user_id: uuid.UUID, *, actor: str, reason: str
) -> int:
    get_user(db, institution_id, user_id)
    count = identity_service.revoke_all_sessions_for_user(
        db, user_id, revoked_by=actor, reason=reason
    )
    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.AUTHORIZATION,
        action="USER_SESSIONS_REVOKED",
        resource_type="user",
        resource_id=str(user_id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        justification=reason,
        event_metadata={"revoked_count": count},
    )
    db.commit()
    return count
