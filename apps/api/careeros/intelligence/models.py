from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.clock import utcnow
from careeros.db.base import Base, UUIDPrimaryKey


class JobAnalysis(UUIDPrimaryKey, Base):
    """Structured JD extraction, cached per job text (shared by all users)."""

    __tablename__ = "job_analyses"
    __table_args__ = (UniqueConstraint("job_id", "description_hash", "version"),)

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    description_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(40))
    extractor: Mapped[str] = mapped_column(String(40))  # HEURISTIC | LLM | HEURISTIC_FALLBACK
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(160))
    extraction: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
