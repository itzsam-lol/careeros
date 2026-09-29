from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.auth.principal import Principal
from careeros.core.clock import utcnow
from careeros.core.errors import ValidationFailedError
from careeros.users.models import User
from careeros.users.schemas import UserSettings, merge_settings

_LOGIN_TOUCH_INTERVAL = timedelta(minutes=15)


async def get_or_create_user(session: AsyncSession, principal: Principal) -> User:
    """Resolve the authenticated principal to a local user, creating it on first sign-in.

    Identity always comes from the verified token, never from client-supplied ids.
    """
    lookup = select(User).where(
        User.auth_provider == principal.provider, User.auth_subject == principal.subject
    )
    user = (await session.execute(lookup)).scalar_one_or_none()
    now = utcnow()
    if user is None:
        # ON CONFLICT makes concurrent first requests from the same user safe.
        await session.execute(
            pg_insert(User)
            .values(
                id=uuid.uuid4(),
                email=principal.email or f"{principal.subject}@users.invalid",
                name=principal.name,
                auth_provider=principal.provider,
                auth_subject=principal.subject,
                settings={},
                last_login_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["auth_provider", "auth_subject"])
        )
        await session.commit()
        return (await session.execute(lookup)).scalar_one()

    changed = False
    if principal.email and user.email != principal.email:
        user.email = principal.email
        changed = True
    if principal.name and user.name != principal.name:
        user.name = principal.name
        changed = True
    if user.last_login_at is None or now - user.last_login_at > _LOGIN_TOUCH_INTERVAL:
        user.last_login_at = now
        changed = True
    if changed:
        await session.commit()
    return user


def read_settings(user: User) -> UserSettings:
    return UserSettings.model_validate(user.settings or {})


async def update_settings(session: AsyncSession, user: User, patch: dict[str, Any]) -> UserSettings:
    merged = merge_settings(user.settings or {}, patch)
    try:
        validated = UserSettings.model_validate(merged)
    except ValueError as exc:
        raise ValidationFailedError("Invalid settings", details={"reason": str(exc)}) from exc
    user.settings = validated.model_dump(mode="json")
    await session.flush()
    return validated
