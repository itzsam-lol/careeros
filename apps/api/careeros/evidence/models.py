from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import EMBEDDING_DIM, Base, Timestamped, UUIDPrimaryKey, enum_type
from careeros.profile.enums import VerificationStatus


class EvidenceItem(UUIDPrimaryKey, Timestamped, Base):
    """One retrievable document per profile item, embedded for semantic search."""

    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("profile_id", "source_type", "source_id"),
        Index(
            "ix_evidence_items_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    verification_status: Mapped[VerificationStatus] = mapped_column(enum_type(VerificationStatus))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
