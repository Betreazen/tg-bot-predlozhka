"""End-to-end user submission flow via mocked aiogram objects."""

from bot.handlers import user_handlers
from bot.models.database import SubmissionStatus
from bot.services.rate_limit import get_rate_limit_service
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.utils.states import SubmissionStates

from tests.factories import make_bot, make_callback, make_message, FakeState


async def test_start_creates_user_and_greets():
    state = FakeState()
    msg = make_message(user_id=7001, username="newbie")

    await user_handlers.cmd_start(msg, state)

    user = await get_user_service().get_user(7001)
    assert user is not None
    assert user.username == "newbie"
    msg.answer.assert_awaited()


async def test_full_submission_reaches_moderators():
    """User: /start -> suggest -> send text -> confirm -> authorship -> queued."""
    bot = make_bot()
    state = FakeState()
    user_id = 7002

    await get_user_service().get_or_create_user(user_id, username="author")

    # 1. Click "suggest content"
    cb = make_callback("suggest_content", user_id=user_id, bot=bot)
    await user_handlers.start_submission(cb, state)
    assert await state.get_state() == SubmissionStates.waiting_for_content

    # 2. Send the actual content (text-only)
    content_msg = make_message(user_id=user_id, text="My great idea", message_id=42)
    await user_handlers.receive_content(content_msg, state)
    assert await state.get_state() == SubmissionStates.waiting_for_confirmation

    # 3. Confirm
    cb_confirm = make_callback("confirm_content", user_id=user_id, bot=bot)
    await user_handlers.confirm_content(cb_confirm, state)
    assert await state.get_state() == SubmissionStates.waiting_for_authorship

    # 4. Choose anonymous -> submission created and presented to admins
    cb_auth = make_callback("authorship_no", user_id=user_id, bot=bot)
    await user_handlers.process_authorship(cb_auth, state)

    # The moderation card was sent to the admin chat.
    bot.send_message.assert_awaited()

    # A PENDING submission now exists, linked to the original message.
    pending = await get_submission_service().get_submissions_by_status(
        SubmissionStatus.PENDING
    )
    assert len(pending) == 1
    sub = pending[0]
    assert sub.user_id == user_id
    assert sub.text_content == "My great idea"
    assert sub.user_message_id == 42
    assert sub.message_id_in_admin_chat == 5001  # bot.send_message return id

    # Counters updated.
    user = await get_user_service().get_user(user_id)
    assert user.total_submissions_count == 1
    assert await get_rate_limit_service().get_count(user_id) == 1

    assert await state.get_state() is None  # state cleared


async def test_blocked_user_cannot_start_submission():
    bot = make_bot()
    state = FakeState()
    user_id = 7003
    await get_user_service().get_or_create_user(user_id)
    await get_user_service().block_user(user_id)

    cb = make_callback("suggest_content", user_id=user_id, bot=bot)
    await user_handlers.start_submission(cb, state)

    cb.answer.assert_awaited()  # blocked alert
    assert await state.get_state() is None  # never entered the flow


async def test_rate_limited_user_cannot_start():
    bot = make_bot()
    state = FakeState()
    user_id = 7004
    await get_user_service().get_or_create_user(user_id)

    rl = get_rate_limit_service()
    for _ in range(rl.limit):
        await rl.try_acquire(user_id)

    cb = make_callback("suggest_content", user_id=user_id, bot=bot)
    await user_handlers.start_submission(cb, state)

    cb.answer.assert_awaited()  # limit alert
    assert await state.get_state() is None
