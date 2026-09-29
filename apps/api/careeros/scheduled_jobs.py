"""Periodic maintenance jobs (deadline checks, outreach follow-ups, ...).

Each phase registers its periodic producers here; the scheduler calls them every tick.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from careeros.container import Container

PeriodicProducer = Callable[[AsyncSession, "Container"], Awaitable[int]]
_PRODUCERS: dict[str, PeriodicProducer] = {}


def periodic(name: str) -> Callable[[PeriodicProducer], PeriodicProducer]:
    def register(fn: PeriodicProducer) -> PeriodicProducer:
        _PRODUCERS[name] = fn
        return fn

    return register


async def schedule_periodic(session: AsyncSession, container: Container) -> dict[str, int]:
    return {name: await producer(session, container) for name, producer in _PRODUCERS.items()}
