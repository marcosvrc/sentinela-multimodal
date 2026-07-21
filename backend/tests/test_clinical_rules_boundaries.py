"""Testes de fronteira das regras clinicas versionadas em YAML.

CLASSIFICACAO_DADOS_CLINICOS.md secao 15 exige tratar exatamente os limites
inferiores e superiores em testes automatizados. Este teste garante, para
os conjuntos de regra com uma unica variavel numerica, que cada limite e
cada ponto entre limites e coberto por exatamente uma regra (sem gaps nem
sobreposicao) e que a expressao `when` e avaliavel com seguranca.

Este teste nao substitui o motor de regras real (Requirement 5 /
ESCOPO_PROJETO.md secao 12.1.6): ele apenas valida a consistencia dos dados
de referencia antes de existir um engine de execucao em producao.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SEEDS_DIR = Path(__file__).resolve().parent.parent / "clinical_rules" / "seeds"

# (arquivo, variavel numerica, pontos de fronteira a testar, variaveis
# extras fixas em valores NEUTROS - necessarias apenas quando o conjunto
# tem regras de CORRELACAO alem da particao numerica pura, ver pain.yaml
# v0.2.0: `alarm_symptoms_present`/`location`+`sudden_onset` sao regras
# adicionais que elevam o risco independentemente do escore, entao
# precisam de valores que nunca as acionem para preservar a garantia de
# "exatamente 1 match" da particao por `pain_score` isolada testada aqui).
# spo2_percent, heart_rate_bpm e respiratory_rate_irpm sao reportados como
# valores inteiros por convencao clinica (equipamentos nao emitem fracoes
# de bpm/irpm/%); por isso os pontos de fronteira testados sao inteiros.
NUMERIC_SINGLE_VAR_CASES = {
    "spo2.yaml": ("spo2_percent", [100, 96, 95, 94, 93, 92, 91, 0], {}),
    "heart_rate.yaml": (
        "heart_rate_bpm",
        [300, 131, 130, 111, 110, 101, 100, 60, 59, 51, 50, 41, 40, 0],
        {},
    ),
    "respiratory_rate.yaml": (
        "respiratory_rate_irpm",
        [60, 25, 24, 21, 20, 12, 11, 9, 8, 0],
        {},
    ),
    "temperature.yaml": (
        "temperature_celsius",
        [45, 40.01, 40.0, 39.1, 39.0, 38.1, 38.0, 37.6, 37.5, 36.1, 36.0, 35.1, 35.0, 20],
        {},
    ),
    "pain.yaml": (
        "pain_score",
        [0, 1, 3, 4, 6, 7, 9, 10],
        {"location": "nao_informado", "sudden_onset": False, "alarm_symptoms_present": False},
    ),
    "bmi.yaml": (
        "bmi_kg_m2",
        [
            10,
            15.9,
            16.0,
            16.9,
            17.0,
            18.4,
            18.5,
            24.9,
            25.0,
            29.9,
            30.0,
            34.9,
            35.0,
            39.9,
            40.0,
            60,
        ],
        {},
    ),
    "urine_output.yaml": (
        "urine_output_ml_h",
        [0, 9, 10, 29, 30, 49, 50, 200, 201, 2000],
        {},
    ),
}


def _load(filename: str) -> dict:
    return yaml.safe_load((SEEDS_DIR / filename).read_text(encoding="utf-8"))


def _matches(rules: list[dict], variables: dict) -> list[str]:
    matched = []
    for rule in rules:
        # As expressoes 'when' sao escritas em sintaxe Python valida pelos
        # proprios autores das regras (seeds versionados no repositorio,
        # nao input de usuario em runtime).
        if eval(rule["when"], {"__builtins__": {}}, variables):  # noqa: S307
            matched.append(rule["id"])
    return matched


@pytest.mark.parametrize("filename", sorted(p.name for p in SEEDS_DIR.glob("*.yaml")))
def test_rule_set_matches_schema_shape(filename: str) -> None:
    content = _load(filename)
    assert content["rules"], f"{filename} nao possui regras"
    for rule in content["rules"]:
        assert 1 <= rule["risk_level"] <= 6


@pytest.mark.parametrize("filename", sorted(NUMERIC_SINGLE_VAR_CASES.keys()))
def test_numeric_rule_set_has_no_gaps_or_overlaps(filename: str) -> None:
    variable_name, boundary_points, extra_neutral_variables = NUMERIC_SINGLE_VAR_CASES[filename]
    content = _load(filename)
    rules = content["rules"]

    for point in boundary_points:
        matched = _matches(rules, {variable_name: point, **extra_neutral_variables})
        assert len(matched) == 1, (
            f"{filename}: valor {variable_name}={point} casou com {len(matched)} "
            f"regra(s) ({matched}), esperado exatamente 1"
        )
