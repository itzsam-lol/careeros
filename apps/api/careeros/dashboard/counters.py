"""Pluggable dashboard counters: each domain registers the live counts it owns."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

Counter = Callable[[AsyncSession, uuid.UUID], Awaitable[int]]
_COUNTERS: dict[str, Counter] = {}


def counter(name: str) -> Callable[[Counter], Counter]:
    def register(fn: Counter) -> Counter:
        _COUNTERS[name] = fn
        return fn

    return register


async def collect(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    return {name: await fn(session, user_id) for name, fn in sorted(_COUNTERS.items())}
