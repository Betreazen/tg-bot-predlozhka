"""Publication + retry flow with a mocked Bot."""

from unittest.mock import AsyncMock

from bot.models.database import SubmissionStatus
from bot.services.error_handler import get_error_handler
from bot.services.publication_service import get_publication_service
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.utils.time import utcnow

from tests.factories import make_bot


async def _make_scheduled(user_id, text="content", with_message=True):
    await get_user_service().get_or_create_user(user_id, username="author")
    svc = get_submission_service()
    sub = await svc.create_submission(
        user_id=user_id,
        show_authorship=False,
        text_content=text,
        user_message_id=42 if with_message else None,
        user_chat_id=user_id if with_message else None,
        has_media=False,
    )
    await svc.schedule_publication(sub.submission_id, utcnow())
    return await svc.get_submission(sub.submission_id)


async def test_publish_to_channel_copies_and_marks_published():
    bot = make_bot()
    sub = await _make_scheduled(9001)

    await get_publication_service()._publish_to_channel(sub, bot)

    bot.copy_message.assert_awaited()
    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLISHED
    assert refreshed.message_id_in_channel == 5002


async def test_publish_after_delay_zero_publishes():
    bot = make_bot()
    sub = await _make_scheduled(9002)

    await get_publication_service()._publish_after_delay(sub.submission_id, 0, bot)

    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLISHED


async def test_publish_skipped_if_not_scheduled():
    """A cancelled/changed submission must not be published."""
    bot = make_bot()
    sub = await _make_scheduled(9003)
    # Cancel before the delay fires.
    await get_submission_service().update_status(
        sub.submission_id, SubmissionStatus.ACCEPTED_NOT_PUBLISHED
    )

    await get_publication_service()._publish_after_delay(sub.submission_id, 0, bot)

    bot.copy_message.assert_not_awaited()
    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.ACCEPTED_NOT_PUBLISHED


async def test_retry_exhausted_marks_failed_and_notifies_admin(monkeypatch):
    from bot.utils.config import config_loader
    cfg = config_loader.load_config()
    monkeypatch.setattr(cfg.error_handling, "retry_delay_seconds", 0)

    bot = make_bot()
    # Force every channel send to fail: copy raises, and with no text/media the
    # "send as new" fallback returns None -> publish raises.
    bot.copy_message = AsyncMock(side_effect=Exception("channel down"))
    sub = await _make_scheduled(9004, text=None)

    await get_error_handler().handle_publication_error(
        sub.submission_id, Exception("initial failure"), bot
    )

    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLICATION_FAILED
    # Admins were notified about the failure.
    bot.send_message.assert_awaited()
    assert refreshed.publication_retry_count >= cfg.error_handling.max_retry_attempts
