"""entry-level-only and hide-unsuitable job feed preferences

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "career_preferences",
        sa.Column("entry_level_only", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "career_preferences",
        sa.Column("hide_unsuitable", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("career_preferences", "hide_unsuitable")
    op.drop_column("career_preferences", "entry_level_only")
