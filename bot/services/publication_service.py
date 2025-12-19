"""Publication scheduling and execution service."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Bot
from aiogram.types import Message

from bot.models.database import SubmissionStatus
from bot.services.submission_service import get_submission_service
from bot.services.user_service import get_user_service
from bot.services.notification_service import get_notification_service
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)


class PublicationService:
    """Service for scheduling and executing publications."""
    
    def __init__(self):
        """Initialize publication service."""
        self.config = config_loader.load_config()
        self.messages = config_loader.load_messages()
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
    
    async def schedule_publication(
        self,
        submission_id: uuid.UUID,
        bot: Bot
    ) -> bool:
        """Schedule publication with configured delay.
        
        Args:
            submission_id: Submission UUID
            bot: Bot instance
            
        Returns:
            True if scheduled successfully
        """
        delay_seconds = self.config.publication.delay_minutes * 60
        scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Update database
        submission_service = get_submission_service()
        success = await submission_service.schedule_publication(submission_id, scheduled_time)
        
        if not success:
            logger.error(f"Failed to schedule publication for {submission_id}")
            return False
        
        # Create async task
        task = asyncio.create_task(
            self._publish_after_delay(submission_id, delay_seconds, bot)
        )
        self.scheduled_tasks[str(submission_id)] = task
        
        logger.info(
            f"Publication scheduled for {submission_id} in {delay_seconds} seconds",
            extra={'submission_id': str(submission_id)}
        )
        
        return True
    
    async def cancel_publication(self, submission_id: uuid.UUID) -> bool:
        """Cancel scheduled publication.
        
        Args:
            submission_id: Submission UUID
            
        Returns:
            True if cancelled successfully
        """
        task_key = str(submission_id)
        task = self.scheduled_tasks.get(task_key)
        
        if task:
            task.cancel()
            del self.scheduled_tasks[task_key]
            logger.info(
                f"Publication cancelled for {submission_id}",
                extra={'submission_id': str(submission_id)}
            )
        
        # Update database status
        submission_service = get_submission_service()
        return await submission_service.update_status(
            submission_id,
            SubmissionStatus.ACCEPTED_NOT_PUBLISHED
        )
    
    async def _publish_after_delay(
        self,
        submission_id: uuid.UUID,
        delay_seconds: int,
        bot: Bot
    ) -> None:
        """Wait for delay period then publish.
        
        Args:
            submission_id: Submission UUID
            delay_seconds: Delay in seconds
            bot: Bot instance
        """
        try:
            await asyncio.sleep(delay_seconds)
            
            # Check if still approved
            submission_service = get_submission_service()
            submission = await submission_service.get_submission(submission_id)
            
            if not submission:
                logger.error(f"Submission {submission_id} not found")
                return
            
            if submission.status != SubmissionStatus.SCHEDULED:
                logger.info(
                    f"Publication cancelled or status changed for {submission_id}",
                    extra={'submission_id': str(submission_id)}
                )
                return
            
            # Publish to channel
            await self._publish_to_channel(submission, bot)
            
        except asyncio.CancelledError:
            logger.info(
                f"Publication task cancelled for {submission_id}",
                extra={'submission_id': str(submission_id)}
            )
        except Exception as e:
            logger.error(
                f"Error in publication task: {e}",
                extra={'submission_id': str(submission_id)},
                exc_info=True
            )
        finally:
            # Clean up task reference
            task_key = str(submission_id)
            if task_key in self.scheduled_tasks:
                del self.scheduled_tasks[task_key]
    
    async def _publish_to_channel(self, submission, bot: Bot) -> None:
        """Format and publish content to channel.
        
        Args:
            submission: Submission object
            bot: Bot instance
        """
        try:
            # Build caption/text
            text_parts = []
            
            if submission.text_content:
                text_parts.append(submission.text_content)
            
            # Add authorship if requested
            if submission.show_authorship:
                user_service = get_user_service()
                user = await user_service.get_user(submission.user_id)
                if user and user.username:
                    text_parts.append(f"\n\nАвтор: @{user.username}")
                elif user:
                    text_parts.append(f"\n\nАвтор: {user.first_name or 'Аноним'}")
            
            # Add footer if enabled
            if self.config.publication.include_footer and self.config.publication.footer_text:
                text_parts.append(f"\n\n{self.config.publication.footer_text}")
            
            # Add hashtags if enabled
            if self.config.publication.include_hashtags and self.config.publication.hashtags:
                hashtags = " ".join(self.config.publication.hashtags)
                text_parts.append(f"\n\n{hashtags}")
            
            caption = "".join(text_parts) if text_parts else None
            
            # Send to channel
            channel_id = self.config.telegram.channel_id
            
            # Copy message from user chat if we have the message ID
            if submission.user_message_id and submission.user_chat_id:
                try:
                    sent_message = await bot.copy_message(
                        chat_id=channel_id,
                        from_chat_id=submission.user_chat_id,
                        message_id=submission.user_message_id,
                        caption=caption
                    )
                except Exception as e:
                    logger.warning(f"Failed to copy message, sending as new: {e}")
                    sent_message = await self._send_as_new_message(
                        channel_id,
                        submission,
                        caption,
                        bot
                    )
            else:
                sent_message = await self._send_as_new_message(
                    channel_id,
                    submission,
                    caption,
                    bot
                )
            
            if sent_message:
                # Update submission status
                submission_service = get_submission_service()
                await submission_service.set_channel_message_id(
                    submission.submission_id,
                    sent_message.message_id
                )
                await submission_service.update_status(
                    submission.submission_id,
                    SubmissionStatus.PUBLISHED
                )
                
                logger.info(
                    f"Published submission {submission.submission_id} to channel",
                    extra={'submission_id': str(submission.submission_id)}
                )
            
        except Exception as e:
            logger.error(
                f"Failed to publish submission {submission.submission_id}: {e}",
                extra={'submission_id': str(submission.submission_id)},
                exc_info=True
            )
            await self._handle_publication_error(submission, str(e), bot)
    
    async def _send_as_new_message(
        self,
        channel_id: int,
        submission,
        caption: Optional[str],
        bot: Bot
    ) -> Optional[Message]:
        """Send submission as new message to channel.
        
        Args:
            channel_id: Channel ID
            submission: Submission object
            caption: Message caption
            bot: Bot instance
            
        Returns:
            Sent message or None
        """
        # If we only have text content
        if caption and not submission.has_media:
            return await bot.send_message(channel_id, caption)
        
        # If we have media but no file_id stored, we can't send it
        # This is a fallback - ideally we should always have message_id
        if caption:
            return await bot.send_message(channel_id, caption)
        
        return None
    
    async def _handle_publication_error(
        self,
        submission,
        error_message: str,
        bot: Bot
    ) -> None:
        """Handle publication failure.
        
        Args:
            submission: Submission object
            error_message: Error description
            bot: Bot instance
        """
        # Update submission with error
        submission_service = get_submission_service()
        await submission_service.set_publication_error(
            submission.submission_id,
            error_message
        )
        
        # Notify admins in admin chat
        admin_config = self.config.telegram
        error_text = self.messages.admin["publication_error"].format(
            submission_id=str(submission.submission_id),
            username=f"@{submission.user.username}" if hasattr(submission, 'user') and submission.user.username else f"ID: {submission.user_id}",
            error=error_message,
            attempt=1,
            max_attempts=self.config.error_handling.max_retry_attempts
        )
        
        try:
            await bot.send_message(admin_config.admin_chat_id, error_text)
        except Exception as e:
            logger.error(f"Failed to notify admins of publication error: {e}")


# Global publication service instance
publication_service: Optional[PublicationService] = None


def get_publication_service() -> PublicationService:
    """Get global publication service instance.
    
    Returns:
        PublicationService instance
    """
    global publication_service
    if publication_service is None:
        publication_service = PublicationService()
    return publication_service
