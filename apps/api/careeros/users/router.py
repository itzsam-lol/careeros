from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from careeros.api.deps import CurrentUser, DbSession
from careeros.audit import service as audit
from careeros.audit.models import AuditAction
from careeros.users import service
from careeros.users.schemas import MeResponse, UserSettings

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
async def get_me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        auth_provider=user.auth_provider,
        created_at=user.created_at,
        settings=service.read_settings(user),
    )


@router.get("/settings", response_model=UserSettings)
async def get_settings(user: CurrentUser) -> UserSettings:
    return service.read_settings(user)


@router.patch("/settings", response_model=UserSettings)
async def patch_settings(
    user: CurrentUser,
    session: DbSession,
    patch: dict[str, Any] = Body(..., examples=[{"matching": {"high_match_threshold": 0.8}}]),
) -> UserSettings:
    updated = await service.update_settings(session, user, patch)
    await audit.record(
        session,
        action=AuditAction.SETTINGS_UPDATED,
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        metadata={"keys": sorted(patch.keys())},
    )
    await session.commit()
    return updated
