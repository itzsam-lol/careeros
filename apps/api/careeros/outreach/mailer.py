"""Sending email and finding replies through the user's own Gmail.

Personal Gmail accounts cannot use the OAuth `gmail.send` scope without Google's app review
(unreviewed apps get sign-ins that expire every week), so CareerOS uses the route Google offers
mail apps: an app password over SMTP (sending) and IMAP (finding replies). The password is
encrypted at rest and only ever sent to Google's mail servers.
"""

from __future__ import annotations

import asyncio
import contextlib
import email
import email.policy
import html
import imaplib
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parsedate_to_datetime
from typing import Protocol

from careeros.config import Settings
from careeros.core.errors import ConfigurationError, EmailProviderError
from careeros.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MailServer:
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int


GMAIL = MailServer("smtp.gmail.com", 587, "imap.gmail.com", 993)


@dataclass(frozen=True, slots=True)
class Mailbox:
    server: MailServer
    address: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Reply:
    in_reply_to: str  # the Message-ID of our email it answers
    sender: str
    received_at: datetime | None
    snippet: str


class EmailLoginError(EmailProviderError):
    """The mail server rejected the email address or app password."""

    code = "email_login_failed"
    http_status = 422
    retryable = False


class MailTransport(Protocol):
    async def verify(self, mailbox: Mailbox) -> None: ...

    async def send(self, mailbox: Mailbox, message: EmailMessage) -> None: ...

    async def find_replies(
        self, mailbox: Mailbox, message_ids: list[str], since: date
    ) -> list[Reply]: ...


def build_email(
    *,
    sender: str,
    sender_name: str | None,
    to: str,
    to_name: str | None,
    subject: str,
    body: str,
    attachment: tuple[str, bytes] | None = None,
) -> EmailMessage:
    message = EmailMessage(policy=email.policy.SMTP)
    message["From"] = formataddr((sender_name or "", sender))
    message["To"] = formataddr((to_name or "", to))
    message["Subject"] = subject
    message["Date"] = formatdate(usegmt=True)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
    message.set_content(body)
    if attachment:
        name, data = attachment
        message.add_attachment(data, maintype="application", subtype="pdf", filename=name)
    return message


_QUOTE_START = re.compile(r"^(on .+ wrote:|-+ ?original message ?-+|from: .+)$", re.IGNORECASE)


def reply_snippet(message: email.message.EmailMessage, limit: int = 400) -> str:
    """The new text of a reply: first plain-text part, without the quoted original."""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = str(part.get_content())
    if part.get_content_type() == "text/html":
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _QUOTE_START.match(stripped):
            break
        if not stripped.startswith(">"):
            kept.append(stripped)
    return " ".join(" ".join(kept).split())[:limit]


