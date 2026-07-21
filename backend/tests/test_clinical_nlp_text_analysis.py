"""Testes de `app.clinical_nlp.text_analysis` (secao 4.3 do escopo).

Cobrem literalmente os exemplos do escopo: "paciente apresenta dor",
"paciente nega dor", "apresentou dor ontem" e "histórico familiar de dor"
devem produzir representacoes diferentes (negacao/temporalidade/
experienciador).
"""

from __future__ import annotations

from app.clinical_nlp.text_analysis import (
    Certainty,
    Experiencer,
    Negation,
    Temporality,
    analyze_clinical_text,
)


def test_empty_text_returns_no_mentions() -> None:
    assert analyze_clinical_text("") == []
    assert analyze_clinical_text(None) == []  # type: ignore[arg-type]


def test_affirmed_current_patient_mention() -> None:
    mentions = analyze_clinical_text("Paciente apresenta dor.")
    assert len(mentions) == 1
    mention = mentions[0]
    assert mention.term == "dor"
    assert mention.negation is Negation.AFFIRMED
    assert mention.temporality is Temporality.CURRENT
    assert mention.experiencer is Experiencer.PATIENT
    assert mention.certainty is Certainty.CONFIRMED


def test_negated_mention() -> None:
    mentions = analyze_clinical_text("Paciente nega dor.")
    assert len(mentions) == 1
    assert mentions[0].negation is Negation.NEGATED


def test_past_temporality_mention() -> None:
    mentions = analyze_clinical_text("Apresentou dor ontem.")
    assert len(mentions) == 1
    mention = mentions[0]
    assert mention.negation is Negation.AFFIRMED
    assert mention.temporality is Temporality.PAST


def test_family_history_mention() -> None:
    mentions = analyze_clinical_text("Histórico familiar de dor.")
    assert len(mentions) == 1
    mention = mentions[0]
    assert mention.experiencer is Experiencer.FAMILY_MEMBER


def test_the_four_scope_examples_produce_distinct_representations() -> None:
    """Requisito explicito do escopo (secao 4.3): as quatro frases de exemplo
    devem produzir representacoes diferentes entre si."""
    affirmed = analyze_clinical_text("Paciente apresenta dor.")[0]
    negated = analyze_clinical_text("Paciente nega dor.")[0]
    past = analyze_clinical_text("Apresentou dor ontem.")[0]
    family = analyze_clinical_text("Histórico familiar de dor.")[0]

    representations = {
        (m.negation, m.temporality, m.experiencer)
        for m in (affirmed, negated, past, family)
    }
    assert len(representations) == 4


def test_suspected_certainty_cue() -> None:
    mentions = analyze_clinical_text("Suspeita de dispneia associada ao esforco.")
    assert len(mentions) == 1
    assert mentions[0].certainty is Certainty.SUSPECTED


def test_possible_certainty_cue() -> None:
    mentions = analyze_clinical_text("Possivel taquicardia aos esforcos.")
    assert len(mentions) == 1
    assert mentions[0].certainty is Certainty.POSSIBLE


def test_confirmed_certainty_cue() -> None:
    mentions = analyze_clinical_text("Confirmado quadro de convulsao no plantao anterior.")
    assert len(mentions) == 1
    assert mentions[0].certainty is Certainty.CONFIRMED


def test_negation_scope_stops_at_conjunction() -> None:
    """"nega X mas apresenta Y": a negacao de X nao deve vazar para Y."""
    mentions = analyze_clinical_text("Paciente nega febre mas apresenta tosse.")
    by_term = {m.term: m for m in mentions}
    assert by_term["febre"].negation is Negation.NEGATED
    assert by_term["tosse"].negation is Negation.AFFIRMED


def test_longest_term_match_wins_over_substring() -> None:
    """"dor toracica" deve casar como um unico termo, nao como "dor" duas vezes."""
    mentions = analyze_clinical_text("Paciente com dor toracica subita.")
    assert len(mentions) == 1
    assert mentions[0].term == "dor toracica"


def test_multiple_sentences_each_scoped_independently() -> None:
    text = "Paciente nega dor. Familiar relata confusao mental do paciente ontem."
    mentions = analyze_clinical_text(text)
    by_term = {m.term: m for m in mentions}
    assert by_term["dor"].negation is Negation.NEGATED
    assert by_term["confusao mental"].negation is Negation.AFFIRMED
    assert by_term["confusao mental"].temporality is Temporality.PAST


def test_no_clinical_term_returns_empty_list() -> None:
    assert analyze_clinical_text("Paciente orientado, sem queixas relevantes hoje.") == []
