from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.companies.models import Company
from careeros.core.clock import utcnow
from careeros.discovery.normalize import normalize_company


async def get_or_create_company(session: AsyncSession, name: str) -> Company:
    display = " ".join(name.split())[:200] or "Unknown company"
    key = normalize_company(display) or display.lower()
    now = utcnow()
    await session.execute(
        pg_insert(Company)
        .values(
            id=uuid.uuid4(),
            name=display,
            normalized_name=key[:200],
            locations=[],
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["normalized_name"])
    )
    company = (
        await session.execute(select(Company).where(Company.normalized_name == key[:200]))
    ).scalar_one()
    return company
