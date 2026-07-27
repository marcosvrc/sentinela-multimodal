"""Cliente DICOMweb para Azure Health Data Services.

Implementa STOW-RS (upload) e WADO-RS (download) usando httpx + OAuth2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from azure.identity import ClientSecretCredential

_logger = logging.getLogger(__name__)

_DICOM_SCOPE = "https://dicom.healthcareapis.azure.com/.default"


@dataclass
class DicomStudyMetadata:
    """Metadados resumidos extraídos do DICOM."""

    study_instance_uid: str
    series_instance_uid: str | None = None
    sop_instance_uid: str | None = None
    modality: str | None = None  # CR, CT, MR, US, etc.
    body_part: str | None = None
    patient_name: str | None = None
    patient_id: str | None = None
    institution_name: str | None = None
    manufacturer: str | None = None
    study_description: str | None = None
    series_description: str | None = None


class DicomClient:
    """Cliente para Azure DICOM Service via DICOMweb."""

    def __init__(
        self,
        *,
        endpoint: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    def _get_token(self) -> str:
        token = self._credential.get_token(_DICOM_SCOPE)
        return token.token

    def store(self, dicom_bytes: bytes) -> str | None:
        """Upload DICOM via STOW-RS. Retorna Study Instance UID ou None se falhar."""
        url = f"{self._endpoint}/v2/studies"
        boundary = "----DICOMBoundary"
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/dicom\r\n\r\n"
        ).encode() + dicom_bytes + f"\r\n--{boundary}--\r\n".encode()

        try:
            response = httpx.post(
                url,
                content=body,
                headers={
                    "Authorization": f"Bearer {self._get_token()}",
                    "Content-Type": f"multipart/related; type=\"application/dicom\"; boundary={boundary}",
                    "Accept": "application/dicom+json",
                },
                timeout=60.0,
            )
            if response.status_code in (200, 202):
                _logger.info("DICOM stored successfully")
                return "stored"
            _logger.warning("DICOM store failed: %d %s", response.status_code, response.text[:200])
            return None
        except Exception as exc:  # noqa: BLE001
            _logger.warning("DICOM store error: %s", exc)
            return None

    def retrieve_frame_png(self, study_uid: str, series_uid: str, instance_uid: str) -> bytes | None:
        """Download de um frame renderizado como PNG via WADO-RS."""
        url = (
            f"{self._endpoint}/v2/studies/{study_uid}/series/{series_uid}"
            f"/instances/{instance_uid}/frames/1"
        )
        try:
            response = httpx.get(
                url,
                headers={
                    "Authorization": f"Bearer {self._get_token()}",
                    "Accept": "image/png",
                },
                timeout=30.0,
            )
            if response.status_code == 200:
                return response.content
            return None
        except Exception:  # noqa: BLE001
            return None
