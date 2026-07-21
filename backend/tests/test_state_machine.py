"""Testes da execucao real da maquina de estados (sem banco)."""

from __future__ import annotations

import pytest

from app.core.enums import AnalysisStatus
from app.orchestrator.state_machine import InvalidTransitionError, transition


def test_valid_transition_created_to_uploading() -> None:
    assert transition(AnalysisStatus.CREATED, AnalysisStatus.UPLOADING) is AnalysisStatus.UPLOADING


def test_valid_transition_queued_to_processing() -> None:
    assert transition(AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING) is AnalysisStatus.PROCESSING


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(AnalysisStatus.CREATED, AnalysisStatus.COMPLETED)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for terminal in (
        AnalysisStatus.COMPLETED,
        AnalysisStatus.FAILED_FINAL,
        AnalysisStatus.CANCELLED,
    ):
        with pytest.raises(InvalidTransitionError):
            transition(terminal, AnalysisStatus.QUEUED)


def test_failed_retryable_can_go_back_to_queued() -> None:
    assert (
        transition(AnalysisStatus.FAILED_RETRYABLE, AnalysisStatus.QUEUED) is AnalysisStatus.QUEUED
    )


def test_invalid_transition_error_carries_states() -> None:
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(AnalysisStatus.WAITING_REVIEW, AnalysisStatus.CANCELLED)
    assert exc_info.value.current is AnalysisStatus.WAITING_REVIEW
    assert exc_info.value.target is AnalysisStatus.CANCELLED