class SmtpImapTransport:
    """Gmail over SMTP (STARTTLS) and IMAP (TLS); blocking libraries run in worker threads."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def _smtp(self, mailbox: Mailbox) -> smtplib.SMTP:
        server = mailbox.server
        try:
            smtp = smtplib.SMTP(server.smtp_host, server.smtp_port, timeout=self.timeout)
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(mailbox.address, mailbox.password)
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailLoginError(
                "Gmail rejected the address or app password. Check both, and that 2-Step "
                "Verification is on for the account."
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailProviderError(f"Could not reach {server.smtp_host}: {exc}") from exc
        return smtp

    def _verify(self, mailbox: Mailbox) -> None:
        self._smtp(mailbox).quit()

    def _send(self, mailbox: Mailbox, message: EmailMessage) -> None:
        smtp = self._smtp(mailbox)
        try:
            smtp.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailProviderError(
                "Gmail refused the recipient address", retryable=False
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailProviderError(f"Gmail did not accept the email: {exc}") from exc
        finally:
            with contextlib.suppress(smtplib.SMTPException, OSError):
                smtp.quit()

    def _find_replies(self, mailbox: Mailbox, message_ids: list[str], since: date) -> list[Reply]:
        server = mailbox.server
        try:
            imap = imaplib.IMAP4_SSL(
                server.imap_host,
                server.imap_port,
                ssl_context=ssl.create_default_context(),
                timeout=self.timeout,
            )
        except OSError as exc:
            raise EmailProviderError(f"Could not reach {server.imap_host}: {exc}") from exc
        try:
            try:
                imap.login(mailbox.address, mailbox.password)
            except imaplib.IMAP4.error as exc:
                raise EmailLoginError(
                    "Gmail rejected the app password when checking replies"
                ) from exc
            imap.select("INBOX", readonly=True)
            replies: list[Reply] = []
            for message_id in message_ids:
                found = self._search(imap, message_id, since)
                if found is None:
                    continue
                status, data = imap.fetch(found, "(BODY.PEEK[])")
                raw = next((item[1] for item in data or [] if isinstance(item, tuple)), None)
                if status != "OK" or not isinstance(raw, bytes):
                    continue
                parsed = email.message_from_bytes(raw, policy=email.policy.default)
                received = None
                if parsed["Date"]:
                    try:
                        received = parsedate_to_datetime(str(parsed["Date"]))
                    except (TypeError, ValueError):
                        received = None
                replies.append(
                    Reply(
                        in_reply_to=message_id,
                        sender=str(parsed["From"] or ""),
                        received_at=received,
                        snippet=reply_snippet(parsed),
                    )
                )
            return replies
        except imaplib.IMAP4.error as exc:
            raise EmailProviderError(f"Checking replies failed: {exc}") from exc
        finally:
            with contextlib.suppress(imaplib.IMAP4.error, OSError):
                imap.logout()

    @staticmethod
    def _search(imap: imaplib.IMAP4, message_id: str, since: date) -> str | None:
        quoted = '"' + message_id.replace("\\", "").replace('"', "") + '"'
        for header in ("In-Reply-To", "References"):
            status, data = imap.search(
                None, "SINCE", since.strftime("%d-%b-%Y"), "HEADER", header, quoted
            )
            numbers: list[bytes] = data[0].split() if status == "OK" and data and data[0] else []
            if numbers:
                return numbers[-1].decode()  # the latest reply
        return None

    async def verify(self, mailbox: Mailbox) -> None:
        await asyncio.to_thread(self._verify, mailbox)

    async def send(self, mailbox: Mailbox, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send, mailbox, message)

    async def find_replies(
        self, mailbox: Mailbox, message_ids: list[str], since: date
    ) -> list[Reply]:
        if not message_ids:
            return []
        return await asyncio.to_thread(self._find_replies, mailbox, message_ids, since)


class LoggingTransport:
    """Development only: accepts any password and logs emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def verify(self, mailbox: Mailbox) -> None:
        log.info("email_verify_skipped", address=mailbox.address)

    async def send(self, mailbox: Mailbox, message: EmailMessage) -> None:
        self.sent.append(message)
        log.info(
            "email_not_sent_development", to=str(message["To"]), subject=str(message["Subject"])
        )

    async def find_replies(
        self, mailbox: Mailbox, message_ids: list[str], since: date
    ) -> list[Reply]:
        return []


class DisabledTransport:
    """A deployed server with EMAIL_PROVIDER=mock: fail loudly rather than pretend to send."""

    async def verify(self, mailbox: Mailbox) -> None:
        raise ConfigurationError("Email is turned off on this server (EMAIL_PROVIDER=mock)")

    async def send(self, mailbox: Mailbox, message: EmailMessage) -> None:
        raise ConfigurationError("Email is turned off on this server (EMAIL_PROVIDER=mock)")

    async def find_replies(
        self, mailbox: Mailbox, message_ids: list[str], since: date
    ) -> list[Reply]:
        return []


def build_mail_transport(settings: Settings) -> MailTransport:
    if settings.email_provider == "gmail":
        return SmtpImapTransport()
    return DisabledTransport() if settings.is_deployed else LoggingTransport()
