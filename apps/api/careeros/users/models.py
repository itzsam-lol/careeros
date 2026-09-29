from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject"),)

    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    auth_provider: Mapped[str] = mapped_column(String(32))
    auth_subject: Mapped[str] = mapped_column(String(128))
    # Validated through `UserSettings`; stored sparse so new defaults apply automatically.
    settings: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    last_login_at: Mapped[datetime | None]
    # Self-hosted password accounts only (never set for Firebase users).
    password_hash: Mapped[str | None] = mapped_column(String(300))
    # Bumped on password change / "sign out everywhere": invalidates older session tokens.
    session_version: Mapped[int] = mapped_column(default=0, server_default="0")
