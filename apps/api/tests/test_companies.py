from __future__ import annotations

from pathlib import Path

import httpx
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.jobs.models import Job
from careeros.tasks.runtime import Worker
from tests.test_matching import _setup


async def _job_id(session: AsyncSession, title: str) -> str:
    return str((await session.execute(select(Job.id).where(Job.title == title))).scalars().first())


@respx.mock
async def test_company_insights_summarise_roles_and_link_people(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, worker: Worker,
    fixtures_dir: Path,
) -> None:  # fmt: skip
    respx.get("https://en.wikipedia.org/w/api.php").mock(
        return_value=httpx.Response(200, json={"query": {"search": [{"title": "Nimbus AI"}]}})
    )
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Nimbus_AI").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "standard",
                "description": "Indian artificial intelligence company",
                "extract": "Nimbus AI is an Indian company building machine learning tools.",
                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Nimbus_AI"}},
            },
        )
    )
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(session, "Machine Learning Engineer Intern")

    insights = (await client.get(f"/api/v1/jobs/{job_id}/company")).json()
    assert insights["name"] == "Nimbus AI"
    assert insights["summary"].startswith("Nimbus AI is an Indian company")
    assert insights["open_roles"] >= 2  # the intern role and the senior role
    assert insights["entry_level_roles"] >= 1
    assert {c["label"] for c in insights["by_country"]} == {"India"}
    assert any(s["label"] == "PyTorch" for s in insights["top_skills"])
    assert insights["your_matches"]
    labels = [link["label"] for link in insights["people_searches"]]
    assert labels[0].startswith("Alumni from")
    assert all(
        link["url"].startswith("https://www.linkedin.com/search/")
        for link in insights["people_searches"]
    )

    # Another user cannot look up a job that is not in their inbox.
    assert (await other_client.get(f"/api/v1/jobs/{job_id}/company")).status_code == 404
