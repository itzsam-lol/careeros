from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dateutil import parser as date_parser

from careeros.core.clock import ensure_aware
from careeros.core.enums import CompensationPeriod


def parse_datetime(value: Any) -> datetime | None:
    """Parse ISO strings, epoch milliseconds/seconds or datetimes; None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC)
    try:
        return ensure_aware(date_parser.isoparse(str(value)))
    except (ValueError, OverflowError):
        try:
            return ensure_aware(date_parser.parse(str(value)))
        except (ValueError, OverflowError):
            return None


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def period_from_text(value: str | None) -> CompensationPeriod | None:
    if not value:
        return None
    v = value.lower()
    if "hour" in v:
        return CompensationPeriod.HOUR
    if "week" in v:
        return CompensationPeriod.WEEK
    if "month" in v:
        return CompensationPeriod.MONTH
    if "year" in v or "annual" in v or "annum" in v:
        return CompensationPeriod.YEAR
    return None


def as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None
