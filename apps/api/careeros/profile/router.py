# NOTE: no `from __future__ import annotations` here. Section endpoints are generated in a
# factory and FastAPI must resolve their per-section schema annotations from closure scope.
import uuid
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import Response

from careeros.api.deps import CurrentUser, DbSession
from careeros.audit import service as audit
from careeros.audit.models import AuditAction
from careeros.core.errors import NotFoundError
from careeros.profile import service
from careeros.profile.importer import ImportResult, ProfileImport, import_profile
from careeros.profile.schemas import (
    BulkVerificationRequest,
    PreferencesIn,
    PreferencesOut,
    ProfileBasicsIn,
    ProfileBasicsOut,
    ProfileOut,
    VerificationUpdate,
)
from careeros.profile.sections import SECTIONS, Section

router = APIRouter(prefix="/profile", tags=["profile"])


def _serialize(section: Section, item: Any) -> Any:
    return section.schema_out.model_validate(item)


@router.get("", response_model=ProfileOut, summary="The full professional profile")
async def get_profile(user: CurrentUser, session: DbSession) -> ProfileOut:
    profile = await service.get_or_create_profile(session, user)
    snapshot = await service.load_snapshot(session, profile)
    await session.commit()
    return ProfileOut(
        basics=ProfileBasicsOut.model_validate(profile),
        preferences=PreferencesOut.model_validate(snapshot.preferences),
        stats=service.compute_stats(snapshot),
        **{
            key: [_serialize(section, item) for item in getattr(snapshot, key)]
            for key, section in SECTIONS.items()
        },
    )


@router.put("/basics", response_model=ProfileBasicsOut)
async def put_basics(
    payload: ProfileBasicsIn, user: CurrentUser, session: DbSession
) -> ProfileBasicsOut:
    profile = await service.get_or_create_profile(session, user)
    await service.update_basics(session, profile, payload)
    await audit.record(
        session,
        action=AuditAction.PROFILE_UPDATED,
        user_id=user.id,
        entity_type="profile",
        entity_id=profile.id,
        metadata={"section": "basics", "fields": sorted(payload.model_fields_set)},
    )
    await session.commit()
    return ProfileBasicsOut.model_validate(profile)


@router.put("/preferences", response_model=PreferencesOut)
async def put_preferences(
    payload: PreferencesIn, user: CurrentUser, session: DbSession
) -> PreferencesOut:
    profile = await service.get_or_create_profile(session, user)
    prefs = await service.update_preferences(session, profile, payload)
    await audit.record(
        session,
        action=AuditAction.PROFILE_UPDATED,
        user_id=user.id,
        entity_type="profile",
        entity_id=profile.id,
        metadata={"section": "preferences", "fields": sorted(payload.model_fields_set)},
    )
    await session.commit()
    return PreferencesOut.model_validate(prefs)


@router.post("/verification", summary="Set the verification status of several items at once")
async def bulk_verification(
    payload: BulkVerificationRequest, user: CurrentUser, session: DbSession
) -> dict[str, int]:
    section = SECTIONS.get(payload.section)
    if section is None:
        raise NotFoundError("Unknown profile section")
    profile = await service.get_or_create_profile(session, user)
    items = await service.set_status(session, profile, section, payload.ids, payload.status)
    await audit.record(
        session,
        action=AuditAction.PROFILE_ITEM_VERIFIED,
        user_id=user.id,
        entity_type=section.entity,
        metadata={"count": len(items), "status": payload.status.value},
    )
    await session.commit()
    return {"updated": len(items)}


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Import a structured profile (items start UNVERIFIED until reviewed)",
)
async def import_json(
    payload: ProfileImport, user: CurrentUser, session: DbSession
) -> ImportResult:
    profile = await service.get_or_create_profile(session, user)
    result = await import_profile(session, profile, payload)
    await audit.record(
        session,
        action=AuditAction.PROFILE_IMPORTED,
        user_id=user.id,
        entity_type="profile",
        entity_id=profile.id,
        metadata={"created": result.created, "skipped": result.skipped},
    )
    await session.commit()
    return result


