"""Time helpers. All timestamps in CareerOS are timezone-aware UTC."""

from __future__ import annotations

from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def today_utc() -> date:
    return utcnow().date()


def ensure_aware(value: datetime) -> datetime:
    """Treat naive datetimes from external sources as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
