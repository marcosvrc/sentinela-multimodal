"""Gravacao e consulta de eventos de auditoria.

`record_event` NAO comita por padrao: o chamador decide se o evento entra
na mesma transacao da operacao de negocio (recomendado para escritas, pois
uma falha no registro de auditoria deve bloquear a operacao que o
originou) ou se comita isoladamente (leituras, que nao tem uma
transacao de escrita para se juntar).

A serializacao e o lock (`SELECT ... FOR UPDATE` em `audit_chain_state`)
garantem que escritas concorrentes nao quebrem a cadeia de hash: cada
gravacao le e trava o ultimo hash, calcula o proximo elo e atualiza o
estado antes de liberar o lock.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.hashing import compute_event_hash
from app.audit.models import AuditChainState, AuditEvent
from app.core.enums import AuditCategory, AuditResult

# Campos incluidos no calculo do hash. NAO inclui `id`, `sequence` nem
# `occurred_at` (gerados pelo banco no INSERT, portanto desconhecidos no
# momento do calculo) - a integridade cobre o conteudo semantico do evento.
_HASHED_FIELDS = (
    "institution_id",
    "actor",
    "actor_role",
    "unit",
    "category",
    "action",
    "resource_type",
    "resource_id",
    "result",
    "justification",
    "request_id",
    "analysis_id",
    "workflow_id",
    "job_id",
    "event_metadata",
)


def record_event(
    db: Session,
    *,
    actor: str,
    category: AuditCategory,
    action: str,
    resource_type: str,
    result: AuditResult,
    institution_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    unit: str | None = None,
    resource_id: str | None = None,
    justification: str | None = None,
    request_id: str | None = None,
    analysis_id: str | None = None,
    workflow_id: str | None = None,
    job_id: str | None = None,
    event_metadata: dict | None = None,
) -> AuditEvent:
    fields = {
        "institution_id": str(institution_id) if institution_id else None,
        "actor": actor,
        "actor_role": actor_role,
        "unit": unit,
        "category": category.value,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "result": result.value,
        "justification": justification,
        "request_id": request_id,
        "analysis_id": analysis_id,
        "workflow_id": workflow_id,
        "job_id": job_id,
        "event_metadata": event_metadata or {},
    }
    if set(fields) != set(_HASHED_FIELDS):
        # Guarda contra drift de schema: se um campo for adicionado/removido
        # aqui sem atualizar `_HASHED_FIELDS`, falhar alto em vez de gravar
        # um evento com hash calculado sobre um conjunto de campos errado.
        raise RuntimeError("Campos do evento de auditoria divergem de _HASHED_FIELDS.")

    chain_state = db.execute(
        select(AuditChainState).where(AuditChainState.id == 1).with_for_update()
    ).scalar_one()

    event_hash = compute_event_hash(chain_state.last_hash, fields)

    event = AuditEvent(
        institution_id=institution_id,
        actor=actor,
        actor_role=actor_role,
        unit=unit,
        category=category.value,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result.value,
        justification=justification,
        request_id=request_id,
        analysis_id=analysis_id,
        workflow_id=workflow_id,
        job_id=job_id,
        event_metadata=event_metadata or {},
        prev_hash=chain_state.last_hash,
        event_hash=event_hash,
    )
    db.add(event)

    chain_state.last_hash = event_hash

    db.flush()
    return event


MAX_PAGE_SIZE = 100


def query_events(
    db: Session,
    *,
    institution_id: uuid.UUID,
    actor: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    result: AuditResult | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditEvent], int]:
    """Busca paginada de eventos.

    Sempre restrita a `institution_id`: um auditor de uma instituicao nunca
    ve eventos de outra (mesmo principio de isolamento multi-tenant das
    demais entidades).
    """
    page_size = min(page_size, MAX_PAGE_SIZE)

    filters = [AuditEvent.institution_id == institution_id]
    if actor:
        filters.append(AuditEvent.actor == actor)
    if action:
        filters.append(AuditEvent.action == action)
    if resource_type:
        filters.append(AuditEvent.resource_type == resource_type)
    if resource_id:
        filters.append(AuditEvent.resource_id == resource_id)
    if result:
        filters.append(AuditEvent.result == result.value)

    from sqlalchemy import func as sa_func

    total_items = db.scalar(select(sa_func.count()).select_from(AuditEvent).where(*filters))

    items = db.scalars(
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.sequence.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return list(items), int(total_items or 0)


def verify_stored_chain(db: Session) -> list:
    """Recalcula a cadeia inteira armazenada e retorna as violacoes encontradas.

    Uso administrativo/operacional (nao exposto como endpoint publico neste
    scaffold); util para reconciliacao periodica.
    """
    from app.audit.hashing import verify_chain

    events = db.scalars(select(AuditEvent).order_by(AuditEvent.sequence.asc())).all()
    formatted = [
        {
            "sequence": event.sequence,
            "prev_hash": event.prev_hash,
            "event_hash": event.event_hash,
            "fields": {field: _serialize(getattr(event, field)) for field in _HASHED_FIELDS},
        }
        for event in events
    ]
    return verify_chain(formatted)


def _serialize(value: object) -> object:
    return str(value) if isinstance(value, uuid.UUID) else value
