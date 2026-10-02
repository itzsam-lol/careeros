"""prepared applications: when a dream-company role's kit was tailored and announced

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-02 13:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_jobs", sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_jobs", sa.Column("ready_alerted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_jobs", "ready_alerted_at")
    op.drop_column("user_jobs", "prepared_at")
