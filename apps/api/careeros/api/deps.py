"""Shared FastAPI dependencies."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.auth.principal import Principal
from careeros.container import Container
from careeros.core.errors import AuthenticationError, RateLimitedError
from careeros.core.logging import bind_context
from careeros.users.models import User
from careeros.users.service import get_or_create_user

_bearer = HTTPBearer(auto_error=False, description="Firebase ID token (or dev token locally)")


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.db.session() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_principal(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer token")
    return await container.auth_provider.verify(credentials.credentials)


async def get_current_user(
    principal: Annotated[Principal, Depends(get_principal)],
    session: DbSession,
    container: ContainerDep,
) -> User:
    user = await get_or_create_user(session, principal)
    bind_context(user_id=str(user.id))
    result = await container.rate_limiter.hit(
        f"api:{user.id}", limit=container.settings.api_rate_limit_per_minute, window_seconds=60
    )
    if not result.allowed:
        raise RateLimitedError(
            "Too many requests", details={"retry_after_seconds": round(result.retry_after_seconds)}
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def rate_limit(bucket: str, *, limit: int, window_seconds: float) -> Callable[..., Awaitable[None]]:
    """Per-user limit for expensive operations (LLM generation, discovery runs, ...)."""

    async def _dependency(user: CurrentUser, container: ContainerDep) -> None:
        result = await container.rate_limiter.hit(
            f"{bucket}:{user.id}", limit=limit, window_seconds=window_seconds
        )
        if not result.allowed:
            raise RateLimitedError(
                f"Rate limit exceeded for {bucket}",
                details={"retry_after_seconds": round(result.retry_after_seconds)},
            )

    return _dependency


async def verify_internal_caller(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Authenticates Cloud Scheduler / Pub/Sub push (OIDC) or a shared token in development."""
    if credentials is None:
        raise AuthenticationError("Missing internal credentials")
    settings = container.settings
    if settings.internal_auth_mode == "oidc":
        if container.internal_verifier is None:
            raise AuthenticationError("Internal OIDC verification is not configured")
        await container.internal_verifier.verify(credentials.credentials)
        return
    expected = settings.internal_api_token.get_secret_value()
    if not hmac.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise AuthenticationError("Invalid internal token")


InternalCaller = Depends(verify_internal_caller)
