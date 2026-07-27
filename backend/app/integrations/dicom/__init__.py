"""Integração com Azure Health Data Services — DICOM Service.

Permite upload (STOW-RS), download (WADO-RS) e busca (QIDO-RS) de
imagens médicas DICOM via API DICOMweb padrão. Autenticação por
service principal (OAuth2 via azure-identity).
"""

from __future__ import annotations

from app.core.config import get_settings

from .client import DicomClient


def get_dicom_client() -> DicomClient | None:
    """Retorna cliente DICOM configurado, ou None se não configurado."""
    settings = get_settings()
    if not settings.azure_dicom_endpoint:
        return None
    return DicomClient(
        endpoint=settings.azure_dicom_endpoint,
        tenant_id=settings.azure_dicom_tenant_id or "",
        client_id=settings.azure_dicom_client_id or "",
        client_secret=settings.azure_dicom_client_secret or "",
    )
