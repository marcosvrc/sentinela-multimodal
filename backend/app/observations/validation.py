"""Validacao pura de observacoes clinicas (sem dependencia de banco de dados).

Cobre duas responsabilidades distintas:

1. Faixa fisiologicamente possivel: valores fora do fisiologicamente
   sobrevivivel sao rejeitados distinguindo "fora de faixa" de "unidade
   incompativel" - nunca corrigidos silenciosamente.
2. Contexto obrigatorio por tipo de observacao: glicemia exige momento,
   tipo de paciente e uso de insulina; outros tipos podem ganhar regras
   especificas aqui no futuro sem migrar o schema (o valor e o contexto
   ficam em colunas JSONB).

Este modulo nao acessa o banco: recebe dados ja desserializados e devolve
uma lista de erros de campo, permitindo reuso tanto no endpoint HTTP quanto
em testes unitarios rapidos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.enums import ObservationType


@dataclass(frozen=True)
class PhysiologicalRange:
    """Faixa fisiologicamente possivel para um valor numerico unico."""

    minimum: float
    maximum: float
    expected_unit: str


# Limites de sobrevivencia fisiologica, nao os limiares clinicos de risco
# (esses ultimos vivem em backend/clinical_rules/seeds/*.yaml). Um valor
# fora destes limites e um erro de entrada, nao uma classificacao de risco.
PHYSIOLOGICAL_RANGES: dict[ObservationType, PhysiologicalRange] = {
    ObservationType.HEIGHT: PhysiologicalRange(minimum=30, maximum=272, expected_unit="cm"),
    ObservationType.WEIGHT: PhysiologicalRange(minimum=0.5, maximum=650, expected_unit="kg"),
    ObservationType.SPO2: PhysiologicalRange(minimum=0, maximum=100, expected_unit="%"),
    ObservationType.TEMPERATURE: PhysiologicalRange(
        minimum=20, maximum=45, expected_unit="celsius"
    ),
    ObservationType.HEART_RATE: PhysiologicalRange(minimum=0, maximum=300, expected_unit="bpm"),
    ObservationType.RESPIRATORY_RATE: PhysiologicalRange(
        minimum=0, maximum=100, expected_unit="irpm"
    ),
    ObservationType.PAIN: PhysiologicalRange(minimum=0, maximum=10, expected_unit="score_0_10"),
    ObservationType.GLYCEMIA: PhysiologicalRange(minimum=0, maximum=1000, expected_unit="mg/dL"),
    # Debito urinario/diurese - sinal classico de monitoramento em
    # UTI/sepse. Faixa fisiologicamente possivel deliberadamente ampla
    # (cobre desde anuria completa a poliuria extrema de diabetes
    # insipidus) - os limiares CLINICOS reais vivem em
    # clinical_rules/seeds/urine_output.yaml, nao aqui.
    ObservationType.URINE_OUTPUT: PhysiologicalRange(minimum=0, maximum=2000, expected_unit="mL/h"),
}

BLOOD_PRESSURE_SYSTOLIC_RANGE = PhysiologicalRange(minimum=30, maximum=300, expected_unit="mmHg")
BLOOD_PRESSURE_DIASTOLIC_RANGE = PhysiologicalRange(minimum=10, maximum=200, expected_unit="mmHg")

VALID_CONSCIOUSNESS_LEVELS = {
    "alerta",
    "confusao_recente",
    "responde_voz",
    "responde_dor",
    "nao_responde",
}

REQUIRED_GLYCEMIA_CONTEXT_FIELDS = ("moment", "patient_type", "insulin_use")
VALID_GLYCEMIA_MOMENTS = {"jejum", "antes_refeicao", "apos_refeicao", "aleatoria"}
VALID_GLYCEMIA_PATIENT_TYPES = {"diabetico", "nao_diabetico"}

# Contexto ampliado de dor: a intensidade numerica isolada nao e
# suficiente para classificar urgencia - localizacao toracica/abdominal,
# inicio subito e sintomas associados podem ELEVAR o risco
# independentemente do numero. Campos OBRIGATORIOS com valor padrao
# neutro (nunca opcionais soltos): o motor de regras
# (`app.rules_engine.evaluator`) fica INCONCLUSIVO se uma expressao `when`
# referenciar uma variavel ausente do dicionario de entradas, entao
# "nao informado" precisa ser um valor valido explicito, nao a ausencia
# da chave.
REQUIRED_PAIN_CONTEXT_FIELDS = ("location", "sudden_onset", "alarm_symptoms_present")
VALID_PAIN_LOCATIONS = {
    "toracica",
    "abdominal",
    "cabeca",
    "dorso",
    "membro",
    "outra",
    "nao_informado",
}

# Convulsao: por definicao um EVENTO (ocorreu ou nao nesta observacao),
# nao uma serie numerica - mesmo padrao boolean/categorico simples de
# `CONSCIOUSNESS`. Aplicavel a qualquer contexto de internacao, nao
# apenas cirurgico.
REQUIRED_SEIZURE_CONTEXT_FIELDS = ("witnessed",)


def validate_observation(
    observation_type: ObservationType,
    value: dict,
    unit: str | None,
    context: dict,
) -> dict[str, str]:
    """Valida um valor de observacao. Retorna um dict de field_errors (vazio se valido).

    `value` e sempre um dict para acomodar tipos compostos (pressao
    arterial tem sistolica+diastolica); tipos simples usam a chave
    `"value"`.
    """
    errors: dict[str, str] = {}

    if observation_type == ObservationType.BLOOD_PRESSURE:
        errors.update(_validate_blood_pressure(value))
    elif observation_type == ObservationType.CONSCIOUSNESS:
        errors.update(_validate_consciousness(value))
    elif observation_type == ObservationType.SEIZURE:
        errors.update(_validate_seizure(value, context))
    elif observation_type in PHYSIOLOGICAL_RANGES:
        errors.update(_validate_single_numeric(observation_type, value))

    if observation_type == ObservationType.GLYCEMIA:
        errors.update(_validate_glycemia_context(context))
    elif observation_type == ObservationType.PAIN:
        errors.update(_validate_pain_context(context))

    return errors


def _validate_single_numeric(observation_type: ObservationType, value: dict) -> dict[str, str]:
    range_ = PHYSIOLOGICAL_RANGES[observation_type]
    raw = value.get("value")
    if raw is None:
        return {"value": "Campo obrigatorio ausente."}
    if not isinstance(raw, int | float):
        return {"value": "Unidade ou tipo de valor incompativel: esperado numero."}
    if not (range_.minimum <= raw <= range_.maximum):
        return {
            "value": (
                f"Valor fora da faixa fisiologicamente possivel "
                f"({range_.minimum}-{range_.maximum} {range_.expected_unit})."
            )
        }
    return {}


def _validate_blood_pressure(value: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    systolic = value.get("systolic")
    diastolic = value.get("diastolic")

    if systolic is None:
        errors["systolic"] = "Campo obrigatorio ausente."
    elif not isinstance(systolic, int | float):
        errors["systolic"] = "Unidade ou tipo de valor incompativel: esperado numero."
    elif not (
        BLOOD_PRESSURE_SYSTOLIC_RANGE.minimum <= systolic <= BLOOD_PRESSURE_SYSTOLIC_RANGE.maximum
    ):
        errors["systolic"] = "Valor fora da faixa fisiologicamente possivel (30-300 mmHg)."

    if diastolic is None:
        errors["diastolic"] = "Campo obrigatorio ausente."
    elif not isinstance(diastolic, int | float):
        errors["diastolic"] = "Unidade ou tipo de valor incompativel: esperado numero."
    elif not (
        BLOOD_PRESSURE_DIASTOLIC_RANGE.minimum
        <= diastolic
        <= BLOOD_PRESSURE_DIASTOLIC_RANGE.maximum
    ):
        errors["diastolic"] = "Valor fora da faixa fisiologicamente possivel (10-200 mmHg)."

    if (
        not errors
        and isinstance(systolic, int | float)
        and isinstance(diastolic, int | float)
        and diastolic >= systolic
    ):
        errors["diastolic"] = "Pressao diastolica nao pode ser maior ou igual a sistolica."

    return errors


def _validate_consciousness(value: dict) -> dict[str, str]:
    level = value.get("level")
    if level is None:
        return {"level": "Campo obrigatorio ausente."}
    if level not in VALID_CONSCIOUSNESS_LEVELS:
        return {"level": f"Valor invalido. Esperado um de: {sorted(VALID_CONSCIOUSNESS_LEVELS)}."}
    return {}


def _validate_pain_context(context: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field in REQUIRED_PAIN_CONTEXT_FIELDS:
        if context.get(field) is None:
            errors[field] = "Campo de contexto obrigatorio ausente para dor."

    location = context.get("location")
    if location is not None and location not in VALID_PAIN_LOCATIONS:
        errors["location"] = f"Valor invalido. Esperado um de: {sorted(VALID_PAIN_LOCATIONS)}."

    sudden_onset = context.get("sudden_onset")
    if sudden_onset is not None and not isinstance(sudden_onset, bool):
        errors["sudden_onset"] = "Valor invalido. Esperado booleano (verdadeiro/falso)."

    alarm_symptoms = context.get("alarm_symptoms_present")
    if alarm_symptoms is not None and not isinstance(alarm_symptoms, bool):
        errors["alarm_symptoms_present"] = "Valor invalido. Esperado booleano (verdadeiro/falso)."

    return errors


def _validate_seizure(value: dict, context: dict) -> dict[str, str]:
    """Convulsao e um evento (ocorreu/nao ocorreu nesta observacao), nao
    um valor numerico - mesmo padrao categorico simples de
    `_validate_consciousness`."""
    errors: dict[str, str] = {}
    occurred = value.get("occurred")
    if occurred is None:
        errors["occurred"] = "Campo obrigatorio ausente."
    elif not isinstance(occurred, bool):
        errors["occurred"] = "Valor invalido. Esperado booleano (verdadeiro/falso)."

    for field in REQUIRED_SEIZURE_CONTEXT_FIELDS:
        if context.get(field) is None:
            errors[field] = "Campo de contexto obrigatorio ausente para convulsao."
    return errors


def _validate_glycemia_context(context: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field in REQUIRED_GLYCEMIA_CONTEXT_FIELDS:
        if context.get(field) in (None, ""):
            errors[field] = "Campo de contexto obrigatorio ausente para glicemia."

    moment = context.get("moment")
    if moment is not None and moment not in VALID_GLYCEMIA_MOMENTS:
        errors["moment"] = f"Valor invalido. Esperado um de: {sorted(VALID_GLYCEMIA_MOMENTS)}."

    patient_type = context.get("patient_type")
    if patient_type is not None and patient_type not in VALID_GLYCEMIA_PATIENT_TYPES:
        errors["patient_type"] = (
            f"Valor invalido. Esperado um de: {sorted(VALID_GLYCEMIA_PATIENT_TYPES)}."
        )

    return errors


def compute_age(birth_date: date, as_of: date) -> int:
    """Calcula a idade em anos completos na data de referencia.

    A idade nunca e armazenada: sempre derivada de `birth_date` no
    momento da consulta/analise.
    """
    if birth_date > as_of:
        raise ValueError("Data de nascimento nao pode ser posterior a data de referencia.")
    years = as_of.year - birth_date.year
    had_birthday = (as_of.month, as_of.day) >= (birth_date.month, birth_date.day)
    if not had_birthday:
        years -= 1
    return years
