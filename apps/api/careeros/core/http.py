"""Polite, SSRF-safe outbound HTTP for fetching external career data.

* Only http(s) URLs to public addresses: hosts resolving to private, loopback, link-local
  (e.g. the cloud metadata server 169.254.169.254), multicast or reserved ranges are refused,
  and every redirect hop is re-validated.
* robots.txt is honoured for page crawling (official ATS APIs opt out explicitly).
* Requests to the same host are spaced out; 429/5xx responses are retried with Retry-After.
* Response bodies are capped to avoid memory blow-ups.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
import urllib.robotparser
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from careeros.config import Settings
from careeros.core.clock import utcnow
from careeros.core.errors import SourceFetchError
from careeros.core.logging import get_logger

log = get_logger(__name__)

Resolver = Callable[[str], Awaitable[list[str]]]

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_ROBOTS_TTL_SECONDS = 12 * 3600


async def system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None
            and not is_public_address(str(ip.ipv4_mapped)))
    )  # fmt: skip


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    fetched_at_epoch: float

    @property
    def text(self) -> str:
        return self.content.decode(self._charset(), errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.content)

    def _charset(self) -> str:
        content_type = self.headers.get("content-type", "")
        if "charset=" in content_type:
            return content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        return "utf-8"


class PoliteHttpClient:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        resolver: Resolver = system_resolver,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.http_user_agent, "Accept-Language": "en"},
            follow_redirects=False,
        )
        self._resolver = resolver
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- guards --------------------------------------------------------------------------------

    async def ensure_public_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise SourceFetchError("Only public http(s) URLs can be fetched", retryable=False)
        if parts.port not in (None, 80, 443):
            raise SourceFetchError("Only standard web ports can be fetched", retryable=False)
        host = parts.hostname
        try:
            addresses = [host] if _is_ip_literal(host) else await self._resolver(host)
        except OSError as exc:
            raise SourceFetchError(f"Could not resolve {host}", retryable=True) from exc
        if not addresses or not all(is_public_address(a) for a in addresses):
            raise SourceFetchError(
                f"Refusing to fetch non-public address for {host}", retryable=False
            )

    async def _allowed_by_robots(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached is None or cached[0] < time.monotonic():
            parser: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                response = await self._request(f"{origin}/robots.txt", max_bytes=500_000, retries=1)
                if response.status_code >= 400:
                    parser = None  # no robots.txt (or unreadable): allowed
                elif parser is not None:
                    parser.parse(response.text.splitlines())
            except SourceFetchError:
                parser = None
            self._robots[origin] = (time.monotonic() + _ROBOTS_TTL_SECONDS, parser)
            cached = self._robots[origin]
        parser = cached[1]
        return True if parser is None else parser.can_fetch(self._settings.http_user_agent, url)

    async def _throttle(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._last_request.get(host, 0.0) + self._settings.http_min_host_interval_seconds
            delay = wait - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request[host] = time.monotonic()

    # --- requests ------------------------------------------------------------------------------

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        respect_robots: bool = True,
        max_bytes: int | None = None,
    ) -> FetchedPage:
        if params:
            url = str(httpx.URL(url, params=params))
        if respect_robots and self._settings.http_respect_robots_txt:
            await self.ensure_public_url(url)
            if not await self._allowed_by_robots(url):
                raise SourceFetchError(f"robots.txt disallows fetching {url}", retryable=False)
        page = await self._request(url, headers=headers, max_bytes=max_bytes)
        if page.status_code >= 400:
            raise SourceFetchError(
                f"{urlsplit(url).netloc} returned HTTP {page.status_code}",
                details={"status": page.status_code},
                retryable=page.status_code in _RETRY_STATUSES,
            )
        return page

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        page = await self.get(url, **kwargs)
        try:
            return page.json()
        except ValueError as exc:
            raise SourceFetchError(f"{urlsplit(url).netloc} returned invalid JSON") from exc

    async def _request(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        retries: int = 3,
    ) -> FetchedPage:
        limit = max_bytes or self._settings.http_max_response_bytes
        current = url
        for attempt in range(retries):
            for _hop in range(6):
                await self.ensure_public_url(current)
                await self._throttle(urlsplit(current).netloc)
                try:
                    async with self._client.stream("GET", current, headers=headers) as response:
                        if response.is_redirect and "location" in response.headers:
                            current = urljoin(current, response.headers["location"])
                            continue
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > limit:
                                raise SourceFetchError(
                                    f"Response from {urlsplit(current).netloc} is too large",
                                    retryable=False,
                                )
                        page = FetchedPage(
                            url=current,
                            status_code=response.status_code,
                            headers={k.lower(): v for k, v in response.headers.items()},
                            content=bytes(body),
                            fetched_at_epoch=time.time(),
                        )
                except httpx.TransportError as exc:
                    if attempt == retries - 1:
                        raise SourceFetchError(
                            f"Could not reach {urlsplit(current).netloc}", retryable=True
                        ) from exc
                    await asyncio.sleep(_backoff(attempt))
                    break
                if page.status_code in _RETRY_STATUSES and attempt < retries - 1:
                    delay = _retry_after(page.headers.get("retry-after")) or _backoff(attempt)
                    log.info(
                        "http_retry",
                        host=urlsplit(current).netloc,
                        status=page.status_code,
                        delay_s=delay,
                    )
                    await asyncio.sleep(min(delay, 30.0))
                    break
                return page
            else:
                raise SourceFetchError("Too many redirects", retryable=False)
        raise SourceFetchError(f"Could not fetch {urlsplit(url).netloc}", retryable=True)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def _backoff(attempt: int) -> float:
    return min(20.0, 2.0**attempt)


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, (when - utcnow()).total_seconds())
