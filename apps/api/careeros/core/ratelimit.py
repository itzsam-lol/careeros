"""Rate limiting.

`RateLimiter` is an interface so a shared backend (e.g. Redis/Memorystore) can replace the
in-process implementation when the API runs on many instances. Safety-critical limits such as
outreach volume are *not* enforced here: they are computed from the database, which is the
authoritative record of what was actually sent.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: float


class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window_seconds: float) -> RateLimitResult: ...


class InMemoryRateLimiter:
    """Token bucket per key. Capacity `limit`, refilled evenly over `window_seconds`."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, max_keys: int = 50_000):
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, updated_at)
        self._lock = asyncio.Lock()
        self._max_keys = max_keys

    async def hit(self, key: str, *, limit: int, window_seconds: float) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(False, 0, window_seconds)
        rate = limit / window_seconds
        async with self._lock:
            now = self._clock()
            tokens, updated = self._buckets.get(key, (float(limit), now))
            tokens = min(float(limit), tokens + (now - updated) * rate)
            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = (tokens, now)
                result = RateLimitResult(True, int(tokens), 0.0)
            else:
                self._buckets[key] = (tokens, now)
                result = RateLimitResult(False, 0, (1.0 - tokens) / rate)
            if len(self._buckets) > self._max_keys:
                self._evict_idle_buckets(now)
        return result

    def _evict_idle_buckets(self, now: float) -> None:
        # Buckets idle long enough to be full carry no state worth keeping.
        stale = [k for k, (_, updated) in self._buckets.items() if now - updated > 3600]
        for key in stale:
            del self._buckets[key]
