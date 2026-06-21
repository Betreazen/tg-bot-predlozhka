"""User notification service."""

import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.config import config_loader

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications to users."""
    
    def __init__(self):
        """Initialize notification service."""

    @property
    def messages(self):
        """Current messages config (read live so reload() takes effect)."""
        return config_loader.load_messages()
    
    async def notify_approved_and_published(self, user_id: int, bot: Bot) -> bool:
        """Notify user that submission was approved and published.
        
        Args:
            user_id: User ID
            bot: Bot instance
            
        Returns:
            True if notification sent successfully
        """
        text = self.messages.notifications["approved_and_published"]
        
        # Add "Suggest Content" button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Предложить ещё контент",
                    callback_data="suggest_content"
                )
            ]
        ])
        
        return await self._send_notification(user_id, text, bot, keyboard)
    
    async def notify_approved_only(self, user_id: int, bot: Bot) -> bool:
        """Notify user that submission was approved but not published.
        
        Args:
            user_id: User ID
            bot: Bot instance
            
        Returns:
            True if notification sent successfully
        """
        text = self.messages.notifications["approved_only"]
        
        # Add "Suggest Content" button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Предложить контент",
                    callback_data="suggest_content"
                )
            ]
        ])
        
        return await self._send_notification(user_id, text, bot, keyboard)
    
    async def notify_rejected(self, user_id: int, bot: Bot) -> bool:
        """Notify user that submission was rejected.
        
        Args:
            user_id: User ID
            bot: Bot instance
            
        Returns:
            True if notification sent successfully
        """
        text = self.messages.notifications["rejected"]
        
        # Add "Try Again" button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Попробовать снова",
                    callback_data="suggest_content"
                )
            ]
        ])
        
        return await self._send_notification(user_id, text, bot, keyboard)
    
    async def notify_user_blocked(self, user_id: int, bot: Bot) -> bool:
        """Notify user that they were blocked.
        
        Args:
            user_id: User ID
            bot: Bot instance
            
        Returns:
            True if notification sent successfully
        """
        text = self.messages.notifications["user_blocked"]
        return await self._send_notification(user_id, text, bot)
    
    async def notify_user_unblocked(self, user_id: int, bot: Bot) -> bool:
        """Notify user that they were unblocked.
        
        Args:
            user_id: User ID
            bot: Bot instance
            
        Returns:
            True if notification sent successfully
        """
        text = self.messages.notifications["user_unblocked"]
        return await self._send_notification(user_id, text, bot)
    
    async def _send_notification(self, user_id: int, text: str, bot: Bot, keyboard: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Send notification to user.
        
        Args:
            user_id: User ID
            text: Notification text
            bot: Bot instance
            keyboard: Optional inline keyboard
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await bot.send_message(user_id, text, reply_markup=keyboard)
            logger.info(f"Notification sent to user {user_id}", extra={'user_id': user_id})
            return True
        except Exception as e:
            logger.error(
                f"Failed to send notification to user {user_id}: {e}",
                extra={'user_id': user_id}
            )
            return False


# Global notification service instance
notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get global notification service instance.
    
    Returns:
        NotificationService instance
    """
    global notification_service
    if notification_service is None:
        notification_service = NotificationService()
    return notification_service
