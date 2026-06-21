"""Media submissions (photo/video) go through copy_message, not plain text."""

from types import SimpleNamespace

from bot.handlers import admin_handlers, user_handlers
from bot.models.database import SubmissionStatus
from bot.services.publication_service import get_publication_service
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.utils.states import SubmissionStates
from bot.utils.time import utcnow

from tests.factories import make_bot, make_message, FakeState


async def _media_submission(user_id, caption="nice pic"):
    await get_user_service().get_or_create_user(user_id, username="author")
    return await get_submission_service().create_submission(
        user_id=user_id,
        show_authorship=False,
        text_content=caption,
        user_message_id=77,
        user_chat_id=user_id,
        has_media=True,
        media_type="photo",
    )


async def test_present_media_uses_copy_message():
    bot = make_bot()
    sub = await _media_submission(8101)

    ok = await admin_handlers.present_submission_to_admins(sub.submission_id, bot)
    assert ok is True

    # Media is copied (preserving the file), not re-sent as text.
    bot.copy_message.assert_awaited()
    bot.send_message.assert_not_awaited()

    call = bot.copy_message.await_args
    assert call.kwargs["from_chat_id"] == 8101
    assert call.kwargs["message_id"] == 77

    refreshed = await get_submission_service().get_submission(sub.submission_id)
    assert refreshed.message_id_in_admin_chat == 5002  # copy_message return id


async def test_publish_media_copies_to_channel():
    bot = make_bot()
    svc = get_submission_service()
    sub = await _media_submission(8102)
    await svc.schedule_publication(sub.submission_id, utcnow())

    await get_publication_service()._publish_to_channel(
        await svc.get_submission(sub.submission_id), bot
    )

    bot.copy_message.assert_awaited()
    call = bot.copy_message.await_args
    assert call.kwargs["from_chat_id"] == 8102
    assert call.kwargs["message_id"] == 77

    refreshed = await svc.get_submission(sub.submission_id)
    assert refreshed.status == SubmissionStatus.PUBLISHED
    assert refreshed.message_id_in_channel == 5002


async def test_receive_photo_marks_has_media():
    state = FakeState()
    await state.set_state(SubmissionStates.waiting_for_content)

    msg = make_message(user_id=8103, text=None, message_id=77)
    msg.photo = [SimpleNamespace(file_size=2048, file_id="abc")]

    await user_handlers.receive_content(msg, state)

    assert await state.get_state() == SubmissionStates.waiting_for_confirmation
    data = await state.get_data()
    assert data["has_media"] is True
    assert data["message_id"] == 77


async def test_receive_oversized_photo_rejected():
    state = FakeState()
    await state.set_state(SubmissionStates.waiting_for_content)

    msg = make_message(user_id=8104, text=None)
    # 250 MB exceeds the default 200 MB limit.
    msg.photo = [SimpleNamespace(file_size=250 * 1024 * 1024, file_id="big")]

    await user_handlers.receive_content(msg, state)

    msg.answer.assert_awaited()  # "file too large"
    # Flow not advanced.
    assert await state.get_state() == SubmissionStates.waiting_for_content
