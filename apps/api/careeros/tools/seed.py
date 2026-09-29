"""Load synthetic demo data for the local developer account.

    uv run python -m careeros.tools.seed            # demo profile (marked verified)
    uv run python -m careeros.tools.seed --reset    # wipe the dev user's profile first

Only runs outside deployed environments. The data is fictional (fixtures/profiles).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import delete

from careeros.auth.principal import Principal
from careeros.config import REPO_ROOT, get_settings
from careeros.db.session import Database
from careeros.evidence.service import sync_profile_evidence
from careeros.llm.router import LLMRouter
from careeros.profile.importer import ProfileImport, import_profile
from careeros.profile.models import ProfessionalProfile
from careeros.profile.service import get_or_create_profile
from careeros.users.service import get_or_create_user


async def _seed(reset: bool) -> None:
    settings = get_settings()
    if settings.is_deployed:
        sys.exit("refusing to seed a deployed environment")
    db = Database.from_settings(settings)
    principal = Principal(
        provider="dev",
        subject="dev-user",
        email=settings.dev_auth_email,
        name=settings.dev_auth_name,
        email_verified=True,
    )
    payload = ProfileImport.model_validate(
        json.loads((REPO_ROOT / "fixtures" / "profiles" / "demo_profile.json").read_text("utf-8"))
    )
    try:
        async with db.session() as session:
            user = await get_or_create_user(session, principal)
            if reset:
                await session.execute(
                    delete(ProfessionalProfile).where(ProfessionalProfile.user_id == user.id)
                )
                await session.commit()
            profile = await get_or_create_profile(session, user)
            result = await import_profile(session, profile, payload, status_override="VERIFIED")
            await sync_profile_evidence(session, profile, LLMRouter(settings).embedder)
            await session.commit()
            sys.stdout.write(f"seeded demo profile for {user.email}: {result.created}\n")
    finally:
        await db.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete the dev user's profile first")
    args = parser.parse_args()
    asyncio.run(_seed(args.reset))


if __name__ == "__main__":
    main()
