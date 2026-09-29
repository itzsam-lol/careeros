"""Usage sinks: where metered LLM calls are recorded."""

from __future__ import annotations

import uuid
from typing import Protocol

import structlog

from careeros.core.logging import get_logger
from careeros.db.session import Database
from careeros.llm.models import LLMUsage
from careeros.llm.types import UsageEvent

log = get_logger(__name__)


class UsageSink(Protocol):
    async def record(self, event: UsageEvent) -> None: ...


class NullUsageSink:
    async def record(self, event: UsageEvent) -> None:
        return None


class InMemoryUsageSink:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


def _current_user_id() -> uuid.UUID | None:
    raw = structlog.contextvars.get_contextvars().get("user_id")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


class DatabaseUsageSink:
    """Writes usage in its own short transaction so it survives a rolled-back unit of work."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def record(self, event: UsageEvent) -> None:
        log.info(
            "llm_call",
            task=event.task,
            provider=event.provider,
            model=event.model,
            operation=event.operation,
            success=event.success,
            latency_ms=round(event.latency_ms),
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            error_type=event.error_type,
        )
        try:
            async with self._db.session() as session:
                session.add(
                    LLMUsage(
                        user_id=_current_user_id(),
                        task=event.task,
                        provider=event.provider,
                        model=event.model[:160],
                        operation=event.operation,
                        success=event.success,
                        input_tokens=event.input_tokens,
                        output_tokens=event.output_tokens,
                        latency_ms=round(event.latency_ms),
                        error_type=event.error_type,
                        metadata_=dict(event.metadata),
                    )
                )
                await session.commit()
        except Exception as exc:  # metering must never break the pipeline
            log.warning("llm_usage_record_failed", error_type=type(exc).__name__)
