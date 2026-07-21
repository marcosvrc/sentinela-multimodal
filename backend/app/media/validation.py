"""Politica de validacao de uploads de midia.

Logica pura (sem I/O), para ser testavel sem storage nem banco. Cobre:

1. Metadados declarados (MIME + tamanho) contra a politica por modalidade,
   no momento em que a URL de upload e solicitada.
2. Assinatura real do arquivo ("magic bytes") apos o upload - extensao e
   MIME informados pelo cliente nunca sao aceitos como prova suficiente
   do tipo real do arquivo; o `declared_mime_type` e apenas uma
   expectativa a ser confirmada contra os bytes reais, nunca uma verdade
   aceita sem checagem.
3. Um estagio de varredura antimalware. A implementacao aqui e um
   PLACEHOLDER deliberado (checagem de uma assinatura de teste conhecida,
   estilo EICAR) e NAO substitui uma varredura real (ClamAV/AWS
   GuardDuty Malware Protection ou equivalente) - isso fica para quando o
   pipeline de processamento tiver um worker dedicado com acesso a um
   motor de AV de verdade. Documentado aqui para que o gap fique visivel
   em vez de escondido atras de um nome que sugira protecao real.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import ModalityType

# Formatos aceitos por modalidade (audio, video, imagem).
# `ModalityType.TEXT` nao passa por upload de midia - o texto adicional e
# um campo direto da analise (ver app/media/service.py::create_analysis).
ALLOWED_MIME_TYPES: dict[ModalityType, frozenset[str]] = {
    ModalityType.AUDIO: frozenset({"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4"}),
    ModalityType.VIDEO: frozenset({"video/mp4", "video/quicktime"}),
    ModalityType.IMAGE: frozenset({"image/jpeg", "image/png"}),
}

# Tamanho maximo por modalidade, em bytes.
MAX_SIZE_BYTES: dict[ModalityType, int] = {
    ModalityType.AUDIO: 200 * 1024 * 1024,
    ModalityType.VIDEO: 1024 * 1024 * 1024,
    ModalityType.IMAGE: 25 * 1024 * 1024,
}

UPLOADABLE_MODALITIES = frozenset(ALLOWED_MIME_TYPES)


def validate_declared_metadata(
    modality_type: ModalityType, mime_type: str, size_bytes: int
) -> dict[str, str]:
    """Valida o que o cliente DECLAROU antes de emitir a URL de upload.

    Retorna um dict de field_errors (vazio se valido). Nao substitui a
    verificacao pos-upload feita por `detect_mime_type_from_signature`.
    """
    errors: dict[str, str] = {}

    if modality_type not in UPLOADABLE_MODALITIES:
        errors["modality_type"] = (
            "Esta modalidade nao usa upload de midia "
            "(TEXT e enviado como campo de texto na propria analise)."
        )
        return errors

    allowed = ALLOWED_MIME_TYPES[modality_type]
    if mime_type not in allowed:
        errors["mime_type"] = f"Tipo nao permitido para {modality_type.value}: {mime_type}."

    max_size = MAX_SIZE_BYTES[modality_type]
    if size_bytes <= 0:
        errors["size_bytes"] = "Tamanho declarado deve ser maior que zero."
    elif size_bytes > max_size:
        errors["size_bytes"] = f"Tamanho declarado excede o limite de {max_size} bytes."

    return errors


# Assinaturas (magic bytes) minimas o suficiente para desmentir um MIME
# declarado incorretamente - nao e um detector completo de formato de
# arquivo, apenas uma primeira barreira.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"RIFF", "audio/wav"),  # WAVE (RIFF....WAVEfmt); refinado abaixo
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def detect_mime_type_from_signature(content_prefix: bytes) -> str | None:
    """Deduz um MIME a partir dos primeiros bytes do arquivo enviado."""
    if content_prefix[:4] == b"RIFF" and content_prefix[8:12] == b"WAVE":
        return "audio/wav"
    if content_prefix[4:8] == b"ftyp":
        # Container ISO BMFF: usado por MP4 (video ou audio/m4a) e MOV.
        # Sem inspecionar a `major_brand` nao da para distinguir com
        # certeza; tratamos como valido para os MIMEs de container
        # aceitos e deixamos a comparacao final decidir.
        return "container/isobmff"
    for signature, mime_type in _SIGNATURES:
        if content_prefix.startswith(signature):
            return mime_type
    return None


_CONTAINER_COMPATIBLE_MIME_TYPES = frozenset({"video/mp4", "video/quicktime", "audio/mp4"})


def signature_matches_declared_mime(detected: str | None, declared: str) -> bool:
    if detected is None:
        return False
    if detected == "container/isobmff":
        return declared in _CONTAINER_COMPATIBLE_MIME_TYPES
    return detected == declared


# Assinatura de teste padrao da industria para verificar o CAMINHO de
# deteccao de um scanner antimalware sem usar malware real (EICAR).
_EICAR_TEST_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    reason: str | None = None


def run_placeholder_antimalware_scan(content_prefix: bytes) -> ScanResult:
    """Verificacao MINIMA, NAO substitui varredura antimalware real.

    Existe apenas para dar um ponto de extensao unico
    (`app/media/service.py` chama somente esta funcao) para quando um
    motor real (ClamAV, AWS GuardDuty Malware Protection ou similar) for
    integrado. Hoje so reconhece a assinatura de teste EICAR.
    """
    if _EICAR_TEST_SIGNATURE in content_prefix:
        return ScanResult(clean=False, reason="Assinatura de teste EICAR detectada.")
    return ScanResult(clean=True)
