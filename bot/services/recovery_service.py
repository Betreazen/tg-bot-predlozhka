"""Startup recovery service for pending tasks."""

import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot

from bot.models.database import SubmissionStatus
from bot.services.submission_service import get_submission_service
from bot.services.publication_service import get_publication_service
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)


class RecoveryService:
    """Handles recovery of pending tasks on bot startup."""
    
    def __init__(self):
        """Initialize recovery service."""
        self.config = config_loader.load_config()
        self.messages = config_loader.load_messages()
    
    async def recover_pending_tasks(self, bot: Bot) -> None:
        """Recover all pending tasks on startup.
        
        Args:
            bot: Bot instance
        """
        logger.info("Starting recovery of pending tasks...")
        
        # Recover scheduled publications
        await self._recover_scheduled_publications(bot)
        
        # Recover pending submissions (if needed)
        await self._recover_pending_submissions(bot)
        
        # Send recovery notification to admins
        await self._notify_recovery_complete(bot)
        
        logger.info("Task recovery completed")
    
    async def _recover_scheduled_publications(self, bot: Bot) -> None:
        """Recover scheduled publications that weren't executed.
        
        Args:
            bot: Bot instance
        """
        submission_service = get_submission_service()
        publication_service = get_publication_service()
        
        # Get all scheduled submissions
        scheduled = await submission_service.get_scheduled_publications()
        
        logger.info(f"Found {len(scheduled)} scheduled publications to recover")
        
        for submission in scheduled:
            if not submission.scheduled_publication_time:
                continue
            
            # Check if publication time has passed
            now = datetime.utcnow()
            time_diff = (submission.scheduled_publication_time - now).total_seconds()
            
            if time_diff <= 0:
                # Time has passed, publish immediately
                logger.info(
                    f"Publishing overdue submission {submission.submission_id}",
                    extra={'submission_id': str(submission.submission_id)}
                )
                
                try:
                    await publication_service._publish_to_channel(submission, bot)
                except Exception as e:
                    logger.error(
                        f"Failed to publish recovered submission: {e}",
                        extra={'submission_id': str(submission.submission_id)}
                    )
            else:
                # Reschedule with remaining time
                logger.info(
                    f"Rescheduling submission {submission.submission_id} in {time_diff} seconds",
                    extra={'submission_id': str(submission.submission_id)}
                )
                
                # Create new task
                import asyncio
                task = asyncio.create_task(
                    publication_service._publish_after_delay(
                        submission.submission_id,
                        int(time_diff),
                        bot
                    )
                )
                publication_service.scheduled_tasks[str(submission.submission_id)] = task
    
    async def _recover_pending_submissions(self, bot: Bot) -> None:
        """Check for pending submissions that need attention.
        
        Args:
            bot: Bot instance
        """
        submission_service = get_submission_service()
        
        # Get all pending submissions
        pending = await submission_service.get_pending_submissions()
        
        if pending:
            logger.warning(f"Found {len(pending)} pending submissions awaiting moderation")
            
            # Optionally notify admins about pending items
            # This can be useful if bot was down for a while
            if len(pending) > 10:
                admin_chat_id = self.config.telegram.admin_chat_id
                try:
                    await bot.send_message(
                        admin_chat_id,
                        f"⚠️ {len(pending)} предложений ожидают модерации"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify about pending submissions: {e}")
    
    async def _notify_recovery_complete(self, bot: Bot) -> None:
        """Notify admins that recovery is complete.
        
        Args:
            bot: Bot instance
        """
        admin_chat_id = self.config.telegram.admin_chat_id
        restart_message = self.messages.admin.get("bot_restarted", "🔄 Бот перезапущен")
        
        try:
            await bot.send_message(admin_chat_id, restart_message)
            logger.info("Recovery notification sent to admin chat")
        except Exception as e:
            logger.error(f"Failed to send recovery notification: {e}")


# Global recovery service instance
recovery_service: Optional[RecoveryService] = None


def get_recovery_service() -> RecoveryService:
    """Get global recovery service instance.
    
    Returns:
        RecoveryService instance
    """
    global recovery_service
    if recovery_service is None:
        recovery_service = RecoveryService()
    return recovery_service
