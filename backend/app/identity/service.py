"""Resolucao de identidade (usuarios/instituicoes) e controles de acesso
reais (bloqueio por tentativa, sessao revogavel, break glass,
unidade/vinculo assistencial).

Mantido separado das rotas HTTP e do adaptador de autenticacao
(`app.core.security`) para que a origem das claims (token Cognito validado,
ou o cabecalho local em dev/testes) seja um detalhe isolado. Nenhuma outra
parte do sistema deve consultar `User`/`Institution` diretamente para fins
de autenticacao.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import ApiError
from app.identity.models import (
    AuthFailedAttempt,
    BreakGlassGrant,
    CareUnit,
    Institution,
    PatientCareAssignment,
    User,
    UserSession,
)


def get_user_by_external_subject(db: Session, external_subject: str) -> User | None:
    return db.scalar(select(User).where(User.external_subject == external_subject))


def get_users_by_external_subjects(
    db: Session, institution_id: uuid.UUID, external_subjects: set[str]
) -> dict[str, User]:
    """Resolve varios `external_subject` de uma vez (ex: coluna "Medico"
    do historico de analises - `Analysis.created_by` guarda apenas o
    external_subject, nao um nome). Usado para exibir nome completo em vez
    do identificador tecnico, sem 1 query por linha da tabela."""
    if not external_subjects:
        return {}
    users = db.scalars(
        select(User).where(
            User.institution_id == institution_id,
            User.external_subject.in_(external_subjects),
        )
    ).all()
    return {user.external_subject: user for user in users}


def list_clinical_staff(db: Session, institution_id: uuid.UUID) -> list[User]:
    """Medicos/enfermeiros ativos da instituicao, para preencher o filtro
    "Medico" do historico de analises."""
    return list(
        db.scalars(
            select(User)
            .where(
                User.institution_id == institution_id,
                User.role.in_([UserRole.MEDICO.value, UserRole.ENFERMEIRO.value]),
                User.active.is_(True),
            )
            .order_by(User.full_name)
        ).all()
    )


def get_or_create_institution(db: Session, name: str) -> Institution:
    institution = db.scalar(select(Institution).where(Institution.name == name))
    if institution is not None:
        return institution
    institution = Institution(name=name)
    db.add(institution)
    db.flush()
    return institution


def get_or_create_user(
    db: Session,
    *,
    institution_id: uuid.UUID,
    external_subject: str,
    full_name: str,
    role: str,
) -> User:
    """Cria o usuario se nao existir; idempotente por `external_subject`.

    Usado hoje pelo script de seed de desenvolvimento
    (`scripts/seed_dev_data.py`) e pelo provisionamento administrativo
    (`app.administration.service` - CRUD de usuarios/papeis).
    """
    user = get_user_by_external_subject(db, external_subject)
    if user is not None:
        return user
    user = User(
        institution_id=institution_id,
        external_subject=external_subject,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


# --- Bloqueio por tentativa --------------------------------------------------


def record_failed_attempt(db: Session, external_subject: str, reason: str) -> None:
    db.add(AuthFailedAttempt(external_subject=external_subject, reason=reason[:100]))
    db.flush()


def is_locked_out(db: Session, external_subject: str) -> bool:
    settings = get_settings()
    window_start = datetime.now(tz=timezone.utc) - timedelta(
        seconds=settings.login_lockout_window_seconds
    )
    recent_failures = db.scalar(
        select(func.count())
        .select_from(AuthFailedAttempt)
        .where(
            AuthFailedAttempt.external_subject == external_subject,
            AuthFailedAttempt.occurred_at >= window_start,
        )
    )
    return int(recent_failures or 0) >= settings.login_max_failed_attempts


# --- Sessoes revogaveis centralmente -----------------------------------------


def register_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_token_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> UserSession:
    """Registra (ou reaproveita) a sessao local associada a um token real.

    `session_token_id` e o identificador estavel do token (claim `jti` do
    Cognito). Isto permite revogar uma sessao especifica antes do JWT
    expirar - `get_current_user` (app.core.security) consulta esta tabela a
    cada requisicao quando o provedor real esta ativo.
    """
    existing = db.scalar(
        select(UserSession).where(UserSession.session_token_id == session_token_id)
    )
    if existing is not None:
        return existing
    session_row = UserSession(
        user_id=user_id,
        session_token_id=session_token_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    db.add(session_row)
    db.flush()
    return session_row


def get_active_session(db: Session, session_token_id: str) -> UserSession | None:
    session_row = db.scalar(
        select(UserSession).where(UserSession.session_token_id == session_token_id)
    )
    if session_row is None:
        return None
    if session_row.revoked_at is not None:
        return None
    if session_row.expires_at <= datetime.now(tz=timezone.utc):
        return None
    return session_row


def revoke_session(
    db: Session, session_id: uuid.UUID, *, revoked_by: str, reason: str
) -> UserSession:
    session_row = db.scalar(select(UserSession).where(UserSession.id == session_id))
    if session_row is None:
        raise ApiError(code="SESSION_NOT_FOUND", message="Sessao nao encontrada.", status_code=404)
    session_row.revoked_at = datetime.now(tz=timezone.utc)
    session_row.revoked_by = revoked_by
    session_row.revoke_reason = reason
    db.flush()
    return session_row


def revoke_all_sessions_for_user(
    db: Session, user_id: uuid.UUID, *, revoked_by: str, reason: str
) -> int:
    sessions = list(
        db.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
            )
        ).all()
    )
    now = datetime.now(tz=timezone.utc)
    for session_row in sessions:
        session_row.revoked_at = now
        session_row.revoked_by = revoked_by
        session_row.revoke_reason = reason
    db.flush()
    return len(sessions)


# --- Unidade e vinculo assistencial ------------------------------------------


def has_active_assignment(
    db: Session, *, institution_id: uuid.UUID, user_id: uuid.UUID, patient_id: uuid.UUID
) -> bool:
    assignment = db.scalar(
        select(PatientCareAssignment).where(
            PatientCareAssignment.institution_id == institution_id,
            PatientCareAssignment.user_id == user_id,
            PatientCareAssignment.patient_id == patient_id,
            PatientCareAssignment.active.is_(True),
        )
    )
    return assignment is not None


def has_active_break_glass_grant(
    db: Session, *, user_id: uuid.UUID, patient_id: uuid.UUID
) -> BreakGlassGrant | None:
    grant = db.scalar(
        select(BreakGlassGrant)
        .where(
            BreakGlassGrant.user_id == user_id,
            BreakGlassGrant.patient_id == patient_id,
            BreakGlassGrant.revoked_at.is_(None),
            BreakGlassGrant.expires_at > datetime.now(tz=timezone.utc),
        )
        .order_by(BreakGlassGrant.granted_at.desc())
    )
    return grant


def create_care_unit(db: Session, institution_id: uuid.UUID, name: str) -> CareUnit:
    unit = CareUnit(institution_id=institution_id, name=name.strip())
    db.add(unit)
    db.flush()
    return unit


def _get_care_unit(db: Session, institution_id: uuid.UUID, care_unit_id: uuid.UUID) -> CareUnit:
    unit = db.scalar(
        select(CareUnit).where(
            CareUnit.id == care_unit_id, CareUnit.institution_id == institution_id
        )
    )
    if unit is None:
        raise ApiError(
            code="CARE_UNIT_NOT_FOUND",
            message="Unidade assistencial nao encontrada.",
            status_code=404,
        )
    return unit


def update_care_unit(
    db: Session,
    institution_id: uuid.UUID,
    care_unit_id: uuid.UUID,
    *,
    name: str | None,
    active: bool | None,
) -> CareUnit:
    """Atualiza nome e/ou status de uma unidade assistencial existente.

    Nunca remove o registro (mesmo principio de nao-destrutividade das
    demais entidades de administracao) - `active=False` apenas encerra o
    uso da unidade para novos vinculos, sem apagar historico associado.
    """
    unit = _get_care_unit(db, institution_id, care_unit_id)
    if name is not None:
        unit.name = name.strip()
    if active is not None:
        unit.active = active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            code="DUPLICATE_CARE_UNIT_NAME",
            message="Ja existe uma unidade assistencial com este nome nesta instituicao.",
            status_code=409,
            field_errors={"name": "Unidade ja cadastrada."},
        ) from exc
    return unit


def list_care_units(
    db: Session,
    institution_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    search: str | None = None,
    active_only: bool = False,
    active: bool | None = None,
) -> tuple[list[CareUnit], int]:
    """`active` e um filtro tri-state explicito (None = qualquer status);
    `active_only` fica mantido por compatibilidade, mas `active` tem
    precedencia quando informado."""
    filters = [CareUnit.institution_id == institution_id]
    if active is not None:
        filters.append(CareUnit.active.is_(active))
    elif active_only:
        filters.append(CareUnit.active.is_(True))
    if search:
        filters.append(CareUnit.name.ilike(f"%{search.strip()}%"))

    total_items = db.scalar(select(func.count()).select_from(CareUnit).where(*filters))
    items = db.scalars(
        select(CareUnit)
        .where(*filters)
        .order_by(CareUnit.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), int(total_items or 0)


def create_patient_care_assignment(
    db: Session,
    *,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    user_id: uuid.UUID,
    care_unit_id: uuid.UUID | None,
    assigned_by: str,
) -> PatientCareAssignment:
    assignment = PatientCareAssignment(
        institution_id=institution_id,
        patient_id=patient_id,
        user_id=user_id,
        care_unit_id=care_unit_id,
        assigned_by=assigned_by,
    )
    db.add(assignment)
    db.flush()
    return assignment


def end_patient_care_assignment(db: Session, assignment_id: uuid.UUID) -> PatientCareAssignment:
    assignment = db.scalar(
        select(PatientCareAssignment).where(PatientCareAssignment.id == assignment_id)
    )
    if assignment is None:
        raise ApiError(
            code="CARE_ASSIGNMENT_NOT_FOUND",
            message="Vinculo assistencial nao encontrado.",
            status_code=404,
        )
    assignment.active = False
    assignment.ended_at = datetime.now(tz=timezone.utc)
    db.flush()
    return assignment


def create_break_glass_grant(
    db: Session,
    *,
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    justification: str,
    duration_seconds: int,
) -> BreakGlassGrant:
    now = datetime.now(tz=timezone.utc)
    grant = BreakGlassGrant(
        institution_id=institution_id,
        user_id=user_id,
        patient_id=patient_id,
        justification=justification,
        expires_at=now + timedelta(seconds=duration_seconds),
    )
    db.add(grant)
    db.flush()
    return grant
