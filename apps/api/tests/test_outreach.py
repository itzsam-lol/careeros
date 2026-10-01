from __future__ import annotations

from datetime import UTC, date, datetime
from email.message import EmailMessage
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.audit.models import AuditAction, AuditLog
from careeros.container import Container
from careeros.outreach.mailer import EmailLoginError, Mailbox, Reply
from careeros.outreach.models import EmailAccount, OutreachMessage
from careeros.outreach.tasks import enqueue_reply_checks
from careeros.tasks.models import AgentTask, TaskType
from careeros.tasks.runtime import Worker
from tests.test_matching import _setup

APP_PASSWORD = "abcdefghijklmnop"


class FakeMail:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.replies: list[Reply] = []
        self.send_error: Exception | None = None

    async def verify(self, mailbox: Mailbox) -> None:
        if mailbox.password != APP_PASSWORD:
            raise EmailLoginError()

    async def send(self, mailbox: Mailbox, message: EmailMessage) -> None:
        if self.send_error:
            raise self.send_error
        self.sent.append(message)

    async def find_replies(
        self, mailbox: Mailbox, message_ids: list[str], since: date
    ) -> list[Reply]:
        return [r for r in self.replies if r.in_reply_to in message_ids]


@pytest.fixture
def mail(container: Container) -> FakeMail:
    fake = FakeMail()
    container.mail = fake
    return fake


async def _connect(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/email/account",
        json={
            "address": "satyam@example.com",
            "app_password": "abcd efgh ijkl mnop",
            "display_name": "Satyam",
        },
    )
    assert response.status_code == 200, response.text


async def _job_id(client: AsyncClient, title: str) -> str:
    jobs = (await client.get("/api/v1/jobs", params={"view": "ALL", "limit": 50})).json()["items"]
    return next(j["job_id"] for j in jobs if j["title"] == title)


async def _draft(client: AsyncClient, job_id: str | None, **extra: object) -> dict[str, object]:
    payload = {
        "job_id": job_id,
        "kind": "referral_request",
        "to_address": "asha@nimbus.example",
        "to_name": "Asha Rao",
        "subject": "Referral for the Machine Learning Engineer Intern role",
        "body": "Hi Asha,\n\nWould you be open to referring me?\n\nThanks,\nSatyam",
        **extra,
    }
    response = await client.post("/api/v1/email/messages", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_connect_checks_the_app_password_and_stores_it_encrypted(
    client: AsyncClient, session: AsyncSession, mail: FakeMail
) -> None:
    rejected = await client.put(
        "/api/v1/email/account",
        json={"address": "satyam@example.com", "app_password": "wrongpassword1"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "email_login_failed"
    assert not (await client.get("/api/v1/email/account")).json()["connected"]

    await _connect(client)
    account = (await client.get("/api/v1/email/account")).json()
    assert account["connected"] is True
    assert account["address"] == "satyam@example.com"
    assert APP_PASSWORD not in str(account)
    stored = (await session.execute(select(EmailAccount))).scalar_one()
    assert APP_PASSWORD not in stored.secret  # encrypted at rest

    assert (await client.delete("/api/v1/email/account")).status_code == 204
    assert (await session.execute(select(EmailAccount))).scalar_one_or_none() is None


async def test_send_needs_explicit_approval_then_tracks_the_reply(
    client: AsyncClient,
    other_client: AsyncClient,
    session: AsyncSession,
    worker: Worker,
    container: Container,
    mail: FakeMail,
    fixtures_dir: Path,
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(client, "Machine Learning Engineer Intern")
    draft = await _draft(client, job_id)
    assert draft["status"] == "DRAFT"

    # Not connected yet, and never without the explicit confirmation flag.
    assert (
        await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True})
    ).status_code == 409
    await _connect(client)
    assert (
        await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={})
    ).status_code == 422
    assert mail.sent == []

    # Another user can't see or send it.
    assert (await other_client.get(f"/api/v1/email/messages/{draft['id']}")).status_code == 404

    sent = await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True})
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "SENT"
    assert body["job_title"] == "Machine Learning Engineer Intern"
    [email] = mail.sent
    assert email["To"] == "Asha Rao <asha@nimbus.example>"
    assert email["From"] == "Satyam <satyam@example.com>"
    assert email["Subject"] == "Referral for the Machine Learning Engineer Intern role"
    assert "Would you be open to referring me?" in email.get_content()

    # A sent email can't be edited or sent again.
    assert (
        await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True})
    ).status_code == 409
    assert (
        await client.patch(f"/api/v1/email/messages/{draft['id']}", json={"subject": "x"})
    ).status_code == 409

    actions = set((await session.execute(select(AuditLog.action))).scalars())
    assert {
        AuditAction.EMAIL_DRAFT_CREATED,
        AuditAction.EMAIL_APPROVED,
        AuditAction.EMAIL_SENT,
    } <= actions

    # The periodic check queues a reply check; the worker finds the reply and alerts the user.
    message_id = (await session.execute(select(OutreachMessage.message_id))).scalar_one()
    assert message_id
    mail.replies = [
        Reply(
            message_id, "Asha Rao <asha@nimbus.example>", datetime.now(UTC), "Happy to refer you!"
        )
    ]
    assert await enqueue_reply_checks(session, container) == 1
    await session.commit()
    await worker.drain()
    checks = (
        (await session.execute(select(AgentTask).where(AgentTask.type == TaskType.CHECK_OUTREACH)))
        .scalars()
        .all()
    )
    assert [t.result for t in checks] == [{"replies": 1}]
    replied = (await client.get(f"/api/v1/email/messages/{draft['id']}")).json()
    assert replied["reply_snippet"] == "Happy to refer you!"
    alerts = [
        n
        for n in (await client.get("/api/v1/notifications")).json()
        if n["type"] == "REPLY_RECEIVED"
    ]
    assert len(alerts) == 1
    assert alerts[0]["job_id"] == job_id
    assert alerts[0]["title"].startswith("Asha Rao replied")
    # Found once: no second alert, no more checks while nothing is awaiting a reply.
    assert (await client.post("/api/v1/email/check-replies")).json() == {"replies": 0}
    assert await enqueue_reply_checks(session, container) == 0


