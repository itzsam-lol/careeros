"""Authentication providers.

* `FirebaseAuthProvider` verifies Firebase ID tokens (RS256, Google-rotated certificates).
* `DevAuthProvider` accepts a static development token. It can only be constructed outside
  deployed environments (enforced by `Settings` validation and again here).
* `GoogleOIDCVerifier` verifies Google-signed OIDC tokens sent by Cloud Scheduler and Pub/Sub
  push subscriptions to internal endpoints.
"""

from __future__ import annotations

import asyncio
import hmac
import re
import time
from typing import Any, Protocol

import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate

from careeros.auth.principal import Principal
from careeros.config import Settings
from careeros.core.errors import AuthenticationError, ConfigurationError

FIREBASE_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
GOOGLE_OAUTH_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
_MAX_AGE = re.compile(r"max-age=(\d+)")
_DEV_SUFFIX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")


class AuthProvider(Protocol):
    name: str

    async def verify(self, token: str) -> Principal: ...


class GoogleCertificateCache:
    """Caches Google's PEM signing certificates, honouring Cache-Control max-age."""

    def __init__(self, url: str, http: httpx.AsyncClient) -> None:
        self._url = url
        self._http = http
        self._certs: dict[str, str] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, kid: str) -> str | None:
        if time.monotonic() >= self._expires_at or kid not in self._certs:
            await self._refresh(force=kid not in self._certs)
        return self._certs.get(kid)

    async def _refresh(self, *, force: bool) -> None:
        async with self._lock:
            if not force and time.monotonic() < self._expires_at:
                return
            try:
                response = await self._http.get(self._url, timeout=10)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                if self._certs:  # keep serving cached certificates during an outage
                    return
                raise AuthenticationError("Unable to fetch token signing keys") from exc
            self._certs = {str(k): str(v) for k, v in response.json().items()}
            match = _MAX_AGE.search(response.headers.get("cache-control", ""))
            ttl = int(match.group(1)) if match else 3600
            self._expires_at = time.monotonic() + max(60, ttl)


async def _decode_google_jwt(
    token: str,
    certs: GoogleCertificateCache,
    *,
    audience: str,
    issuer: str | list[str],
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Malformed token") from exc
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise AuthenticationError("Unexpected token algorithm")
    pem = await certs.get(str(header["kid"]))
    if pem is None:
        raise AuthenticationError("Unknown token signing key")
    public_key = load_pem_x509_certificate(pem.encode()).public_key()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            public_key,  # type: ignore[arg-type]
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc
    return claims


class FirebaseAuthProvider:
    name = "firebase"

    def __init__(self, project_id: str, http: httpx.AsyncClient) -> None:
        self._project_id = project_id
        self._certs = GoogleCertificateCache(FIREBASE_CERTS_URL, http)

    async def verify(self, token: str) -> Principal:
        claims = await _decode_google_jwt(
            token,
            self._certs,
            audience=self._project_id,
            issuer=f"https://securetoken.google.com/{self._project_id}",
        )
        subject = str(claims.get("sub") or "")
        if not subject or len(subject) > 128:
            raise AuthenticationError("Invalid token subject")
        if int(claims.get("auth_time", 0)) > int(time.time()) + 30:
            raise AuthenticationError("Invalid token auth_time")
        return Principal(
            provider=self.name,
            subject=subject,
            email=claims.get("email"),
            name=claims.get("name"),
            email_verified=bool(claims.get("email_verified", False)),
        )


class DevAuthProvider:
    """Static-token auth for local development and tests.

    `Bearer <token>` signs in as the default developer. `Bearer <token>:<suffix>` signs in as an
    additional isolated local user, which the test-suite uses to verify tenant isolation.
    """

    name = "dev"

    def __init__(self, settings: Settings) -> None:
        if settings.is_deployed:
            raise ConfigurationError("Development authentication is disabled in deployed envs")
        self._token = settings.dev_auth_token.get_secret_value()
        self._email = settings.dev_auth_email
        self._display_name = settings.dev_auth_name

    async def verify(self, token: str) -> Principal:
        base, _, suffix = token.partition(":")
        if not hmac.compare_digest(base.encode(), self._token.encode()):
            raise AuthenticationError("Invalid development token")
        if not suffix:
            return Principal(
                provider=self.name,
                subject="dev-user",
                email=self._email,
                name=self._display_name,
                email_verified=True,
            )
        if not _DEV_SUFFIX.match(suffix):
            raise AuthenticationError("Invalid development user suffix")
        return Principal(
            provider=self.name,
            subject=f"dev-{suffix}",
            email=f"{suffix}@careeros.local",
            name=suffix.title(),
            email_verified=True,
        )


class GoogleOIDCVerifier:
    """Verifies OIDC tokens attached by Cloud Scheduler / Pub/Sub push to internal endpoints."""

    def __init__(self, audience: str, service_account: str, http: httpx.AsyncClient) -> None:
        self._audience = audience
        self._service_account = service_account
        self._certs = GoogleCertificateCache(GOOGLE_OAUTH_CERTS_URL, http)

    async def verify(self, token: str) -> dict[str, Any]:
        claims = await _decode_google_jwt(
            token,
            self._certs,
            audience=self._audience,
            issuer=["https://accounts.google.com", "accounts.google.com"],
        )
        if claims.get("email") != self._service_account or not claims.get("email_verified"):
            raise AuthenticationError("Token was not issued to the expected service account")
        return claims


class PasswordSessionProvider:
    """Verifies CareerOS-issued session tokens (self-hosted email + password accounts)."""

    name = "password"

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.signing_secret.get_secret_value()

    async def verify(self, token: str) -> Principal:
        from careeros.auth.passwords import decode_session_token

        claims = decode_session_token(token, signing_secret=self._secret)
        return Principal(
            provider=self.name,
            subject=claims.subject,
            email=claims.email,
            name=claims.name,
            email_verified=True,
            session_version=claims.session_version,
        )


def build_auth_provider(settings: Settings, http: httpx.AsyncClient) -> AuthProvider:
    if settings.auth_mode == "firebase":
        if not settings.firebase_project_id:
            raise ConfigurationError("FIREBASE_PROJECT_ID is required for firebase auth")
        return FirebaseAuthProvider(settings.firebase_project_id, http)
    if settings.auth_mode == "password":
        return PasswordSessionProvider(settings)
    return DevAuthProvider(settings)
