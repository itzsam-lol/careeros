"""Resume templates and generated documents (tailored resumes, cover letters)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey, enum_type


class DocumentKind(StrEnum):
    RESUME = "RESUME"
    COVER_LETTER = "COVER_LETTER"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class ResumeMaster(UUIDPrimaryKey, Timestamped, Base):
    """The user's own LaTeX resume: the source every tailored version starts from."""

    __tablename__ = "resume_masters"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    filename: Mapped[str] = mapped_column(String(200), default="resume.tex")
    tex: Mapped[str] = mapped_column(Text)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary)
    pages: Mapped[int | None] = mapped_column(Integer)
    engine: Mapped[str | None] = mapped_column(String(20))
    compiled_at: Mapped[datetime | None]
    compile_error: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ResumeDocument(UUIDPrimaryKey, Timestamped, Base):
    """A generated document for one job (or a general one), kept as an immutable version."""

    __tablename__ = "resume_documents"
    __table_args__ = (Index("ix_resume_documents_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[DocumentKind] = mapped_column(enum_type(DocumentKind), default=DocumentKind.RESUME)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_type(DocumentStatus), default=DocumentStatus.PENDING
    )
    title: Mapped[str] = mapped_column(String(300))
    master_revision: Mapped[int | None] = mapped_column(Integer)
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    tex: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)  # plain text (cover letters)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary)
    pages: Mapped[int | None] = mapped_column(Integer)
    engine: Mapped[str | None] = mapped_column(String(20))
    changes: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    keywords_before: Mapped[dict[str, Any]] = mapped_column(default=dict)
    keywords_after: Mapped[dict[str, Any]] = mapped_column(default=dict)
    coverage_before: Mapped[float | None]
    coverage_after: Mapped[float | None]
    error: Mapped[str | None] = mapped_column(Text)
    starred: Mapped[bool] = mapped_column(default=False)
