"""Push notifications to the user's phone through Firebase Cloud Messaging (HTTP v1 API).

Every alert CareerOS creates (`NOTIFICATION_CREATED`) is pushed right away to the user's
registered phones, so it arrives even when the app is closed. Android throttles apps that poll in
the background; FCM is the delivery path it keeps open.

Authentication uses the VM's own service account through the GCE metadata server, so no key
file exists anywhere. Off GCE, or without FCM_PROJECT_ID, pushing is disabled and the app's
background checks remain the fallback.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

import httpx
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.errors import CareerOSError
from careeros.core.logging import get_logger
from careeros.events.models import DomainEvent, EventType
from careeros.events.service import subscribe
from careeros.notifications.models import Notification, PushDevice
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue
from careeros.tasks.runtime import TaskContext, task_handler

if TYPE_CHECKING:
    from careeros.config import Settings

log = get_logger(__name__)

METADATA_AUTH_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
FCM_SEND = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
CHANNEL_ID = "job-alerts"


class PushResult(StrEnum):
    SENT = "SENT"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105 - app uninstalled or token rotated: forget the device
    DISABLED = "DISABLED"


class PushError(CareerOSError):
    """Push delivery failed (retried by the task runner)."""

    code = "push_error"
    http_status = 502
    retryable = True


class PushSender(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def send(
        self, token: str, *, title: str, body: str, data: dict[str, str]
    ) -> PushResult: ...


class DisabledPush:
    enabled = False

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> PushResult:
        return PushResult.DISABLED


class FCMSender:
    enabled = True

    def __init__(self, project_id: str, http: httpx.AsyncClient) -> None:
        self.project_id = project_id
        self.http = http
        self._token: str | None = None
        self._expires = 0.0

    async def _access_token(self) -> str:
        if self._token and time.monotonic() < self._expires:
            return self._token
        try:
            response = await self.http.get(
                METADATA_AUTH_URL, headers={"Metadata-Flavor": "Google"}, timeout=10
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PushError(f"Could not get credentials for FCM: {exc}") from exc
        body = response.json()
        self._token = str(body["access_token"])
        self._expires = time.monotonic() + int(body.get("expires_in", 3600)) - 120
        return self._token

    async def send(self, token: str, *, title: str, body: str, data: dict[str, str]) -> PushResult:
        message: dict[str, Any] = {
            "token": token,
            "notification": {"title": title[:200], "body": body[:500]},
            "data": data,
            "android": {
                "priority": "HIGH",
                "notification": {"channel_id": CHANNEL_ID, "color": "#0A84FF"},
            },
        }
        try:
            response = await self.http.post(
                FCM_SEND.format(project=self.project_id),
                json={"message": message},
                headers={"Authorization": f"Bearer {await self._access_token()}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise PushError(f"FCM did not respond: {exc}") from exc
        if response.status_code == 200:
            return PushResult.SENT
        detail = response.text[:300]
        if (
            response.status_code == 404
            or "UNREGISTERED" in detail
            or (response.status_code == 400 and "registration token" in detail.lower())
        ):
            return PushResult.INVALID_TOKEN
        if response.status_code in (401, 403):
            self._token = None  # credentials or permissions: log loudly, retry later
            log.error("fcm_unauthorized", status=response.status_code, detail=detail)
        raise PushError(f"FCM rejected the push ({response.status_code}): {detail}")


def build_push_sender(settings: Settings, http: httpx.AsyncClient) -> PushSender:
    if settings.fcm_project_id:
        return FCMSender(settings.fcm_project_id, http)
    return DisabledPush()


@subscribe(EventType.NOTIFICATION_CREATED)
async def _queue_push(session: AsyncSession, event: DomainEvent) -> None:
    notification_id = (event.payload or {}).get("notification_id")
    if event.user_id is None or not notification_id:
        return
    registered = (
        await session.execute(select(exists().where(PushDevice.user_id == event.user_id)))
    ).scalar_one()
    if not registered:
        return
    await enqueue(
        session,
        TaskType.SEND_PUSH,
        {"notification_id": str(notification_id)},
        user_id=event.user_id,
        idempotency_key=f"push:{notification_id}",
        priority=9,  # ahead of discovery and matching: alerts should arrive at once
    )


def push_data(notification: Notification) -> dict[str, str]:
    """FCM data values must be strings; the app routes taps with these."""
    extra = notification.data or {}
    return {
        "notificationId": str(notification.id),
        "jobId": str(notification.job_id) if notification.job_id else "",
        "documentId": str(extra.get("document_id") or ""),
        "outreachId": str(extra.get("outreach_id") or notification.outreach_id or ""),
        "type": notification.type.value,
    }


@task_handler(TaskType.SEND_PUSH)
async def handle_send_push(ctx: TaskContext) -> dict[str, Any]:
    sender: PushSender = ctx.container.push
    if not sender.enabled:
        return {"skipped": "push not configured"}
    notification = await ctx.session.get(Notification, uuid.UUID(ctx.payload["notification_id"]))
    if notification is None or notification.read:
        return {"skipped": "already read"}
    devices = list(
        (
            await ctx.session.execute(
                select(PushDevice).where(PushDevice.user_id == notification.user_id)
            )
        ).scalars()
    )
    sent = removed = 0
    for device in devices:
        result = await sender.send(
            device.token,
            title=notification.title,
            body=notification.body,
            data=push_data(notification),
        )
        if result == PushResult.SENT:
            sent += 1
        elif result == PushResult.INVALID_TOKEN:
            await ctx.session.execute(delete(PushDevice).where(PushDevice.id == device.id))
            removed += 1
    return {"sent": sent, "removed": removed}
