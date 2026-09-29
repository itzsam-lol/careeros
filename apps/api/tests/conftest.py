"""Test harness.

* Pure unit tests need nothing.
* Tests that use `session`, `client` or `database` run against a real PostgreSQL + pgvector
  database (`TEST_DATABASE_URL`). It is recreated and migrated once per test session; every
  test runs inside a transaction that is rolled back, so tests are isolated and fast.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from careeros.api.deps import get_session
from careeros.config import API_ROOT, Settings
from careeros.container import Container, build_container
from careeros.db.session import Database
from careeros.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://careeros:careeros@localhost:5433/careeros_test"
)
DB_FIXTURES = {"database", "session", "client", "app", "container", "other_client"}
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if DB_FIXTURES.intersection(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=TEST_DATABASE_URL,
        auth_mode="dev",
        log_json=False,
        log_level="WARNING",
        storage_backend="local",
        local_storage_dir=tmp_path_factory.mktemp("storage"),
        llm_extraction_provider="local",
        llm_match_provider="local",
        llm_resume_provider="local",
        llm_outreach_provider="local",
        llm_research_provider="local",
        llm_application_provider="local",
        llm_profile_import_provider="local",
        embedding_provider="local",
        email_provider="mock",
        search_provider="none",
        task_dispatch_mode="database",
        http_respect_robots_txt=False,
        api_rate_limit_per_minute=10_000,
    )


async def _recreate_database(url: str) -> None:
    parsed = make_url(url)
    name = parsed.database
    admin = create_async_engine(
        parsed.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OSError as exc:  # connection refused etc.
        pytest.fail(
            f"PostgreSQL is not reachable at {parsed.render_as_string(hide_password=True)}. "
            "Start it with `docker compose up -d db` or set TEST_DATABASE_URL. "
            f"({exc})"
        )
    finally:
        await admin.dispose()


@pytest_asyncio.fixture(scope="session")
async def database(settings: Settings) -> AsyncIterator[Database]:
    await _recreate_database(settings.database_url)
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    cfg.attributes["configure_logger"] = False
    # Alembic's async env calls asyncio.run(); run it on a worker thread with its own loop.
    await asyncio.to_thread(command.upgrade, cfg, "head")
    db = Database(settings.database_url, pool_size=5, max_overflow=5)
    yield db
    await db.dispose()


@pytest_asyncio.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.engine.connect() as conn:
        outer = await conn.begin()
        db_session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield db_session
        finally:
            await db_session.close()
            if outer.is_active:
                await outer.rollback()


@pytest_asyncio.fixture
async def container(settings: Settings, database: Database) -> AsyncIterator[Container]:
    built = build_container(settings, db=database)
    yield built
    await built.aclose()


@pytest_asyncio.fixture
async def app(settings: Settings, container: Container, session: AsyncSession):  # type: ignore[no-untyped-def]
    application = create_app(settings, container=container)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = _session_override
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer dev-token"},
    ) as http:
        yield http


@pytest_asyncio.fixture
async def other_client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """A second, unrelated user — used to prove tenant isolation."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer dev-token:mallory"},
    ) as http:
        yield http
