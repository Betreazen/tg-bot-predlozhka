"""Statistics display handlers."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command

from bot.services.statistics_service import get_statistics_service
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


def format_statistics_message(stats: dict, messages: dict) -> str:
    """Format statistics into display message.
    
    Args:
        stats: Statistics dictionary
        messages: Messages configuration
        
    Returns:
        Formatted statistics text
    """
    # Get month name in Russian
    month_names_ru = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    month_name_ru = month_names_ru[stats['month'] - 1]
    period_str = f"{month_name_ru} {stats['year']}"
    
    # Build message
    text_parts = [
        messages.statistics["title"].format(period=period_str),
        "",
        messages.statistics["submissions_total"].format(count=stats['total_submissions']),
        messages.statistics["submissions_approved"].format(count=stats['approved']),
        messages.statistics["submissions_published"].format(count=stats['published']),
        messages.statistics["submissions_rejected"].format(count=stats['rejected']),
        "",
        messages.statistics["unique_users"].format(count=stats['unique_users']),
        messages.statistics["new_users"].format(count=stats['new_users']),
        messages.statistics["blocked_users"].format(count=stats['blocked_users']),
    ]
    
    # Add rates
    if stats['total_submissions'] > 0:
        text_parts.append("")
        text_parts.append(messages.statistics["rates"].format(
            approval_rate=stats['approval_rate'],
            publication_rate=stats['publication_rate'],
            rejection_rate=stats['rejection_rate']
        ))
    
    # Add admin performance
    if stats['admin_stats']:
        text_parts.append("")
        text_parts.append(messages.statistics["admin_performance"])
        for admin in stats['admin_stats']:
            text_parts.append(messages.statistics["admin_line"].format(
                username=admin['username'],
                count=admin['decision_count']
            ))
    
    return "\n".join(text_parts)


def create_statistics_keyboard(year: int, month: int, messages: dict) -> InlineKeyboardMarkup:
    """Create inline keyboard for statistics navigation.
    
    Args:
        year: Current year
        month: Current month
        messages: Messages configuration
        
    Returns:
        InlineKeyboardMarkup with navigation buttons
    """
    # Calculate prev/next month
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    current_year, current_month = get_statistics_service().current_year_month()

    # Don't show next button if we're at current month
    show_next = not (year == current_year and month == current_month)
    
    keyboard = []
    
    # Navigation row
    nav_row = [
        InlineKeyboardButton(
            text=messages.statistics["navigation"]["prev_month"],
            callback_data=f"stats:{prev_year}:{prev_month}"
        )
    ]
    
    if show_next:
        nav_row.append(
            InlineKeyboardButton(
                text=messages.statistics["navigation"]["next_month"],
                callback_data=f"stats:{next_year}:{next_month}"
            )
        )
    
    keyboard.append(nav_row)
    
    # Current month button
    if not (year == current_year and month == current_month):
        keyboard.append([
            InlineKeyboardButton(
                text=messages.statistics["navigation"]["current_month"],
                callback_data=f"stats:{current_year}:{current_month}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Handle /stats command.
    
    Args:
        message: Incoming message
    """
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Только для администраторов")
        return
    
    statistics_service = get_statistics_service()
    messages = config_loader.load_messages()

    year, month = statistics_service.current_year_month()

    try:
        # Get statistics for current month
        stats = await statistics_service.get_monthly_stats(year, month)

        # Format message
        text = format_statistics_message(stats, messages)

        # Create keyboard
        keyboard = create_statistics_keyboard(year, month, messages)
        
        # Send message
        await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}", exc_info=True)
        await message.answer("❌ Ошибка получения статистики")


@router.callback_query(F.data == "show_statistics")
async def show_current_statistics(callback: CallbackQuery) -> None:
    """Show current month statistics.
    
    Args:
        callback: Callback query
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return

    year, month = get_statistics_service().current_year_month()
    await show_statistics_for_month(callback, year, month)


@router.callback_query(F.data.startswith("stats:"))
async def show_statistics_handler(callback: CallbackQuery) -> None:
    """Show statistics for specific month.
    
    Args:
        callback: Callback query
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Только для администраторов", show_alert=True)
        return
    
    # Parse year and month from callback data
    parts = callback.data.split(":")
    year = int(parts[1])
    month = int(parts[2])
    
    await show_statistics_for_month(callback, year, month)


async def show_statistics_for_month(callback: CallbackQuery, year: int, month: int) -> None:
    """Show statistics for specified month.
    
    Args:
        callback: Callback query
        year: Year
        month: Month (1-12)
    """
    statistics_service = get_statistics_service()
    messages = config_loader.load_messages()
    
    try:
        # Get statistics
        stats = await statistics_service.get_monthly_stats(year, month)
        
        # Format message
        text = format_statistics_message(stats, messages)
        
        # Create keyboard
        keyboard = create_statistics_keyboard(year, month, messages)
        
        # Edit or send message
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}", exc_info=True)
        await callback.answer("❌ Ошибка получения статистики", show_alert=True)
