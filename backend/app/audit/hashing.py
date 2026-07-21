"""Encadeamento de hash da trilha de auditoria (sem dependencia de banco).

Os eventos de auditoria armazenados devem ser protegidos por um mecanismo
de integridade encadeada que permita detectar qualquer registro inserido,
excluido ou modificado.

Modelo: cada evento carrega `prev_hash` (o `event_hash` do evento anterior
na cadeia, ou None para o primeiro) e um `event_hash` = sha256(prev_hash +
conteudo canonico do evento). Alterar qualquer campo de um evento antigo, ou
remover/inserir um evento no meio da cadeia, quebra o hash de todos os
eventos posteriores - detectavel por `verify_chain`.

A serializacao canonica (chaves ordenadas, separadores compactos) garante
que o mesmo conteudo semantico sempre produza o mesmo hash, e que a ordem
de insercao dos campos no dict nao afete o resultado.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def canonical_payload(fields: dict) -> str:
    """Serializacao estavel e determinista de um evento para hashing."""
    return json.dumps(
        fields, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")
    )


def compute_event_hash(prev_hash: str | None, fields: dict) -> str:
    """Hash do proximo elo da cadeia a partir do elo anterior e do conteudo do evento."""
    payload = canonical_payload(fields)
    digest_input = f"{prev_hash or ''}:{payload}".encode()
    return hashlib.sha256(digest_input).hexdigest()


@dataclass(frozen=True)
class ChainViolation:
    """Uma quebra detectada na cadeia de integridade."""

    sequence: int
    reason: str


def verify_chain(events: list[dict]) -> list[ChainViolation]:
    """Recalcula a cadeia e retorna as violacoes encontradas (vazio = integra).

    Cada item de `events` deve conter: sequence, prev_hash, event_hash e os
    campos originais usados no calculo do hash (mesmo formato passado a
    `compute_event_hash`, sob a chave "fields"). A lista deve estar ordenada
    por `sequence` crescente.
    """
    violations: list[ChainViolation] = []
    expected_prev_hash: str | None = None

    for event in events:
        sequence = event["sequence"]

        if event["prev_hash"] != expected_prev_hash:
            violations.append(
                ChainViolation(
                    sequence=sequence,
                    reason="prev_hash nao corresponde ao event_hash do evento anterior",
                )
            )

        recomputed = compute_event_hash(event["prev_hash"], event["fields"])
        if recomputed != event["event_hash"]:
            violations.append(
                ChainViolation(
                    sequence=sequence,
                    reason=(
                        "event_hash nao corresponde ao conteudo do evento (possivel adulteracao)"
                    ),
                )
            )

        expected_prev_hash = event["event_hash"]

    return violations
