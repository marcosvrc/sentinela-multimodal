"""Testes de logica pura de validacao de upload (sem storage/banco)."""

from __future__ import annotations

from app.core.enums import ModalityType
from app.media.validation import (
    ALLOWED_MIME_TYPES,
    MAX_SIZE_BYTES,
    detect_mime_type_from_signature,
    run_placeholder_antimalware_scan,
    signature_matches_declared_mime,
    validate_declared_metadata,
)


def test_validate_declared_metadata_accepts_allowed_mime_and_size() -> None:
    errors = validate_declared_metadata(ModalityType.IMAGE, "image/png", 1024)
    assert errors == {}


def test_validate_declared_metadata_rejects_disallowed_mime() -> None:
    errors = validate_declared_metadata(ModalityType.IMAGE, "application/pdf", 1024)
    assert "mime_type" in errors


def test_validate_declared_metadata_rejects_oversized_file() -> None:
    max_size = MAX_SIZE_BYTES[ModalityType.IMAGE]
    errors = validate_declared_metadata(ModalityType.IMAGE, "image/png", max_size + 1)
    assert "size_bytes" in errors


def test_validate_declared_metadata_rejects_zero_size() -> None:
    errors = validate_declared_metadata(ModalityType.AUDIO, "audio/wav", 0)
    assert "size_bytes" in errors


def test_validate_declared_metadata_rejects_text_modality() -> None:
    errors = validate_declared_metadata(ModalityType.TEXT, "text/plain", 10)
    assert "modality_type" in errors


def test_all_uploadable_modalities_have_size_limits() -> None:
    for modality_type in ALLOWED_MIME_TYPES:
        assert modality_type in MAX_SIZE_BYTES


def test_detect_mime_type_from_signature_png() -> None:
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert detect_mime_type_from_signature(png_header) == "image/png"


def test_detect_mime_type_from_signature_jpeg() -> None:
    jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    assert detect_mime_type_from_signature(jpeg_header) == "image/jpeg"


def test_detect_mime_type_from_signature_wav() -> None:
    wav_header = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 20
    assert detect_mime_type_from_signature(wav_header) == "audio/wav"


def test_detect_mime_type_from_signature_mp4_container() -> None:
    mp4_header = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20
    assert detect_mime_type_from_signature(mp4_header) == "container/isobmff"


def test_detect_mime_type_from_signature_unknown_returns_none() -> None:
    assert detect_mime_type_from_signature(b"not-a-real-file-signature") is None


def test_signature_matches_declared_mime_direct_match() -> None:
    assert signature_matches_declared_mime("image/png", "image/png") is True


def test_signature_matches_declared_mime_mismatch() -> None:
    assert signature_matches_declared_mime("image/png", "image/jpeg") is False


def test_signature_matches_declared_mime_none_never_matches() -> None:
    assert signature_matches_declared_mime(None, "image/png") is False


def test_signature_matches_declared_mime_container_accepts_compatible_types() -> None:
    assert signature_matches_declared_mime("container/isobmff", "video/mp4") is True
    assert signature_matches_declared_mime("container/isobmff", "audio/mp4") is True


def test_signature_matches_declared_mime_container_rejects_incompatible_type() -> None:
    assert signature_matches_declared_mime("container/isobmff", "image/png") is False


def test_placeholder_antimalware_scan_clean_file() -> None:
    result = run_placeholder_antimalware_scan(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    assert result.clean is True


def test_placeholder_antimalware_scan_flags_eicar_signature() -> None:
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    result = run_placeholder_antimalware_scan(eicar)
    assert result.clean is False
    assert result.reason is not None
