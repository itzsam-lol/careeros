from __future__ import annotations

import httpx
import pytest
import respx

from careeros.config import Settings
from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient, is_public_address


def _settings() -> Settings:
    return Settings(_env_file=None, http_min_host_interval_seconds=0, http_respect_robots_txt=True)  # type: ignore[call-arg]


async def _resolver(host: str) -> list[str]:
    table = {
        "public.example.com": ["93.184.216.34"],
        "internal.example.com": ["10.0.0.5"],
        "sneaky.example.com": ["93.184.216.34", "127.0.0.1"],
    }
    return table.get(host, ["93.184.216.34"])


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("93.184.216.34", True),
        ("8.8.8.8", True),
        ("10.1.2.3", False),
        ("192.168.1.1", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),  # cloud metadata service
        ("::1", False),
        ("::ffff:127.0.0.1", False),
        ("0.0.0.0", False),  # noqa: S104 - classification input, not a bind address
    ],
)
def test_public_address_classification(address: str, public: bool) -> None:
    assert is_public_address(address) is public


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/computeMetadata/v1/",
        "http://internal.example.com/admin",
        "http://sneaky.example.com/",
        "file:///etc/passwd",
        "ftp://public.example.com/file",
        "http://public.example.com:6379/",
    ],
)
async def test_non_public_targets_are_refused(url: str) -> None:
    client = PoliteHttpClient(_settings(), resolver=_resolver)
    with pytest.raises(SourceFetchError):
        await client.ensure_public_url(url)
    await client.aclose()


@respx.mock
async def test_redirects_into_private_space_are_blocked() -> None:
    respx.get("https://public.example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://public.example.com/jobs").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
    )
    client = PoliteHttpClient(_settings(), resolver=_resolver)
    with pytest.raises(SourceFetchError, match="non-public"):
        await client.get("https://public.example.com/jobs")
    await client.aclose()


@respx.mock
async def test_robots_txt_is_honoured() -> None:
    respx.get("https://public.example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
    )
    respx.get("https://public.example.com/open").mock(return_value=httpx.Response(200, text="ok"))
    client = PoliteHttpClient(_settings(), resolver=_resolver)
    assert (await client.get("https://public.example.com/open")).text == "ok"
    with pytest.raises(SourceFetchError, match=r"robots.txt"):
        await client.get("https://public.example.com/private/page")
    await client.aclose()


@respx.mock
async def test_oversized_responses_are_rejected() -> None:
    respx.get("https://public.example.com/big").mock(
        return_value=httpx.Response(200, content=b"x" * 2048)
    )
    client = PoliteHttpClient(_settings(), resolver=_resolver)
    with pytest.raises(SourceFetchError, match="too large"):
        await client.get("https://public.example.com/big", respect_robots=False, max_bytes=1024)
    await client.aclose()


@respx.mock
async def test_transient_errors_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("careeros.core.http.asyncio.sleep", no_sleep)
    route = respx.get("https://public.example.com/flaky").mock(
        side_effect=[
            httpx.Response(503, headers={"retry-after": "1"}),
            httpx.Response(200, text="ok"),
        ]
    )
    client = PoliteHttpClient(_settings(), resolver=_resolver)
    page = await client.get("https://public.example.com/flaky", respect_robots=False)
    assert page.text == "ok"
    assert route.call_count == 2
    await client.aclose()
