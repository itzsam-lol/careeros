from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.audit.models import AuditAction, AuditLog
from careeros.core.logging import get_logger, redact_value

log = get_logger(__name__)

USER_ACTOR = "user"
SYSTEM_ACTOR = "system"


def agent_actor(name: str) -> str:
    return f"agent:{name}"


async def record(
    session: AsyncSession,
    *,
    action: AuditAction,
    user_id: uuid.UUID | None,
    actor: str = USER_ACTOR,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit entry to the current unit of work (committed with the action itself)."""
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    entry = AuditLog(
        user_id=user_id,
        actor=actor,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=redact_value(metadata or {}),
        request_id=request_id,
    )
    session.add(entry)
    log.info("audit", action=action.value, entity_type=entity_type, entity_id=str(entity_id))
    return entry


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 100
) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())
