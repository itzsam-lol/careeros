from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints

from careeros.api.deps import ContainerDep, CurrentUser, DbSession, rate_limit
from careeros.evidence import service
from careeros.profile.enums import VerificationStatus
from careeros.profile.service import get_or_create_profile

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceSearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=4000)]
    limit: Annotated[int, Field(ge=1, le=20)] = 6
    include_unverified: bool = False


class EvidenceHitOut(BaseModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    title: str
    content: str
    verification_status: VerificationStatus
    relevance: float


class IndexStatus(BaseModel):
    embedded: int
    unchanged: int
    removed: int
    embedding_model: str


@router.post("/reindex", response_model=IndexStatus)
async def reindex(
    user: CurrentUser,
    session: DbSession,
    container: ContainerDep,
    _: Annotated[None, Depends(rate_limit("evidence.reindex", limit=10, window_seconds=60))],
) -> IndexStatus:
    profile = await get_or_create_profile(session, user)
    embedder = container.llm.embedder
    result = await service.sync_profile_evidence(session, profile, embedder)
    await session.commit()
    return IndexStatus(**asdict(result), embedding_model=embedder.model)


@router.post("/search", response_model=list[EvidenceHitOut])
async def search(
    payload: EvidenceSearchRequest,
    user: CurrentUser,
    session: DbSession,
    container: ContainerDep,
    _: Annotated[None, Depends(rate_limit("evidence.search", limit=60, window_seconds=60))],
) -> list[EvidenceHitOut]:
    profile = await get_or_create_profile(session, user)
    embedder = container.llm.embedder
    await service.ensure_indexed(session, profile, embedder)
    query_vector = await embedder.embed_query(payload.query)
    statuses = (
        (VerificationStatus.VERIFIED, VerificationStatus.UNVERIFIED)
        if payload.include_unverified
        else (VerificationStatus.VERIFIED,)
    )
    hits = await service.search_evidence(
        session, profile.id, query_vector, embedder, limit=payload.limit, statuses=statuses
    )
    await session.commit()
    return [
        EvidenceHitOut(
            id=hit.item.id,
            source_type=hit.item.source_type,
            source_id=hit.item.source_id,
            title=hit.item.title,
            content=hit.item.content,
            verification_status=hit.item.verification_status,
            relevance=round(hit.relevance, 3),
        )
        for hit in hits
    ]