def _register_section(section: Section) -> None:
    schema_in = section.schema_in
    schema_out = section.schema_out
    key = section.key

    async def list_section(user: CurrentUser, session: DbSession) -> list[Any]:
        profile = await service.get_or_create_profile(session, user)
        items = await service.list_items(session, profile, section)
        await session.commit()
        return [_serialize(section, item) for item in items]

    async def create_section_item(
        payload: schema_in,  # type: ignore[valid-type]
        user: CurrentUser,
        session: DbSession,
    ) -> Any:
        profile = await service.get_or_create_profile(session, user)
        item = await service.create_item(session, profile, section, payload.model_dump())  # type: ignore[attr-defined]
        await audit.record(
            session,
            action=AuditAction.PROFILE_UPDATED,
            user_id=user.id,
            entity_type=section.entity,
            entity_id=item.id,
            metadata={"operation": "create"},
        )
        await session.commit()
        return _serialize(section, item)

    async def update_section_item(
        item_id: uuid.UUID,
        payload: schema_in,  # type: ignore[valid-type]
        user: CurrentUser,
        session: DbSession,
    ) -> Any:
        profile = await service.get_or_create_profile(session, user)
        item = await service.update_item(
            session,
            profile,
            section,
            item_id,
            payload.model_dump(),  # type: ignore[attr-defined]
        )
        await audit.record(
            session,
            action=AuditAction.PROFILE_UPDATED,
            user_id=user.id,
            entity_type=section.entity,
            entity_id=item.id,
            metadata={"operation": "update"},
        )
        await session.commit()
        return _serialize(section, item)

    async def delete_section_item(
        item_id: uuid.UUID, user: CurrentUser, session: DbSession
    ) -> Response:
        profile = await service.get_or_create_profile(session, user)
        await service.delete_item(session, profile, section, item_id)
        await audit.record(
            session,
            action=AuditAction.PROFILE_UPDATED,
            user_id=user.id,
            entity_type=section.entity,
            entity_id=item_id,
            metadata={"operation": "delete"},
        )
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def verify_section_item(
        item_id: uuid.UUID, payload: VerificationUpdate, user: CurrentUser, session: DbSession
    ) -> Any:
        profile = await service.get_or_create_profile(session, user)
        [item] = await service.set_status(session, profile, section, [item_id], payload.status)
        await audit.record(
            session,
            action=AuditAction.PROFILE_ITEM_VERIFIED,
            user_id=user.id,
            entity_type=section.entity,
            entity_id=item_id,
            metadata={"status": payload.status.value},
        )
        await session.commit()
        return _serialize(section, item)

    tag = f"profile:{key}"
    router.add_api_route(
        f"/{key}",
        list_section,
        methods=["GET"],
        response_model=list[schema_out],  # type: ignore[valid-type]
        operation_id=f"list_{key}",
        tags=[tag],
    )
    router.add_api_route(
        f"/{key}",
        create_section_item,
        methods=["POST"],
        response_model=schema_out,
        status_code=status.HTTP_201_CREATED,
        operation_id=f"create_{key}",
        tags=[tag],
    )
    router.add_api_route(
        f"/{key}/{{item_id}}",
        update_section_item,
        methods=["PUT"],
        response_model=schema_out,
        operation_id=f"update_{key}",
        tags=[tag],
    )
    router.add_api_route(
        f"/{key}/{{item_id}}",
        delete_section_item,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        operation_id=f"delete_{key}",
        tags=[tag],
    )
    router.add_api_route(
        f"/{key}/{{item_id}}/verification",
        verify_section_item,
        methods=["POST"],
        response_model=schema_out,
        operation_id=f"verify_{key}",
        tags=[tag],
    )


for _section in SECTIONS.values():
    _register_section(_section)
