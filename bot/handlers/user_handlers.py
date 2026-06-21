"""User flow handlers - /start command and content submission."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.config import config_loader
from bot.utils.states import SubmissionStates
from bot.services.user_service import get_user_service
from bot.services.rate_limit import get_rate_limit_service
from bot.services.submission_service import get_submission_service

logger = logging.getLogger(__name__)
router = Router()


async def _is_blocked(user_id: int) -> bool:
    """Check whether a user is blocked, honoring the enable_blocking flag.

    Args:
        user_id: Telegram user ID

    Returns:
        True if blocking is enabled and the user is blocked.
    """
    config = config_loader.load_config()
    if not config.features.enable_blocking:
        return False
    return await get_user_service().is_blocked(user_id)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command.

    Args:
        message: Incoming message
        state: FSM context
    """
    # Clear any existing state
    await state.clear()

    # Get or create user
    user_service = get_user_service()
    await user_service.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    # Load messages
    messages = config_loader.load_messages()
    welcome = messages.user["welcome"]

    # Create keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=welcome["button"], callback_data="suggest_content")]
    ])

    # Send welcome message
    text = f"{welcome['title']}\n\n{welcome['text']}"
    await message.answer(text, reply_markup=keyboard)

    logger.info(f"User {message.from_user.id} started bot", extra={'user_id': message.from_user.id})


