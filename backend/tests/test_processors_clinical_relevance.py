"""Testes de `app.processors.clinical_relevance.is_clinically_relevant`
(funcao pura, sem banco/rede) - guardrail unico de relevancia clinica de
UM achado, reaproveitado por `app.clinical_support.service.
should_run_automatic_clinical_support` e por `app.reports.builder`
(calculo do "Nivel de atencao por modalidade").
"""

from __future__ import annotations

from app.processors.clinical_relevance import is_clinically_relevant


class TestIsClinicallyRelevant:
    def test_original_data_never_relevant(self) -> None:
        assert is_clinically_relevant("ORIGINAL_DATA", {"width": 300, "height": 300}) is False

    def test_assisted_hypothesis_always_relevant(self) -> None:
        assert is_clinically_relevant("ASSISTED_HYPOTHESIS", {}) is True

    def test_model_observation_with_relevant_clinical_relevance_is_relevant(self) -> None:
        assert (
            is_clinically_relevant("MODEL_OBSERVATION", {"clinical_relevance": "RELEVANT"})
            is True
        )

    def test_model_observation_with_not_relevant_clinical_relevance_is_not_relevant(self) -> None:
        assert (
            is_clinically_relevant("MODEL_OBSERVATION", {"clinical_relevance": "NOT_RELEVANT"})
            is False
        )

    def test_model_observation_with_undetermined_clinical_relevance_is_not_relevant(self) -> None:
        assert (
            is_clinically_relevant("MODEL_OBSERVATION", {"clinical_relevance": "UNDETERMINED"})
            is False
        )

    def test_sentiment_alone_is_not_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", {"sentiment": "POSITIVE"}) is False

    def test_category_alone_is_not_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", {"category": "PHOTOGRAPH"}) is False

    def test_clinical_term_is_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", {"term": "dor toracica"}) is True

    def test_acoustic_dsp_metric_is_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", {"rms_energy_mean": 0.02}) is True

    def test_empty_quality_metrics_is_not_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", {}) is False

    def test_none_quality_metrics_is_not_relevant(self) -> None:
        assert is_clinically_relevant("MODEL_OBSERVATION", None) is False
