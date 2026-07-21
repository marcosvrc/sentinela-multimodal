"""Modelos do modulo de administracao.

Cobrem os dois CRUDs administrativos que ainda nao existiam: especialidade
medica e funcionarios (medicos). A gestao das referencias de dados
clinicos nao ganha tabela nova aqui - reaproveita `ClinicalRuleSet`
(`app.rules_engine.models`), que ja tem versao, fonte, aprovacao e
vigencia; o que faltava era o fluxo de publicacao/rollback, implementado
em `app.administration.service`.

`Employee` representa o registro administrativo do profissional (nome,
CPF, matricula, email, especialidade) e e distinto de `User`
(`app.identity.models`, o espelho de identidade/autenticacao). Um
funcionario pode ou nao ter uma conta de acesso vinculada (`user_id`
opcional) - cadastrar o funcionario administrativamente e provisionar o
acesso dele ao sistema sao passos diferentes (a integracao Cognito real,
que criaria o `User`, ainda nao existe e continua sendo uma lacuna
conhecida do sistema).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class MedicalSpecialty(Base):
    __tablename__ = "medical_specialties"
    __table_args__ = (
        UniqueConstraint("institution_id", "name", name="uq_specialty_name_per_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("institution_id", "cpf", name="uq_employee_cpf_per_tenant"),
        UniqueConstraint(
            "institution_id", "registration_number", name="uq_employee_registration_per_tenant"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    # Preenchido automaticamente na criacao do funcionario (nunca escolhido
    # separadamente pela tela de Usuarios - ver
    # app.administration.service.create_employee): cadastrar o funcionario
    # e provisionar o acesso dele passaram a ser o mesmo passo.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True
    )
    specialty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_specialties.id"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Profissao-base (Medico/Enfermeiro) - determina quais papeis de acesso
    # (`UserRole` do `User` vinculado) sao permitidos para este funcionario.
    professional_type: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
