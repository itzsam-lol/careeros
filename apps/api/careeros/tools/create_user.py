"""Create or reset a self-hosted (AUTH_MODE=password) account.

    uv run python -m careeros.tools.create_user --email you@example.com --name "Your Name"
    uv run python -m careeros.tools.create_user --email you@example.com --generate   # random password

The password is read interactively (or from CAREEROS_NEW_PASSWORD for automation) and only a
scrypt hash is stored. Re-running for an existing email resets the password and signs out
every existing session.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import secrets
import string
import sys
import uuid

from sqlalchemy import select

from careeros.auth.passwords import hash_password, validate_password_strength
from careeros.config import get_settings
from careeros.core.clock import utcnow
from careeros.core.errors import ValidationFailedError
from careeros.db.session import Database
from careeros.users.models import User


def _generate() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(16))
        try:
            validate_password_strength(candidate)
        except ValidationFailedError:
            continue
        return candidate


async def _run(email: str, name: str | None, password: str) -> str:
    settings = get_settings()
    db = Database.from_settings(settings)
    subject = email.lower()
    try:
        async with db.session() as session:
            user = (
                await session.execute(
                    select(User).where(
                        User.auth_provider == "password", User.auth_subject == subject
                    )
                )
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    id=uuid.uuid4(),
                    email=subject,
                    name=name,
                    auth_provider="password",
                    auth_subject=subject,
                    settings={},
                    session_version=0,
                    created_at=utcnow(),
                )
                session.add(user)
                action = "created"
            else:
                user.session_version = (user.session_version or 0) + 1
                if name:
                    user.name = name
                action = "reset"
            user.password_hash = hash_password(password)
            await session.commit()
            return action
    finally:
        await db.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name")
    parser.add_argument("--generate", action="store_true", help="generate a strong random password")
    args = parser.parse_args()

    if args.generate:
        password = _generate()
    else:
        password = os.environ.get("CAREEROS_NEW_PASSWORD") or getpass.getpass("New password: ")
        if not os.environ.get("CAREEROS_NEW_PASSWORD") and password != getpass.getpass(
            "Repeat password: "
        ):
            sys.exit("Passwords do not match")
    try:
        validate_password_strength(password)
    except ValidationFailedError as exc:
        sys.exit(f"Weak password: {exc.message}")
    action = asyncio.run(_run(args.email, args.name, password))
    sys.stdout.write(f"Account {action} for {args.email.lower()}\n")
    if args.generate:
        sys.stdout.write(f"Generated password (shown once): {password}\n")


if __name__ == "__main__":
    main()
