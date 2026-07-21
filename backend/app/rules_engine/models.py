"""Modelos de regras clinicas versionadas.

`risk_levels` e a tabela canonica estatica de niveis de risco, reaproveitada
pelo backend e pelo frontend (RiskBadge).

As demais entidades implementam o fluxo:

    Documento clinico -> revisao/aprovacao -> YAML estruturado
    -> validacao de schema -> seed idempotente -> PostgreSQL -> publicacao

Mapeamento de responsabilidade (decisao de design registrada aqui; sujeita
a revisao quando o motor de execucao real for implementado):

- `ClinicalRuleSet`: cabecalho de um conjunto de regras para um sinal/
  avaliacao (ex: "blood_pressure" v0.1.0). Uma linha por (code, version).
  Publicacoes criam nova versao imutavel; nunca sobrescrevem uma versao
  ja usada em analises anteriores (content_hash detecta tentativa de
  reescrever uma versao existente com conteudo diferente).
- `ClinicalRuleSource`: referencia bibliografica/protocolar que sustenta o
  conjunto (pode haver mais de uma por conjunto).
- `ClinicalRuleApproval`: trilha de aprovacao clinica (aprovador, decisao,
  justificativa, data) — suporta rollback ao permitir identificar a ultima
  aprovacao valida de uma versao.
- `ClinicalRule`: uma regra individual dentro do conjunto (id textual,
  expressao `when`, nivel de risco, rotulo de classificacao).
- `ClinicalRuleCondition`: a condicao (expressao `when`) de uma regra,
  separada estruturalmente de `ClinicalRule` para permitir, no futuro,
  decomposicao em arvore de condicoes estruturadas em vez de uma unica
  expressao textual.
- `ClinicalRuleAction`: conduta sistemica esperada quando uma regra e
  acionada, por nivel de risco dentro do conjunto. Tem default a partir de
  `risk_levels.meaning`, mas pode ser sobrescrita quando o protocolo exigir
  orientacao mais especifica que o texto generico da tabela canonica.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_base import Base


class RiskLevel(Base):
    __tablename__ = "risk_levels"

    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    meaning: Mapped[str] = mapped_column(String(200), nullable=False)


class ClinicalRuleSet(Base):
    """Conjunto de regras versionado e imutavel apos publicacao."""

    __tablename__ = "clinical_rule_sets"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_rule_set_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    population: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_inputs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    exclusions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list[ClinicalRuleSource]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[ClinicalRuleApproval]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan"
    )
    rules: Mapped[list[ClinicalRule]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan"
    )
    actions: Mapped[list[ClinicalRuleAction]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan"
    )


class ClinicalRuleSource(Base):
    """Referencia (diretriz, protocolo, literatura) que sustenta o conjunto."""

    __tablename__ = "clinical_rule_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_rule_sets.id"), nullable=False
    )
    reference: Mapped[str] = mapped_column(String(500), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)

    rule_set: Mapped[ClinicalRuleSet] = relationship(back_populates="sources")


class ClinicalRuleApproval(Base):
    """Trilha de aprovacao clinica de um conjunto de regras."""

    __tablename__ = "clinical_rule_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_rule_sets.id"), nullable=False
    )
    approver: Mapped[str] = mapped_column(String(200), nullable=False)
    # approved | rejected | published | rollback | retired_by_new_publication |
    # retired_by_rollback (os quatro ultimos adicionados junto com o fluxo
    # de publicacao formal - ver
    # app.administration.service.publish_rule_set/rollback_rule_set).
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rule_set: Mapped[ClinicalRuleSet] = relationship(back_populates="approvals")


class ClinicalRule(Base):
    """Uma regra individual dentro de um conjunto."""

    __tablename__ = "clinical_rules"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "rule_key", name="uq_clinical_rule_key_per_set"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_rule_sets.id"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, ForeignKey("risk_levels.code"), nullable=False)
    classification_label: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rule_set: Mapped[ClinicalRuleSet] = relationship(back_populates="rules")
    condition: Mapped[ClinicalRuleCondition] = relationship(
        back_populates="rule", cascade="all, delete-orphan", uselist=False
    )


class ClinicalRuleCondition(Base):
    """Condicao (`when`) de uma regra individual.

    Hoje armazena a expressao como texto (avaliada apenas pelo motor de
    regras do modulo funcional, fora do escopo deste scaffold de
    persistencia). A separacao em tabela propria permite evoluir para uma
    representacao estruturada (arvore de condicoes) sem migrar `clinical_rules`.
    """

    __tablename__ = "clinical_rule_conditions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_rules.id"), nullable=False, unique=True
    )
    expression: Mapped[str] = mapped_column(Text, nullable=False)

    rule: Mapped[ClinicalRule] = relationship(back_populates="condition")


class ClinicalRuleAction(Base):
    """Conduta sistemica esperada por nivel de risco dentro de um conjunto.

    Uma linha por nivel de risco distinto presente nas regras do conjunto.
    `description` comeca como copia de `risk_levels.meaning` e pode ser
    sobrescrita quando o protocolo publicado exigir orientacao mais
    especifica que o texto generico da tabela canonica.
    """

    __tablename__ = "clinical_rule_actions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "risk_level", name="uq_rule_action_per_risk_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_rule_sets.id"), nullable=False
    )
    risk_level: Mapped[int] = mapped_column(Integer, ForeignKey("risk_levels.code"), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)

    rule_set: Mapped[ClinicalRuleSet] = relationship(back_populates="actions")
