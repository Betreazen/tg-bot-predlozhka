"""Admin moderation handlers."""

import logging
import uuid
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.models.database import SubmissionStatus, ActionType
from bot.services.user_service import get_user_service
from bot.services.submission_service import get_submission_service
from bot.services.decision_manager import get_decision_manager, LockNotAcquiredError, AlreadyDecidedError
from bot.services.publication_service import get_publication_service
from bot.services.notification_service import get_notification_service
from bot.services.rate_limit import get_rate_limit_service
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin.
    
    Args:
        user_id: User ID to check
        
    Returns:
        True if admin, False otherwise
    """
    return config_loader.is_admin(user_id)


def get_message_text_or_caption(message: Message) -> str:
    """Get text or caption from message.
    
    Args:
        message: Message object
        
    Returns:
        Text or caption content, or empty string
    """
    return message.caption if message.caption else (message.text or "")


async def update_admin_message_with_decision(
    bot: Bot,
    chat_id: int,
    message_id: int,
    current_message: Message,
    decision_text: str,
    moderator: str
) -> None:
    """Update admin message with decision footer.
    
    Args:
        bot: Bot instance
        chat_id: Chat ID
        message_id: Message ID to update
        current_message: Current message object
        decision_text: Decision description
        moderator: Moderator username or ID
    """
    messages = config_loader.load_messages()
    decision_footer = messages.admin["decision_made"].format(
        decision=decision_text,
        moderator=moderator,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    
    try:
        # First remove the keyboard
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
        
        # Try to add decision footer - first try caption (for media), then text
        current_text = get_message_text_or_caption(current_message)
        new_text = current_text + decision_footer
        
        try:
            # Try editing as caption first (for media messages)
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=new_text
            )
        except Exception:
            # If that fails, try editing as text
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_text
            )
    except Exception as e:
        logger.error(f"Failed to update admin message: {e}", exc_info=True)


async def present_submission_to_admins(
    submission_id: uuid.UUID,
    bot: Bot
) -> None:
    """Present submission in admin chat with action buttons.
    
    Args:
        submission_id: Submission UUID
        bot: Bot instance
    """
    submission_service = get_submission_service()
    user_service = get_user_service()
    config = config_loader.load_config()
    messages = config_loader.load_messages()
    
    # Get submission and user
    submission = await submission_service.get_submission(submission_id)
    if not submission:
        logger.error(f"Submission {submission_id} not found")
        return
    
    user = await user_service.get_user(submission.user_id)
    if not user:
        logger.error(f"User {submission.user_id} not found")
        return
    
    # Build header message
    user_info = f"@{user.username}" if user.username else f"ID: {user.user_id}"
    blocked_status = messages.admin["blocked_indicator"] if user.is_blocked else ""
    authorship_info = messages.admin["authorship_yes"] if submission.show_authorship else messages.admin["authorship_no"]
    
    header = messages.admin["submission_header"].format(
        submission_number=user.total_submissions_count,
        user_info=user_info,
        total_submissions=user.total_submissions_count,
        timestamp=submission.submission_timestamp.strftime("%Y-%m-%d %H:%M"),
        blocked_status=blocked_status,
        note_section="",
        authorship_info=authorship_info
    )
    
    # Create inline keyboard with shortened callback data
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["approve_publish"],
                callback_data=f"adm_app_pub:{str(submission_id)[:8]}"
            )
        ],
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["approve_only"],
                callback_data=f"adm_app:{str(submission_id)[:8]}"
            ),
            InlineKeyboardButton(
                text=messages.admin["buttons"]["reject"],
                callback_data=f"adm_rej:{str(submission_id)[:8]}"
            )
        ],
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["block_user"] if not user.is_blocked else messages.admin["buttons"]["unblock_user"],
                callback_data=f"adm_blk:{submission.user_id}" if not user.is_blocked else f"adm_unblk:{submission.user_id}"
            )
        ]
    ])
    
    # Store submission ID mapping in a comment for reference
    submission_id_short = str(submission_id)[:8]
    
    # Send or copy message to admin chat
    admin_chat_id = config.telegram.admin_chat_id
    
    try:
        # Check if submission has media or just text
        has_media = submission.has_media and submission.user_message_id and submission.user_chat_id
        
        if has_media:
            # For media messages: copy the message with caption
            caption_text = header
            if submission.text_content:
                caption_text += f"\n\n{submission.text_content}"
            
            # Add submission ID reference at the end
            caption_text += f"\n\n[ID: {submission_id_short}]"
            
            sent_message = await bot.copy_message(
                chat_id=admin_chat_id,
                from_chat_id=submission.user_chat_id,
                message_id=submission.user_message_id,
                caption=caption_text,
                reply_markup=keyboard
            )
        else:
            # For text-only messages: send as regular text message
            message_text = header
            if submission.text_content:
                message_text += f"\n\n{submission.text_content}"
            message_text += f"\n\n[ID: {submission_id_short}]"
            
            sent_message = await bot.send_message(
                chat_id=admin_chat_id,
                text=message_text,
                reply_markup=keyboard
            )
        
        # Store admin chat message ID
        await submission_service.set_admin_chat_message_id(
            submission_id,
            sent_message.message_id
        )
        
        logger.info(
            f"Submission {submission_id} presented to admins",
            extra={'submission_id': str(submission_id)}
        )
        
    except Exception as e:
        logger.error(f"Failed to present submission to admins: {e}", exc_info=True)


@router.callback_query(F.data.startswith("adm_app_pub:"))
async def handle_approve_publish(callback: CallbackQuery, bot: Bot) -> None:
    """Handle approve and publish decision.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Extract short ID from callback data and find full submission
    short_id = callback.data.split(":")[1]
    submission_service = get_submission_service()
    submission = await submission_service.get_submission_by_short_id(short_id)
    
    if not submission:
        await callback.answer("❌ Предложка не найдена", show_alert=True)
        return
    
    messages = config_loader.load_messages()
    
    # Create confirmation keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["confirm"],
                callback_data=f"adm_conf_pub:{short_id}"
            ),
            InlineKeyboardButton(
                text=messages.admin["buttons"]["cancel"],
                callback_data=f"adm_cancel_pub:{short_id}"
            )
        ]
    ])
    
    # Edit the original message to show confirmation - replace keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(messages.admin["confirm_approve_publish"])
    except Exception as e:
        logger.error(f"Failed to edit message: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("adm_conf_pub:"))
async def confirm_approve_publish(callback: CallbackQuery, bot: Bot) -> None:
    """Confirm and execute approve+publish decision.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Get submission by short ID
    short_id = callback.data.split(":")[1]
    submission_service = get_submission_service()
    submission = await submission_service.get_submission_by_short_id(short_id)
    
    if not submission:
        await callback.answer("❌ Предложка не найдена", show_alert=True)
        return
    
    messages = config_loader.load_messages()
    decision_manager = get_decision_manager()
    config = config_loader.load_config()
    
    try:
        # Make decision with locking - this checks if already processed
        success = await decision_manager.make_decision(
            submission.submission_id,
            'approve_publish',
            callback.from_user.id
        )
        
        if success:
            # Schedule publication FIRST
            publication_service = get_publication_service()
            await publication_service.schedule_publication(submission.submission_id, bot)
            
            # Send notification to user BEFORE updating admin message
            notification_service = get_notification_service()
            await notification_service.notify_approved_and_published(submission.user_id, bot)
            
            # Update admin message with decision footer (removes keyboard)
            await update_admin_message_with_decision(
                bot,
                config.telegram.admin_chat_id,
                submission.message_id_in_admin_chat,
                callback.message,
                "Принято и запланировано к публикации",
                callback.from_user.username or str(callback.from_user.id)
            )
            
            await callback.answer("✅ Принято и запланировано к публикации")
            
    except LockNotAcquiredError:
        await callback.answer(messages.admin["processing_by_another"], show_alert=True)
    except AlreadyDecidedError:
        await callback.answer(messages.admin["already_processed"], show_alert=True)
    except Exception as e:
        logger.error(f"Error in approve_publish: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при обработке", show_alert=True)


@router.callback_query(F.data == "adm_cancel")
async def handle_cancel(callback: CallbackQuery) -> None:
    """Handle cancel button.
    
    Args:
        callback: Callback query
    """
    try:
        await callback.message.delete()
        await callback.answer("❌ Отменено")
    except Exception as e:
        logger.error(f"Error in cancel: {e}", exc_info=True)
        await callback.answer("✅ Отменено")


@router.callback_query(F.data.startswith("adm_cancel_pub:"))
async def handle_cancel_publish(callback: CallbackQuery, bot: Bot) -> None:
    """Handle cancel publish - restore original buttons.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Get submission by short ID
    short_id = callback.data.split(":")[1]
    submission_service = get_submission_service()
    submission = await submission_service.get_submission_by_short_id(short_id)
    
    if not submission:
        await callback.answer("❌ Предложка не найдена", show_alert=True)
        return
    
    # Get user info to rebuild buttons
    user_service = get_user_service()
    user = await user_service.get_user(submission.user_id)
    
    if not user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    messages = config_loader.load_messages()
    
    # Rebuild original keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["approve_publish"],
                callback_data=f"adm_app_pub:{short_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["approve_only"],
                callback_data=f"adm_app:{short_id}"
            ),
            InlineKeyboardButton(
                text=messages.admin["buttons"]["reject"],
                callback_data=f"adm_rej:{short_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=messages.admin["buttons"]["block_user"] if not user.is_blocked else messages.admin["buttons"]["unblock_user"],
                callback_data=f"adm_blk:{submission.user_id}" if not user.is_blocked else f"adm_unblk:{submission.user_id}"
            )
        ]
    ])
    
    # Restore original keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("❌ Отменено")
    except Exception as e:
        logger.error(f"Failed to restore keyboard: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("adm_app:"))
async def handle_approve_only(callback: CallbackQuery, bot: Bot) -> None:
    """Handle approve without publish decision.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Get submission by short ID
    short_id = callback.data.split(":")[1]
    submission_service = get_submission_service()
    submission = await submission_service.get_submission_by_short_id(short_id)
    
    if not submission:
        await callback.answer("❌ Предложка не найдена", show_alert=True)
        return
    
    messages = config_loader.load_messages()
    decision_manager = get_decision_manager()
    config = config_loader.load_config()
    
    try:
        # Make decision with locking
        success = await decision_manager.make_decision(
            submission.submission_id,
            'approve_only',
            callback.from_user.id
        )
        
        if success:
            # Send notification BEFORE updating admin UI
            notification_service = get_notification_service()
            await notification_service.notify_approved_only(submission.user_id, bot)
            
            # Update admin message with decision footer (removes keyboard)
            await update_admin_message_with_decision(
                bot,
                config.telegram.admin_chat_id,
                submission.message_id_in_admin_chat,
                callback.message,
                "Принято без публикации",
                callback.from_user.username or str(callback.from_user.id)
            )
            
            await callback.answer("✅ Принято без публикации")
            
    except LockNotAcquiredError:
        await callback.answer(messages.admin["processing_by_another"], show_alert=True)
    except AlreadyDecidedError:
        await callback.answer(messages.admin["already_processed"], show_alert=True)
    except Exception as e:
        logger.error(f"Error in approve_only: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("adm_rej:"))
async def handle_reject(callback: CallbackQuery, bot: Bot) -> None:
    """Handle reject decision.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Get submission by short ID
    short_id = callback.data.split(":")[1]
    submission_service = get_submission_service()
    submission = await submission_service.get_submission_by_short_id(short_id)
    
    if not submission:
        await callback.answer("❌ Предложка не найдена", show_alert=True)
        return
    
    messages = config_loader.load_messages()
    decision_manager = get_decision_manager()
    config = config_loader.load_config()
    
    try:
        # Make decision with locking
        success = await decision_manager.make_decision(
            submission.submission_id,
            'reject',
            callback.from_user.id
        )
        
        if success:
            # Send notification BEFORE updating admin UI
            notification_service = get_notification_service()
            await notification_service.notify_rejected(submission.user_id, bot)
            
            # Update admin message with decision footer (removes keyboard)
            await update_admin_message_with_decision(
                bot,
                config.telegram.admin_chat_id,
                submission.message_id_in_admin_chat,
                callback.message,
                "Отклонено",
                callback.from_user.username or str(callback.from_user.id)
            )
            
            await callback.answer("❌ Отклонено")
            
    except LockNotAcquiredError:
        await callback.answer(messages.admin["processing_by_another"], show_alert=True)
    except AlreadyDecidedError:
        await callback.answer(messages.admin["already_processed"], show_alert=True)
    except Exception as e:
        logger.error(f"Error in reject: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("adm_blk:"))
async def handle_block_user(callback: CallbackQuery, bot: Bot) -> None:
    """Handle user blocking.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    parts = callback.data.split(":")
    user_id = int(parts[1])
    
    user_service = get_user_service()
    success = await user_service.block_user(user_id)
    
    if success:
        notification_service = get_notification_service()
        await notification_service.notify_user_blocked(user_id, bot)
        await callback.answer("🚫 Пользователь заблокирован")
    else:
        await callback.answer("❌ Ошибка блокировки", show_alert=True)


@router.callback_query(F.data.startswith("adm_unblk:"))
async def handle_unblock_user(callback: CallbackQuery, bot: Bot) -> None:
    """Handle user unblocking.
    
    Args:
        callback: Callback query
        bot: Bot instance
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    parts = callback.data.split(":")
    user_id = int(parts[1])
    
    user_service = get_user_service()
    success = await user_service.unblock_user(user_id)
    
    if success:
        notification_service = get_notification_service()
        await notification_service.notify_user_unblocked(user_id, bot)
        await callback.answer("✅ Пользователь разблокирован")
    else:
        await callback.answer("❌ Ошибка разблокировки", show_alert=True)



