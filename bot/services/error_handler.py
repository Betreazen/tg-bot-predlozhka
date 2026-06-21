"""Error handling and retry logic."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot

from bot.services.submission_service import get_submission_service
from bot.services.publication_service import get_publication_service
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles errors and implements retry logic."""
    
    def __init__(self):
        """Initialize error handler."""

    @property
    def config(self):
        """Current config (read live so reload() takes effect)."""
        return config_loader.load_config()

    @property
    def messages(self):
        """Current messages config."""
        return config_loader.load_messages()
    
    async def handle_publication_error(
        self,
        submission_id,
        error: Exception,
        bot: Bot
    ) -> None:
        """Handle publication failure with retry logic.
        
        Args:
            submission_id: Submission UUID
            error: Exception that occurred
            bot: Bot instance
        """
        submission_service = get_submission_service()
        
        # Get current retry count
        retry_count = await submission_service.increment_retry_count(submission_id)
        
        logger.error(
            f"Publication error for {submission_id}: {error} (attempt {retry_count})",
            extra={'submission_id': str(submission_id)},
            exc_info=True
        )
        
        # Check if we should retry
        max_retries = self.config.error_handling.max_retry_attempts
        
        if retry_count < max_retries:
            # Schedule retry
            retry_delay = self.config.error_handling.retry_delay_seconds
            logger.info(
                f"Scheduling retry for {submission_id} in {retry_delay} seconds",
                extra={'submission_id': str(submission_id)}
            )
            
            await asyncio.sleep(retry_delay)
            
            # Retry publication
            publication_service = get_publication_service()
            submission = await submission_service.get_submission(submission_id)
            
            if submission:
                try:
                    await publication_service._publish_to_channel(submission, bot)
                except Exception as retry_error:
                    # Recursive call for next retry
                    await self.handle_publication_error(submission_id, retry_error, bot)
        else:
            # Max retries reached
            logger.error(
                f"Max retries ({max_retries}) reached for {submission_id}",
                extra={'submission_id': str(submission_id)}
            )
            
            # Mark as failed
            await submission_service.set_publication_error(submission_id, str(error))
            
            # Notify admins
            await self._notify_admins_of_failure(submission_id, error, retry_count, bot)
    
    async def _notify_admins_of_failure(
        self,
        submission_id,
        error: Exception,
        attempt: int,
        bot: Bot
    ) -> None:
        """Notify administrators of publication failure.
        
        Args:
            submission_id: Submission UUID
            error: Exception that occurred
            attempt: Number of attempts made
            bot: Bot instance
        """
        submission_service = get_submission_service()
        submission = await submission_service.get_submission(submission_id)
        
        if not submission:
            return
        
        # Build error notification message
        from bot.services.user_service import get_user_service
        user_service = get_user_service()
        user = await user_service.get_user(submission.user_id)
        
        username = f"@{user.username}" if user and user.username else f"ID:{submission.user_id}"
        
        error_text = self.messages.admin["publication_error"].format(
            submission_id=str(submission_id),
            username=username,
            error=str(error),
            attempt=attempt,
            max_attempts=self.config.error_handling.max_retry_attempts
        )
        
        # Send to admin chat
        admin_chat_id = self.config.telegram.admin_chat_id
        
        try:
            await bot.send_message(admin_chat_id, error_text)
            logger.info(f"Error notification sent to admin chat for {submission_id}")
        except Exception as e:
            logger.error(f"Failed to notify admins of error: {e}")
    
    async def notify_database_error(self, error: Exception, bot: Bot) -> None:
        """Notify admins of database connection error.
        
        Args:
            error: Exception that occurred
            bot: Bot instance
        """
        error_text = self.messages.admin["database_error"].format(error=str(error))
        await self._send_admin_notification(error_text, bot)
    
    async def notify_redis_error(self, error: Exception, bot: Bot) -> None:
        """Notify admins of Redis connection error.
        
        Args:
            error: Exception that occurred
            bot: Bot instance
        """
        error_text = self.messages.admin["redis_error"].format(error=str(error))
        await self._send_admin_notification(error_text, bot)
    
    async def _send_admin_notification(self, text: str, bot: Bot) -> None:
        """Send notification to admin chat.
        
        Args:
            text: Message text
            bot: Bot instance
        """
        admin_chat_id = self.config.telegram.admin_chat_id
        
        try:
            await bot.send_message(admin_chat_id, text)
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")


# Global error handler instance
error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance.
    
    Returns:
        ErrorHandler instance
    """
    global error_handler
    if error_handler is None:
        error_handler = ErrorHandler()
    return error_handler
