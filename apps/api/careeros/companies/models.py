from __future__ import annotations

from typing import Any

from sqlalchemy import String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey


class Company(UUIDPrimaryKey, Timestamped, Base):
    """A hiring organisation. Shared across users (public information only)."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    career_url: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    locations: Mapped[list[str]] = mapped_column(default=list, server_default=text("'[]'::jsonb"))
    research_summary: Mapped[str | None] = mapped_column(Text)
    technology_summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", default=dict, server_default=text("'{}'::jsonb")
    )
