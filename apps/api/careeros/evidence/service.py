"""Evidence indexing (incremental re-embedding) and semantic retrieval."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.logging import get_logger
from careeros.evidence.documents import EvidenceDocument, build_documents
from careeros.evidence.models import EvidenceItem
from careeros.llm.types import Embedder
from careeros.profile.enums import VerificationStatus
from careeros.profile.models import ProfessionalProfile
from careeros.profile.service import load_snapshot

log = get_logger(__name__)

DEFAULT_STATUSES = (VerificationStatus.VERIFIED,)


@dataclass(frozen=True, slots=True)
class IndexResult:
    embedded: int
    unchanged: int
    removed: int


@dataclass(frozen=True, slots=True)
class EvidenceHit:
    item: EvidenceItem
    similarity: float  # raw cosine similarity
    relevance: float  # calibrated 0..1 for the active embedding model


async def sync_profile_evidence(
    session: AsyncSession, profile: ProfessionalProfile, embedder: Embedder
) -> IndexResult:
    """Bring the evidence index in line with the profile. Only changed documents are embedded."""
    snapshot = await load_snapshot(session, profile)
    documents = build_documents(snapshot)
    existing = {
        (row.source_type, row.source_id): row
        for row in (
            await session.execute(select(EvidenceItem).where(EvidenceItem.profile_id == profile.id))
        ).scalars()
    }
    to_embed: list[tuple[EvidenceDocument, EvidenceItem]] = []
    unchanged = 0
    wanted: set[tuple[str, uuid.UUID]] = set()
    for doc in documents:
        key = (doc.source_type, doc.source_id)
        wanted.add(key)
        row = existing.get(key)
        if row is None:
            row = EvidenceItem(
                profile_id=profile.id,
                source_type=doc.source_type,
                source_id=doc.source_id,
                title=doc.title,
                content=doc.content,
                content_hash=doc.content_hash,
                verification_status=doc.verification_status,
            )
            session.add(row)
            to_embed.append((doc, row))
            continue
        row.verification_status = doc.verification_status
        if (
            row.content_hash != doc.content_hash
            or row.embedding_model != embedder.model
            or row.embedding is None
        ):
            row.title, row.content, row.content_hash = doc.title, doc.content, doc.content_hash
            to_embed.append((doc, row))
        else:
            unchanged += 1

    if to_embed:
        vectors = await embedder.embed_documents([f"{d.title}\n{d.content}" for d, _ in to_embed])
        for (_, row), vector in zip(to_embed, vectors, strict=True):
            row.embedding = vector
            row.embedding_model = embedder.model

    removed = 0
    for key, row in existing.items():
        if key not in wanted:
            await session.delete(row)
            removed += 1

    profile.indexed_version = profile.version
    await session.flush()
    log.info(
        "evidence_indexed",
        profile_id=str(profile.id),
        embedded=len(to_embed),
        unchanged=unchanged,
        removed=removed,
    )
    return IndexResult(embedded=len(to_embed), unchanged=unchanged, removed=removed)


async def ensure_indexed(
    session: AsyncSession, profile: ProfessionalProfile, embedder: Embedder
) -> None:
    if profile.indexed_version != profile.version:
        await sync_profile_evidence(session, profile, embedder)


async def search_evidence(
    session: AsyncSession,
    profile_id: uuid.UUID,
    query_vector: Sequence[float],
    embedder: Embedder,
    *,
    limit: int = 8,
    source_types: Sequence[str] | None = None,
    statuses: Sequence[VerificationStatus] = DEFAULT_STATUSES,
) -> list[EvidenceHit]:
    distance = EvidenceItem.embedding.cosine_distance(list(query_vector))
    stmt = (
        select(EvidenceItem, distance.label("distance"))
        .where(
            EvidenceItem.profile_id == profile_id,
            EvidenceItem.embedding.is_not(None),
            EvidenceItem.embedding_model == embedder.model,
            EvidenceItem.verification_status.in_(list(statuses)),
        )
        .order_by(distance)
        .limit(limit)
    )
    if source_types:
        stmt = stmt.where(EvidenceItem.source_type.in_(list(source_types)))
    hits: list[EvidenceHit] = []
    for item, dist in (await session.execute(stmt)).all():
        similarity = 1.0 - float(dist)
        hits.append(
            EvidenceHit(item=item, similarity=similarity, relevance=embedder.calibrate(similarity))
        )
    return hits
