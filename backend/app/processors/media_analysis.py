"""Extracao deterministica de metadados estruturais de midia.

Nao faz reconhecimento de conteudo (nao ha transcricao de fala nem visao
computacional aqui - isso depende de servicos externos como Amazon
Transcribe ou um modelo de visao, integrados separadamente). O que este
modulo faz e extrair fatos estruturais reais do proprio arquivo, sem
bibliotecas externas, para que cada modalidade produza uma avaliacao de
qualidade genuina e independente do achado clinico (resolucao, duracao
etc.):

- PNG/JPEG: dimensoes (largura x altura), lidas diretamente dos cabecalhos
  do formato (chunk IHDR do PNG; marcadores SOFn do JPEG).
- WAV: duracao em segundos, calculada do cabecalho RIFF (`byte_rate` e
  tamanho do chunk `data`).
- MP4/MOV (ISO BMFF): duracao em segundos, lida da box `moov/mvhd`.

Formatos sem parser aqui (MP3, M4A) resultam em `None` nos campos que nao
puderam ser determinados - o processador da modalidade trata isso como
"metrica indisponivel neste ambiente", nunca como um valor inventado.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


def parse_png_dimensions(content: bytes) -> ImageDimensions | None:
    """PNG: assinatura (8 bytes) + chunk IHDR (comeca no byte 8, campo de
    tamanho + tipo = 8 bytes, depois 4 bytes de largura e 4 de altura)."""
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if content[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", content[16:24])
    return ImageDimensions(width=width, height=height)


def parse_jpeg_dimensions(content: bytes) -> ImageDimensions | None:
    """JPEG: percorre os marcadores ate achar um SOFn (Start Of Frame),
    que carrega altura/largura logo apos o tamanho do segmento."""
    if len(content) < 4 or content[:2] != b"\xff\xd8":
        return None

    offset = 2
    length = len(content)
    # Marcadores SOF validos para dimensoes (exclui SOF que sao DHT/DAC/etc).
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }

    while offset + 4 <= length:
        if content[offset] != 0xFF:
            offset += 1
            continue
        marker = content[offset + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        if marker == 0xD9:  # EOI
            break
        segment_length = struct.unpack(">H", content[offset + 2 : offset + 4])[0]
        if marker in sof_markers:
            if offset + 9 > length:
                return None
            height, width = struct.unpack(">HH", content[offset + 5 : offset + 9])
            return ImageDimensions(width=width, height=height)
        offset += 2 + segment_length

    return None


def parse_wav_duration_seconds(content: bytes) -> float | None:
    """WAV (RIFF/WAVE): soma linear dos chunks ate achar `fmt ` (byte_rate)
    e `data` (tamanho); duracao = tamanho_data / byte_rate."""
    if len(content) < 44 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        return None

    offset = 12
    byte_rate: int | None = None
    data_size: int | None = None

    while offset + 8 <= len(content):
        chunk_id = content[offset : offset + 4]
        chunk_size = struct.unpack("<I", content[offset + 4 : offset + 8])[0]
        chunk_body_start = offset + 8

        if chunk_id == b"fmt " and chunk_body_start + 16 <= len(content):
            byte_rate = struct.unpack("<I", content[chunk_body_start + 8 : chunk_body_start + 12])[
                0
            ]
        elif chunk_id == b"data":
            data_size = chunk_size

        offset = chunk_body_start + chunk_size + (chunk_size % 2)  # chunks sao alinhados a 2 bytes

    if not byte_rate or data_size is None:
        return None
    return data_size / byte_rate


@dataclass(frozen=True)
class WavPcmSamples:
    """Amostras PCM normalizadas (-1.0 a 1.0), reduzidas a mono por media dos
    canais quando o arquivo e estereo. Usado por `app.acoustics.voice_analysis`
    para extrair caracteristicas acusticas reais - nunca reconstroi fala ou
    conteudo semantico, apenas amplitude ao longo do tempo."""

    sample_rate: int
    samples: list[float]


# PCM integer (tag 1) e o unico formato suportado - suficiente para o WAV
# nao comprimido tipicamente usado em gravacoes clinicas simples. WAV com
# outros codecs (ADPCM, float, mu-law) retornam None, nunca uma decodificacao
# incorreta silenciosa.
_PCM_FORMAT_TAG = 1


def parse_wav_pcm_samples(content: bytes, *, max_samples: int = 200_000) -> WavPcmSamples | None:
    """WAV (RIFF/WAVE) PCM inteiro, 8 ou 16 bits. `max_samples` limita a
    quantidade de amostras decodificadas (reamostra por passo fixo) para
    manter a analise rapida mesmo em arquivos longos - preserva o formato do
    sinal (envelope de energia/passagens por zero) sem decodificar cada
    amostra de um audio de varios minutos."""
    if len(content) < 44 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        return None

    offset = 12
    format_tag: int | None = None
    channels: int | None = None
    sample_rate: int | None = None
    bits_per_sample: int | None = None
    data_start: int | None = None
    data_size: int | None = None

    while offset + 8 <= len(content):
        chunk_id = content[offset : offset + 4]
        chunk_size = struct.unpack("<I", content[offset + 4 : offset + 8])[0]
        chunk_body_start = offset + 8

        if chunk_id == b"fmt " and chunk_body_start + 16 <= len(content):
            (format_tag, channels, sample_rate, _byte_rate, _block_align, bits_per_sample) = (
                struct.unpack("<HHIIHH", content[chunk_body_start : chunk_body_start + 16])
            )
        elif chunk_id == b"data":
            data_start = chunk_body_start
            data_size = min(chunk_size, len(content) - chunk_body_start)

        offset = chunk_body_start + chunk_size + (chunk_size % 2)

    if (
        format_tag != _PCM_FORMAT_TAG
        or not channels
        or not sample_rate
        or bits_per_sample not in (8, 16)
        or data_start is None
        or not data_size
    ):
        return None

    bytes_per_sample = bits_per_sample // 8
    frame_size = bytes_per_sample * channels
    frame_count = data_size // frame_size
    if frame_count == 0:
        return None

    step = max(1, frame_count // max_samples)
    samples: list[float] = []
    for frame_index in range(0, frame_count, step):
        frame_offset = data_start + frame_index * frame_size
        channel_values = []
        for channel in range(channels):
            sample_offset = frame_offset + channel * bytes_per_sample
            raw = content[sample_offset : sample_offset + bytes_per_sample]
            if bits_per_sample == 8:
                # WAV de 8 bits e sem sinal, centrado em 128.
                value = (raw[0] - 128) / 128.0
            else:
                value = struct.unpack("<h", raw)[0] / 32768.0
            channel_values.append(value)
        samples.append(sum(channel_values) / len(channel_values))

    return WavPcmSamples(sample_rate=sample_rate, samples=samples)


def parse_isobmff_duration_seconds(content: bytes) -> float | None:
    """MP4/MOV (ISO BMFF): percorre boxes de topo ate `moov`, dentro dele
    ate `mvhd`, e le `timescale`/`duration` (versao 0 = 32 bits; versao 1 =
    64 bits) para calcular a duracao em segundos."""
    moov = _find_box(content, b"moov", 0, len(content))
    if moov is None:
        return None
    moov_start, moov_end = moov

    mvhd = _find_box(content, b"mvhd", moov_start, moov_end)
    if mvhd is None:
        return None
    mvhd_start, mvhd_end = mvhd

    if mvhd_start >= len(content):
        return None
    version = content[mvhd_start]

    try:
        if version == 1:
            # version(1) + flags(3) + creation(8) + modification(8) = 20 bytes antes de timescale
            timescale, duration = struct.unpack(">IQ", content[mvhd_start + 20 : mvhd_start + 32])
        else:
            # version(1) + flags(3) + creation(4) + modification(4) = 12 bytes antes de timescale
            timescale, duration = struct.unpack(">II", content[mvhd_start + 12 : mvhd_start + 20])
    except struct.error:
        return None

    if not timescale:
        return None
    return duration / timescale


def _find_box(
    content: bytes, box_type: bytes, search_start: int, search_end: int
) -> tuple[int, int] | None:
    """Acha a primeira box `box_type` dentro de `[search_start, search_end)`.

    Retorna `(inicio_do_corpo, fim_da_box)`; o corpo comeca apos o cabecalho
    de 8 bytes (tamanho de 32 bits + tipo de 4 bytes) - box de tamanho
    estendido (64 bits) tambem e suportada.
    """
    offset = search_start
    while offset + 8 <= search_end:
        box_size = struct.unpack(">I", content[offset : offset + 4])[0]
        current_box_type = content[offset + 4 : offset + 8]
        header_size = 8

        if box_size == 1:
            if offset + 16 > search_end:
                return None
            box_size = struct.unpack(">Q", content[offset + 8 : offset + 16])[0]
            header_size = 16
        elif box_size == 0:
            box_size = search_end - offset

        if box_size < header_size:
            return None

        body_start = offset + header_size
        box_end = offset + box_size

        if current_box_type == box_type:
            return body_start, box_end
        if current_box_type == b"moov" and box_type != b"moov":
            # Recursao apenas dentro de `moov` (container), evitando
            # descer em boxes de midia que nao interessam aqui.
            nested = _find_box(content, box_type, body_start, box_end)
            if nested is not None:
                return nested

        offset = box_end

    return None
