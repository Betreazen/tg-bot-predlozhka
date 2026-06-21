"""Startup recovery service for pending tasks."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot

from bot.models.database import SubmissionStatus
from bot.services.submission_service import get_submission_service
from bot.services.publication_service import get_publication_service
from bot.utils.config import config_loader
from bot.utils.time import utcnow

logger = logging.getLogger(__name__)


class RecoveryService:
    """Handles recovery of pending tasks on bot startup."""

    def __init__(self):
        """Initialize recovery service."""

    @property
    def config(self):
        """Current config (read live so reload() takes effect)."""
        return config_loader.load_config()

    @property
    def messages(self):
        """Current messages config."""
        return config_loader.load_messages()

    async def recover_pending_tasks(self, bot: Bot) -> None:
        """Recover all pending tasks on startup.

        Args:
            bot: Bot instance
        """
        logger.info("Starting recovery of pending tasks...")

        # Re-schedule any approved-but-not-yet-scheduled submissions (covers a
        # crash between the decision and scheduling steps).
        await self._recover_approved_submissions(bot)

        # Recover scheduled publications
        await self._recover_scheduled_publications(bot)

        # Recover pending submissions (if needed)
        await self._recover_pending_submissions(bot)
        
        # Send recovery notification to admins
        await self._notify_recovery_complete(bot)
        
        logger.info("Task recovery completed")
    
    async def _recover_approved_submissions(self, bot: Bot) -> None:
        """Schedule submissions stuck in APPROVED (decision saved, not scheduled).

        Args:
            bot: Bot instance
        """
        submission_service = get_submission_service()
        publication_service = get_publication_service()

        approved = await submission_service.get_submissions_by_status(
            SubmissionStatus.APPROVED
        )
        if not approved:
            return

        logger.info(f"Found {len(approved)} approved submissions to schedule")
        for submission in approved:
            await publication_service.schedule_publication(submission.submission_id, bot)

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
            time_diff = (submission.scheduled_publication_time - utcnow()).total_seconds()

            if time_diff <= 0:
                # Time has passed, publish immediately
                logger.info(
                    f"Publishing overdue submission {submission.submission_id}",
                    extra={'submission_id': str(submission.submission_id)}
                )

                try:
                    await publication_service._publish_to_channel(submission, bot)
                except Exception as e:
                    from bot.services.error_handler import get_error_handler
                    await get_error_handler().handle_publication_error(
                        submission.submission_id, e, bot
                    )
            else:
                # Reschedule with remaining time
                logger.info(
                    f"Rescheduling submission {submission.submission_id} in {time_diff} seconds",
                    extra={'submission_id': str(submission.submission_id)}
                )

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
