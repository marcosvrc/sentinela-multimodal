"""Testes do motor de regras deterministico (pure, sem banco)."""

from __future__ import annotations

from app.core.enums import RuleEvaluationInconclusiveReason, RuleEvaluationOutcome
from app.rules_engine.engine import RuleDefinition, evaluate_rule_set

SPO2_RULES = [
    RuleDefinition("normal", "spo2_percent >= 96", 1, "Normal", position=0),
    RuleDefinition(
        "mildly_reduced", "94 <= spo2_percent <= 95", 3, "Levemente reduzida", position=1
    ),
    RuleDefinition("hypoxemia", "92 <= spo2_percent <= 93", 4, "Hipoxemia", position=2),
    RuleDefinition("severe_hypoxemia", "spo2_percent <= 91", 6, "Hipoxemia grave", position=3),
]
SPO2_REQUIRED_INPUTS = ["spo2_percent"]


def test_matches_expected_rule() -> None:
    evaluation = evaluate_rule_set(SPO2_RULES, SPO2_REQUIRED_INPUTS, {"spo2_percent": 98})
    assert evaluation.outcome is RuleEvaluationOutcome.MATCHED
    assert evaluation.matched_rule.rule_key == "normal"
    assert evaluation.risk_level == 1


def test_matches_boundary_value() -> None:
    evaluation = evaluate_rule_set(SPO2_RULES, SPO2_REQUIRED_INPUTS, {"spo2_percent": 94})
    assert evaluation.matched_rule.rule_key == "mildly_reduced"


def test_matches_severe_case() -> None:
    evaluation = evaluate_rule_set(SPO2_RULES, SPO2_REQUIRED_INPUTS, {"spo2_percent": 50})
    assert evaluation.matched_rule.rule_key == "severe_hypoxemia"
    assert evaluation.risk_level == 6


def test_missing_required_input_is_inconclusive() -> None:
    evaluation = evaluate_rule_set(SPO2_RULES, SPO2_REQUIRED_INPUTS, {})
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT
    assert evaluation.matched_rule is None


def test_none_value_for_required_input_is_inconclusive() -> None:
    evaluation = evaluate_rule_set(SPO2_RULES, SPO2_REQUIRED_INPUTS, {"spo2_percent": None})
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT


def test_no_rule_matches_gap_is_inconclusive() -> None:
    # Gap deliberado: nenhuma regra cobre exatamente spo2_percent == 93.5
    # (as faixas do fixture sao inteiras); expõe um buraco na tabela.
    rules_with_gap = [
        RuleDefinition("normal", "spo2_percent >= 96", 1, "Normal", position=0),
        RuleDefinition("severe_hypoxemia", "spo2_percent <= 91", 6, "Hipoxemia grave", position=1),
    ]
    evaluation = evaluate_rule_set(rules_with_gap, SPO2_REQUIRED_INPUTS, {"spo2_percent": 93})
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.NO_RULE_MATCHED


def test_conflicting_rules_pick_highest_risk_and_report_others() -> None:
    overlapping_rules = [
        RuleDefinition("rule_a", "value >= 10", 2, "Baixo", position=0),
        RuleDefinition("rule_b", "value >= 10", 6, "Critico", position=1),
    ]
    evaluation = evaluate_rule_set(overlapping_rules, ["value"], {"value": 20})
    assert evaluation.outcome is RuleEvaluationOutcome.MATCHED
    assert evaluation.matched_rule.rule_key == "rule_b"
    assert evaluation.risk_level == 6
    assert [rule.rule_key for rule in evaluation.other_matched_rules] == ["rule_a"]


def test_invalid_input_type_is_inconclusive_not_a_crash() -> None:
    evaluation = evaluate_rule_set(
        SPO2_RULES, SPO2_REQUIRED_INPUTS, {"spo2_percent": "noventa e oito"}
    )
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.INVALID_INPUT


