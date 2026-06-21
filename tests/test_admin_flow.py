"""Admin moderation flow via mocked aiogram objects."""

import asyncio

from bot.handlers import admin_handlers
from bot.models.database import SubmissionStatus
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service

from tests.factories import make_bot, make_callback

ADMIN_ID = 111  # present in ADMIN_IDS for the test stack


async def _seed_submission(user_id=8001, username="author", text="hello", with_present=True):
    """Create a user + submission and (optionally) present it to admins."""
    await get_user_service().get_or_create_user(user_id, username=username)
    bot = make_bot()
    sub = await get_submission_service().create_submission(
        user_id=user_id,
        show_authorship=False,
        text_content=text,
        user_message_id=42,
        user_chat_id=user_id,
        has_media=False,
    )
    if with_present:
        ok = await admin_handlers.present_submission_to_admins(sub.submission_id, bot)
        assert ok is True
    return sub, bot


async def _wait_published(submission_id, timeout=3.0):
    """Poll until the submission becomes PUBLISHED (publication runs in a task)."""
    svc = get_submission_service()
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        sub = await svc.get_submission(submission_id)
        if sub.status == SubmissionStatus.PUBLISHED:
            return sub
        await asyncio.sleep(0.02)
    return await svc.get_submission(submission_id)


async def test_present_text_submission_sends_card():
    sub, bot = await _seed_submission()
    bot.send_message.assert_awaited()  # text-only -> send_message

    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.message_id_in_admin_chat == 5001


async def test_approve_publish_publishes_to_channel(monkeypatch):
    # Publish immediately (no 2-minute wait).
    from bot.utils.config import config_loader
    cfg = config_loader.load_config()
    monkeypatch.setattr(cfg.publication, "delay_minutes", 0)

    sub, bot = await _seed_submission(user_id=8002)

    # Step 1: admin taps "approve & publish" -> confirmation keyboard shown.
    cb1 = make_callback(f"adm_app_pub:{sub.submission_id}", user_id=ADMIN_ID, bot=bot)
    await admin_handlers.handle_approve_publish(cb1, bot)
    cb1.message.edit_reply_markup.assert_awaited()

    # Step 2: admin confirms -> decision made, publication scheduled (delay 0).
    cb2 = make_callback(f"adm_conf_pub:{sub.submission_id}", user_id=ADMIN_ID, bot=bot)
    await admin_handlers.confirm_approve_publish(cb2, bot)

    # The author is notified...
    bot.send_message.assert_awaited()
    # ...and the content lands in the channel.
    published = await _wait_published(sub.submission_id)
    assert published.status == SubmissionStatus.PUBLISHED
    assert published.message_id_in_channel == 5002  # copy_message return id
    bot.copy_message.assert_awaited()


async def test_reject_notifies_author():
    sub, bot = await _seed_submission(user_id=8003)

    cb = make_callback(f"adm_rej:{sub.submission_id}", user_id=ADMIN_ID, bot=bot)
    await admin_handlers.handle_reject(cb, bot)

    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.REJECTED
    # The author got a rejection DM.
    assert any(call.args and call.args[0] == 8003 for call in bot.send_message.await_args_list) \
        or any(call.kwargs.get("chat_id") == 8003 for call in bot.send_message.await_args_list)


async def test_non_admin_cannot_moderate():
    sub, bot = await _seed_submission(user_id=8004)
    bot.send_message.reset_mock()

    cb = make_callback(f"adm_rej:{sub.submission_id}", user_id=999999, bot=bot)
    await admin_handlers.handle_reject(cb, bot)

    cb.answer.assert_awaited()  # "admins only" alert
    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PENDING  # unchanged


async def test_block_user_from_card():
    sub, bot = await _seed_submission(user_id=8005)

    cb = make_callback(f"adm_blk:{8005}", user_id=ADMIN_ID, bot=bot)
    await admin_handlers.handle_block_user(cb, bot)

    assert await get_user_service().is_blocked(8005) is True
