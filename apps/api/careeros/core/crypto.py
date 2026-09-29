"""Encryption and signing helpers.

* `TokenCipher` encrypts OAuth tokens at rest (Fernet: AES-128-CBC + HMAC-SHA256).
* `sign_state` / `verify_state` produce tamper-proof, expiring payloads for OAuth `state`
  parameters so callbacks can be tied to the user who started the flow.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from careeros.core.errors import AuthenticationError, ConfigurationError


class TokenCipher:
    def __init__(self, key: str | bytes) -> None:
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ConfigurationError("ENCRYPTION_KEY is not a valid Fernet key") from exc

    @classmethod
    def derived_for_development(cls, secret: str) -> TokenCipher:
        """Deterministic key for local development only (production requires ENCRYPTION_KEY)."""
        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=b"careeros-dev", info=b"token-cipher"
        ).derive(secret.encode())
        return cls(base64.urlsafe_b64encode(key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ConfigurationError("Stored credential could not be decrypted") from exc


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_state(payload: dict[str, Any], secret: str, ttl_seconds: int = 600) -> str:
    body = {**payload, "exp": int(time.time()) + ttl_seconds, "nonce": secrets.token_urlsafe(8)}
    encoded = _b64encode(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def verify_state(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthenticationError("Malformed state") from exc
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(signature)):
        raise AuthenticationError("Invalid state signature")
    body: dict[str, Any] = json.loads(_b64decode(encoded))
    if int(body.get("exp", 0)) < int(time.time()):
        raise AuthenticationError("State has expired")
    return body


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
