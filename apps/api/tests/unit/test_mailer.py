from __future__ import annotations

import email
import email.policy

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