def test_string_based_rule_set_matches() -> None:
    consciousness_rules = [
        RuleDefinition("alert", "acvpu_level == 'alerta'", 1, "Alerta", position=0),
        RuleDefinition(
            "unresponsive", "acvpu_level == 'nao_responde'", 6, "Nao responde", position=1
        ),
    ]
    evaluation = evaluate_rule_set(
        consciousness_rules, ["acvpu_level"], {"acvpu_level": "nao_responde"}
    )
    assert evaluation.matched_rule.rule_key == "unresponsive"


# Cobertura completa da tabela de pressao arterial (docs/CLASSIFICACAO_
# DADOS_CLINICOS.md secao 1, backend/clinical_rules/seeds/blood_pressure.
# yaml v0.2.0) - antes so 3 das 8 faixas documentadas estavam
# implementadas, deixando sistolica 91-180 mmHg sem cobertura.
BLOOD_PRESSURE_RULES = [
    RuleDefinition("hypotension_severe", "systolic_mmhg <= 90", 6, "Hipotensao grave", position=0),
    RuleDefinition("hypotension", "91 <= systolic_mmhg <= 100", 4, "Hipotensao", position=1),
    RuleDefinition(
        "low_borderline", "101 <= systolic_mmhg <= 110", 3, "Limitrofe baixa", position=2
    ),
    RuleDefinition(
        "normal",
        "111 <= systolic_mmhg <= 119 and diastolic_mmhg < 80",
        1,
        "Normal",
        position=3,
    ),
    RuleDefinition(
        "elevated",
        "120 <= systolic_mmhg <= 129 and diastolic_mmhg < 80",
        3,
        "Pressao elevada",
        position=4,
    ),
    RuleDefinition(
        "hypertension_stage_1",
        "(130 <= systolic_mmhg <= 139) or (80 <= diastolic_mmhg <= 89)",
        3,
        "Hipertensao estagio 1",
        position=5,
    ),
    RuleDefinition(
        "hypertension_stage_2",
        "(140 <= systolic_mmhg <= 180) or (90 <= diastolic_mmhg <= 120)",
        4,
        "Hipertensao estagio 2",
        position=6,
    ),
    RuleDefinition(
        "hypertensive_crisis",
        "systolic_mmhg > 180 or diastolic_mmhg > 120",
        6,
        "Crise hipertensiva",
        position=7,
    ),
]
BLOOD_PRESSURE_REQUIRED_INPUTS = ["systolic_mmhg", "diastolic_mmhg"]


def test_blood_pressure_hypotension_severe() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 85, "diastolic_mmhg": 60},
    )
    assert evaluation.matched_rule.rule_key == "hypotension_severe"
    assert evaluation.risk_level == 6


def test_blood_pressure_hypotension() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 95, "diastolic_mmhg": 65},
    )
    assert evaluation.matched_rule.rule_key == "hypotension"
    assert evaluation.risk_level == 4


def test_blood_pressure_low_borderline() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 105, "diastolic_mmhg": 65},
    )
    assert evaluation.matched_rule.rule_key == "low_borderline"
    assert evaluation.risk_level == 3


def test_blood_pressure_normal_requires_both_systolic_and_diastolic() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 115, "diastolic_mmhg": 75},
    )
    assert evaluation.matched_rule.rule_key == "normal"
    assert evaluation.risk_level == 1


def test_blood_pressure_elevated() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 125, "diastolic_mmhg": 70},
    )
    assert evaluation.matched_rule.rule_key == "elevated"
    assert evaluation.risk_level == 3


def test_blood_pressure_hypertension_stage_1_by_systolic() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 135, "diastolic_mmhg": 70},
    )
    assert evaluation.matched_rule.rule_key == "hypertension_stage_1"


def test_blood_pressure_hypertension_stage_1_by_diastolic_conflict_picks_highest_risk() -> None:
    """Sistolica 115 (Normal-elegivel) e diastolica 85 (estagio 1) caem
    em categorias diferentes - regra de conflito do documento: usar
    sempre a de MAIOR risco. "Normal" exige diastolica < 80, entao nem
    chega a casar aqui; o motor deve escolher hypertension_stage_1."""
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 115, "diastolic_mmhg": 85},
    )
    assert evaluation.matched_rule.rule_key == "hypertension_stage_1"
    assert evaluation.risk_level == 3


