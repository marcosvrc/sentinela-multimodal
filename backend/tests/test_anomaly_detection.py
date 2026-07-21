"""Testes puros de `app.anomaly_detection.detection` (sem banco de dados -
mesma filosofia de `app.rules_engine.engine`: logica testada isoladamente
da persistencia)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.anomaly_detection.detection import (
    VitalSignSample,
    detect_vital_sign_anomaly,
)
from app.core.enums import AlertSeverity

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _samples(
    values: list[float], *, start=BASE_TIME, step=timedelta(hours=1)
) -> list[VitalSignSample]:
    return [VitalSignSample(measured_at=start + step * i, value=v) for i, v in enumerate(values)]


class TestUnconfiguredSignal:
    def test_signal_without_thresholds_never_flags_anomaly(self) -> None:
        history = _samples([60, 61, 62])
        new_sample = VitalSignSample(measured_at=BASE_TIME + timedelta(hours=10), value=999)
        result = detect_vital_sign_anomaly("WEIGHT", history, new_sample)
        assert result.is_anomalous is False
        assert result.evidence["reason"] == "SIGNAL_NOT_CONFIGURED"


class TestInsufficientHistory:
    def test_fewer_than_minimum_samples_never_flags_baseline_deviation(self) -> None:
        history = _samples([80, 82])  # menos que MIN_BASELINE_SAMPLES=3
        new_sample = VitalSignSample(
            measured_at=BASE_TIME + timedelta(hours=2, minutes=1), value=180
        )
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        # Sem linha de base nao ha desvio, mas rate-of-change ainda pode
        # disparar se a janela de tempo permitir - aqui o intervalo (2h+1min)
        # excede a janela de 30min do HEART_RATE, entao nada dispara.
        assert result.is_anomalous is False


class TestBaselineDeviation:
    def test_stable_heart_rate_history_does_not_flag_similar_value(self) -> None:
        history = _samples([78, 80, 79, 81, 80])
        new_sample = VitalSignSample(
            measured_at=BASE_TIME + timedelta(hours=5, minutes=45), value=81
        )
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        assert result.is_anomalous is False

    def test_large_deviation_from_stable_baseline_flags_critical(self) -> None:
        history = _samples([78, 80, 79, 81, 80])
        new_sample = VitalSignSample(
            measured_at=BASE_TIME + timedelta(hours=5, minutes=45), value=180
        )
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        assert result.is_anomalous is True
        assert result.severity is AlertSeverity.CRITICAL
        assert "BASELINE_DEVIATION" in result.triggered_by
        assert result.confidence is not None

    def test_constant_baseline_with_any_new_value_flags_critical_without_crashing(self) -> None:
        history = _samples([98, 98, 98, 98])
        new_sample = VitalSignSample(measured_at=BASE_TIME + timedelta(hours=10), value=90)
        result = detect_vital_sign_anomaly("SPO2", history, new_sample)
        assert result.is_anomalous is True
        assert result.severity is AlertSeverity.CRITICAL
        assert result.evidence["baseline_deviation"]["deviation_sd"] is None
        assert result.evidence["baseline_deviation"]["baseline_constant"] is True
        assert result.confidence == 1.0

    def test_constant_baseline_with_same_value_is_not_anomalous(self) -> None:
        history = _samples([98, 98, 98, 98])
        new_sample = VitalSignSample(measured_at=BASE_TIME + timedelta(hours=10), value=98)
        result = detect_vital_sign_anomaly("SPO2", history, new_sample)
        assert result.is_anomalous is False


class TestRateOfChange:
    def test_abrupt_jump_within_window_flags_high_even_with_short_history(self) -> None:
        history = _samples([75, 76], step=timedelta(minutes=10))
        last_measured_at = history[-1].measured_at
        new_sample = VitalSignSample(measured_at=last_measured_at + timedelta(minutes=5), value=130)
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        assert result.is_anomalous is True
        assert "RATE_OF_CHANGE" in result.triggered_by
        assert result.severity is AlertSeverity.HIGH

    def test_abrupt_jump_outside_time_window_does_not_trigger_rate_of_change(self) -> None:
        history = _samples([75, 76], step=timedelta(minutes=10))
        last_measured_at = history[-1].measured_at
        new_sample = VitalSignSample(measured_at=last_measured_at + timedelta(hours=5), value=130)
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        assert "RATE_OF_CHANGE" not in result.triggered_by

    def test_small_change_within_window_does_not_trigger(self) -> None:
        history = _samples([75, 76], step=timedelta(minutes=10))
        last_measured_at = history[-1].measured_at
        new_sample = VitalSignSample(measured_at=last_measured_at + timedelta(minutes=5), value=80)
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        assert result.is_anomalous is False


class TestEvidenceShape:
    def test_evidence_is_json_serializable(self) -> None:
        import json

        history = _samples([78, 80, 79, 81, 80])
        new_sample = VitalSignSample(
            measured_at=BASE_TIME + timedelta(hours=5, minutes=45), value=180
        )
        result = detect_vital_sign_anomaly("HEART_RATE", history, new_sample)
        json.dumps(result.evidence)  # nao deve levantar (ex.: float('inf') quebraria)