async def test_send_guards_daily_limit_duplicates_and_bad_input(
    client: AsyncClient,
    session: AsyncSession,
    worker: Worker,
    container: Container,
    mail: FakeMail,
    fixtures_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(client, "Machine Learning Engineer Intern")
    await _connect(client)

    bad = await client.post(
        "/api/v1/email/messages",
        json={"to_address": "not-an-address", "subject": "Hi", "body": "Hello"},
    )
    assert bad.status_code == 422
    injected = await _draft(client, None, subject="Hello\r\nBcc: everyone@example.com")
    assert "\n" not in str(injected["subject"])  # header injection is flattened

    # A draft can start without a recipient, but can't be sent without one.
    blank = await _draft(client, None, to_address="", subject="No recipient yet")
    response = await client.post(
        f"/api/v1/email/messages/{blank['id']}/send", json={"confirm": True}
    )
    assert response.status_code == 422
    assert "recipient" in response.json()["error"]["message"]

    # Attaching a résumé needs a tailored résumé for the job.
    attach = await _draft(client, job_id, attach_resume=True, subject="With résumé")
    response = await client.post(
        f"/api/v1/email/messages/{attach['id']}/send", json={"confirm": True}
    )
    assert response.status_code == 422
    assert "tailored résumé" in response.json()["error"]["message"]

    first = await _draft(client, job_id)
    assert (
        await client.post(f"/api/v1/email/messages/{first['id']}/send", json={"confirm": True})
    ).status_code == 200
    duplicate = await _draft(client, job_id)
    response = await client.post(
        f"/api/v1/email/messages/{duplicate['id']}/send", json={"confirm": True}
    )
    assert response.status_code == 409  # the same email to the same person within 24 hours

    monkeypatch.setattr(container.settings, "outreach_daily_limit", 1)
    other = await _draft(client, job_id, subject="Another note")
    response = await client.post(
        f"/api/v1/email/messages/{other['id']}/send", json={"confirm": True}
    )
    assert response.status_code == 429
    assert len(mail.sent) == 1


async def test_a_revoked_app_password_marks_the_mailbox_for_reconnection(
    client: AsyncClient, session: AsyncSession, mail: FakeMail
) -> None:
    await _connect(client)
    draft = await _draft(client, None)
    mail.send_error = EmailLoginError()
    response = await client.post(
        f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True}
    )
    assert response.status_code == 422
    failed = (await client.get(f"/api/v1/email/messages/{draft['id']}")).json()
    assert failed["status"] == "FAILED"
    account = (await client.get("/api/v1/email/account")).json()
    assert account["connected"] is False
    assert account["status"] == "ERROR"
    mail.send_error = None
    retry = await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True})
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "email_not_connected"
    await _connect(client)  # reconnecting fixes it
    retry = await client.post(f"/api/v1/email/messages/{draft['id']}/send", json={"confirm": True})
    assert retry.status_code == 200
