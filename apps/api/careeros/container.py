"""Composition root.

Builds long-lived collaborators once per process (API or worker) and exposes them to request
handlers and task handlers. Keeping construction here makes every integration swappable in
tests and keeps modules free of global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from careeros import __version__
from careeros.auth.providers import AuthProvider, GoogleOIDCVerifier, build_auth_provider
from careeros.config import Settings
from careeros.core.ratelimit import InMemoryRateLimiter, RateLimiter
from careeros.db.session import Database
from careeros.llm.router import LLMRouter
from careeros.llm.usage import DatabaseUsageSink


@dataclass
class Container:
    settings: Settings
    db: Database
    http: httpx.AsyncClient
    auth_provider: AuthProvider
    rate_limiter: RateLimiter
    llm: LLMRouter
    internal_verifier: GoogleOIDCVerifier | None = None
    owns_db: bool = True
    extras: dict[str, object] = field(default_factory=dict)

    async def aclose(self) -> None:
        await self.http.aclose()
        if self.owns_db:
            await self.db.dispose()


def build_container(settings: Settings, *, db: Database | None = None) -> Container:
    http = httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": f"CareerOS/{__version__}"},
        follow_redirects=False,
    )
    internal_verifier = None
    if (
        settings.internal_auth_mode == "oidc"
        and settings.internal_oidc_audience
        and settings.internal_oidc_service_account
    ):
        internal_verifier = GoogleOIDCVerifier(
            settings.internal_oidc_audience, settings.internal_oidc_service_account, http
        )
    database = db or Database.from_settings(settings)
    return Container(
        settings=settings,
        db=database,
        http=http,
        auth_provider=build_auth_provider(settings, http),
        rate_limiter=InMemoryRateLimiter(),
        llm=LLMRouter(settings, usage=DatabaseUsageSink(database)),
        internal_verifier=internal_verifier,
        owns_db=db is None,
    )
