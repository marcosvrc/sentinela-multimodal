"""Testes unitarios de `app.integrations.identity.cognito.CognitoIdentityVerifier`.

Puramente unitario (nenhum acesso a rede/JWKS real ou banco): gera um par de
chaves RSA em memoria, assina tokens com a chave privada e monkeypatcha
`PyJWKClient.get_signing_key_from_jwt` para devolver a chave publica
correspondente - o mesmo ponto de entrada que a classe usaria com um JWKS
real do Cognito. Cobre a cadeia de validacao descrita na docstring do
modulo: assinatura, emissor, audiencia (por tipo de token), expiracao,
`token_use`, e presenca das claims obrigatorias (sub/jti/iat/exp).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integrations.identity.base import IdentityVerificationError
from app.integrations.identity.cognito import CognitoIdentityVerifier

_ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TESTPOOL"
_CLIENT_ID = "test-client-id"


@dataclass
class _FakeSigningKey:
    key: object


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def verifier(rsa_keypair, monkeypatch: pytest.MonkeyPatch) -> CognitoIdentityVerifier:
    _, public_key = rsa_keypair
    instance = CognitoIdentityVerifier(
        user_pool_id="us-east-1_TESTPOOL",
        client_id=_CLIENT_ID,
        issuer_url=_ISSUER,
        region="us-east-1",
    )
    monkeypatch.setattr(
        instance._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: _FakeSigningKey(key=public_key),
    )
    return instance


def _sign(private_key, claims: dict) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-kid"})


def _base_claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "sub": "external-subject-123",
        "jti": "session-token-abc",
        "iat": now,
        "exp": now + 3600,
        "iss": _ISSUER,
        "token_use": "access",
        "client_id": _CLIENT_ID,
        "amr": ["mfa"],
    }
    claims.update(overrides)
    return claims


class TestCognitoIdentityVerifier:
    def test_valid_access_token_is_accepted(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        token = _sign(private_key, _base_claims())

        identity = verifier.verify(token)

        assert identity.subject == "external-subject-123"
        assert identity.session_token_id == "session-token-abc"
        assert identity.mfa_verified is True

    def test_valid_id_token_checks_aud_instead_of_client_id(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        claims = _base_claims(token_use="id", aud=_CLIENT_ID)
        del claims["client_id"]
        token = _sign(private_key, claims)

        identity = verifier.verify(token)
        assert identity.subject == "external-subject-123"

    def test_expired_token_is_rejected(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        now = int(time.time())
        token = _sign(private_key, _base_claims(iat=now - 7200, exp=now - 3600))

        with pytest.raises(IdentityVerificationError, match="expirado"):
            verifier.verify(token)

    def test_wrong_issuer_is_rejected(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        token = _sign(private_key, _base_claims(iss="https://attacker.example.com/pool"))

        with pytest.raises(IdentityVerificationError, match="[Ee]missor"):
            verifier.verify(token)

    def test_wrong_client_id_is_rejected(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        token = _sign(private_key, _base_claims(client_id="some-other-client"))

        with pytest.raises(IdentityVerificationError, match="[Aa]udiencia"):
            verifier.verify(token)

    def test_refresh_token_use_is_rejected(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        token = _sign(private_key, _base_claims(token_use="refresh"))

        with pytest.raises(IdentityVerificationError, match="[Tt]ipo de token"):
            verifier.verify(token)

    def test_missing_jti_claim_is_rejected(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        claims = _base_claims()
        del claims["jti"]
        token = _sign(private_key, claims)

        with pytest.raises(IdentityVerificationError, match="claims obrigatorias"):
            verifier.verify(token)

    def test_token_signed_by_different_key_is_rejected(self, verifier) -> None:
        other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign(other_private_key, _base_claims())

        with pytest.raises(IdentityVerificationError):
            verifier.verify(token)

    def test_no_mfa_amr_means_mfa_not_verified(self, verifier, rsa_keypair) -> None:
        private_key, _ = rsa_keypair
        token = _sign(private_key, _base_claims(amr=["pwd"]))

        identity = verifier.verify(token)
        assert identity.mfa_verified is False
