"""Engine and session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from careeros.config import Settings


class Database:
    """Owns the async engine and hands out sessions.

    Services never commit implicitly: API handlers and task handlers commit explicitly once a
    unit of work succeeds, so partial work is never persisted.
    """

    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 5,
        echo: bool = False,
        use_null_pool: bool = False,
    ) -> None:
        engine_kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
        if use_null_pool:
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs.update(pool_size=pool_size, max_overflow=max_overflow)
        self.engine: AsyncEngine = create_async_engine(url, **engine_kwargs)
        self.sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        return cls(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.database_echo,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    async def ping(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()
