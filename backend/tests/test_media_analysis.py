"""Testes dos parsers estruturais de midia (sem banco, sem I/O externo).

As amostras sao construidas em memoria (nao sao arquivos reais de midia) -
o suficiente para exercitar cada parser com os campos que ele realmente
le, sem depender de fixtures binarias versionadas no repositorio.
"""

from __future__ import annotations

import struct

from app.processors.media_analysis import (
    parse_isobmff_duration_seconds,
    parse_jpeg_dimensions,
    parse_png_dimensions,
    parse_wav_duration_seconds,
    parse_wav_pcm_samples,
)


def _build_png(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_length = struct.pack(">I", 13)
    ihdr_type = b"IHDR"
    ihdr_body = struct.pack(">II", width, height) + bytes(5)  # bit depth/color type/etc, ignorados
    return signature + ihdr_length + ihdr_type + ihdr_body + b"\x00\x00\x00\x00"  # CRC ficticio


def _build_jpeg(width: int, height: int) -> bytes:
    soi = b"\xff\xd8"
    # SOF0: marcador + tamanho do segmento (8 + 3*num_componentes, aqui 3 componentes) +
    # precisao(1) + altura(2) + largura(2) + num_componentes(1) + dados de componente.
    num_components = 3
    segment_length = 2 + 1 + 2 + 2 + 1 + num_components * 3
    sof0 = (
        b"\xff\xc0"
        + struct.pack(">H", segment_length)
        + bytes([8])
        + struct.pack(">HH", height, width)
        + bytes([num_components])
        + bytes([1, 0x11, 0, 2, 0x11, 1, 3, 0x11, 1])
    )
    eoi = b"\xff\xd9"
    return soi + sof0 + eoi


def _build_wav(
    *, sample_rate: int, num_channels: int, bits_per_sample: int, data_size: int
) -> bytes:
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack(
            "<HHIIHH", 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample
        )
    )
    data_chunk = b"data" + struct.pack("<I", data_size) + bytes(data_size)
    riff_body = b"WAVE" + fmt_chunk + data_chunk
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


def _build_wav_with_pcm16_samples(*, sample_rate: int, samples: list[int]) -> bytes:
    """Constroi um WAV mono PCM 16-bit real a partir de amostras inteiras
    ja quantizadas (-32768 a 32767) - usado para testar `parse_wav_pcm_samples`
    e `app.acoustics.voice_analysis` com sinais conhecidos."""
    data = b"".join(struct.pack("<h", max(-32768, min(32767, s))) for s in samples)
    return _build_wav_raw(sample_rate, data)


def _build_wav_raw(sample_rate: int, data: bytes) -> bytes:
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack(
            "<HHIIHH", 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample
        )
    )
    data_chunk = b"data" + struct.pack("<I", len(data)) + data
    riff_body = b"WAVE" + fmt_chunk + data_chunk
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


def _build_box(box_type: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + box_type + body


def _build_mp4(*, timescale: int, duration: int) -> bytes:
    mvhd_body = (
        bytes([0])
        + bytes(3)  # version + flags
        + struct.pack(">II", 0, 0)  # creation/modification time
        + struct.pack(">II", timescale, duration)
        + bytes(80)  # resto do mvhd, irrelevante para o parser
    )
    mvhd = _build_box(b"mvhd", mvhd_body)
    moov = _build_box(b"moov", mvhd)
    ftyp = _build_box(b"ftyp", b"isom" + struct.pack(">I", 0) + b"isomiso2avc1mp41")
    return ftyp + moov


def test_parse_png_dimensions() -> None:
    png = _build_png(width=800, height=600)
    dimensions = parse_png_dimensions(png)
    assert dimensions is not None
    assert dimensions.width == 800
    assert dimensions.height == 600


def test_parse_png_dimensions_rejects_non_png() -> None:
    assert parse_png_dimensions(b"not a png") is None


def test_parse_jpeg_dimensions() -> None:
    jpeg = _build_jpeg(width=1920, height=1080)
    dimensions = parse_jpeg_dimensions(jpeg)
    assert dimensions is not None
    assert dimensions.width == 1920
    assert dimensions.height == 1080


def test_parse_jpeg_dimensions_rejects_non_jpeg() -> None:
    assert parse_jpeg_dimensions(b"not a jpeg") is None


def test_parse_wav_duration_seconds() -> None:
    # 1 segundo de audio mono 16-bit a 8000 Hz -> data_size = byte_rate.
    wav = _build_wav(sample_rate=8000, num_channels=1, bits_per_sample=16, data_size=16000)
    duration = parse_wav_duration_seconds(wav)
    assert duration is not None
    assert duration == 1.0


def test_parse_wav_duration_seconds_half_second() -> None:
    wav = _build_wav(sample_rate=8000, num_channels=1, bits_per_sample=16, data_size=8000)
    duration = parse_wav_duration_seconds(wav)
    assert duration == 0.5


def test_parse_wav_duration_seconds_rejects_non_wav() -> None:
    assert parse_wav_duration_seconds(b"not a wav") is None


def test_parse_wav_pcm_samples_decodes_known_values() -> None:
    wav = _build_wav_with_pcm16_samples(sample_rate=8000, samples=[0, 16384, -16384, 32767])
    pcm = parse_wav_pcm_samples(wav)
    assert pcm is not None
    assert pcm.sample_rate == 8000
    assert len(pcm.samples) == 4
    assert pcm.samples[0] == 0.0
    assert pcm.samples[1] == 0.5
    assert pcm.samples[2] == -0.5
    assert round(pcm.samples[3], 3) == round(32767 / 32768, 3)


def test_parse_wav_pcm_samples_rejects_non_wav() -> None:
    assert parse_wav_pcm_samples(b"not a wav") is None


def test_parse_wav_pcm_samples_downsamples_long_files() -> None:
    wav = _build_wav_with_pcm16_samples(sample_rate=8000, samples=[100] * 500_000)
    pcm = parse_wav_pcm_samples(wav, max_samples=1_000)
    assert pcm is not None
    assert len(pcm.samples) <= 1_000


def test_parse_isobmff_duration_seconds() -> None:
    # timescale=1000 (ms), duration=5000 -> 5 segundos.
    mp4 = _build_mp4(timescale=1000, duration=5000)
    duration = parse_isobmff_duration_seconds(mp4)
    assert duration == 5.0


def test_parse_isobmff_duration_seconds_rejects_non_mp4() -> None:
    assert parse_isobmff_duration_seconds(b"not an mp4") is None


def test_parse_isobmff_duration_seconds_handles_missing_moov() -> None:
    ftyp_only = _build_box(b"ftyp", b"isom")
    assert parse_isobmff_duration_seconds(ftyp_only) is None
