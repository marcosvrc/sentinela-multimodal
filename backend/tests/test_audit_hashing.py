"""Testes do encadeamento de hash da auditoria (sem banco).

Cobre Requirement 14.9: deteccao de registro inserido, excluido ou
modificado na cadeia de integridade.
"""

from __future__ import annotations

from app.audit.hashing import canonical_payload, compute_event_hash, verify_chain


def _build_chain(payloads: list[dict]) -> list[dict]:
    """Constroi uma cadeia valida a partir de uma lista de payloads (helper de teste)."""
    events = []
    prev_hash = None
    for sequence, fields in enumerate(payloads, start=1):
        event_hash = compute_event_hash(prev_hash, fields)
        events.append(
            {
                "sequence": sequence,
                "prev_hash": prev_hash,
                "event_hash": event_hash,
                "fields": fields,
            }
        )
        prev_hash = event_hash
    return events


def test_canonical_payload_is_deterministic_regardless_of_key_order() -> None:
    a = {"action": "PATIENT_CREATE", "actor": "user-1"}
    b = {"actor": "user-1", "action": "PATIENT_CREATE"}
    assert canonical_payload(a) == canonical_payload(b)


def test_compute_event_hash_changes_with_prev_hash() -> None:
    fields = {"action": "PATIENT_CREATE"}
    hash_a = compute_event_hash(None, fields)
    hash_b = compute_event_hash("some-other-prev-hash", fields)
    assert hash_a != hash_b


def test_compute_event_hash_changes_with_content() -> None:
    hash_a = compute_event_hash(None, {"action": "PATIENT_CREATE"})
    hash_b = compute_event_hash(None, {"action": "PATIENT_READ"})
    assert hash_a != hash_b


def test_valid_chain_has_no_violations() -> None:
    chain = _build_chain(
        [
            {"action": "PATIENT_CREATE", "resource_id": "p1"},
            {"action": "OBSERVATION_CREATE", "resource_id": "o1"},
            {"action": "PATIENT_READ", "resource_id": "p1"},
        ]
    )
    assert verify_chain(chain) == []


def test_tampered_event_content_is_detected() -> None:
    chain = _build_chain(
        [
            {"action": "PATIENT_CREATE", "resource_id": "p1"},
            {"action": "OBSERVATION_CREATE", "resource_id": "o1"},
        ]
    )
    # Simula adulteracao: o conteudo do primeiro evento foi alterado depois
    # de gravado, mas o event_hash armazenado nao foi recalculado.
    chain[0]["fields"]["resource_id"] = "p1-adulterado"

    violations = verify_chain(chain)
    assert len(violations) == 1
    assert violations[0].sequence == 1


def test_removed_event_breaks_the_chain() -> None:
    chain = _build_chain(
        [
            {"action": "PATIENT_CREATE", "resource_id": "p1"},
            {"action": "OBSERVATION_CREATE", "resource_id": "o1"},
            {"action": "PATIENT_READ", "resource_id": "p1"},
        ]
    )
    # Remove o evento do meio, deixando um "buraco" na cadeia.
    tampered = [chain[0], chain[2]]

    violations = verify_chain(tampered)
    assert len(violations) == 1
    assert violations[0].sequence == chain[2]["sequence"]


def test_reordered_events_break_the_chain() -> None:
    chain = _build_chain(
        [
            {"action": "PATIENT_CREATE", "resource_id": "p1"},
            {"action": "OBSERVATION_CREATE", "resource_id": "o1"},
        ]
    )
    reordered = [chain[1], chain[0]]
    reordered[0]["sequence"], reordered[1]["sequence"] = 1, 2

    violations = verify_chain(reordered)
    assert len(violations) >= 1
