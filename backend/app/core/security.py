"""Resolucao de identidade autenticada e controle de acesso por papel.

Dois adaptadores, selecionados por `Settings.identity_provider`:

- `LOCAL` (dev/testes apenas - nunca permitido quando
  `Settings.requires_real_identity_provider` e verdadeiro): resolve o
  usuario a partir do cabecalho de desenvolvimento `X-Dev-Subject`
  contendo o `external_subject` de um usuario ja cadastrado (ver
  `scripts/seed_dev_data.py`), sem MFA e sem sessao revogavel real.
- `COGNITO`: resolve a partir de um token Bearer validado
  (`app.integrations.identity.cognito.CognitoIdentityVerifier` - assinatura
  JWKS, emissor, audiencia, expiracao), exige MFA verificado na sessao
  (`VerifiedIdentity.mfa_verified`) e consulta `UserSession` para permitir
  revogacao centralizada mesmo com JWT ainda valido.

Em ambos os casos, `institution_id`, `role` e o nome do ator sao SEMPRE
lidos do registro `User` no banco, nunca aceitos diretamente do cliente -
o token/cabecalho traz apenas um identificador verificado (`sub`/
`external_subject`); instituicao e papel vem do espelho local
(`app.identity`). Isso preserva a regra "o frontend nao e fonte de
autorizacao" em ambos os modos.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.enums import AuditCategory, AuditResult, AuthProvider, UserRole
from app.core.errors import ApiError
from app.identity import service as identity_service
from app.identity.models import User


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identidade resolvida para a requisicao atual."""

    id: uuid.UUID
    institution_id: uuid.UUID
    external_subject: str
    full_name: str
    role: UserRole
    session_id: uuid.UUID | None = None
    mfa_verified: bool = False


def _role_for(user: User) -> UserRole:
    try:
        return UserRole(user.role)
    except ValueError as exc:
        # Defesa em profundidade: um `role` gravado fora do enum (ex.: dado
        # legado ou erro de seed) nunca deve ser silenciosamente aceito.
        raise ApiError(
            code="INVALID_USER_ROLE",
            message="O usuario possui um papel nao reconhecido pelo sistema.",
            status_code=403,
        ) from exc


async def _get_current_user_local(
    db: Session,
    x_dev_subject: str | None,
) -> AuthenticatedUser:
    settings = get_settings()
    if settings.requires_real_identity_provider:
        # Trava de seguranca: mesmo que alguem reconfigure identity_provider
        # de volta para LOCAL por engano em homologation/production, o
        # ambiente nunca aceita o cabecalho de desenvolvimento.
        raise ApiError(
            code="LOCAL_IDENTITY_PROVIDER_FORBIDDEN",
            message=(
                "O adaptador de identidade local (X-Dev-Subject) esta desabilitado "
                "neste ambiente. Configure identity_provider=COGNITO."
            ),
            status_code=401,
        )

    if not x_dev_subject:
        raise ApiError(
            code="MISSING_AUTH_CONTEXT",
            message=(
                "Identidade ausente. Envie o cabecalho X-Dev-Subject com o "
                "identificador de um usuario de desenvolvimento (nunca "
                "disponivel em homologation/production; ver `make seed-dev-data`)."
            ),
            status_code=401,
        )

    user = identity_service.get_user_by_external_subject(db, x_dev_subject)
    if user is None:
        # Mesma resposta para "cabecalho invalido" e "usuario inexistente":
        # nao revelar quais identificadores existem (mesmo principio de
        # "resposta indistinguivel" usado no isolamento entre instituicoes).
        raise ApiError(
            code="INVALID_AUTH_CONTEXT",
            message="Nenhum usuario de desenvolvimento corresponde a X-Dev-Subject.",
            status_code=401,
        )

    return AuthenticatedUser(
        id=user.id,
        institution_id=user.institution_id,
        external_subject=user.external_subject,
        full_name=user.full_name,
        role=_role_for(user),
        session_id=None,
        mfa_verified=False,
    )


async def _get_current_user_cognito(
    db: Session,
    authorization: str | None,
) -> AuthenticatedUser:
    from app.integrations.identity import get_identity_verifier
    from app.integrations.identity.base import IdentityVerificationError

    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(
            code="MISSING_AUTH_CONTEXT",
            message="Identidade ausente. Envie o cabecalho Authorization: Bearer <token>.",
            status_code=401,
        )
    bearer_token = authorization.split(" ", 1)[1].strip()

    settings = get_settings()
    verifier = get_identity_verifier()
    try:
        verified = verifier.verify(bearer_token)
    except IdentityVerificationError as exc:
        raise ApiError(
            code="INVALID_AUTH_CONTEXT",
            message=f"Token de identidade invalido: {exc.reason}",
            status_code=401,
        ) from exc

    # Bloqueio por tentativa: o token ja foi verificado
    # (assinatura/emissor/audiencia/expiracao), entao `verified.subject" e
    # confiavel - nao e possivel um atacante inflar o contador de outra
    # pessoa so por tentar tokens aleatorios (eles nunca passam de
    # `verifier.verify` acima). O bloqueio protege contra uma conta
    # desativada/removida sendo testada repetidamente com um token ainda
    # valido (assinatura Cognito nao revoga so por isso).
    if identity_service.is_locked_out(db, verified.subject):
        raise ApiError(
            code="ACCOUNT_LOCKED",
            message=(
                "Muitas tentativas de autenticacao invalidas recentes. "
                "Aguarde antes de tentar novamente ou contate a administracao."
            ),
            status_code=401,
        )

    if settings.is_production and not verified.mfa_verified:
        raise ApiError(
            code="MFA_REQUIRED",
            message="MFA e obrigatorio para acessar este ambiente.",
            status_code=401,
        )

    user = identity_service.get_user_by_external_subject(db, verified.subject)
    if user is None or not user.active:
        identity_service.record_failed_attempt(
            db, verified.subject, reason="user_not_found_or_inactive"
        )
        db.commit()
        raise ApiError(
            code="INVALID_AUTH_CONTEXT",
            message="Nenhum usuario ativo corresponde ao token apresentado.",
            status_code=401,
        )

    session_row = identity_service.register_session(
        db,
        user_id=user.id,
        session_token_id=verified.session_token_id,
        issued_at=datetime.fromtimestamp(verified.issued_at_epoch, tz=timezone.utc),
        expires_at=datetime.fromtimestamp(verified.expires_at_epoch, tz=timezone.utc),
    )
    active_session = identity_service.get_active_session(db, verified.session_token_id)
    if active_session is None:
        raise ApiError(
            code="SESSION_REVOKED",
            message="Esta sessao foi revogada ou expirou. Faca login novamente.",
            status_code=401,
        )
    db.commit()

    return AuthenticatedUser(
        id=user.id,
        institution_id=user.institution_id,
        external_subject=user.external_subject,
        full_name=user.full_name,
        role=_role_for(user),
        session_id=session_row.id,
        mfa_verified=verified.mfa_verified,
    )


