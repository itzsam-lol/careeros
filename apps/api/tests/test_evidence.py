from __future__ import annotations

import json
from pathlib import Path

from httpx import AsyncClient


async def _import_demo(client: AsyncClient, fixtures_dir: Path) -> None:
    payload = json.loads((fixtures_dir / "profiles" / "demo_profile.json").read_text("utf-8"))
    assert (await client.post("/api/v1/profile/import", json=payload)).status_code == 200


async def _verify_everything(client: AsyncClient) -> None:
    profile = (await client.get("/api/v1/profile")).json()
    for section in (
        "projects",
        "experience",
        "research",
        "publications",
        "education",
        "skills",
        "achievements",
    ):
        ids = [item["id"] for item in profile[section]]
        if ids:
            await client.post(
                "/api/v1/profile/verification",
                json={"section": section, "ids": ids, "status": "VERIFIED"},
            )


async def test_search_ranks_relevant_evidence_first(
    client: AsyncClient, fixtures_dir: Path
) -> None:
    await _import_demo(client, fixtures_dir)
    await _verify_everything(client)

    hits = (
        await client.post(
            "/api/v1/evidence/search",
            json={"query": "retrieval augmented generation chatbot with pgvector and LangChain"},
        )
    ).json()
    assert hits[0]["title"] == "Project: Campus RAG Assistant"
    assert 0 <= hits[-1]["relevance"] <= hits[0]["relevance"] <= 1

    vision = (
        await client.post(
            "/api/v1/evidence/search",
            json={
                "query": "fine-tuning vision transformers with LoRA for medical imaging research"
            },
        )
    ).json()
    assert vision[0]["source_type"] in {"research", "publication"}


async def test_unverified_evidence_is_excluded_by_default(
    client: AsyncClient, fixtures_dir: Path
) -> None:
    await _import_demo(client, fixtures_dir)  # everything imported is UNVERIFIED
    default = await client.post("/api/v1/evidence/search", json={"query": "PyTorch"})
    assert default.json() == []
    widened = await client.post(
        "/api/v1/evidence/search", json={"query": "PyTorch", "include_unverified": True}
    )
    assert len(widened.json()) > 0
    assert {h["verification_status"] for h in widened.json()} == {"UNVERIFIED"}


async def test_reindex_only_embeds_changed_documents(
    client: AsyncClient, fixtures_dir: Path
) -> None:
    await _import_demo(client, fixtures_dir)
    first = (await client.post("/api/v1/evidence/reindex")).json()
    assert first["embedded"] > 5
    assert first["embedding_model"] == "local-hashing-v1"

    second = (await client.post("/api/v1/evidence/reindex")).json()
    assert second["embedded"] == 0
    assert second["unchanged"] == first["embedded"]

    project = (await client.get("/api/v1/profile/projects")).json()[0]
    update = {
        k: project[k] for k in ("name", "description", "technologies", "highlights", "metrics")
    }
    update["highlights"] = [*update["highlights"], "Added multilingual support"]
    await client.put(f"/api/v1/profile/projects/{project['id']}", json=update)
    third = (await client.post("/api/v1/evidence/reindex")).json()
    assert third["embedded"] == 1
