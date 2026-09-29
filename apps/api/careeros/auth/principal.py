from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    """A verified identity produced by an `AuthProvider`."""

    provider: str
    subject: str
    email: str | None
    name: str | None = None
    email_verified: bool = False
    # Only for self-hosted password sessions: must equal the user's current session version.
    session_version: int | None = None
