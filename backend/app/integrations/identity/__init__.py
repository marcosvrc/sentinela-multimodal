"""Adaptador de resolucao de identidade real (Amazon Cognito).

So existe um adaptador real (Cognito); o modo LOCAL de desenvolvimento nao
passa por aqui - continua resolvido diretamente pelo cabecalho
`X-Dev-Subject` em `app.core.security.get_current_user` (nunca envolve
verificacao de token, propositalmente, para deixar claro que nao e um
mecanismo de autenticacao real).
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.integrations.identity.base import IdentityVerifier
from app.integrations.identity.cognito import CognitoIdentityVerifier


@lru_cache
def get_identity_verifier() -> IdentityVerifier:
    settings = get_settings()
    if not (settings.cognito_user_pool_id and settings.cognito_client_id):
        raise RuntimeError(
            "identity_provider=COGNITO exige cognito_user_pool_id e cognito_client_id "
            "configurados."
        )
    return CognitoIdentityVerifier(
        user_pool_id=settings.cognito_user_pool_id,
        client_id=settings.cognito_client_id,
        issuer_url=settings.cognito_issuer_url,
        region=settings.aws_region,
        jwks_cache_ttl_seconds=settings.cognito_jwks_cache_ttl_seconds,
    )


__all__ = ["IdentityVerifier", "get_identity_verifier"]
