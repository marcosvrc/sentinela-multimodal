"""Verificador real de token do Amazon Cognito.

Valida, na ordem:
1. Assinatura RS256 contra a chave publica correspondente ao `kid` do
   cabecalho do JWT, obtida do endpoint JWKS do User Pool (cacheado -
   `PyJWKClient` do PyJWT, com TTL configuravel).
2. Emissor (`iss`) igual ao User Pool configurado.
3. Audiencia/client id (`aud` para id tokens, `client_id` para access
   tokens - o Cognito usa nomes de claim diferentes por tipo de token).
4. Expiracao (`exp`) e "usado antes de emitido" (`iat`), verificados pelo
   proprio PyJWT.
5. `token_use` precisa ser "access" ou "id" (nunca aceita um refresh token
   como credencial de API).

Nunca inventa uma identidade quando a validacao falha - qualquer problema
leva a `IdentityVerificationError`, tratado por `app.core.security` como
401 (mesmo padrao dos demais adaptadores reais: falhar de forma honesta,
nunca fabricar sucesso).
"""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.integrations.identity.base import IdentityVerificationError, VerifiedIdentity


class CognitoIdentityVerifier:
    def __init__(
        self,
        *,
        user_pool_id: str,
        client_id: str,
        issuer_url: str | None,
        region: str,
        jwks_cache_ttl_seconds: int = 3600,
    ) -> None:
        self._client_id = client_id
        self._issuer_url = issuer_url or f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        jwks_url = f"{self._issuer_url}/.well-known/jwks.json"
        self._jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=jwks_cache_ttl_seconds)

    def verify(self, bearer_token: str) -> VerifiedIdentity:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(bearer_token)
            claims = jwt.decode(
                bearer_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer_url,
                # Audiencia checada manualmente abaixo (ver docstring da classe).
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise IdentityVerificationError("Token expirado.") from exc
        except jwt.InvalidIssuerError as exc:
            raise IdentityVerificationError(
                "Emissor do token nao corresponde ao esperado."
            ) from exc
        except jwt.PyJWTError as exc:
            raise IdentityVerificationError(f"Token invalido: {exc}") from exc

        token_use = claims.get("token_use")
        if token_use not in ("access", "id"):
            raise IdentityVerificationError(
                "Tipo de token nao aceito como credencial de API (esperado access ou id)."
            )

        audience = claims.get("aud") if token_use == "id" else claims.get("client_id")
        if audience != self._client_id:
            raise IdentityVerificationError(
                "Audiencia do token nao corresponde ao client configurado."
            )

        subject = claims.get("sub")
        session_token_id = claims.get("jti")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        if not subject or not session_token_id or issued_at is None or expires_at is None:
            raise IdentityVerificationError(
                "Token nao contem as claims obrigatorias (sub/jti/iat/exp)."
            )

        amr = claims.get("amr") or []
        if not isinstance(amr, list):
            amr = []

        return VerifiedIdentity(
            subject=str(subject),
            session_token_id=str(session_token_id),
            issued_at_epoch=int(issued_at),
            expires_at_epoch=int(expires_at),
            amr=tuple(str(item) for item in amr),
        )