def test_blood_pressure_hypertension_stage_2() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 150, "diastolic_mmhg": 95},
    )
    assert evaluation.matched_rule.rule_key == "hypertension_stage_2"
    assert evaluation.risk_level == 4


def test_blood_pressure_hypertensive_crisis() -> None:
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 190, "diastolic_mmhg": 70},
    )
    assert evaluation.matched_rule.rule_key == "hypertensive_crisis"
    assert evaluation.risk_level == 6


def test_blood_pressure_crisis_conflict_beats_stage_2() -> None:
    """Sistolica 150 (estagio 2) e diastolica 125 (crise) - a regra de
    conflito do documento exige escolher a de maior risco: crise
    hipertensiva (nivel 6) vence estagio 2 (nivel 4)."""
    evaluation = evaluate_rule_set(
        BLOOD_PRESSURE_RULES,
        BLOOD_PRESSURE_REQUIRED_INPUTS,
        {"systolic_mmhg": 150, "diastolic_mmhg": 125},
    )
    assert evaluation.matched_rule.rule_key == "hypertensive_crisis"
    assert evaluation.risk_level == 6


# Regras de correlacao de dor (docs/CLASSIFICACAO_DADOS_CLINICOS.md secao
# 8: "a intensidade numerica isolada NAO e suficiente para classificar
# urgencia"; localizacao toracica/abdominal + inicio subito, e sintomas
# de alarme associados, podem ELEVAR o risco independentemente do numero
# - backend/clinical_rules/seeds/pain.yaml v0.2.0).
PAIN_RULES_WITH_CONTEXT = [
    RuleDefinition("no_pain", "pain_score == 0", 1, "Sem dor", position=0),
    RuleDefinition("mild_pain", "1 <= pain_score <= 3", 1, "Dor leve", position=1),
    RuleDefinition("moderate_pain", "4 <= pain_score <= 6", 3, "Dor moderada", position=2),
    RuleDefinition("intense_pain", "7 <= pain_score <= 9", 4, "Dor intensa", position=3),
    RuleDefinition("unbearable_pain", "pain_score == 10", 6, "Dor insuportavel", position=4),
    RuleDefinition(
        "alarm_symptoms_elevate_risk",
        "alarm_symptoms_present == True",
        5,
        "Dor com sintomas de alarme associados",
        position=5,
    ),
    RuleDefinition(
        "thoracic_or_abdominal_sudden_onset_elevates_risk",
        "(location == 'toracica' or location == 'abdominal') and sudden_onset == True",
        5,
        "Dor toracica/abdominal de inicio subito",
        position=6,
    ),
]
PAIN_REQUIRED_INPUTS = ["pain_score", "location", "sudden_onset", "alarm_symptoms_present"]


def test_pain_low_score_without_alarm_context_stays_low_risk() -> None:
    evaluation = evaluate_rule_set(
        PAIN_RULES_WITH_CONTEXT,
        PAIN_REQUIRED_INPUTS,
        {
            "pain_score": 5,
            "location": "membro",
            "sudden_onset": False,
            "alarm_symptoms_present": False,
        },
    )
    assert evaluation.matched_rule.rule_key == "moderate_pain"
    assert evaluation.risk_level == 3


def test_pain_thoracic_sudden_onset_beats_higher_raw_score() -> None:
    """Exemplo textual do documento: dor toracica 5/10 subita (nivel 5)
    deve superar dor musculoesqueletica 8/10 (nivel 4, intense_pain)."""
    thoracic_low_score = evaluate_rule_set(
        PAIN_RULES_WITH_CONTEXT,
        PAIN_REQUIRED_INPUTS,
        {
            "pain_score": 5,
            "location": "toracica",
            "sudden_onset": True,
            "alarm_symptoms_present": False,
        },
    )
    musculoskeletal_high_score = evaluate_rule_set(
        PAIN_RULES_WITH_CONTEXT,
        PAIN_REQUIRED_INPUTS,
        {
            "pain_score": 8,
            "location": "membro",
            "sudden_onset": False,
            "alarm_symptoms_present": False,
        },
    )
    assert thoracic_low_score.risk_level == 5
    assert musculoskeletal_high_score.risk_level == 4
    assert thoracic_low_score.risk_level > musculoskeletal_high_score.risk_level


