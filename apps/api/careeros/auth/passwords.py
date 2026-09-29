"""Password hashing (scrypt, stdlib) and signed session tokens for self-hosted deployments."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from careeros.core.errors import AuthenticationError, ValidationFailedError

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64
_ISSUER = "careeros"
_AUDIENCE = "careeros-app"
SESSION_TTL_SECONDS = 30 * 24 * 3600
MIN_PASSWORD_LENGTH = 10


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationFailedError(f"Use at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > 256:
        raise ValidationFailedError("Password is too long")
    if (
        password.lower() == password
        or password.upper() == password
        or not any(c.isdigit() for c in password)
    ):
        raise ValidationFailedError("Mix upper- and lower-case letters and at least one digit")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
        maxmem=128 * 1024 * 1024,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check. Always does the full scrypt work, even for unknown users."""
    if not stored:
        stored = _DUMMY_HASH
        expected = False
    else:
        expected = True
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode(),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(digest)),
            maxmem=128 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, _unb64(digest)) and expected


_DUMMY_HASH = hash_password("CareerOS-dummy-password-1")


def _session_key(signing_secret: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"careeros-sessions", info=b"session-token"
    ).derive(signing_secret.encode())


@dataclass(frozen=True, slots=True)
class SessionClaims:
    subject: str
    email: str
    name: str | None
    session_version: int
    expires_at: int


def issue_session_token(
    *, signing_secret: str, subject: str, email: str, name: str | None, session_version: int
) -> tuple[str, int]:
    now = int(time.time())
    expires = now + SESSION_TTL_SECONDS
    payload: dict[str, Any] = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": subject,
        "email": email,
        "name": name,
        "sv": session_version,
        "iat": now,
        "exp": expires,
        "jti": secrets.token_urlsafe(12),
        "typ": "session",
    }
    return jwt.encode(payload, _session_key(signing_secret), algorithm="HS256"), expires


def decode_session_token(token: str, *, signing_secret: str) -> SessionClaims:
    try:
        claims = jwt.decode(
            token,
            _session_key(signing_secret),
            algorithms=["HS256"],
            audience=_AUDIENCE,
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Your session has expired; please sign in again") from exc
    if claims.get("typ") != "session":
        raise AuthenticationError("Invalid session token")
    return SessionClaims(
        subject=str(claims["sub"]),
        email=str(claims.get("email") or ""),
        name=claims.get("name"),
        session_version=int(claims.get("sv", 0)),
        expires_at=int(claims["exp"]),
    )
