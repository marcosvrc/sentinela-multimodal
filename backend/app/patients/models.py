"""Modelo minimo de paciente.

Este e o esqueleto de dados inicial; os campos clinicos completos,
alergias, medicamentos e historico longitudinal serao adicionados nas
migrations do modulo funcional de pacientes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "medical_record_number", name="uq_patient_record_per_tenant"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    medical_record_number: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    registered_sex: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Altura em cm, capturada uma vez no cadastro (nao e uma serie
    # temporal como o peso - ver `ObservationType.WEIGHT`). Opcional:
    # pacientes cadastrados antes desta mudanca ficam com `None` ate o
    # profissional preencher. Usada com o peso mais recente (observacao
    # clinica) para calcular o IMC - o calculo em si fica no
    # frontend/relatorio, nunca armazenado aqui para nao desatualizar
    # quando o peso mudar.
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    # "Exclusao" e sempre desativacao (nunca apaga o registro - historico
    # de observacoes/analises/auditoria de um paciente inativo permanece
    # integro, mesmo principio de `Employee.active`/`CareUnit.active`).
    # Pacientes inativos ficam fora da listagem/busca por padrao.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
