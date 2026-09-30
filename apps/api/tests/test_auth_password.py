from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.api.deps import get_session
from careeros.auth.passwords import (
    decode_session_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from careeros.config import Settings
from careeros.container import build_container
from careeros.core.errors import ValidationFailedError
from careeros.db.session import Database
from careeros.main import create_app
from careeros.users.models import User

SECRET = "s" * 48
PASSWORD = "Correct-Horse-9"


@pytest_asyncio.fixture
async def password_client(
    settings: Settings, database: Database, session: AsyncSession
) -> AsyncIterator[AsyncClient]:
    configured = settings.model_copy(
        update={
            "auth_mode": "password",
            "signing_secret": settings.signing_secret.__class__(SECRET),
        }
    )
    container = build_container(configured, db=database)
    app = create_app(configured, container=container)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http
    await container.aclose()


async def _create_user(session: AsyncSession, email: str = "owner@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        name="Owner",
        auth_provider="password",
        auth_subject=email,
        settings={},
        password_hash=hash_password(PASSWORD),
        session_version=0,
    )
    session.add(user)
    await session.commit()
    return user


async def _login(
    client: AsyncClient, email: str = "owner@example.com", password: str = PASSWORD
) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def test_password_hashing_round_trip() -> None:
    stored = hash_password(PASSWORD)
    assert stored.startswith("scrypt$")
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong-Password-1", stored)
    assert not verify_password(PASSWORD, None)  # unknown user: still runs, still False
    assert not verify_password(PASSWORD, "garbage")


@pytest.mark.parametrize(
    "weak", ["short1A", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHereAtAll"]
)
def test_weak_passwords_are_rejected(weak: str) -> None:
    with pytest.raises(ValidationFailedError):
        validate_password_strength(weak)


async def test_auth_config_is_public(password_client: AsyncClient) -> None:
    response = await password_client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert response.json()["mode"] == "password"


async def test_login_and_use_session(password_client: AsyncClient, session: AsyncSession) -> None:
    await _create_user(session)
    token = await _login(password_client, email="OWNER@example.com")  # emails are case-insensitive
    claims = decode_session_token(token, signing_secret=SECRET)
    assert claims.email == "owner@example.com"
    me = await password_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"


async def test_unknown_user_and_wrong_password_look_identical(
    password_client: AsyncClient, session: AsyncSession
) -> None:
    await _create_user(session)
    unknown = await password_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    wrong = await password_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "Wrong-Password-1"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]


async def test_login_is_rate_limited(password_client: AsyncClient, session: AsyncSession) -> None:
    await _create_user(session)
    statuses = [
        (
            await password_client.post(
                "/api/v1/auth/login", json={"email": "owner@example.com", "password": "Nope-nope-1"}
            )
        ).status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[-1] == 429


async def test_password_change_revokes_other_sessions(
    password_client: AsyncClient, session: AsyncSession
) -> None:
    await _create_user(session)
    old = await _login(password_client)
    changed = await password_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old}"},
        json={"current_password": PASSWORD, "new_password": "Brand-New-Secret-7"},
    )
    assert changed.status_code == 200, changed.text
    new = changed.json()["access_token"]
    assert (
        await password_client.get("/api/v1/me", headers={"Authorization": f"Bearer {old}"})
    ).status_code == 401
    assert (
        await password_client.get("/api/v1/me", headers={"Authorization": f"Bearer {new}"})
    ).status_code == 200


async def test_logout_everywhere(password_client: AsyncClient, session: AsyncSession) -> None:
    await _create_user(session)
    token = await _login(password_client)
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        await password_client.post("/api/v1/auth/logout-all", headers=headers)
    ).status_code == 204
    assert (await password_client.get("/api/v1/me", headers=headers)).status_code == 401


async def test_tokens_never_create_users_and_forged_tokens_fail(
    password_client: AsyncClient, session: AsyncSession
) -> None:
    from careeros.auth.passwords import issue_session_token

    ghost, _ = issue_session_token(
        signing_secret=SECRET,
        subject="ghost@example.com",
        email="ghost@example.com",
        name=None,
        session_version=0,
    )
    assert (
        await password_client.get("/api/v1/me", headers={"Authorization": f"Bearer {ghost}"})
    ).status_code == 401
    forged, _ = issue_session_token(
        signing_secret="x" * 48,
        subject="owner@example.com",
        email="owner@example.com",
        name=None,
        session_version=0,
    )
    await _create_user(session)
    assert (
        await password_client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"})
    ).status_code == 401


async def test_login_accepts_reserved_domain_accounts(
    password_client: AsyncClient, session: AsyncSession
) -> None:
    # create_user allows any address, so login must not reject e.g. ".local" domains.
    await _create_user(session, email="owner@careeros.local")
    response = await password_client.post(
        "/api/v1/auth/login", json={"email": " Owner@careeros.local ", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "owner@careeros.local"
