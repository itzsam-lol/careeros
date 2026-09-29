"""Sign-in for self-hosted deployments (AUTH_MODE=password) and public auth configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import select

from careeros.api.deps import ContainerDep, CurrentUser, DbSession
from careeros.auth.passwords import (
    hash_password,
    issue_session_token,
    validate_password_strength,
    verify_password,
)
from careeros.core.clock import utcnow
from careeros.core.errors import AuthenticationError, ConflictError, RateLimitedError
from careeros.core.logging import get_logger
from careeros.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

Password = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class AuthConfig(BaseModel):
    mode: Literal["firebase", "password", "dev"]
    app_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: Password


class SessionOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_at: int
    email: str
    name: str | None


class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: Annotated[str, Field(min_length=10, max_length=256)]


@router.get("/config", response_model=AuthConfig, summary="How clients should sign in (public)")
async def auth_config(container: ContainerDep) -> AuthConfig:
    return AuthConfig(mode=container.settings.auth_mode, app_name=container.settings.app_name)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=SessionOut, summary="Sign in with email and password")
async def login(
    payload: LoginRequest, request: Request, session: DbSession, container: ContainerDep
) -> SessionOut:
    settings = container.settings
    if settings.auth_mode != "password":
        raise ConflictError("Password sign-in is not enabled on this server")
    email = payload.email.lower()
    limiter = container.rate_limiter
    for key, limit, window in (
        (f"login:ip:{_client_ip(request)}", 10, 300.0),
        (f"login:email:{email}", 5, 300.0),
    ):
        result = await limiter.hit(key, limit=limit, window_seconds=window)
        if not result.allowed:
            raise RateLimitedError(
                "Too many sign-in attempts. Try again in a few minutes.",
                details={"retry_after_seconds": round(result.retry_after_seconds)},
            )
    user = (
        await session.execute(
            select(User).where(User.auth_provider == "password", User.auth_subject == email)
        )
    ).scalar_one_or_none()
    # verify_password does the full scrypt work even when the user does not exist.
    if not verify_password(payload.password, user.password_hash if user else None) or user is None:
        log.info("login_failed", ip=_client_ip(request))
        raise AuthenticationError("Incorrect email or password")
    token, expires = issue_session_token(
        signing_secret=settings.signing_secret.get_secret_value(),
        subject=user.auth_subject,
        email=user.email,
        name=user.name,
        session_version=user.session_version,
    )
    user.last_login_at = utcnow()
    await session.commit()
    log.info("login_succeeded", user_id=str(user.id))
    return SessionOut(access_token=token, expires_at=expires, email=user.email, name=user.name)


@router.post("/logout-all", status_code=204, summary="Invalidate every existing session token")
async def logout_everywhere(user: CurrentUser, session: DbSession) -> None:
    user.session_version = (user.session_version or 0) + 1
    await session.commit()


@router.post("/change-password", response_model=SessionOut)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, session: DbSession, container: ContainerDep
) -> SessionOut:
    if user.auth_provider != "password":
        raise ConflictError("This account signs in with an external provider")
    if not verify_password(payload.current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")
    validate_password_strength(payload.new_password)
    user.password_hash = hash_password(payload.new_password)
    user.session_version = (user.session_version or 0) + 1  # other devices must sign in again
    token, expires = issue_session_token(
        signing_secret=container.settings.signing_secret.get_secret_value(),
        subject=user.auth_subject,
        email=user.email,
        name=user.name,
        session_version=user.session_version,
    )
    await session.commit()
    return SessionOut(access_token=token, expires_at=expires, email=user.email, name=user.name)
