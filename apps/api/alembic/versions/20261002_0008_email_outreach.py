"""email outreach: connected mailbox and approved outreach messages

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-02 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("smtp_host", sa.String(length=200), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("imap_host", sa.String(length=200), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("CONNECTED", "ERROR", name="emailaccountstatus", native_enum=False, length=48),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replies_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_email_accounts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_accounts")),
        sa.UniqueConstraint("user_id", name=op.f("uq_email_accounts_user_id")),
    )
    op.create_table(
        "outreach_messages",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("to_name", sa.String(length=200), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attach_resume", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "SENDING", "SENT", "FAILED", name="outreachstatus", native_enum=False, length=48),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("message_id", sa.String(length=300), nullable=True),
        sa.Column("attachment_name", sa.String(length=200), nullable=True),
        sa.Column("reply_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_from", sa.String(length=320), nullable=True),
        sa.Column("reply_snippet", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_outreach_messages_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_outreach_messages_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_messages")),
    )
    op.create_index(op.f("ix_outreach_messages_message_id"), "outreach_messages", ["message_id"])
    op.create_index("ix_outreach_messages_user_created", "outreach_messages", ["user_id", "created_at"])
    op.create_index("ix_outreach_messages_user_job", "outreach_messages", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_user_job", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_user_created", table_name="outreach_messages")
    op.drop_index(op.f("ix_outreach_messages_message_id"), table_name="outreach_messages")
    op.drop_table("outreach_messages")
    op.drop_table("email_accounts")
