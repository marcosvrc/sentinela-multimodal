"""Rotas publicas de health/readiness.

`healthz` nao depende de nenhuma integracao externa (liveness).
`readyz` verifica a conectividade com o banco de dados (readiness),
usada por orquestradores de container e pelo frontend no scaffold inicial.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health")
def healthz(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.api_version,
        "environment": settings.environment.value,
    }


@router.get("/health/ready")
def readyz(response: Response, db: Session = Depends(get_db_session)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - erro convertido, sem detalhes internos expostos
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "dependency": "database"}
    return {"status": "ready"}
