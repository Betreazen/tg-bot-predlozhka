"""Shared pytest fixtures.

The suite runs against real PostgreSQL and Redis instances (see
docker-compose.test.yml). The schema is created once per session via the app's
own metadata, and every test starts from a clean state.
"""

import asyncio
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text

from bot.utils.config import config_loader
from bot.utils.database import init_db_manager
from bot.utils.redis_manager import init_redis_manager


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop so session fixtures share one loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def _migrated():
    """Build the schema via Alembic — the exact path used in production.

    Running real migrations (instead of metadata create_all) ensures the tests
    exercise the deployed schema and catch any migration/model drift.
    """
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    return True


@pytest_asyncio.fixture(scope="session")
async def db_manager(_migrated):
    """Connect to the migrated test database."""
    config = config_loader.load_config()
    manager = init_db_manager(config.database)
    await manager.connect()
    yield manager
    await manager.disconnect()


@pytest_asyncio.fixture(scope="session")
async def redis_manager():
    """Connect to the test Redis once."""
    config = config_loader.load_config()
    manager = init_redis_manager(config.redis)
    await manager.connect()
    yield manager
    await manager.disconnect()


def _cancel_scheduled_tasks():
    """Cancel any in-memory publication tasks left over from a prior test."""
    from bot.services.publication_service import get_publication_service

    ps = get_publication_service()
    for task in list(ps.scheduled_tasks.values()):
        task.cancel()
    ps.scheduled_tasks.clear()


@pytest_asyncio.fixture(autouse=True)
async def _clean_state(db_manager, redis_manager):
    """Reset DB tables, Redis and background tasks before each test."""
    _cancel_scheduled_tasks()
    async with db_manager.session() as session:
        await session.execute(
            text("TRUNCATE admin_action_logs, submissions, users RESTART IDENTITY CASCADE")
        )
    await redis_manager.get_client().flushdb()
    yield
    _cancel_scheduled_tasks()
