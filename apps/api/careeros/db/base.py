"""Declarative base, shared column mixins and column-type helpers."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from careeros.core.clock import utcnow

# Every embedding stored in CareerOS uses this dimensionality. Providers are asked for exactly
# this many dimensions (Gemini/Titan support it natively; the local embedder is built for it).
EMBEDDING_DIM = 1024

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy reads this class attribute
        datetime: DateTime(timezone=True),
        uuid.UUID: UUID(as_uuid=True),
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        list[dict[str, Any]]: JSONB,
    }


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamped:
    # Python-side defaults keep values populated on the instance after flush, which avoids
    # implicit refresh (lazy IO) under asyncio.
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now(), onupdate=utcnow
    )


def enum_type[E: StrEnum](enum_cls: type[E], length: int = 48) -> SAEnum:
    """Store enums as VARCHAR of their values (no native PG enum: painless migrations)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
