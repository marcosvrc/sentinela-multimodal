"""Logica de carga (seed) idempotente das regras clinicas no PostgreSQL.

Separado de `cli.py` para manter a logica pura (hash, decisao de
inserir/pular/conflitar) testavel sem uma conexao real com o banco. A
integracao com SQLAlchemy fica isolada nas funcoes que recebem uma `Session`.

Fluxo (ESCOPO_PROJETO.md secao 12.1.6):

    YAML validado -> content_hash -> upsert por (code, version)
        - mesmo hash já existente -> no-op (idempotente)
        - hash diferente para (code, version) já existente -> conflito
          (versoes sao imutaveis; publique uma nova versao)
        - (code, version) inexistente -> insercao completa (rule_set,
          sources, rules, conditions, actions)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum


def compute_content_hash(content: dict) -> str:
    """Hash estavel do conteudo de um conjunto de regras.

    Usa serializacao canonica (chaves ordenadas) para que o mesmo conteudo
    semantico sempre produza o mesmo hash, independente da ordem original
    das chaves no arquivo YAML.
    """
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SeedOutcome(str, Enum):
    CREATED = "created"
    SKIPPED_UNCHANGED = "skipped_unchanged"
    CONFLICT = "conflict"


@dataclass
class SeedDecision:
    """Decisao pura sobre o que fazer com um conjunto de regras.

    `existing_hash` e None quando (code, version) ainda nao existe no banco.
    """

    code: str
    version: str
    new_hash: str
    existing_hash: str | None

    @property
    def outcome(self) -> SeedOutcome:
        if self.existing_hash is None:
            return SeedOutcome.CREATED
        if self.existing_hash == self.new_hash:
            return SeedOutcome.SKIPPED_UNCHANGED
        return SeedOutcome.CONFLICT


def decide(content: dict, existing_hash: str | None) -> SeedDecision:
    """Decide a acao para um conjunto de regras, sem tocar no banco."""
    return SeedDecision(
        code=content["code"],
        version=content["version"],
        new_hash=compute_content_hash(content),
        existing_hash=existing_hash,
    )


def default_action_descriptions(
    content: dict, risk_level_meanings: dict[int, str]
) -> dict[int, str]:
    """Deriva a descricao padrao de conduta por nivel de risco presente no conjunto.

    Usa o texto canonico de `risk_levels.meaning` como default; o protocolo
    publicado pode sobrescrever isso depois via UPDATE administrativo
    (fora do escopo deste seed inicial).
    """
    levels_in_set = {rule["risk_level"] for rule in content["rules"]}
    return {level: risk_level_meanings[level] for level in levels_in_set}
