"""Testes de `app.acoustics.voice_analysis` (secao 4.2 do escopo).

Constroi sinais sinteticos com propriedades conhecidas (senoide continua,
senoide com pausas periodicas, senoide de baixa amplitude, silencio total)
para verificar que as caracteristicas acusticas extraidas e as hipoteses
geradas se comportam de forma consistente e conservadora - nunca gerando
hipotese sem cruzar o limiar heuristico documentado.
"""

from __future__ import annotations

import math

from app.acoustics.voice_analysis import (
    extract_acoustic_features,
    generate_vocal_alteration_hypotheses,
)
from app.processors.media_analysis import WavPcmSamples


def _sine_wave(*, amplitude: float, cycles: int, samples_per_cycle: int = 20) -> list[float]:
    total = cycles * samples_per_cycle
    return [
        amplitude * math.sin(2 * math.pi * i / samples_per_cycle) for i in range(total)
    ]


def _with_periodic_silence(
    *, amplitude: float, voiced_bursts: int, voiced_len: int, silence_len: int
) -> list[float]:
    signal: list[float] = []
    for _ in range(voiced_bursts):
        signal.extend(_sine_wave(amplitude=amplitude, cycles=voiced_len // 20 or 1))
        signal.extend([0.0] * silence_len)
    return signal


def test_extract_acoustic_features_returns_none_for_empty_samples() -> None:
    pcm = WavPcmSamples(sample_rate=8000, samples=[])
    assert extract_acoustic_features(pcm) is None


def test_continuous_loud_speech_has_low_pause_ratio() -> None:
    samples = _sine_wave(amplitude=0.8, cycles=200)
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    assert features.pause_ratio < 0.1
    assert features.rms_energy_mean > 0.3


def test_fragmented_speech_with_many_pauses_is_detected() -> None:
    samples = _with_periodic_silence(
        amplitude=0.8, voiced_bursts=6, voiced_len=40, silence_len=200
    )
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    assert features.pause_ratio >= 0.5
    assert features.voiced_segment_count >= 3

    hypotheses = generate_vocal_alteration_hypotheses(features)
    labels = {h.label for h in hypotheses}
    assert "possivel_padrao_de_fala_fragmentada" in labels


def test_low_amplitude_signal_triggers_low_energy_hypothesis() -> None:
    # Amplitude escolhida para que o RMS (~amplitude/sqrt(2) ~= 0.042) fique
    # ACIMA do limiar de silencio (0.02, senao nao conta como "vozeado") mas
    # ABAIXO do limiar de baixa energia (0.05).
    samples = _sine_wave(amplitude=0.06, cycles=200)
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    assert features.voiced_segment_count > 0

    hypotheses = generate_vocal_alteration_hypotheses(features)
    labels = {h.label for h in hypotheses}
    assert "possivel_reducao_de_energia_vocal" in labels


def test_loud_continuous_signal_triggers_no_hypotheses() -> None:
    samples = _sine_wave(amplitude=0.9, cycles=200)
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    assert generate_vocal_alteration_hypotheses(features) == []


def test_total_silence_does_not_trigger_fragmented_speech_hypothesis() -> None:
    """Silencio total nao tem "segmentos de fala" - nao deve ser confundido
    com fala fragmentada (que exige pausas ENTRE trechos de fala real)."""
    samples = [0.0] * 2000
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    assert features.voiced_segment_count == 0

    hypotheses = generate_vocal_alteration_hypotheses(features)
    labels = {h.label for h in hypotheses}
    assert "possivel_padrao_de_fala_fragmentada" not in labels


def test_hypothesis_detail_never_claims_diagnosis() -> None:
    samples = _with_periodic_silence(
        amplitude=0.8, voiced_bursts=6, voiced_len=40, silence_len=200
    )
    pcm = WavPcmSamples(sample_rate=8000, samples=samples)
    features = extract_acoustic_features(pcm)
    assert features is not None
    for hypothesis in generate_vocal_alteration_hypotheses(features):
        assert "nao e um diagnostico" in hypothesis.detail.lower() or (
            "não é um diagnóstico" in hypothesis.detail.lower()
        )
