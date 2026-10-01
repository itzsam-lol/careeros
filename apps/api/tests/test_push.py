from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.container import Container
from careeros.notifications.models import NotificationType, PushDevice
from careeros.notifications.push import (
    FCM_SEND,
    METADATA_AUTH_URL,
    FCMSender,
    PushError,
    PushResult,
)
from careeros.notifications.service import notify
from careeros.tasks.models import AgentTask, TaskType
from careeros.tasks.runtime import Worker

PHONE = "fcm-phone-token-" + "a" * 40
OLD_PHONE = "fcm-phone-token-" + "b" * 40


class FakePush:
    enabled = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, dict[str, str]]] = []
        self.uninstalled: set[str] = set()

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> PushResult:
        if token in self.uninstalled:
            return PushResult.INVALID_TOKEN
        self.sent.append((token, title, body, data))
        return PushResult.SENT


@pytest.fixture
def push(container: Container) -> FakePush:
    fake = FakePush()
    container.push = fake
    return fake


async def _user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/me")).json()["id"])


async def _push_tasks(session: AsyncSession) -> list[AgentTask]:
    return list(
        (await session.execute(select(AgentTask).where(AgentTask.type == TaskType.SEND_PUSH)))
        .scalars()
        .all()
    )


async def test_phones_register_move_between_accounts_and_unregister(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    assert (await client.get("/api/v1/devices/status")).json() == {
        "push_enabled": False,
        "devices": 0,
    }
    first = await client.post("/api/v1/devices", json={"token": PHONE})
    assert first.status_code == 200, first.text
    assert first.json()["devices"] == 1
    again = await client.post("/api/v1/devices", json={"token": PHONE})
    assert again.json()["devices"] == 1  # re-registering the same phone is a no-op

    # The same phone signed in to another account now alerts that account only.
    moved = await other_client.post("/api/v1/devices", json={"token": PHONE})
    assert moved.json()["devices"] == 1
    assert (await client.get("/api/v1/devices/status")).json()["devices"] == 0

    # Nobody can unregister another account's phone.
    assert (
        await client.post("/api/v1/devices/unregister", json={"token": PHONE})
    ).status_code == 204
    assert (await other_client.get("/api/v1/devices/status")).json()["devices"] == 1
    assert (
        await other_client.post("/api/v1/devices/unregister", json={"token": PHONE})
    ).status_code == 204
    assert (await other_client.get("/api/v1/devices/status")).json()["devices"] == 0

    assert (await client.post("/api/v1/devices", json={"token": "short"})).status_code == 422


async def test_alerts_are_pushed_at_once_and_dead_phones_forgotten(
    client: AsyncClient, session: AsyncSession, worker: Worker, push: FakePush
) -> None:
    user_id = await _user_id(client)
    await notify(
        session,
        user_id=user_id,
        type=NotificationType.FOLLOW_UP_DUE,
        title="Follow up with Nimbus",
        dedupe_key="push-test:no-phone",
    )
    assert await _push_tasks(session) == []  # no phone registered: nothing to push

    for token in (PHONE, OLD_PHONE):
        assert (await client.post("/api/v1/devices", json={"token": token})).status_code == 200
    push.uninstalled = {OLD_PHONE}
    job_id = uuid.uuid4()
    await notify(
        session,
        user_id=user_id,
        type=NotificationType.HIGH_MATCH,
        title="92% match: Machine Learning Intern at Nimbus",
        body="Bengaluru · Internship",
        dedupe_key="push-test:match",
        job_id=job_id,
    )
    [task] = await _push_tasks(session)
    assert task.priority == 9

    await worker.drain()
    [(token, title, body, data)] = push.sent
    assert (token, title, body) == (
        PHONE,
        "92% match: Machine Learning Intern at Nimbus",
        "Bengaluru · Internship",
    )
    assert data["type"] == "HIGH_MATCH"
    assert data["jobId"] == str(job_id)
    assert all(isinstance(value, str) for value in data.values())
    tokens = (await session.execute(select(PushDevice.token))).scalars().all()
    assert list(tokens) == [PHONE]  # the uninstalled app's token is dropped

    # Read in the app before the push went out: no push.
    await notify(
        session,
        user_id=user_id,
        type=NotificationType.NEW_JOB,
        title="New role: Data Analyst Intern",
        dedupe_key="push-test:read",
    )
    await client.post("/api/v1/notifications/read", json={})
    await worker.drain()
    assert len(push.sent) == 1


@respx.mock
async def test_fcm_sender_uses_the_vm_identity_and_spots_dead_tokens() -> None:
    metadata = respx.get(METADATA_AUTH_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.vm", "expires_in": 3600})
    )
    send = respx.post(FCM_SEND.format(project="careeros-test")).mock(
        side_effect=[
            httpx.Response(200, json={"name": "projects/careeros-test/messages/1"}),
            httpx.Response(404, json={"error": {"status": "NOT_FOUND"}}),
            httpx.Response(
                400, json={"error": {"message": "The registration token is not a valid FCM token"}}
            ),
            httpx.Response(503, text="unavailable"),
        ]
    )
    async with httpx.AsyncClient() as http:
        sender = FCMSender("careeros-test", http)
        sent = await sender.send(PHONE, title="Hi", body="There", data={"jobId": ""})
        assert sent == PushResult.SENT
        assert await sender.send(PHONE, title="Hi", body="", data={}) == PushResult.INVALID_TOKEN
        assert await sender.send(PHONE, title="Hi", body="", data={}) == PushResult.INVALID_TOKEN
        with pytest.raises(PushError):
            await sender.send(PHONE, title="Hi", body="", data={})

    assert metadata.call_count == 1  # the access token is cached
    assert metadata.calls[0].request.headers["Metadata-Flavor"] == "Google"
    first = send.calls[0].request
    assert first.headers["Authorization"] == "Bearer ya29.vm"
    message = json.loads(first.content)["message"]
    assert message["token"] == PHONE
    assert message["android"]["priority"] == "HIGH"
    assert message["android"]["notification"]["channel_id"] == "job-alerts"
