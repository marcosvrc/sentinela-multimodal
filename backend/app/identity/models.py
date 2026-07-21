"""Modelos de identidade, institucao (tenant) e controles de acesso reais.

`Institution`/`User` seguem o espelho local original (o token Cognito traz
apenas um `sub` verificado; instituicao e papel sempre vem daqui - ver
`app.core.security.get_current_user`). As demais tabelas implementam os
controles de acesso reais que dependiam de identidade real:

- `CareUnit`/`PatientCareAssignment`: o eixo "unidade" e "vinculo
  assistencial" da autorizacao (papel + instituicao + unidade + vinculo),
  que `require_role` documentava como ainda inexistente.
- `UserSession`: permite revogacao centralizada de uma sessao mesmo que o
  token JWT subjacente ainda nao tenha expirado (sessoes revogaveis
  centralmente).
- `AuthFailedAttempt`: base para bloqueio por tentativa.
- `BreakGlassGrant`: acesso de emergencia auditado e com prazo, para o caso
  em que um profissional precisa acessar um paciente fora do seu vinculo
  assistencial normal (break glass).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_base import Base


class Institution(Base):
    """Instituicao (hospital) - raiz do isolamento multi-tenant."""

    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship(back_populates="institution")


class User(Base):
    """Profissional autenticado (espelho local do identity provider)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution: Mapped[Institution] = relationship(back_populates="users")


class CareUnit(Base):
    """Unidade assistencial (ala, setor, ambulatorio) dentro de uma
    instituicao - eixo "unidade" da autorizacao."""

    __tablename__ = "care_units"
    __table_args__ = (UniqueConstraint("institution_id", "name", name="uq_care_unit_per_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PatientCareAssignment(Base):
    """Vinculo assistencial entre um profissional e um paciente, dentro de
    uma unidade - eixo "vinculo" da autorizacao (acesso a paciente depende
    de papel+instituicao+unidade+vinculo).

    Nunca apagado: `active=False` encerra o vinculo sem destruir o
    historico (mesmo principio de nao-destrutividade usado em
    `ClinicalRuleSet`/`ModalityFinding`)."""

    __tablename__ = "patient_care_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    care_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("care_units.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assigned_by: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    """Sessao autenticada real (token Cognito), rastreada localmente para
    permitir revogacao centralizada antes da expiracao do JWT."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    session_token_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthFailedAttempt(Base):
    """Tentativa de autenticacao falha, usada para bloqueio por tentativa.
    Append-only; nunca apagado (a contagem de
    tentativas recentes e feita por janela de tempo, nao por reset manual)."""

    __tablename__ = "auth_failed_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BreakGlassGrant(Base):
    """Acesso de emergencia ("break glass") a um paciente fora do vinculo
    assistencial normal do profissional.

    Sempre exige justificativa, tem prazo de expiracao curto e gera evento
    de auditoria (categoria AUTHORIZATION) tanto na concessao quanto em
    cada acesso realizado sob o grant - nunca e um bypass silencioso."""

    __tablename__ = "break_glass_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
