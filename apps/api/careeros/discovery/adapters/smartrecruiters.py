"""SmartRecruiters public Posting API (official)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import parse_datetime, title_from_slug
from careeros.discovery.normalize import extract_countries
from careeros.discovery.raw import KnownPostings, RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import SmartRecruitersConfig

API = "https://api.smartrecruiters.com/v1/companies"
_PAGE = 100
_MAX_POSTINGS = 500


class SmartRecruitersAdapter:
    complete_listing = True

    def __init__(self, config: SmartRecruitersConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http
        self.known = KnownPostings()

    async def _details(self, ref: str) -> dict[str, Any]:
        try:
            detail = await self.http.get_json(ref, respect_robots=False)
        except SourceFetchError:
            return {}
        return detail if isinstance(detail, dict) else {}

    async def discover_jobs(self) -> list[RawJob]:
        postings: list[dict[str, Any]] = []
        offset = 0
        while offset < _MAX_POSTINGS:
            page = await self.http.get_json(
                f"{API}/{self.config.company}/postings",
                params={"limit": _PAGE, "offset": offset},
                respect_robots=False,
            )
            content = page.get("content", []) if isinstance(page, dict) else []
            postings.extend(content)
            if len(content) < _PAGE:
                break
            offset += _PAGE

        results: list[RawJob] = []
        wanted = set(extract_countries(self.config.countries or []))
        details_left = self.config.max_details
        for posting in postings:
            if not posting.get("id") or not posting.get("name"):
                continue
            loc = posting.get("location") or {}
            location = loc.get("fullLocation") or ", ".join(
                str(p) for p in (loc.get("city"), loc.get("region"), loc.get("country")) if p
            )
            code = str(loc.get("country") or "").lower()
            found = set(extract_countries([location, *([code.upper()] if code else [])]))
            if wanted and found and not found & wanted:
                continue  # global boards list the whole world; skip before fetching details
            company = (
                self.config.company_name
                or (posting.get("company") or {}).get("name")
                or title_from_slug(self.config.company)
            )
            description_html = None
            posting_url = None
            is_new = str(posting["id"]) not in self.known.ids
            if is_new and details_left > 0 and posting.get("ref"):
                details_left -= 1
                detail = await self._details(str(posting["ref"]))
                sections = (detail.get("jobAd") or {}).get("sections") or {}
                description_html = "\n".join(
                    str((sections.get(key) or {}).get("text") or "")
                    for key in ("jobDescription", "qualifications", "additionalInformation")
                )
                posting_url = detail.get("postingUrl") or detail.get("applyUrl")
            results.append(
                RawJob(
                    external_id=str(posting["id"]),
                    title=str(posting["name"]),
                    company=str(company),
                    url=posting_url,
                    apply_url=posting_url,
                    location=location or None,
                    locations=[location] if location else [],
                    description_html=description_html,
                    posted_at=parse_datetime(posting.get("releasedDate")),
                    employment_type_hint=(posting.get("typeOfEmployment") or {}).get("label"),
                    remote_hint="remote" if loc.get("remote") else None,
                    department=(posting.get("department") or {}).get("label"),
                    metadata={
                        "experience_level": (posting.get("experienceLevel") or {}).get("label")
                    },
                )
            )
        return results
