"""Identidade autenticada atual (`GET /me`).

Sem `require_role`: qualquer usuario autenticado (qualquer papel) pode
consultar o proprio registro. Esta rota nao expoe dados de OUTROS usuarios
(isso continua exigindo papel de administrador via `/admin/users`) - serve
apenas para o frontend saber, apos o login, qual e o papel do usuario ativo
e decidir quais itens de navegacao exibir.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.schemas.me import CurrentUserRead
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(tags=["me"])


@router.get("/me", response_model=CurrentUserRead)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> CurrentUserRead:
    return CurrentUserRead(
        id=current_user.id,
        institution_id=current_user.institution_id,
        external_subject=current_user.external_subject,
        full_name=current_user.full_name,
        role=current_user.role.value,
    )
