from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.audit.models import AuditLog
from careeros.config import Settings
from careeros.core.crypto import TokenCipher, sign_state, verify_state
from careeros.core.errors import AuthenticationError
from careeros.core.logging import redact_value
from careeros.core.ratelimit import InMemoryRateLimiter


async def test_health_endpoints(client: AsyncClient) -> None:
    live = await client.get("/healthz")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    ready = await client.get("/readyz")
    assert ready.status_code == 200
    assert ready.headers["x-request-id"]


async def test_requests_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me", headers={"Authorization": ""})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"

    bad = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


async def test_me_creates_user_from_token(client: AsyncClient, other_client: AsyncClient) -> None:
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "dev@careeros.local"
    assert body["settings"]["matching"]["high_match_threshold"] == 0.75

    other = await other_client.get("/api/v1/me")
    assert other.json()["id"] != body["id"]


async def test_settings_patch_is_validated_and_audited(
    client: AsyncClient, session: AsyncSession
) -> None:
    ok = await client.patch("/api/v1/me/settings", json={"matching": {"high_match_threshold": 0.8}})
    assert ok.status_code == 200
    assert ok.json()["matching"] == {"high_match_threshold": 0.8, "notify_threshold": 0.55}

    bad = await client.patch("/api/v1/me/settings", json={"outreach": {"max_emails_per_day": 999}})
    assert bad.status_code == 422

    actions = (await session.execute(select(AuditLog.action))).scalars().all()
    assert "SETTINGS_UPDATED" in actions


async def test_security_headers_present(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_deployed_settings_refuse_unsafe_defaults() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE"):
        Settings(_env_file=None, app_env="production")  # type: ignore[call-arg]


def test_auto_submit_and_auto_send_cannot_be_enabled() -> None:
    with pytest.raises(ValidationError, match="AUTO_SUBMIT_APPLICATIONS"):
        Settings(_env_file=None, auto_submit_applications=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="AUTO_SEND_EMAILS"):
        Settings(_env_file=None, auto_send_emails=True)  # type: ignore[call-arg]


def test_database_url_is_normalised_to_asyncpg() -> None:
    settings = Settings(_env_file=None, database_url="postgresql://u:p@h:5432/db")  # type: ignore[call-arg]
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_token_cipher_round_trip() -> None:
    cipher = TokenCipher.derived_for_development("secret")
    encrypted = cipher.encrypt("ya29.token")
    assert encrypted != "ya29.token"
    assert cipher.decrypt(encrypted) == "ya29.token"


def test_signed_state_rejects_tampering_and_expiry() -> None:
    token = sign_state({"uid": "123"}, "k" * 32)
    assert verify_state(token, "k" * 32)["uid"] == "123"
    with pytest.raises(AuthenticationError):
        verify_state(token, "x" * 32)
    expired = sign_state({"uid": "123"}, "k" * 32, ttl_seconds=-5)
    with pytest.raises(AuthenticationError):
        verify_state(expired, "k" * 32)


def test_log_redaction() -> None:
    redacted = redact_value(
        {"access_token": "abc", "input_tokens": 12, "nested": {"password": "p", "ok": 1}}
    )
    assert redacted == {
        "access_token": "[REDACTED]",
        "input_tokens": 12,
        "nested": {"password": "[REDACTED]", "ok": 1},
    }


async def test_token_bucket_rate_limiter() -> None:
    now = [0.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    results = [await limiter.hit("k", limit=3, window_seconds=60) for _ in range(4)]
    assert [r.allowed for r in results] == [True, True, True, False]
    assert results[-1].retry_after_seconds == pytest.approx(20.0)
    now[0] = 20.0
    assert (await limiter.hit("k", limit=3, window_seconds=60)).allowed