def test_pain_alarm_symptoms_elevate_risk_regardless_of_score() -> None:
    evaluation = evaluate_rule_set(
        PAIN_RULES_WITH_CONTEXT,
        PAIN_REQUIRED_INPUTS,
        {
            "pain_score": 2,
            "location": "outra",
            "sudden_onset": False,
            "alarm_symptoms_present": True,
        },
    )
    assert evaluation.matched_rule.rule_key == "alarm_symptoms_elevate_risk"
    assert evaluation.risk_level == 5


def test_pain_missing_context_field_is_inconclusive() -> None:
    """Contexto ampliado e OBRIGATORIO (nao opcional) - ausencia de
    qualquer campo deve ser INCONCLUSIVO, nunca assumir um valor neutro
    silenciosamente."""
    evaluation = evaluate_rule_set(
        PAIN_RULES_WITH_CONTEXT, PAIN_REQUIRED_INPUTS, {"pain_score": 5}
    )
    assert evaluation.outcome is RuleEvaluationOutcome.INCONCLUSIVE
    assert evaluation.inconclusive_reason is RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT


# Convulsao isolada (backend/clinical_rules/seeds/seizure.yaml).
SEIZURE_RULES = [
    RuleDefinition("no_seizure", "seizure_occurred == False", 1, "Sem convulsao", position=0),
    RuleDefinition("seizure_occurred", "seizure_occurred == True", 6, "Convulsao", position=1),
]


def test_seizure_occurred_is_critical() -> None:
    evaluation = evaluate_rule_set(SEIZURE_RULES, ["seizure_occurred"], {"seizure_occurred": True})
    assert evaluation.matched_rule.rule_key == "seizure_occurred"
    assert evaluation.risk_level == 6


def test_seizure_not_occurred_is_low_risk() -> None:
    evaluation = evaluate_rule_set(SEIZURE_RULES, ["seizure_occurred"], {"seizure_occurred": False})
    assert evaluation.matched_rule.rule_key == "no_seizure"
    assert evaluation.risk_level == 1


# Debito urinario / diurese (backend/clinical_rules/seeds/urine_output.yaml).
URINE_OUTPUT_RULES = [
    RuleDefinition("anuria", "urine_output_ml_h < 10", 6, "Anuria", position=0),
    RuleDefinition(
        "severe_oliguria", "10 <= urine_output_ml_h < 30", 5, "Oliguria grave", position=1
    ),
    RuleDefinition("oliguria", "30 <= urine_output_ml_h < 50", 4, "Oliguria", position=2),
    RuleDefinition("normal", "50 <= urine_output_ml_h <= 200", 1, "Diurese normal", position=3),
    RuleDefinition("polyuria", "urine_output_ml_h > 200", 3, "Poliuria", position=4),
]


def test_urine_output_anuria() -> None:
    evaluation = evaluate_rule_set(
        URINE_OUTPUT_RULES, ["urine_output_ml_h"], {"urine_output_ml_h": 5}
    )
    assert evaluation.matched_rule.rule_key == "anuria"
    assert evaluation.risk_level == 6


def test_urine_output_normal() -> None:
    evaluation = evaluate_rule_set(
        URINE_OUTPUT_RULES, ["urine_output_ml_h"], {"urine_output_ml_h": 100}
    )
    assert evaluation.matched_rule.rule_key == "normal"
    assert evaluation.risk_level == 1


def test_urine_output_polyuria() -> None:
    evaluation = evaluate_rule_set(
        URINE_OUTPUT_RULES, ["urine_output_ml_h"], {"urine_output_ml_h": 250}
    )
    assert evaluation.matched_rule.rule_key == "polyuria"
    assert evaluation.risk_level == 3