async def get_current_user(
    db: Session = Depends(get_db_session),
    x_dev_subject: str | None = Header(default=None, alias="X-Dev-Subject"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    settings = get_settings()
    if settings.identity_provider is AuthProvider.COGNITO:
        return await _get_current_user_cognito(db, authorization)
    return await _get_current_user_local(db, x_dev_subject)


async def get_current_institution_id(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> uuid.UUID:
    """Instituicao (tenant) do usuario autenticado.

    Nunca aceita `institution_id` do cliente: deriva sempre do registro
    `User` resolvido por `get_current_user`.
    """
    return current_user.institution_id


async def get_current_actor(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> str:
    """Identificador estavel do ator para os eventos de auditoria.

    Usa `external_subject` (e nao o nome de exibicao) por ser o
    identificador que sobrevive a trocas de nome e e o mesmo campo que
    viria do `sub` de um token Cognito validado.
    """
    return current_user.external_subject


def require_role(*allowed_roles: UserRole) -> Callable[..., AuthenticatedUser]:
    """Fabrica de dependencia FastAPI: exige que o usuario tenha um dos papeis.

    Esta e a primeira camada de autorizacao (papel + instituicao, esta
    ultima sempre aplicada pelos servicos de dominio via `institution_id`).
    O eixo "unidade + vinculo assistencial com o paciente" e uma camada
    adicional, aplicada por `require_patient_access` (abaixo) nas rotas que
    recebem um `patient_id` - papeis administrativos/auditoria nao
    acessam prontuario clinico identificado e por isso nao precisam dela.
    """

    allowed = frozenset(allowed_roles)

    async def _dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if current_user.role not in allowed:
            raise ApiError(
                code="FORBIDDEN_ROLE",
                message="Seu papel nao tem permissao para executar esta acao.",
                status_code=403,
            )
        return current_user

    return _dependency


def require_patient_access(
    db: Session,
    current_user: AuthenticatedUser,
    patient_id: uuid.UUID,
) -> None:
    """Ultimo eixo de autorizacao: papel+instituicao (ja aplicados por
    `require_role`/`institution_id`) + vinculo assistencial com o paciente.

    Administradores e auditores nunca chamam esta funcao (nao acessam
    prontuario clinico identificado). Papeis assistenciais (medico,
    enfermeiro) precisam de um `PatientCareAssignment` ativo OU de um
    `BreakGlassGrant` ativo para o paciente; sem nenhum dos dois, o acesso
    e negado e um evento AUTHORIZATION/DENIED e registrado. Chamado pelas
    rotas de paciente/analise depois de `get_patient`/`get_analysis`
    confirmarem o isolamento multi-tenant.
    """
    from app.audit import service as audit_service

    if identity_service.has_active_assignment(
        db,
        institution_id=current_user.institution_id,
        user_id=current_user.id,
        patient_id=patient_id,
    ):
        return

    grant = identity_service.has_active_break_glass_grant(
        db, user_id=current_user.id, patient_id=patient_id
    )
    if grant is not None:
        audit_service.record_event(
            db,
            actor=current_user.external_subject,
            actor_role=current_user.role.value,
            category=AuditCategory.AUTHORIZATION,
            action="PATIENT_ACCESS_VIA_BREAK_GLASS",
            resource_type="patient",
            resource_id=str(patient_id),
            result=AuditResult.SUCCESS,
            institution_id=current_user.institution_id,
            justification=grant.justification,
        )
        return

    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.AUTHORIZATION,
        action="PATIENT_ACCESS_DENIED",
        resource_type="patient",
        resource_id=str(patient_id),
        result=AuditResult.DENIED,
        institution_id=current_user.institution_id,
    )
    db.commit()
    raise ApiError(
        code="NO_CARE_ASSIGNMENT",
        message=(
            "Voce nao possui vinculo assistencial ativo com este paciente. "
            "Solicite o vinculo a administracao ou, em emergencia, um "
            "acesso break glass (POST /patients/{patient_id}/break-glass)."
        ),
        status_code=403,
    )
