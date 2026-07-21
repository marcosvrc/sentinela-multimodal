"""Deteccao de anomalia em serie temporal de sinal vital.

Metodo determinístico e explicavel - nao um modelo treinado -, consistente
com o principio de que o risco clinico e calculado por regras
deterministicas, nunca por LLM/estatistica como fonte de verdade da
classificacao: esta deteccao NUNCA alimenta `RiskConsolidation` nem altera
a classificacao de risco do motor de regras. E um alerta consultivo
separado, para fins de monitoramento preventivo.

Dois criterios independentes, cada leitura pode disparar por um ou ambos:

1. **Desvio em relacao a linha de base** (media/desvio-padrao das leituras
   anteriores do paciente para o mesmo sinal, "self-baseline"): o metodo
   estatistico mais simples e auditavel para "o normal deste paciente"
   sem exigir uma populacao de referencia externa. Exige um numero minimo
   de leituras anteriores (`MIN_BASELINE_SAMPLES`); com historico
   insuficiente, nunca infere - resultado explicito "inconclusivo",
   mesmo padrao usado em `app.rules_engine` para dado insuficiente.
2. **Variacao abrupta entre leituras consecutivas** ("rate of change"):
   captura uma mudanca clinicamente relevante mesmo quando a linha de
   base ainda nao se estabeleceu ou quando o novo valor continua dentro
   da faixa historica mas mudou rapido demais (ex.: FC subindo 40 bpm em
   poucos minutos).

Nenhum dos dois criterios substitui a faixa fisiologicamente possivel
(`app.observations.validation`, ja aplicada na escrita) nem os limiares
clinicos de risco (`clinical_rules/seeds/*.yaml`) - sao camadas
independentes e complementares.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.enums import AlertSeverity

DETECTOR_VERSION = "anomaly_detection.self_baseline_v1"

MIN_BASELINE_SAMPLES = 3
BASELINE_WINDOW_SIZE = 10

# Configuracao por tipo de observacao numerica simples: limiar de desvio
# (em desvios-padrao da linha de base) para cada severidade, e limiar de
# variacao abrupta absoluta entre leituras consecutivas dentro da janela de
# tempo `rate_of_change_window`. Escolhidos a partir de literatura clinica
# geral de sinais de alerta precoce (ex.: NEWS2 usa deltas semelhantes de
# FC/FR), documentados aqui como heuristica MVP - nao substituem validacao
# clinica formal.
@dataclass(frozen=True)
class VitalSignThresholds:
    moderate_sd: float
    high_sd: float
    critical_sd: float
    rate_of_change_absolute: float
    rate_of_change_window: timedelta


VITAL_SIGN_THRESHOLDS: dict[str, VitalSignThresholds] = {
    "HEART_RATE": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=40.0,
        rate_of_change_window=timedelta(minutes=30),
    ),
    "RESPIRATORY_RATE": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=10.0,
        rate_of_change_window=timedelta(minutes=30),
    ),
    "SPO2": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=6.0,
        rate_of_change_window=timedelta(minutes=30),
    ),
    "TEMPERATURE": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=1.5,
        rate_of_change_window=timedelta(hours=2),
    ),
    "BLOOD_PRESSURE_SYSTOLIC": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=40.0,
        rate_of_change_window=timedelta(minutes=30),
    ),
    "BLOOD_PRESSURE_DIASTOLIC": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=25.0,
        rate_of_change_window=timedelta(minutes=30),
    ),
    "URINE_OUTPUT": VitalSignThresholds(
        moderate_sd=2.0,
        high_sd=3.0,
        critical_sd=4.0,
        rate_of_change_absolute=30.0,
        rate_of_change_window=timedelta(hours=1),
    ),
}


@dataclass(frozen=True)
class VitalSignSample:
    measured_at: datetime
    value: float


@dataclass(frozen=True)
class AnomalyDetectionResult:
    """Resultado de uma execucao da deteccao para uma unica leitura."""

    is_anomalous: bool
    severity: AlertSeverity | None
    confidence: float | None
    triggered_by: tuple[str, ...]
    evidence: dict


def detect_vital_sign_anomaly(
    signal_key: str,
    history: list[VitalSignSample],
    new_sample: VitalSignSample,
) -> AnomalyDetectionResult:
    """Avalia se `new_sample` e anomalo em relacao a `history` (leituras
    anteriores do MESMO paciente e MESMO sinal, mais antigas que
    `new_sample.measured_at`, ordem cronologica).

    `signal_key` deve ser uma chave de `VITAL_SIGN_THRESHOLDS`. Sinais sem
    configuracao de limiar devolvem sempre `is_anomalous=False` (nunca
    inventa um limiar generico) - a lista deliberadamente cobre os sinais
    vitais monitorados: batimentos, pressao arterial e oxigenacao, entre
    outros.
    """
    thresholds = VITAL_SIGN_THRESHOLDS.get(signal_key)
    if thresholds is None:
        return AnomalyDetectionResult(
            is_anomalous=False,
            severity=None,
            confidence=None,
            triggered_by=(),
            evidence={"reason": "SIGNAL_NOT_CONFIGURED"},
        )

    recent_history = sorted(history, key=lambda s: s.measured_at)[-BASELINE_WINDOW_SIZE:]

    baseline_result = _evaluate_baseline_deviation(thresholds, recent_history, new_sample)
    rate_result = _evaluate_rate_of_change(thresholds, recent_history, new_sample)

    triggered_by: list[str] = []
    severities: list[AlertSeverity] = []
    evidence: dict = {
        "signal": signal_key,
        "value": new_sample.value,
        "baseline_sample_count": len(recent_history),
    }

    if baseline_result is not None:
        severity, deviation_sd, mean, stddev = baseline_result
        triggered_by.append("BASELINE_DEVIATION")
        severities.append(severity)
        evidence["baseline_deviation"] = {
            "baseline_mean": round(mean, 2),
            "baseline_stddev": round(stddev, 2),
            # `deviation_sd=None` com `baseline_constant=True` significa
            # "linha de base sem nenhuma variacao ate agora, e este valor
            # difere dela" - nao ha desvio-padrao para dividir, entao nao
            # existe um numero de desvios-padrao valido a reportar (nunca
            # serializa infinito: JSON nao suporta o valor).
            "deviation_sd": round(deviation_sd, 2) if deviation_sd is not None else None,
            "baseline_constant": deviation_sd is None,
        }

    if rate_result is not None:
        severity, delta, previous_sample = rate_result
        triggered_by.append("RATE_OF_CHANGE")
        severities.append(severity)
        evidence["rate_of_change"] = {
            "previous_value": previous_sample.value,
            "previous_measured_at": previous_sample.measured_at.isoformat(),
            "delta": round(delta, 2),
        }

    if not triggered_by:
        return AnomalyDetectionResult(
            is_anomalous=False,
            severity=None,
            confidence=None,
            triggered_by=(),
            evidence=evidence,
        )

    final_severity = max(severities, key=_SEVERITY_ORDER.index)
    confidence = _confidence_from_evidence(evidence)

    return AnomalyDetectionResult(
        is_anomalous=True,
        severity=final_severity,
        confidence=confidence,
        triggered_by=tuple(triggered_by),
        evidence=evidence,
    )


_SEVERITY_ORDER = [AlertSeverity.MODERATE, AlertSeverity.HIGH, AlertSeverity.CRITICAL]


def _severity_for_deviation(
    thresholds: VitalSignThresholds, deviation_sd: float
) -> AlertSeverity | None:
    if deviation_sd >= thresholds.critical_sd:
        return AlertSeverity.CRITICAL
    if deviation_sd >= thresholds.high_sd:
        return AlertSeverity.HIGH
    if deviation_sd >= thresholds.moderate_sd:
        return AlertSeverity.MODERATE
    return None


def _evaluate_baseline_deviation(
    thresholds: VitalSignThresholds,
    recent_history: list[VitalSignSample],
    new_sample: VitalSignSample,
) -> tuple[AlertSeverity, float | None, float, float] | None:
    if len(recent_history) < MIN_BASELINE_SAMPLES:
        return None

    values = [s.value for s in recent_history]
    mean = statistics.mean(values)
    stddev = statistics.pstdev(values)

    if stddev == 0:
        # Historico completamente constante: qualquer desvio e tratado
        # como o limiar critico (nunca divide por zero, nunca finge que
        # nao ha anomalia so por limitacao aritmetica) - mas sem
        # desvio-padrao nao existe um numero de "desvios-padrao" valido a
        # reportar, entao `deviation_sd` fica `None` (ver
        # `_evaluate_baseline_deviation`/evidencia acima).
        if new_sample.value == mean:
            return None
        return (AlertSeverity.CRITICAL, None, mean, stddev)

    deviation_sd = abs(new_sample.value - mean) / stddev
    severity = _severity_for_deviation(thresholds, deviation_sd)
    if severity is None:
        return None
    return (severity, deviation_sd, mean, stddev)


def _evaluate_rate_of_change(
    thresholds: VitalSignThresholds,
    recent_history: list[VitalSignSample],
    new_sample: VitalSignSample,
) -> tuple[AlertSeverity, float, VitalSignSample] | None:
    if not recent_history:
        return None

    previous_sample = recent_history[-1]
    elapsed = new_sample.measured_at - previous_sample.measured_at
    if elapsed <= timedelta(0) or elapsed > thresholds.rate_of_change_window:
        return None

    delta = abs(new_sample.value - previous_sample.value)
    if delta < thresholds.rate_of_change_absolute:
        return None

    # Variacao abrupta e binaria (ultrapassou o limiar absoluto ou nao) -
    # classificada como HIGH; nao ha um segundo limiar "critico" separado
    # porque o valor absoluto ja foi calibrado para representar uma
    # mudanca clinicamente relevante em si.
    return (AlertSeverity.HIGH, delta, previous_sample)


def _confidence_from_evidence(evidence: dict) -> float:
    """Confianca heuristica (0-1), NUNCA apresentada como probabilidade
    calibrada - apenas uma indicacao relativa de quao longe do padrao
    esperado a leitura esta, para ajudar a equipe a priorizar. Sempre
    disclosed como tal na evidencia do alerta (`detector_source`)."""
    baseline = evidence.get("baseline_deviation")
    if baseline is not None:
        if baseline["baseline_constant"]:
            return 1.0
        return round(min(1.0, baseline["deviation_sd"] / 6.0), 2)
    return 0.6  # so rate-of-change disparou: confianca fixa moderada, sem linha de base
