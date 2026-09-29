from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from httpx import AsyncClient

PROJECT = {
    "name": "Campus RAG Assistant",
    "description": "Retrieval-augmented chatbot over university handbooks.",
    "technologies": ["Python", "LangChain", "pgvector"],
    "highlights": ["Indexed 2,000+ handbook pages", "Added source citations to every answer"],
    "metrics": ["Answered 1,200+ queries in a pilot"],
}


async def _facts_for(client: AsyncClient, source_id: str) -> list[dict[str, Any]]:
    facts = (await client.get("/api/v1/profile/facts")).json()
    return [f for f in facts if f["source_id"] == source_id]


async def test_empty_profile_is_created_with_checklist(client: AsyncClient) -> None:
    response = await client.get("/api/v1/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["basics"]["contact_email"] == "dev@careeros.local"
    assert body["stats"]["completeness"] < 30
    assert {item["key"] for item in body["stats"]["checklist"]} >= {"education", "skills"}


async def test_basics_reject_non_http_urls(client: AsyncClient) -> None:
    bad = await client.put("/api/v1/profile/basics", json={"github_url": "javascript:alert(1)"})
    assert bad.status_code == 422
    ok = await client.put(
        "/api/v1/profile/basics",
        json={"summary": "ML engineer.", "github_url": "https://github.com/alex"},
    )
    assert ok.status_code == 200
    assert ok.json()["basics_status"] == "VERIFIED"


async def test_manual_items_are_verified_and_derive_facts(client: AsyncClient) -> None:
    created = await client.post("/api/v1/profile/projects", json=PROJECT)
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["verification_status"] == "VERIFIED"
    assert project["source"] == "MANUAL"

    facts = await _facts_for(client, project["id"])
    texts = {f["fact"] for f in facts}
    assert "Indexed 2,000+ handbook pages" in texts
    assert "Answered 1,200+ queries in a pilot" in texts
    assert all(f["origin"] == "DERIVED" and f["source_entity"] == "project" for f in facts)
    assert all(f["verification_status"] == "VERIFIED" for f in facts)


async def test_fact_sync_keeps_ids_and_respects_rejections(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/profile/projects", json=PROJECT)).json()
    before = {f["fact"]: f for f in await _facts_for(client, project["id"])}
    kept = before["Indexed 2,000+ handbook pages"]
    rejected = before["Added source citations to every answer"]

    verdict = await client.post(
        f"/api/v1/profile/facts/{rejected['id']}/verification", json={"status": "REJECTED"}
    )
    assert verdict.status_code == 200

    update = {**PROJECT, "highlights": [*PROJECT["highlights"], "Deployed on Cloud Run"]}
    update["metrics"] = []
    assert (
        await client.put(f"/api/v1/profile/projects/{project['id']}", json=update)
    ).status_code == 200

    after = {f["fact"]: f for f in await _facts_for(client, project["id"])}
    assert after["Indexed 2,000+ handbook pages"]["id"] == kept["id"]  # stable citation id
    assert after["Added source citations to every answer"]["verification_status"] == "REJECTED"
    assert "Deployed on Cloud Run" in after
    assert "Answered 1,200+ queries in a pilot" not in after


async def test_derived_facts_cannot_be_edited_or_deleted(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/profile/projects", json=PROJECT)).json()
    fact = (await _facts_for(client, project["id"]))[0]
    edit = await client.put(f"/api/v1/profile/facts/{fact['id']}", json={"fact": "I invented RAG"})
    assert edit.status_code == 422
    delete = await client.delete(f"/api/v1/profile/facts/{fact['id']}")
    assert delete.status_code == 422


async def test_deleting_an_item_removes_its_facts(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/profile/projects", json=PROJECT)).json()
    assert (await client.delete(f"/api/v1/profile/projects/{project['id']}")).status_code == 204
    assert await _facts_for(client, project["id"]) == []


async def test_skills_are_normalised_and_deduplicated(client: AsyncClient) -> None:
    created = await client.post("/api/v1/profile/skills", json={"name": "k8s"})
    assert created.status_code == 201
    skill = created.json()
    assert skill["name"] == "Kubernetes"
    assert skill["category"] == "DEVOPS"
    duplicate = await client.post("/api/v1/profile/skills", json={"name": "Kubernetes"})
    assert duplicate.status_code == 409


async def test_user_facts_and_answers(client: AsyncClient) -> None:
    fact = await client.post(
        "/api/v1/profile/facts", json={"fact": "Mentored 5 juniors in the robotics club"}
    )
    assert fact.status_code == 201
    assert fact.json()["origin"] == "USER"
    answer = await client.post(
        "/api/v1/profile/answers",
        json={
            "question": "Are you authorised to work in India?",
            "answer": "Yes",
            "category": "WORK_AUTHORIZATION",
        },
    )
    assert answer.status_code == 201


async def test_version_increments_on_changes(client: AsyncClient) -> None:
    v1 = (await client.get("/api/v1/profile")).json()["basics"]["version"]
    await client.post("/api/v1/profile/skills", json={"name": "Python"})
    v2 = (await client.get("/api/v1/profile")).json()["basics"]["version"]
    assert v2 > v1


async def test_other_users_cannot_touch_my_items(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    project = (await client.post("/api/v1/profile/projects", json=PROJECT)).json()
    url = f"/api/v1/profile/projects/{project['id']}"
    assert (await other_client.put(url, json=PROJECT)).status_code == 404
    assert (await other_client.delete(url)).status_code == 404
    verify = await other_client.post(f"{url}/verification", json={"status": "REJECTED"})
    assert verify.status_code == 404
    assert (await other_client.get("/api/v1/profile/projects")).json() == []


async def test_import_marks_items_unverified_until_reviewed(
    client: AsyncClient, fixtures_dir: Path
) -> None:
    payload = json.loads((fixtures_dir / "profiles" / "demo_profile.json").read_text("utf-8"))
    result = await client.post("/api/v1/profile/import", json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["created"]["projects"] == 3
    assert body["created"]["skills"] == len(payload["skills"])
    assert body["unverified"] > 0

    profile = (await client.get("/api/v1/profile")).json()
    assert all(p["verification_status"] == "VERIFIED" for p in profile["projects"]) is False
    assert profile["basics"]["basics_status"] == "UNVERIFIED"
    assert profile["stats"]["unverified_items"] == body["unverified"]

    ids = [p["id"] for p in profile["projects"]]
    bulk = await client.post(
        "/api/v1/profile/verification",
        json={"section": "projects", "ids": ids, "status": "VERIFIED"},
    )
    assert bulk.json() == {"updated": 3}
    derived = [
        f for f in (await client.get("/api/v1/profile/facts")).json() if f["source_id"] in ids
    ]
    assert derived
    assert all(f["verification_status"] == "VERIFIED" for f in derived)
