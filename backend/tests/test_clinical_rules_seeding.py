"""Testes da logica pura de seed (sem banco de dados).

A decisao de criar/pular/conflitar e o calculo de hash sao testados aqui
isoladamente; a escrita real no PostgreSQL (clinical_rules.cli.seed) e
exercitada no CI, que tem um servico Postgres disponivel (este sandbox de
desenvolvimento nao tem Postgres instalado).
"""

from __future__ import annotations

from clinical_rules.seeding import (
    SeedOutcome,
    compute_content_hash,
    decide,
    default_action_descriptions,
)

SAMPLE_CONTENT = {
    "code": "spo2",
    "version": "0.1.0",
    "rules": [
        {"id": "normal", "risk_level": 1, "classification_label": "Normal", "when": "x >= 96"},
        {"id": "hypoxemia", "risk_level": 4, "classification_label": "Hipoxemia", "when": "x < 92"},
    ],
}

RISK_MEANINGS = {
    1: "Registrar e seguir rotina",
    4: "Alertar equipe assistencial",
}


def test_content_hash_is_deterministic_regardless_of_key_order() -> None:
    reordered = {
        "rules": SAMPLE_CONTENT["rules"],
        "version": SAMPLE_CONTENT["version"],
        "code": SAMPLE_CONTENT["code"],
    }
    assert compute_content_hash(SAMPLE_CONTENT) == compute_content_hash(reordered)


def test_content_hash_changes_when_content_changes() -> None:
    changed = {**SAMPLE_CONTENT, "version": "0.2.0"}
    assert compute_content_hash(SAMPLE_CONTENT) != compute_content_hash(changed)


def test_decide_created_when_no_existing_hash() -> None:
    decision = decide(SAMPLE_CONTENT, existing_hash=None)
    assert decision.outcome == SeedOutcome.CREATED
    assert decision.code == "spo2"
    assert decision.version == "0.1.0"


def test_decide_skipped_when_hash_matches() -> None:
    new_hash = compute_content_hash(SAMPLE_CONTENT)
    decision = decide(SAMPLE_CONTENT, existing_hash=new_hash)
    assert decision.outcome == SeedOutcome.SKIPPED_UNCHANGED


def test_decide_conflict_when_hash_differs() -> None:
    decision = decide(SAMPLE_CONTENT, existing_hash="some-other-hash")
    assert decision.outcome == SeedOutcome.CONFLICT


def test_default_action_descriptions_maps_only_risk_levels_present() -> None:
    descriptions = default_action_descriptions(SAMPLE_CONTENT, RISK_MEANINGS)
    assert descriptions == {
        1: "Registrar e seguir rotina",
        4: "Alertar equipe assistencial",
    }


def test_default_action_descriptions_raises_for_unmapped_risk_level() -> None:
    incomplete_meanings = {1: "Registrar e seguir rotina"}
    try:
        default_action_descriptions(SAMPLE_CONTENT, incomplete_meanings)
    except KeyError:
        pass
    else:
        raise AssertionError("esperava KeyError para nivel de risco sem descricao mapeada")
