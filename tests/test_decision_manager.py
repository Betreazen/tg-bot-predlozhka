"""Tests for DecisionManager (locking + idempotency)."""

import pytest
from sqlalchemy import func, select

from bot.models.database import AdminActionLog, SubmissionStatus
from bot.services.decision_manager import (
    get_decision_manager,
    LockNotAcquiredError,
    AlreadyDecidedError,
)
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.utils.redis_manager import get_redis_manager


async def _new_submission(user_id: int):
    await get_user_service().get_or_create_user(user_id)
    return await get_submission_service().create_submission(
        user_id=user_id, show_authorship=False
    )


async def test_make_decision_approves_and_logs(db_manager):
    sub = await _new_submission(5001)
    dm = get_decision_manager()

    ok = await dm.make_decision(sub.submission_id, "approve_publish", moderator_id=70)
    assert ok is True

    fetched = await get_submission_service().get_submission(sub.submission_id)
    assert fetched.status == SubmissionStatus.APPROVED
    assert fetched.moderator_id == 70

    async with db_manager.session() as session:
        count = await session.execute(
            select(func.count(AdminActionLog.log_id)).where(
                AdminActionLog.submission_id == sub.submission_id
            )
        )
        assert count.scalar() == 1


async def test_second_decision_raises_already_decided():
    sub = await _new_submission(5002)
    dm = get_decision_manager()
    await dm.make_decision(sub.submission_id, "reject", moderator_id=70)

    with pytest.raises(AlreadyDecidedError):
        await dm.make_decision(sub.submission_id, "approve_only", moderator_id=71)


async def test_lock_held_raises_lock_not_acquired():
    sub = await _new_submission(5003)
    dm = get_decision_manager()

    # Simulate another admin currently holding the lock.
    client = get_redis_manager().get_client()
    await client.set(f"decision_lock:{sub.submission_id}", "1")

    with pytest.raises(LockNotAcquiredError):
        await dm.make_decision(sub.submission_id, "approve_publish", moderator_id=72)


async def test_decision_on_missing_submission_returns_false():
    import uuid
    dm = get_decision_manager()
    assert await dm.make_decision(uuid.uuid4(), "reject", moderator_id=70) is False
