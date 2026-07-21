"""Testes do avaliador seguro de expressoes (sem banco)."""

from __future__ import annotations

import pytest

from app.rules_engine.evaluator import (
    MissingVariableError,
    UnsafeExpressionError,
    compile_condition,
    evaluate_condition,
)


def test_simple_comparison_true() -> None:
    assert evaluate_condition("spo2_percent >= 96", {"spo2_percent": 98}) is True


def test_simple_comparison_false() -> None:
    assert evaluate_condition("spo2_percent >= 96", {"spo2_percent": 90}) is False


def test_chained_comparison() -> None:
    assert evaluate_condition("94 <= spo2_percent <= 95", {"spo2_percent": 94}) is True
    assert evaluate_condition("94 <= spo2_percent <= 95", {"spo2_percent": 96}) is False


def test_and_or() -> None:
    assert (
        evaluate_condition(
            "systolic_mmhg > 180 or diastolic_mmhg > 120",
            {"systolic_mmhg": 190, "diastolic_mmhg": 70},
        )
        is True
    )
    assert (
        evaluate_condition(
            "111 <= systolic_mmhg <= 119 and diastolic_mmhg < 80",
            {"systolic_mmhg": 115, "diastolic_mmhg": 75},
        )
        is True
    )


def test_string_equality() -> None:
    assert evaluate_condition("acvpu_level == 'alerta'", {"acvpu_level": "alerta"}) is True
    assert evaluate_condition("acvpu_level == 'alerta'", {"acvpu_level": "responde_dor"}) is False


def test_not_operator() -> None:
    assert evaluate_condition("not (spo2_percent >= 96)", {"spo2_percent": 90}) is True


def test_missing_variable_raises() -> None:
    with pytest.raises(MissingVariableError) as exc_info:
        evaluate_condition("spo2_percent >= 96", {})
    assert exc_info.value.variable_name == "spo2_percent"


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo pwned')",
        "os.system('echo pwned')",
        "(lambda: 1)()",
        "[x for x in range(10)]",
        "open('/etc/passwd')",
        "1 if True else 2",
        "spo2_percent.bit_length()",
        "spo2_percent[0]",
        "f'{spo2_percent}'",
    ],
)
def test_unsafe_expressions_are_rejected(expression: str) -> None:
    with pytest.raises(UnsafeExpressionError):
        compile_condition(expression)


def test_incompatible_type_comparison_raises_unsafe_expression_error() -> None:
    with pytest.raises(UnsafeExpressionError):
        evaluate_condition("spo2_percent >= 96", {"spo2_percent": "not-a-number"})


def test_non_boolean_result_raises_unsafe_expression_error() -> None:
    with pytest.raises(UnsafeExpressionError):
        evaluate_condition("spo2_percent", {"spo2_percent": 98})


def test_compile_condition_validates_without_evaluating() -> None:
    condition = compile_condition("spo2_percent >= 96")
    assert condition.evaluate({"spo2_percent": 100}) is True
    assert condition.evaluate({"spo2_percent": 50}) is False
