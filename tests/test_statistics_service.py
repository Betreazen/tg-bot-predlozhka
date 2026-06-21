"""Tests for StatisticsService aggregation."""

import uuid
from datetime import datetime

from bot.models.database import Submission, SubmissionStatus
from bot.services.statistics_service import get_statistics_service
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service


async def _seed_current_month(user_id: int):
    sub_svc = get_submission_service()
    # 2 published
    for _ in range(2):
        s = await sub_svc.create_submission(user_id=user_id, show_authorship=False)
        await sub_svc.update_status(s.submission_id, SubmissionStatus.PUBLISHED)
    # 1 accepted (approved, not published)
    s = await sub_svc.create_submission(user_id=user_id, show_authorship=False)
    await sub_svc.update_status(s.submission_id, SubmissionStatus.ACCEPTED_NOT_PUBLISHED)
    # 1 rejected
    s = await sub_svc.create_submission(user_id=user_id, show_authorship=False)
    await sub_svc.update_status(s.submission_id, SubmissionStatus.REJECTED)
    # 1 pending
    await sub_svc.create_submission(user_id=user_id, show_authorship=False)


async def test_current_month_counts_and_rates(db_manager):
    user_id = 4001
    await get_user_service().get_or_create_user(user_id, username="mod")
    await _seed_current_month(user_id)

    # A submission far in the past must be excluded from the current month.
    async with db_manager.session() as session:
        session.add(Submission(
            submission_id=uuid.uuid4(),
            user_id=user_id,
            status=SubmissionStatus.PUBLISHED,
            show_authorship=False,
            submission_timestamp=datetime(2000, 1, 1, 12, 0, 0),
        ))

    stats = await get_statistics_service().get_current_month_stats()

    assert stats["total_submissions"] == 5
    assert stats["published"] == 2
    assert stats["approved"] == 3  # published + accepted
    assert stats["rejected"] == 1
    assert stats["unique_users"] == 1
    assert stats["new_users"] >= 1
    assert stats["approval_rate"] == 60.0
    assert stats["publication_rate"] == round(2 / 3 * 100, 1)
    assert stats["rejection_rate"] == 20.0


async def test_admin_stats_resolves_username():
    moderator_id = 4002
    await get_user_service().get_or_create_user(moderator_id, username="judge")

    sub_svc = get_submission_service()
    s = await sub_svc.create_submission(user_id=moderator_id, show_authorship=False)
    await sub_svc.update_status(s.submission_id, SubmissionStatus.PUBLISHED, moderator_id=moderator_id)

    stats = await get_statistics_service().get_current_month_stats()
    by_id = {a["user_id"]: a for a in stats["admin_stats"]}
    assert moderator_id in by_id
    assert by_id[moderator_id]["username"] == "judge"
    assert by_id[moderator_id]["decision_count"] == 1


async def test_empty_month_has_zero_rates():
    stats = await get_statistics_service().get_current_month_stats()
    assert stats["total_submissions"] == 0
    assert stats["approval_rate"] == 0
    assert stats["admin_stats"] == []
