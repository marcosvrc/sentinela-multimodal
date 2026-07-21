"""Ponto de entrada da API SentinelHealth.

A API executa apenas operacoes rapidas; processamento pesado (audio, video,
imagem, PDF) e realizado por workers assincronos fora do ciclo de
requisicao HTTP.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes.administration import router as administration_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.audit import router as audit_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router
from app.api.routes.media import router as media_router
from app.api.routes.orchestrator import router as orchestrator_router
from app.api.routes.patients import router as patients_router
from app.api.routes.reports import router as reports_router
from app.api.routes.rules import router as rules_router
from app.core.config import get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.core.rate_limit import configure_rate_limiting

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        description=(
            "Sistema de apoio a analises clinicas multimodais. "
            "Nao realiza diagnostico autonomo; toda classificacao e sujeita "
            "a revisao profissional."
        ),
    )

    configure_rate_limiting(app)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(patients_router)
    app.include_router(audit_router)
    app.include_router(media_router)
    app.include_router(rules_router)
    app.include_router(orchestrator_router)
    app.include_router(reports_router)
    app.include_router(administration_router)
    app.include_router(alerts_router)

    return app


app = create_app()