@router.callback_query(F.data == "suggest_content")
async def start_submission(callback: CallbackQuery, state: FSMContext) -> None:
    """Start content submission flow.

    Args:
        callback: Callback query
        state: FSM context
    """
    messages = config_loader.load_messages()
    config = config_loader.load_config()

    # Blocked users cannot submit.
    if await _is_blocked(callback.from_user.id):
        await callback.answer(messages.notifications["user_blocked"], show_alert=True)
        return

    # Advisory rate-limit check for early feedback (authoritative check happens
    # atomically when the submission is finalized).
    rate_limit_service = get_rate_limit_service()
    allowed, _ = await rate_limit_service.check_limit(callback.from_user.id)

    if not allowed:
        limit_msg = messages.user["limit_exceeded"].format(
            limit=config.rate_limits.submissions_per_day
        )
        await callback.answer(limit_msg, show_alert=True)
        return

    # Set state and send prompt
    await state.set_state(SubmissionStates.waiting_for_content)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=messages.user["submission_cancel_button"],
            callback_data="cancel_submission"
        )]
    ])

    await callback.message.answer(
        messages.user["submission_prompt"],
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_submission", StateFilter(SubmissionStates))
async def cancel_submission(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel submission flow.

    Args:
        callback: Callback query
        state: FSM context
    """
    await state.clear()

    messages = config_loader.load_messages()
    await callback.message.answer(messages.user["submission_cancelled"])
    await callback.answer()


async def _ask_authorship(message: Message, state: FSMContext) -> None:
    """Move to the authorship question step.

    Args:
        message: Message to reply to.
        state: FSM context.
    """
    await state.set_state(SubmissionStates.waiting_for_authorship)
    messages = config_loader.load_messages()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=messages.user["authorship_yes"], callback_data="authorship_yes")],
        [InlineKeyboardButton(text=messages.user["authorship_no"], callback_data="authorship_no")]
    ])
    await message.answer(messages.user["authorship_question"], reply_markup=keyboard)


@router.message(StateFilter(SubmissionStates.waiting_for_content))
async def receive_content(message: Message, state: FSMContext) -> None:
    """Receive submitted content.

    Args:
        message: Incoming message with content
        state: FSM context
    """
    messages = config_loader.load_messages()
    config = config_loader.load_config()

    # Check if message has content
    if not message.text and not message.photo and not message.video and not message.document and not message.audio:
        await message.answer(messages.user["unsupported_media"])
        return

    # Check file size for media
    if message.photo or message.video or message.document or message.audio:
        file_size_mb = 0
        if message.photo:
            file_size_mb = message.photo[-1].file_size / (1024 * 1024) if message.photo[-1].file_size else 0
        elif message.video:
            file_size_mb = message.video.file_size / (1024 * 1024) if message.video.file_size else 0
        elif message.document:
            file_size_mb = message.document.file_size / (1024 * 1024) if message.document.file_size else 0
        elif message.audio:
            file_size_mb = message.audio.file_size / (1024 * 1024) if message.audio.file_size else 0

        if file_size_mb > config.publication.max_file_size_mb:
            await message.answer(
                messages.user["file_too_large"].format(max_size=config.publication.max_file_size_mb)
            )
            return

    # Store message data in state
    await state.update_data(
        message_id=message.message_id,
        chat_id=message.chat.id,
        text=message.text or message.caption,
        has_media=bool(message.photo or message.video or message.document or message.audio)
    )

    # Optionally skip the confirmation step.
    if not config.features.require_confirmation:
        await _ask_authorship(message, state)
        return

    # Set next state
    await state.set_state(SubmissionStates.waiting_for_confirmation)

    # Send confirmation prompt
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=messages.user["confirm_button"], callback_data="confirm_content"),
            InlineKeyboardButton(text=messages.user["cancel_button"], callback_data="cancel_submission")
        ]
    ])

    await message.answer(messages.user["submission_received"], reply_markup=keyboard)


@router.callback_query(F.data == "confirm_content", StateFilter(SubmissionStates.waiting_for_confirmation))
async def confirm_content(callback: CallbackQuery, state: FSMContext) -> None:
    """Confirm content submission.

    Args:
        callback: Callback query
        state: FSM context
    """
    await _ask_authorship(callback.message, state)
    await callback.answer()


@router.callback_query(
    F.data.in_(["authorship_yes", "authorship_no"]),
    StateFilter(SubmissionStates.waiting_for_authorship)
)
async def process_authorship(callback: CallbackQuery, state: FSMContext) -> None:
    """Process authorship choice and create submission.

    Args:
        callback: Callback query
        state: FSM context
    """
    messages = config_loader.load_messages()
    config = config_loader.load_config()

    # Re-check blocking at the final step (state may have been entered earlier).
    if await _is_blocked(callback.from_user.id):
        await state.clear()
        await callback.answer(messages.notifications["user_blocked"], show_alert=True)
        return

    show_authorship = callback.data == "authorship_yes"

    # Get stored data
    data = await state.get_data()

    submission_service = get_submission_service()
    user_service = get_user_service()
    rate_limit_service = get_rate_limit_service()

    # Authoritative, race-free rate-limit enforcement.
    allowed, _ = await rate_limit_service.try_acquire(callback.from_user.id)
    if not allowed:
        await state.clear()
        await callback.answer(
            messages.user["limit_exceeded"].format(
                limit=config.rate_limits.submissions_per_day
            ),
            show_alert=True
        )
        return

    submission = await submission_service.create_submission(
        user_id=callback.from_user.id,
        show_authorship=show_authorship,
        user_message_id=data.get('message_id'),
        user_chat_id=data.get('chat_id'),
        text_content=data.get('text'),
        has_media=data.get('has_media', False)
    )

    # Increment lifetime submission counter
    await user_service.increment_submission_count(callback.from_user.id)

    # Send to admin chat for moderation
    from bot.handlers.admin_handlers import present_submission_to_admins
    delivered = await present_submission_to_admins(submission.submission_id, callback.bot)

    # Clear state
    await state.clear()

    if delivered:
        await callback.message.answer(messages.user["submission_accepted"])
    else:
        # The submission is saved (status PENDING) and will be surfaced on the
        # next recovery run, but tell the user it didn't reach moderators now.
        await callback.message.answer(messages.user["error_occurred"])

    await callback.answer()

    logger.info(
        f"User {callback.from_user.id} submitted content",
        extra={'user_id': callback.from_user.id}
    )
