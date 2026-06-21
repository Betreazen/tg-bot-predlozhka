"""Tests for SubmissionService."""

from datetime import datetime

from bot.models.database import SubmissionStatus
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service


async def _make_user(user_id: int = 2001):
    await get_user_service().get_or_create_user(user_id)
    return user_id


async def test_create_and_get_submission():
    user_id = await _make_user()
    svc = get_submission_service()
    sub = await svc.create_submission(
        user_id=user_id, show_authorship=True, text_content="hello"
    )
    assert sub.status == SubmissionStatus.PENDING

    fetched = await svc.get_submission(sub.submission_id)
    assert fetched is not None
    assert fetched.text_content == "hello"
    assert fetched.show_authorship is True


async def test_update_status_sets_moderator_and_timestamp():
    user_id = await _make_user(2002)
    svc = get_submission_service()
    sub = await svc.create_submission(user_id=user_id, show_authorship=False)

    ok = await svc.update_status(sub.submission_id, SubmissionStatus.APPROVED, moderator_id=42)
    assert ok is True

    fetched = await svc.get_submission(sub.submission_id)
    assert fetched.status == SubmissionStatus.APPROVED
    assert fetched.moderator_id == 42
    assert fetched.decision_timestamp is not None


async def test_increment_retry_count_atomic_returns_new_value():
    user_id = await _make_user(2003)
    svc = get_submission_service()
    sub = await svc.create_submission(user_id=user_id, show_authorship=False)

    assert await svc.increment_retry_count(sub.submission_id) == 1
    assert await svc.increment_retry_count(sub.submission_id) == 2


async def test_count_user_submissions_since():
    user_id = await _make_user(2004)
    svc = get_submission_service()
    await svc.create_submission(user_id=user_id, show_authorship=False)
    await svc.create_submission(user_id=user_id, show_authorship=False)

    assert await svc.count_user_submissions_since(user_id, datetime(2000, 1, 1)) == 2
    assert await svc.count_user_submissions_since(user_id, datetime(2999, 1, 1)) == 0


async def test_get_submissions_by_status():
    user_id = await _make_user(2005)
    svc = get_submission_service()
    s1 = await svc.create_submission(user_id=user_id, show_authorship=False)
    await svc.create_submission(user_id=user_id, show_authorship=False)
    await svc.update_status(s1.submission_id, SubmissionStatus.APPROVED)

    pending = await svc.get_submissions_by_status(SubmissionStatus.PENDING)
    approved = await svc.get_submissions_by_status(SubmissionStatus.APPROVED)
    assert len(pending) == 1
    assert len(approved) == 1
