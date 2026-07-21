"""Rate limiting da API, como camada de protecao de aplicacao.

`slowapi` (ja listado em pyproject.toml) sobre `Settings.rate_limit_*`
(existiam configurados desde a integracao com identidade real, mas nunca
foram de fato registrados em `app.main` - lacuna fechada aqui).

Limite por IP do cliente (`get_remote_address`), em memoria por processo:
suficiente para um unico processo da API (ver `app.main`); atras de um
load balancer com multiplas replicas o limite efetivo escala com o numero
de instancias, o que e aceitavel para o proposito de mitigar abuso/DoS
trivial e forca bruta - nao substitui uma camada de protecao de borda
como um WAF/Shield gerenciado.

`rate_limit_default` se aplica a todas as rotas via `Limiter.limit`
default; `rate_limit_auth` e aplicado explicitamente as rotas mais
sensiveis a enumeracao/forca bruta (concessao de break glass), a unica
acao de elevacao de acesso exposta diretamente por esta API - o login em
si acontece no Cognito, fora deste backend.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default] if settings.rate_limit_enabled else [],
    enabled=settings.rate_limit_enabled,
)


async def _rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Converte a resposta padrao do slowapi para o formato de erro da API
    (ver `app.core.errors.ApiError`), mantendo `code`/`message`/`request_id`
    consistentes em toda a superficie HTTP."""
    return JSONResponse(
        status_code=429,
        content={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Numero de requisicoes excedido. Aguarde antes de tentar novamente.",
            "field_errors": {},
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def configure_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_error_handler)
