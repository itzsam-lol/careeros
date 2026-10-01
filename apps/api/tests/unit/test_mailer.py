from __future__ import annotations

import email
import email.policy
from datetime import date
from typing import ClassVar

import pytest

from careeros.outreach.mailer import build_email, reply_snippet


def test_build_email_sets_headers_and_attaches_the_resume() -> None:
    message = build_email(
        sender="satyam@example.com",
        sender_name="Satyam",
        to="asha@nimbus.example",
        to_name="Asha Rao",
        subject="Referral request",
        body="Hi Asha,\n\nThanks!",
        attachment=("Satyam_Resume_Nimbus_AI.pdf", b"%PDF-1.7 fake"),
    )
    assert message["From"] == "Satyam <satyam@example.com>"
    assert message["To"] == "Asha Rao <asha@nimbus.example>"
    assert str(message["Message-ID"]).endswith("@example.com>")
    parts = list(message.iter_attachments())
    assert [p.get_filename() for p in parts] == ["Satyam_Resume_Nimbus_AI.pdf"]
    assert parts[0].get_content() == b"%PDF-1.7 fake"
    body = message.get_body(preferencelist=("plain",))
    assert body is not None
    assert "Hi Asha," in body.get_content()


def test_reply_snippet_keeps_only_the_new_text() -> None:
    raw = (
        b"From: Asha Rao <asha@nimbus.example>\r\n"
        b"Subject: Re: Referral request\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Happy to refer you! Send me the job link.\r\n\r\n"
        b"On Tue, 1 Oct 2026 at 10:00, Satyam <satyam@example.com> wrote:\r\n"
        b"> Hi Asha,\r\n> Would you be open to referring me?\r\n"
    )
    parsed = email.message_from_bytes(raw, policy=email.policy.default)
    assert reply_snippet(parsed) == "Happy to refer you! Send me the job link."  # type: ignore[arg-type]


class _FakeSMTP:
    instances: ClassVar[list[_FakeSMTP]] = []
    reject_login = False

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.calls: list[str] = [f"connect {host}:{port}"]
        _FakeSMTP.instances.append(self)

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self, context: object) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        if _FakeSMTP.reject_login:
            import smtplib

            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.calls.append(f"login {user}")

    def send_message(self, message: object) -> None:
        self.calls.append("send")

    def quit(self) -> None:
        self.calls.append("quit")


async def test_smtp_transport_uses_starttls_and_maps_login_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import smtplib

    from careeros.outreach import mailer

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.instances.clear()
    _FakeSMTP.reject_login = False
    transport = mailer.SmtpImapTransport()
    box = mailer.Mailbox(mailer.GMAIL, "satyam@example.com", "abcdefghijklmnop")
    message = build_email(
        sender=box.address, sender_name=None, to="a@b.co", to_name=None, subject="Hi", body="Hello"
    )
    await transport.send(box, message)
    assert _FakeSMTP.instances[-1].calls == [
        "connect smtp.gmail.com:587", "ehlo", "starttls", "ehlo", "login satyam@example.com", "send", "quit",
    ]  # fmt: skip

    _FakeSMTP.reject_login = True
    with pytest.raises(mailer.EmailLoginError):
        await transport.verify(box)


class _FakeIMAP:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.selected: tuple[str, bool] | None = None

    def login(self, user: str, password: str) -> None:
        pass

    def select(self, mailbox: str, readonly: bool = False) -> None:
        self.selected = (mailbox, readonly)

    def search(self, charset: object, *criteria: str) -> tuple[str, list[bytes]]:
        return ("OK", [b"7"]) if "In-Reply-To" in criteria else ("OK", [b""])

    def fetch(self, number: str, parts: str) -> tuple[str, list[object]]:
        assert number == "7"
        assert "PEEK" in parts  # never marks the reply as read
        return "OK", [(b"7 (BODY[] {123}", self.raw), b")"]

    def logout(self) -> None:
        pass


async def test_imap_transport_finds_replies_without_marking_them_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import imaplib

    from careeros.outreach import mailer

    raw = (
        b"From: Asha Rao <asha@nimbus.example>\r\n"
        b"Date: Wed, 2 Oct 2026 10:00:00 +0000\r\n"
        b"In-Reply-To: <abc@example.com>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Sure, happy to refer you.\r\n"
    )
    fake = _FakeIMAP(raw)
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda *args, **kwargs: fake)
    transport = mailer.SmtpImapTransport()
    box = mailer.Mailbox(mailer.GMAIL, "satyam@example.com", "abcdefghijklmnop")
    [reply] = await transport.find_replies(box, ["<abc@example.com>"], date(2026, 10, 1))
    assert reply.in_reply_to == "<abc@example.com>"
    assert reply.sender == "Asha Rao <asha@nimbus.example>"
    assert reply.snippet == "Sure, happy to refer you."
    assert fake.selected == ("INBOX", True)
