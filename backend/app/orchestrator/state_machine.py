"""Maquina de estados da analise, execucao real das transicoes.

`app.core.enums.ANALYSIS_STATUS_TRANSITIONS` e a fonte de verdade das
transicoes validas; este modulo ENFORCA essa tabela em vez de so
declara-la - qualquer transicao de estado da analise, seja pela API
(submissao, cancelamento) seja pelo orquestrador (processamento, falha),
passa por `transition()`.
"""

from __future__ import annotations

from app.core.enums import ANALYSIS_STATUS_TRANSITIONS, AnalysisStatus


class InvalidTransitionError(Exception):
    def __init__(self, current: AnalysisStatus, target: AnalysisStatus):
        self.current = current
        self.target = target
        super().__init__(f"Transicao invalida: {current.value} -> {target.value}")


def transition(current: AnalysisStatus, target: AnalysisStatus) -> AnalysisStatus:
    """Retorna `target` se a transicao for valida; levanta `InvalidTransitionError` senao."""
    allowed = ANALYSIS_STATUS_TRANSITIONS.get(current, ())
    if target not in allowed:
        raise InvalidTransitionError(current, target)
    return target
