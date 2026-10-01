"""Reply checks: every few minutes, look for answers to sent outreach emails."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.outreach.models import (
    EmailAccount,
    EmailAccountStatus,
    OutreachMessage,
    OutreachStatus,
)
from careeros.outreach.service import REPLY_WINDOW, check_replies
from careeros.scheduled_jobs import periodic
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue
from careeros.tasks.runtime import TaskContext, task_handler

if TYPE_CHECKING:
    from careeros.container import Container

REPLY_CHECK_INTERVAL = timedelta(minutes=10)


@task_handler(TaskType.CHECK_OUTREACH)
async def handle_check_outreach(ctx: TaskContext) -> dict[str, Any]:
    account = await ctx.session.get(EmailAccount, ctx.uuid("account_id"))
    if account is None or account.status != EmailAccountStatus.CONNECTED:
        return {"skipped": "no connected mailbox"}
    found = await check_replies(
        ctx.session, account=account, transport=ctx.container.mail, cipher=ctx.container.cipher
    )
    return {"replies": found}


@periodic("outreach_replies")
async def enqueue_reply_checks(session: AsyncSession, container: Container) -> int:
    """Queue a check for each connected mailbox with sent emails still awaiting a reply."""
    now = utcnow()
    awaiting = exists().where(
        OutreachMessage.user_id == EmailAccount.user_id,
        OutreachMessage.status == OutreachStatus.SENT,
        OutreachMessage.reply_received_at.is_(None),
        OutreachMessage.sent_at >= now - REPLY_WINDOW,
    )
    accounts = (
        await session.execute(
            select(EmailAccount.id, EmailAccount.user_id).where(
                EmailAccount.status == EmailAccountStatus.CONNECTED,
                or_(
                    EmailAccount.replies_checked_at.is_(None),
                    EmailAccount.replies_checked_at <= now - REPLY_CHECK_INTERVAL,
                ),
                awaiting,
            )
        )
    ).all()
    slot = int(now.timestamp() // REPLY_CHECK_INTERVAL.total_seconds())
    for account_id, user_id in accounts:
        await enqueue(
            session,
            TaskType.CHECK_OUTREACH,
            {"account_id": str(account_id)},
            user_id=user_id,
            idempotency_key=f"replies:{account_id}:{slot}",
            priority=2,
        )
    return len(accounts)
