"""Recovery-on-restart flow (stuck SCHEDULED / APPROVED submissions)."""

from datetime import timedelta

from bot.models.database import SubmissionStatus
from bot.services.publication_service import get_publication_service
from bot.services.recovery_service import get_recovery_service
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.utils.time import utcnow

from tests.factories import make_bot


async def _make_submission(user_id, *, text="content", media=True):
    await get_user_service().get_or_create_user(user_id, username="author")
    return await get_submission_service().create_submission(
        user_id=user_id,
        show_authorship=False,
        text_content=text,
        user_message_id=42 if media else None,
        user_chat_id=user_id if media else None,
        has_media=media,
    )


async def test_recover_overdue_scheduled_publishes_now():
    bot = make_bot()
    svc = get_submission_service()
    sub = await _make_submission(6101)
    # Scheduled for the past -> bot was down past the publish time.
    await svc.schedule_publication(sub.submission_id, utcnow() - timedelta(minutes=5))

    await get_recovery_service()._recover_scheduled_publications(bot)

    bot.copy_message.assert_awaited()
    refreshed = await svc.get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLISHED


async def test_recover_future_scheduled_reschedules_task():
    bot = make_bot()
    svc = get_submission_service()
    sub = await _make_submission(6102)
    # Still in the future -> should be rescheduled, not published yet.
    await svc.schedule_publication(sub.submission_id, utcnow() + timedelta(hours=1))

    await get_recovery_service()._recover_scheduled_publications(bot)

    bot.copy_message.assert_not_awaited()
    assert str(sub.submission_id) in get_publication_service().scheduled_tasks
    refreshed = await svc.get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.SCHEDULED


async def test_recover_approved_gets_scheduled():
    """APPROVED but never scheduled (crash between decision and scheduling)."""
    bot = make_bot()
    svc = get_submission_service()
    sub = await _make_submission(6103)
    await svc.update_status(sub.submission_id, SubmissionStatus.APPROVED)

    await get_recovery_service()._recover_approved_submissions(bot)

    refreshed = await svc.get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.SCHEDULED
    assert refreshed.scheduled_publication_time is not None
    # A pending publication task now exists (default 2-min delay -> not yet sent).
    assert str(sub.submission_id) in get_publication_service().scheduled_tasks
    bot.copy_message.assert_not_awaited()


async def test_recover_overdue_failure_marks_failed(monkeypatch):
    from bot.utils.config import config_loader
    cfg = config_loader.load_config()
    monkeypatch.setattr(cfg.error_handling, "retry_delay_seconds", 0)

    bot = make_bot()
    # Force the channel send to fail and leave no fallback content.
    from unittest.mock import AsyncMock
    bot.copy_message = AsyncMock(side_effect=Exception("channel down"))

    svc = get_submission_service()
    sub = await _make_submission(6104, text=None)
    await svc.schedule_publication(sub.submission_id, utcnow() - timedelta(minutes=5))

    await get_recovery_service()._recover_scheduled_publications(bot)

    refreshed = await svc.get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLICATION_FAILED
    bot.send_message.assert_awaited()  # admins notified


async def test_recover_pending_notifies_when_many():
    bot = make_bot()
    svc = get_submission_service()
    await get_user_service().get_or_create_user(6105, username="spammer")
    for _ in range(11):  # threshold is >10
        await svc.create_submission(user_id=6105, show_authorship=False)

    await get_recovery_service()._recover_pending_submissions(bot)

    bot.send_message.assert_awaited()


async def test_recover_pending_tasks_smoke_sends_restart_notice():
    bot = make_bot()
    svc = get_submission_service()
    overdue = await _make_submission(6106)
    await svc.schedule_publication(overdue.submission_id, utcnow() - timedelta(minutes=1))

    await get_recovery_service().recover_pending_tasks(bot)

    # Overdue item published during recovery...
    assert (await svc.get_submission(overdue.submission_id)).status == SubmissionStatus.PUBLISHED
    # ...and the "bot restarted" notice was sent to the admin chat.
    bot.send_message.assert_awaited()
