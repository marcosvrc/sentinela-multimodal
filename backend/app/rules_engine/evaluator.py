"""Avaliador seguro de expressoes booleanas de regra clinica.

As expressoes `when` das regras (backend/clinical_rules/seeds/*.yaml, ex:
`"94 <= spo2_percent <= 95"`) usam uma sintaxe deliberadamente parecida com
Python para ser legivel por quem aprova as regras clinicamente. Isso NAO
significa que sao avaliadas com `eval()`: `eval`/`exec` executariam
qualquer expressao Python (chamada de funcao, import, acesso a atributo
etc.), o que é inaceitavel para conteudo que hoje vem de um YAML revisado
manualmente e no futuro podera vir de um cadastro administrativo (somente
o administrador clinico podera publicar regras clinicas, mas publicar nao
deve implicar execucao de codigo arbitrario).

Este modulo faz o parsing com `ast.parse(..., mode="eval")` e interpreta
manualmente apenas uma lista fechada (allowlist) de nos: comparacoes
(inclusive encadeadas, `a <= x <= b`), `and`/`or`/`not`, nomes de variavel
(devem estar no dicionario de entradas) e constantes numericas/string/bool.
Qualquer outro no (chamada de funcao, atributo, subscrito, f-string,
compreensao, etc.) e rejeitado antes da avaliacao.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

Number = int | float
Scalar = Number | str | bool | None

_ALLOWED_COMPARE_OPS: dict[type[ast.cmpop], object] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}


class UnsafeExpressionError(Exception):
    """A expressao contem sintaxe fora da allowlist (nao sera avaliada)."""


class MissingVariableError(Exception):
    """A expressao referencia uma variavel ausente do dicionario de entradas."""

    def __init__(self, variable_name: str):
        self.variable_name = variable_name
        super().__init__(f"Variavel nao informada: {variable_name}")


@dataclass(frozen=True)
class CompiledCondition:
    """Expressao ja validada (parseada e checada contra a allowlist).

    Separar "compilar" de "avaliar" permite validar todas as condicoes de
    um conjunto de regras no momento do seed/publicacao (falhar cedo em vez
    de descobrir uma expressao invalida so quando um paciente for avaliado).
    """

    source: str
    _tree: ast.Expression

    def evaluate(self, variables: dict[str, Scalar]) -> bool:
        result = _eval_node(self._tree.body, variables)
        if not isinstance(result, bool):
            raise UnsafeExpressionError(
                f"Expressao nao resultou em booleano: {self.source!r} -> {result!r}"
            )
        return result


def compile_condition(expression: str) -> CompiledCondition:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Expressao invalida: {expression!r}") from exc

    _validate_node(tree.body)
    return CompiledCondition(source=expression, _tree=tree)


def evaluate_condition(expression: str, variables: dict[str, Scalar]) -> bool:
    """Atalho para `compile_condition(expression).evaluate(variables)`."""
    return compile_condition(expression).evaluate(variables)


def _validate_node(node: ast.AST) -> None:
    """Levanta `UnsafeExpressionError` se `node` (ou algum filho) nao for permitido."""
    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise UnsafeExpressionError(f"Operador booleano nao suportado: {node.op!r}")
        for value in node.values:
            _validate_node(value)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.Not):
            raise UnsafeExpressionError(f"Operador unario nao suportado: {node.op!r}")
        _validate_node(node.operand)
        return

    if isinstance(node, ast.Compare):
        _validate_node(node.left)
        for op in node.ops:
            if type(op) not in _ALLOWED_COMPARE_OPS:
                raise UnsafeExpressionError(f"Comparador nao suportado: {op!r}")
        for comparator in node.comparators:
            _validate_node(comparator)
        return

    if isinstance(node, ast.Name):
        return

    if isinstance(node, ast.Constant):
        if node.value is not None and not isinstance(node.value, (bool, int, float, str)):
            raise UnsafeExpressionError(f"Constante nao suportada: {node.value!r}")
        return

    raise UnsafeExpressionError(
        f"Elemento de sintaxe nao permitido em expressao de regra: {type(node).__name__}"
    )


def _eval_node(node: ast.AST, variables: dict[str, Scalar]) -> Scalar:
    if isinstance(node, ast.BoolOp):
        values = (_eval_node(value, variables) for value in node.values)
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    if isinstance(node, ast.UnaryOp):
        return not _eval_node(node.operand, variables)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator_node in zip(node.ops, node.comparators, strict=True):
            right = _eval_node(comparator_node, variables)
            if not _apply_comparison(op, left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise MissingVariableError(node.id)
        return variables[node.id]

    if isinstance(node, ast.Constant):
        return node.value

    # Inalcancavel se `_validate_node` rodou antes (sempre roda, via
    # `compile_condition`), mas mantido como defesa em profundidade.
    raise UnsafeExpressionError(f"Elemento de sintaxe nao permitido: {type(node).__name__}")


def _apply_comparison(op: ast.cmpop, left: Scalar, right: Scalar) -> bool:
    try:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right  # type: ignore[operator]
        if isinstance(op, ast.LtE):
            return left <= right  # type: ignore[operator]
        if isinstance(op, ast.Gt):
            return left > right  # type: ignore[operator]
        if isinstance(op, ast.GtE):
            return left >= right  # type: ignore[operator]
    except TypeError as exc:
        raise UnsafeExpressionError(
            f"Comparacao entre tipos incompativeis: {left!r} {op!r} {right!r}"
        ) from exc
    raise UnsafeExpressionError(f"Comparador nao suportado: {op!r}")
