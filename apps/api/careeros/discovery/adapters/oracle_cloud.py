"""Oracle Recruiting Cloud career sites (JPMorgan Chase, Oracle, ...).

Every Oracle HCM "Candidate Experience" site is backed by a public REST search
(`recruitingCEJobRequisitions`) identified by the host and a site number, e.g.
https://jpmc.fa.oraclecloud.com + CX_1001. We narrow to the configured countries with the
site's location facet (or a keyword search when the facet is missing), newest first, and fetch
the full description only for postings we have not stored yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import parse_datetime
from careeros.discovery.raw import KnownPostings, RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import OracleCloudConfig

_PAGE = 25
ISO2 = {
    "india": "IN", "australia": "AU", "singapore": "SG", "united states": "US",
    "united kingdom": "GB", "canada": "CA", "germany": "DE", "ireland": "IE", "japan": "JP",
}  # fmt: skip


class OracleCloudAdapter:
    complete_listing = False

    def __init__(self, config: OracleCloudConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http
        self.host = str(config.host).rstrip("/")
        self.api = f"{self.host}/hcmRestApi/resources/latest"
        self.known = KnownPostings()

    async def _search(self, extra: str) -> dict[str, Any]:
        finder = f"findReqs;siteNumber={self.config.site_number},{extra}"
        data = await self.http.get_json(
            f"{self.api}/recruitingCEJobRequisitions",
            params={
                "onlyData": "true",
                "expand": "requisitionList.secondaryLocations",
                "finder": finder,
            },
            respect_robots=False,
        )
        items = data.get("items") if isinstance(data, dict) else None
        return items[0] if isinstance(items, list) and items else {}

    async def _details(self, job_id: str) -> dict[str, Any]:
        try:
            data = await self.http.get_json(
                f"{self.api}/recruitingCEJobRequisitionDetails",
                params={
                    "expand": "all",
                    "onlyData": "true",
                    "finder": f'ById;Id="{job_id}",siteNumber={self.config.site_number}',
                },
                respect_robots=False,
            )
        except SourceFetchError:
            return {}
        items = data.get("items") if isinstance(data, dict) else None
        return items[0] if isinstance(items, list) and items else {}

    async def _requisitions(self) -> list[dict[str, Any]]:
        facets = await self._search("facetsList=LOCATIONS,limit=1")
        by_name = {
            str(f.get("Name") or "").lower(): f.get("Id")
            for f in facets.get("locationsFacet") or []
        }
        wanted_codes = {ISO2[c.lower()] for c in self.config.countries if c.lower() in ISO2}
        found: dict[str, dict[str, Any]] = {}
        for country in self.config.countries:
            facet_id = by_name.get(country.lower())
            selector = f"selectedLocationsFacet={facet_id}" if facet_id else f'keyword="{country}"'
            offset = 0
            while len(found) < self.config.max_jobs:
                page = await self._search(
                    f"{selector},limit={_PAGE},offset={offset},sortBy=POSTING_DATES_DESC"
                )
                rows = page.get("requisitionList") or []
                for row in rows:
                    code = str(row.get("PrimaryLocationCountry") or "").upper()
                    if row.get("Id") and (not wanted_codes or code in wanted_codes):
                        found.setdefault(str(row["Id"]), row)
                offset += _PAGE
                if len(rows) < _PAGE or offset >= int(page.get("TotalJobsCount") or 0):
                    break
        return list(found.values())[: self.config.max_jobs]

    async def discover_jobs(self) -> list[RawJob]:
        results: list[RawJob] = []
        details_left = self.config.max_details
        for row in await self._requisitions():
            job_id = str(row["Id"])
            if job_id in self.known.ids:
                continue  # stored already; only new postings are fetched
            description = row.get("ShortDescriptionStr") or ""
            if details_left > 0:
                details_left -= 1
                detail = await self._details(job_id)
                description = (
                    "".join(
                        str(detail.get(key) or "")
                        for key in (
                            "ExternalDescriptionStr",
                            "ExternalResponsibilitiesStr",
                            "ExternalQualificationsStr",
                        )
                    )
                    or description
                )
            secondary = [
                str(loc.get("Name"))
                for loc in row.get("secondaryLocations") or []
                if loc.get("Name")
            ]
            location = row.get("PrimaryLocation")
            url = f"{self.host}/hcmUI/CandidateExperience/en/sites/{self.config.site_number}/job/{job_id}"
            results.append(
                RawJob(
                    external_id=job_id,
                    title=str(row.get("Title") or ""),
                    company=self.config.company_name,
                    url=url,
                    apply_url=url,
                    location=location,
                    locations=[str(p) for p in [location, *secondary] if p],
                    description_html=description,
                    posted_at=parse_datetime(row.get("PostedDate")),
                    employment_type_hint=row.get("JobSchedule") or row.get("WorkerType"),
                    remote_hint=row.get("WorkplaceTypeCode"),
                    department=row.get("JobFamily"),
                    metadata={"oracle_site": self.config.site_number},
                )
            )
        return [r for r in results if r.title]
