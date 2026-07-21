"""Testes puros de `app.administration.service.is_valid_cpf` (sem banco).

Algoritmo publico de digitos verificadores (modulo 11) - nao consulta a
Receita Federal, apenas rejeita valores estruturalmente invalidos.
"111.444.777-35" e um CPF de teste amplamente usado (digitos verificadores
corretos) sem correspondencia a uma pessoa real conhecida.
"""

from __future__ import annotations

from app.administration.service import is_valid_cpf


def test_accepts_valid_cpf_with_mask() -> None:
    assert is_valid_cpf("111.444.777-35") is True


def test_accepts_valid_cpf_without_mask() -> None:
    assert is_valid_cpf("11144477735") is True


def test_rejects_wrong_check_digit() -> None:
    assert is_valid_cpf("111.444.777-34") is False


def test_rejects_all_repeated_digits() -> None:
    assert is_valid_cpf("111.111.111-11") is False


def test_rejects_wrong_length() -> None:
    assert is_valid_cpf("123456789") is False


def test_rejects_non_numeric_garbage() -> None:
    assert is_valid_cpf("abc.def.ghi-jk") is False
