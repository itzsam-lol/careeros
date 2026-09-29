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
