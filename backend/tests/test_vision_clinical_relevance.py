"""Testes de `app.vision.clinical_relevance.assess_label_clinical_relevance`
(pure, sem banco) - guardrail contra considerar rotulos genericos do
Amazon Rekognition (imagem/video) como relevantes clinicamente sem
verificacao (ver docstring do modulo)."""

from __future__ import annotations

from app.vision.clinical_relevance import assess_label_clinical_relevance


def test_no_labels_is_undetermined() -> None:
    result = assess_label_clinical_relevance(())
    assert result.relevant is None
    assert "nenhum rotulo" in result.reason.lower() or "nenhum rótulo" in result.reason.lower()


def test_person_and_skin_labels_are_relevant() -> None:
    result = assess_label_clinical_relevance(("Person", "Skin", "Face"))
    assert result.relevant is True


def test_landscape_labels_are_not_relevant() -> None:
    result = assess_label_clinical_relevance(("Mountain", "Sky", "Nature"))
    assert result.relevant is False


def test_vehicle_labels_are_not_relevant() -> None:
    result = assess_label_clinical_relevance(("Car", "Vehicle", "Road"))
    assert result.relevant is False


def test_ambiguous_labels_not_in_either_list_are_undetermined() -> None:
    result = assess_label_clinical_relevance(("Umbrella", "Furniture Placeholder Xyz"))
    assert result.relevant is None


def test_relevant_hint_wins_when_mixed_with_non_clinical_hint() -> None:
    """Conservador na direcao de NAO descartar: se ha qualquer rotulo que
    sugira pessoa/contexto clinico, mesmo junto de rotulos genericos de
    ambiente, o achado e considerado relevante (ex: pessoa em um quarto de
    hospital, junto de "Furniture")."""
    result = assess_label_clinical_relevance(("Person", "Furniture", "Room"))
    assert result.relevant is True


def test_case_insensitive_and_whitespace_tolerant() -> None:
    result = assess_label_clinical_relevance(("  PERSON  ", "skin"))
    assert result.relevant is True
