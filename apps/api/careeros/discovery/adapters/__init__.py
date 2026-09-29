"""Source adapters. Official ATS job-board APIs first; public feeds and pages second."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from careeros.config import Settings
from careeros.core.errors import ValidationFailedError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.models import SourceType
from careeros.discovery.normalize import canonicalize_url
from careeros.discovery.raw import JobSourceAdapter

Slug = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
]
HttpUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^https?://", max_length=1000)
]
CompanyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GreenhouseConfig(_Config):
    board_token: Slug
    company_name: CompanyName | None = None


class LeverConfig(_Config):
    company: Slug
    region: Literal["global", "eu"] = "global"
    company_name: CompanyName | None = None


class AshbyConfig(_Config):
    organization: Slug
    company_name: CompanyName | None = None


class SmartRecruitersConfig(_Config):
    company: Slug
    company_name: CompanyName | None = None
    max_details: Annotated[int, Field(ge=0, le=100)] = 40


class RSSConfig(_Config):
    url: HttpUrl
    company_name: CompanyName | None = None


class CareerPageConfig(_Config):
    url: HttpUrl
    company_name: CompanyName | None = None
    follow_links: bool = False
    link_pattern: Annotated[str, StringConstraints(max_length=200)] | None = None
    max_pages: Annotated[int, Field(ge=1, le=50)] = 20


class FixtureConfig(_Config):
    name: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,60}$")]


CONFIG_MODELS: dict[SourceType, type[_Config]] = {
    SourceType.GREENHOUSE: GreenhouseConfig,
    SourceType.LEVER: LeverConfig,
    SourceType.ASHBY: AshbyConfig,
    SourceType.SMARTRECRUITERS: SmartRecruitersConfig,
    SourceType.RSS: RSSConfig,
    SourceType.CAREER_PAGE: CareerPageConfig,
    SourceType.FIXTURE: FixtureConfig,
}


def validate_config(
    source_type: SourceType, config: dict[str, Any], settings: Settings
) -> tuple[dict[str, Any], str]:
    """Validate a source config; returns (clean config, canonical identity)."""
    if source_type == SourceType.FIXTURE and settings.is_deployed:
        raise ValidationFailedError("Fixture sources are only available in development")
    model = CONFIG_MODELS[source_type]
    try:
        parsed = model.model_validate(config)
    except ValueError as exc:
        raise ValidationFailedError(
            "Invalid source configuration", details={"reason": str(exc)}
        ) from exc
    clean = parsed.model_dump(exclude_none=True)
    match parsed:
        case GreenhouseConfig():
            identity = f"greenhouse:{parsed.board_token.lower()}"
        case LeverConfig():
            identity = f"lever:{parsed.region}:{parsed.company.lower()}"
        case AshbyConfig():
            identity = f"ashby:{parsed.organization.lower()}"
        case SmartRecruitersConfig():
            identity = f"smartrecruiters:{parsed.company.lower()}"
        case RSSConfig() | CareerPageConfig():
            canonical = canonicalize_url(parsed.url)
            if canonical is None:
                raise ValidationFailedError("Invalid URL")
            identity = f"{source_type.value.lower()}:{canonical}"
        case FixtureConfig():
            identity = f"fixture:{parsed.name}"
        case _:  # pragma: no cover
            raise ValidationFailedError("Unsupported source type")
    return clean, identity[:600]


def build_adapter(
    source_type: SourceType, config: dict[str, Any], http: PoliteHttpClient
) -> JobSourceAdapter:
    from careeros.discovery.adapters.ashby import AshbyAdapter
    from careeros.discovery.adapters.career_page import CareerPageAdapter
    from careeros.discovery.adapters.fixture import FixtureAdapter
    from careeros.discovery.adapters.greenhouse import GreenhouseAdapter
    from careeros.discovery.adapters.lever import LeverAdapter
    from careeros.discovery.adapters.rss import RSSAdapter
    from careeros.discovery.adapters.smartrecruiters import SmartRecruitersAdapter

    model = CONFIG_MODELS[source_type]
    parsed: Any = model.model_validate(config)
    adapters: dict[SourceType, Any] = {
        SourceType.GREENHOUSE: GreenhouseAdapter,
        SourceType.LEVER: LeverAdapter,
        SourceType.ASHBY: AshbyAdapter,
        SourceType.SMARTRECRUITERS: SmartRecruitersAdapter,
        SourceType.RSS: RSSAdapter,
        SourceType.CAREER_PAGE: CareerPageAdapter,
        SourceType.FIXTURE: FixtureAdapter,
    }
    adapter: JobSourceAdapter = adapters[source_type](parsed, http)
    return adapter
