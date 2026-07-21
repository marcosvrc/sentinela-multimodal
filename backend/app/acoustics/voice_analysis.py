"""Analise acustica real do sinal de voz, com foco em deteccao de
alteracoes vocais indicativas de condicoes medicas (cansaco, dispneia).

Este modulo calcula caracteristicas acusticas genuinas a partir das
amostras PCM decodificadas (`app.processors.media_analysis.
parse_wav_pcm_samples`) - energia (RMS), proporcao de pausas, taxa de
passagens por zero (proxy grosseiro de vozeamento) e numero de segmentos de
fala. NAO faz reconhecimento de fala nem identifica palavras: e
processamento de sinal (DSP) puro sobre a amplitude ao longo do tempo.

Os limiares usados para sinalizar um possivel padrao (`generate_vocal_
alteration_hypotheses`) sao heuristicos e deliberadamente conservadores -
mesmo principio de `app.processors.quality` (limiares documentados, nao um
modelo de ML, refinaveis por protocolo clinico). Por isso toda hipotese
gerada aqui e `FindingNature.ASSISTED_HYPOTHESIS` - uma possibilidade
apresentada para avaliacao, sempre nao confirmada - nunca uma
classificacao de risco nem uma observacao
factual: "possivel cansaco" nao e o mesmo que "cansaco detectado".
"""

from __future__ import annotations

from dataclasses import dataclass

from app.processors.media_analysis import WavPcmSamples

_WINDOW_COUNT = 40
_SILENCE_RMS_THRESHOLD = 0.02

# Limiares heuristicos (MVP, nao clinicamente validados - ver docstring do
# modulo). Ajustaveis conforme evidencia/protocolo aprovado.
_LOW_ENERGY_RMS_THRESHOLD = 0.05
_FRAGMENTED_SPEECH_PAUSE_RATIO = 0.5
_FRAGMENTED_SPEECH_MIN_VOICED_SEGMENTS = 3


@dataclass(frozen=True)
class AcousticFeatures:
    sample_count: int
    window_count: int
    rms_energy_mean: float
    rms_energy_std: float
    zero_crossing_rate: float
    pause_ratio: float
    voiced_segment_count: int


@dataclass(frozen=True)
class VocalAlterationHypothesis:
    label: str
    detail: str
    based_on: dict[str, float]


def _windowed_rms(samples: list[float], window_count: int) -> list[float]:
    if not samples:
        return []
    window_size = max(1, len(samples) // window_count)
    rms_values = []
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if not window:
            continue
        mean_square = sum(value * value for value in window) / len(window)
        rms_values.append(mean_square**0.5)
    return rms_values


def extract_acoustic_features(pcm: WavPcmSamples) -> AcousticFeatures | None:
    """Funcao pura: recebe amostras ja decodificadas, sem I/O."""
    samples = pcm.samples
    if not samples:
        return None

    rms_windows = _windowed_rms(samples, _WINDOW_COUNT)
    rms_mean = sum(rms_windows) / len(rms_windows)
    rms_variance = sum((value - rms_mean) ** 2 for value in rms_windows) / len(rms_windows)
    rms_std = rms_variance**0.5

    zero_crossings = sum(
        1
        for previous, current in zip(samples, samples[1:], strict=False)
        if (previous >= 0) != (current >= 0)
    )
    zero_crossing_rate = zero_crossings / max(1, len(samples) - 1)

    is_pause = [rms < _SILENCE_RMS_THRESHOLD for rms in rms_windows]
    pause_ratio = sum(is_pause) / len(is_pause)

    voiced_segment_count = 0
    previously_paused = True
    for paused in is_pause:
        if previously_paused and not paused:
            voiced_segment_count += 1
        previously_paused = paused

    return AcousticFeatures(
        sample_count=len(samples),
        window_count=len(rms_windows),
        rms_energy_mean=round(rms_mean, 6),
        rms_energy_std=round(rms_std, 6),
        zero_crossing_rate=round(zero_crossing_rate, 6),
        pause_ratio=round(pause_ratio, 4),
        voiced_segment_count=voiced_segment_count,
    )


def generate_vocal_alteration_hypotheses(
    features: AcousticFeatures,
) -> list[VocalAlterationHypothesis]:
    """Nunca retorna diagnostico - apenas hipoteses nao confirmadas,
    rotuladas explicitamente como tal, quando um limiar heuristico e
    cruzado. Lista vazia quando nenhum padrao e observado (nao inventa
    achado so para preencher a secao do laudo)."""
    hypotheses: list[VocalAlterationHypothesis] = []

    if (
        features.pause_ratio >= _FRAGMENTED_SPEECH_PAUSE_RATIO
        and features.voiced_segment_count >= _FRAGMENTED_SPEECH_MIN_VOICED_SEGMENTS
    ):
        hypotheses.append(
            VocalAlterationHypothesis(
                label="possivel_padrao_de_fala_fragmentada",
                detail=(
                    "Proporcao elevada de pausas entre segmentos de fala "
                    f"({features.pause_ratio:.0%}), com {features.voiced_segment_count} "
                    "segmentos de fala distintos. Pode estar associado a fadiga ou "
                    "dispneia, mas tambem a pausas normais de fala - avaliacao "
                    "clinica necessaria. Nao e um diagnostico."
                ),
                based_on={
                    "pause_ratio": features.pause_ratio,
                    "voiced_segment_count": features.voiced_segment_count,
                },
            )
        )

    if features.rms_energy_mean < _LOW_ENERGY_RMS_THRESHOLD and features.voiced_segment_count > 0:
        hypotheses.append(
            VocalAlterationHypothesis(
                label="possivel_reducao_de_energia_vocal",
                detail=(
                    f"Energia media do sinal de voz baixa ({features.rms_energy_mean:.4f} "
                    "em escala normalizada). Pode estar associado a voz fraca/hipofonia, "
                    "mas tambem a distancia do microfone ou volume de gravacao - avaliacao "
                    "clinica necessaria. Nao e um diagnostico."
                ),
                based_on={"rms_energy_mean": features.rms_energy_mean},
            )
        )

    return hypotheses
