"""Endpoint de consulta de auditoria.

A propria consulta de auditoria gera um evento de auditoria - consultas e
exportacoes da propria auditoria tambem sao auditadas -, registrado apos
a busca principal ser bem-sucedida.

Acesso restrito a auditor e administradores: o log de auditoria e
acessivel apenas aos perfis autorizados. Eventos de auditoria nao
carregam conteudo clinico (apenas metadados de acao/recurso), entao
liberar para administrador tecnico nao viola a restricao de que ele nao
acessa conteudo clinico por padrao.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas.audit import AuditEventRead
from app.api.schemas.common import PageResponse
from app.audit import service as audit_service
from app.core.db import get_db_session
from app.core.enums import AuditCategory, AuditResult, UserRole
from app.core.security import AuthenticatedUser, require_role

router = APIRouter(prefix="/audit", tags=["audit"])

_require_audit_access = require_role(
    UserRole.AUDITOR, UserRole.ADMINISTRADOR_TECNICO, UserRole.ADMINISTRADOR_CLINICO
)


@router.get("/events", response_model=PageResponse[AuditEventRead])
def list_audit_events(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    result: AuditResult | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=audit_service.MAX_PAGE_SIZE),
    db: Session = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(_require_audit_access),
) -> PageResponse[AuditEventRead]:
    events, total_items = audit_service.query_events(
        db,
        institution_id=current_user.institution_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        page=page,
        page_size=page_size,
    )

    audit_service.record_event(
        db,
        actor=current_user.external_subject,
        actor_role=current_user.role.value,
        category=AuditCategory.AUDIT,
        action="AUDIT_QUERY",
        resource_type="audit_event",
        result=AuditResult.SUCCESS,
        institution_id=current_user.institution_id,
        event_metadata={
            "filters": {
                "actor": actor,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "result": result.value if result else None,
            },
            "page": page,
        },
    )
    db.commit()

    return PageResponse.build(
        items=[AuditEventRead.model_validate(event) for event in events],
        page=page,
        page_size=min(page_size, audit_service.MAX_PAGE_SIZE),
        total_items=total_items,
    )
