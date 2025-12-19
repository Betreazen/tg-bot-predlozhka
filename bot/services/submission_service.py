"""Submission management service."""

import logging
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update, and_, func, extract, String
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.database import Submission, SubmissionStatus, User
from bot.utils.database import get_db_manager

logger = logging.getLogger(__name__)


class SubmissionService:
    """Submission management service."""
    
    def __init__(self):
        """Initialize submission service."""
        self.db = get_db_manager()
    
    async def create_submission(
        self,
        user_id: int,
        show_authorship: bool,
        user_message_id: Optional[int] = None,
        user_chat_id: Optional[int] = None,
        text_content: Optional[str] = None,
        has_media: bool = False,
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None
    ) -> Submission:
        """Create new submission.
        
        Args:
            user_id: User ID
            show_authorship: Whether to show author
            user_message_id: Original message ID from user
            user_chat_id: User chat ID
            text_content: Text content
            has_media: Whether submission has media
            media_type: Type of media
            media_file_id: Telegram file ID
            
        Returns:
            Created submission
        """
        async with self.db.session() as session:
            submission = Submission(
                submission_id=uuid.uuid4(),
                user_id=user_id,
                show_authorship=show_authorship,
                user_message_id=user_message_id,
                user_chat_id=user_chat_id,
                text_content=text_content,
                has_media=has_media,
                media_type=media_type,
                media_file_id=media_file_id,
                status=SubmissionStatus.PENDING,
                submission_timestamp=datetime.utcnow()
            )
            session.add(submission)
            await session.commit()
            await session.refresh(submission)
            
            logger.info(
                f"Created submission {submission.submission_id}",
                extra={'user_id': user_id, 'submission_id': str(submission.submission_id)}
            )
            
            return submission
    
    async def get_submission(self, submission_id: uuid.UUID) -> Optional[Submission]:
        """Get submission by ID.
        
        Args:
            submission_id: Submission UUID
            
        Returns:
            Submission instance or None
        """
        async with self.db.session() as session:
            stmt = select(Submission).where(Submission.submission_id == submission_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def get_submission_by_short_id(self, short_id: str) -> Optional[Submission]:
        """Get submission by short ID (first 8 chars of UUID).
        
        Args:
            short_id: First 8 characters of submission UUID
            
        Returns:
            Submission instance or None
        """
        async with self.db.session() as session:
            # Convert short ID to pattern for LIKE query
            pattern = f"{short_id}%"
            stmt = select(Submission).where(
                func.cast(Submission.submission_id, String).like(pattern)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    async def update_status(
        self,
        submission_id: uuid.UUID,
        status: SubmissionStatus,
        moderator_id: Optional[int] = None
    ) -> bool:
        """Update submission status.
        
        Args:
            submission_id: Submission UUID
            status: New status
            moderator_id: Moderator user ID
            
        Returns:
            True if successful
        """
        async with self.db.session() as session:
            values = {
                'status': status,
                'decision_timestamp': datetime.utcnow()
            }
            if moderator_id:
                values['moderator_id'] = moderator_id
            
            stmt = (
                update(Submission)
                .where(Submission.submission_id == submission_id)
                .values(**values)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            success = result.rowcount > 0
            if success:
                logger.info(
                    f"Updated submission {submission_id} status to {status.value}",
                    extra={'submission_id': str(submission_id)}
                )
            return success
    
    async def set_admin_chat_message_id(
        self,
        submission_id: uuid.UUID,
        message_id: int
    ) -> bool:
        """Set admin chat message ID.
        
        Args:
            submission_id: Submission UUID
            message_id: Message ID in admin chat
            
        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(Submission)
                .where(Submission.submission_id == submission_id)
                .values(message_id_in_admin_chat=message_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def set_channel_message_id(
        self,
        submission_id: uuid.UUID,
        message_id: int
    ) -> bool:
        """Set channel message ID.
        
        Args:
            submission_id: Submission UUID
            message_id: Message ID in channel
            
        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(Submission)
                .where(Submission.submission_id == submission_id)
                .values(message_id_in_channel=message_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def schedule_publication(
        self,
        submission_id: uuid.UUID,
        scheduled_time: datetime
    ) -> bool:
        """Schedule submission for publication.
        
        Args:
            submission_id: Submission UUID
            scheduled_time: When to publish
            
        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(Submission)
                .where(Submission.submission_id == submission_id)
                .values(
                    scheduled_publication_time=scheduled_time,
                    status=SubmissionStatus.SCHEDULED
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def get_pending_submissions(self) -> List[Submission]:
        """Get all pending submissions.
        
        Returns:
            List of pending submissions
        """
        async with self.db.session() as session:
            stmt = select(Submission).where(Submission.status == SubmissionStatus.PENDING)
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def get_scheduled_publications(self) -> List[Submission]:
        """Get all scheduled publications.
        
        Returns:
            List of scheduled submissions
        """
        async with self.db.session() as session:
            stmt = select(Submission).where(Submission.status == SubmissionStatus.SCHEDULED)
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def increment_retry_count(self, submission_id: uuid.UUID) -> int:
        """Increment publication retry count.
        
        Args:
            submission_id: Submission UUID
            
        Returns:
            New retry count
        """
        async with self.db.session() as session:
            stmt = select(Submission).where(Submission.submission_id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if submission:
                submission.publication_retry_count += 1
                await session.commit()
                return submission.publication_retry_count
            
            return 0
    
    async def set_publication_error(
        self,
        submission_id: uuid.UUID,
        error_message: str
    ) -> bool:
        """Set publication error message.
        
        Args:
            submission_id: Submission UUID
            error_message: Error description
            
        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(Submission)
                .where(Submission.submission_id == submission_id)
                .values(
                    publication_error_message=error_message,
                    status=SubmissionStatus.PUBLICATION_FAILED
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0


# Global submission service instance
submission_service: Optional[SubmissionService] = None


def get_submission_service() -> SubmissionService:
    """Get global submission service instance.
    
    Returns:
        SubmissionService instance
    """
    global submission_service
    if submission_service is None:
        submission_service = SubmissionService()
    return submission_service
