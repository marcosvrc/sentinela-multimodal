"""Contrato do verificador de identidade.

`verify` recebe um token Bearer bruto e devolve as claims verificadas - ou
levanta `IdentityVerificationError`. Nenhuma outra parte do sistema deve
decodificar JWT diretamente; a validacao de assinatura/emissor/audiencia/
expiracao e responsabilidade exclusiva do adaptador.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class IdentityVerificationError(Exception):
    """Token ausente, malformado, expirado, ou com assinatura/emissor/audiencia invalidos."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class VerifiedIdentity:
    """Claims verificadas de um token de identidade real.

    `subject` e o identificador estavel do usuario (claim `sub` do
    Cognito) - o mesmo valor usado como `external_subject` em
    `app.identity.models.User`. `session_token_id` (claim `jti`) identifica
    a sessao para permitir revogacao centralizada. `amr` (claim padrao
    OIDC "Authentication Methods References") permite confirmar que MFA foi
    de fato usado nesta sessao quando a politica do User Pool exige
    (`mfa_configuration=OPTIONAL` permite login sem MFA para contas que
    ainda nao o configuraram; `ON` obriga em toda conta)."""

    subject: str
    session_token_id: str
    issued_at_epoch: int
    expires_at_epoch: int
    amr: tuple[str, ...] = ()

    @property
    def mfa_verified(self) -> bool:
        return "mfa" in self.amr or "software_token_mfa" in self.amr


class IdentityVerifier(Protocol):
    def verify(self, bearer_token: str) -> VerifiedIdentity: ...
