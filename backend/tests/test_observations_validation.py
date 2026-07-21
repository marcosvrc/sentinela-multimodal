"""Testes de fronteira da validacao pura de observacoes (sem banco).

Cobre Requirement 1.6 (rejeitar valor fora de faixa/unidade incompativel,
distinguindo os dois casos) e Requirement 1.4 (contexto obrigatorio de
glicemia) do requirements.md.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.enums import ObservationType
from app.observations.validation import compute_age, validate_observation


@pytest.mark.parametrize(
    ("observation_type", "value", "should_be_valid"),
    [
        (ObservationType.SPO2, {"value": 0}, True),
        (ObservationType.SPO2, {"value": 100}, True),
        (ObservationType.SPO2, {"value": -1}, False),
        (ObservationType.SPO2, {"value": 101}, False),
        (ObservationType.HEART_RATE, {"value": 0}, True),
        (ObservationType.HEART_RATE, {"value": 300}, True),
        (ObservationType.HEART_RATE, {"value": 301}, False),
        (ObservationType.TEMPERATURE, {"value": 20}, True),
        (ObservationType.TEMPERATURE, {"value": 45}, True),
        (ObservationType.TEMPERATURE, {"value": 19.9}, False),
        (ObservationType.TEMPERATURE, {"value": 45.1}, False),
        (ObservationType.PAIN, {"value": 0}, True),
        (ObservationType.PAIN, {"value": 10}, True),
        (ObservationType.PAIN, {"value": 11}, False),
        (ObservationType.PAIN, {"value": -1}, False),
        (ObservationType.URINE_OUTPUT, {"value": 0}, True),
        (ObservationType.URINE_OUTPUT, {"value": 2000}, True),
        (ObservationType.URINE_OUTPUT, {"value": -1}, False),
        (ObservationType.URINE_OUTPUT, {"value": 2001}, False),
    ],
)
def test_numeric_range_boundaries(
    observation_type: ObservationType, value: dict, should_be_valid: bool
) -> None:
    # PAIN/URINE_OUTPUT nao tem contexto obrigatorio testado aqui (PAIN
    # exige contexto - ver testes dedicados abaixo; passar context={}
    # so avalia a faixa fisiologica do `value`, que e o que este teste
    # parametrizado cobre).
    errors = validate_observation(observation_type, value, unit=None, context={})
    if observation_type == ObservationType.PAIN:
        assert ("value" in errors) != should_be_valid
    else:
        assert (not errors) == should_be_valid


def test_missing_numeric_value_is_rejected() -> None:
    errors = validate_observation(ObservationType.SPO2, {}, unit=None, context={})
    assert "value" in errors


def test_incompatible_type_is_distinguished_from_out_of_range() -> None:
    out_of_range = validate_observation(ObservationType.SPO2, {"value": 999}, None, {})
    incompatible = validate_observation(ObservationType.SPO2, {"value": "noventa"}, None, {})
    assert "fora da faixa" in out_of_range["value"]
    assert "incompativel" in incompatible["value"]


def test_blood_pressure_valid() -> None:
    errors = validate_observation(
        ObservationType.BLOOD_PRESSURE, {"systolic": 120, "diastolic": 80}, "mmHg", {}
    )
    assert errors == {}


def test_blood_pressure_diastolic_greater_than_systolic_is_rejected() -> None:
    errors = validate_observation(
        ObservationType.BLOOD_PRESSURE, {"systolic": 100, "diastolic": 110}, "mmHg", {}
    )
    assert "diastolic" in errors


def test_blood_pressure_missing_fields() -> None:
    errors = validate_observation(ObservationType.BLOOD_PRESSURE, {}, "mmHg", {})
    assert "systolic" in errors
    assert "diastolic" in errors


def test_consciousness_valid_level() -> None:
    errors = validate_observation(ObservationType.CONSCIOUSNESS, {"level": "alerta"}, None, {})
    assert errors == {}


def test_consciousness_invalid_level() -> None:
    errors = validate_observation(ObservationType.CONSCIOUSNESS, {"level": "sonolento"}, None, {})
    assert "level" in errors


def test_glycemia_requires_context_fields() -> None:
    errors = validate_observation(ObservationType.GLYCEMIA, {"value": 90}, "mg/dL", {})
    assert "moment" in errors
    assert "patient_type" in errors
    assert "insulin_use" in errors


def test_glycemia_valid_with_full_context() -> None:
    errors = validate_observation(
        ObservationType.GLYCEMIA,
        {"value": 90},
        "mg/dL",
        {"moment": "jejum", "patient_type": "nao_diabetico", "insulin_use": False},
    )
    assert errors == {}


def test_glycemia_invalid_moment_value() -> None:
    errors = validate_observation(
        ObservationType.GLYCEMIA,
        {"value": 90},
        "mg/dL",
        {"moment": "café da manha", "patient_type": "nao_diabetico", "insulin_use": False},
    )
    assert "moment" in errors


# --- Contexto ampliado de dor (docs/CLASSIFICACAO_DADOS_CLINICOS.md secao
# 8 - localizacao/inicio subito/sintomas de alarme, gap identificado e
# implementado em app.observations.validation._validate_pain_context) --


def test_pain_requires_context_fields() -> None:
    errors = validate_observation(ObservationType.PAIN, {"value": 5}, "score_0_10", {})
    assert "location" in errors
    assert "sudden_onset" in errors
    assert "alarm_symptoms_present" in errors


def test_pain_valid_with_full_context() -> None:
    errors = validate_observation(
        ObservationType.PAIN,
        {"value": 5},
        "score_0_10",
        {"location": "toracica", "sudden_onset": True, "alarm_symptoms_present": False},
    )
    assert errors == {}


def test_pain_invalid_location_value() -> None:
    errors = validate_observation(
        ObservationType.PAIN,
        {"value": 5},
        "score_0_10",
        {"location": "pescoco", "sudden_onset": True, "alarm_symptoms_present": False},
    )
    assert "location" in errors


def test_pain_non_boolean_sudden_onset_is_rejected() -> None:
    errors = validate_observation(
        ObservationType.PAIN,
        {"value": 5},
        "score_0_10",
        {"location": "toracica", "sudden_onset": "sim", "alarm_symptoms_present": False},
    )
    assert "sudden_onset" in errors


# --- Convulsao isolada (app.observations.validation._validate_seizure) --


def test_seizure_valid_occurred_true() -> None:
    errors = validate_observation(
        ObservationType.SEIZURE, {"occurred": True}, None, {"witnessed": True}
    )
    assert errors == {}


def test_seizure_valid_occurred_false() -> None:
    errors = validate_observation(
        ObservationType.SEIZURE, {"occurred": False}, None, {"witnessed": False}
    )
    assert errors == {}


def test_seizure_missing_occurred_field() -> None:
    errors = validate_observation(ObservationType.SEIZURE, {}, None, {"witnessed": True})
    assert "occurred" in errors


def test_seizure_missing_witnessed_context() -> None:
    errors = validate_observation(ObservationType.SEIZURE, {"occurred": True}, None, {})
    assert "witnessed" in errors


def test_seizure_non_boolean_occurred_is_rejected() -> None:
    errors = validate_observation(
        ObservationType.SEIZURE, {"occurred": "sim"}, None, {"witnessed": True}
    )
    assert "occurred" in errors


@pytest.mark.parametrize(
    ("birth_date", "as_of", "expected_age"),
    [
        (date(2000, 7, 11), date(2026, 7, 11), 26),  # aniversario exato
        (date(2000, 7, 12), date(2026, 7, 11), 25),  # um dia antes do aniversario
        (date(2000, 7, 10), date(2026, 7, 11), 26),  # um dia depois do aniversario
        (date(2026, 1, 1), date(2026, 1, 1), 0),  # nascido hoje
    ],
)
def test_compute_age_boundaries(birth_date: date, as_of: date, expected_age: int) -> None:
    assert compute_age(birth_date, as_of) == expected_age


def test_compute_age_rejects_birth_date_in_the_future() -> None:
    with pytest.raises(ValueError, match="posterior"):
        compute_age(date(2027, 1, 1), date(2026, 1, 1))
