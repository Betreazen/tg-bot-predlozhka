"""Decision management with Redis locking."""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from bot.models.database import SubmissionStatus, ActionType, AdminActionLog
from bot.services.submission_service import get_submission_service
from bot.utils.database import get_db_manager
from bot.utils.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)


class LockNotAcquiredError(Exception):
    """Raised when lock cannot be acquired."""
    pass


class AlreadyDecidedError(Exception):
    """Raised when submission already has a decision."""
    pass


class DecisionManager:
    """Manages moderation decisions with distributed locking."""
    
    def __init__(self):
        """Initialize decision manager."""
        self.redis = get_redis_manager()
        self.submission_service = get_submission_service()
        self.lock_timeout = 300  # 5 minutes
    
    @asynccontextmanager
    async def acquire_lock(self, submission_id: uuid.UUID):
        """Acquire distributed lock for submission.
        
        Args:
            submission_id: Submission UUID
            
        Yields:
            None
            
        Raises:
            LockNotAcquiredError: If lock cannot be acquired
        """
        lock_key = f"decision_lock:{submission_id}"
        client = self.redis.get_client()
        
        # Try to acquire lock
        acquired = await client.set(lock_key, "1", nx=True, ex=self.lock_timeout)
        
        if not acquired:
            raise LockNotAcquiredError("Another admin is processing this submission")
        
        try:
            yield
        finally:
            try:
                await client.delete(lock_key)
            except Exception as e:
                logger.error(f"Failed to release lock: {e}")
    
    async def make_decision(
        self,
        submission_id: uuid.UUID,
        decision_type: str,
        moderator_id: int
    ) -> bool:
        """Make moderation decision with locking.
        
        Args:
            submission_id: Submission UUID
            decision_type: Decision type (approve_publish, approve_only, reject)
            moderator_id: Moderator user ID
            
        Returns:
            True if decision made successfully
            
        Raises:
            LockNotAcquiredError: If another admin is processing
            AlreadyDecidedError: If already decided
        """
        async with self.acquire_lock(submission_id):
            # Check if already decided
            submission = await self.submission_service.get_submission(submission_id)
            
            if not submission:
                logger.error(f"Submission {submission_id} not found")
                return False
            
            if submission.status != SubmissionStatus.PENDING:
                raise AlreadyDecidedError("Submission already processed")
            
            # Map decision type to status
            status_map = {
                'approve_publish': SubmissionStatus.APPROVED,
                'approve_only': SubmissionStatus.ACCEPTED_NOT_PUBLISHED,
                'reject': SubmissionStatus.REJECTED
            }
            
            new_status = status_map.get(decision_type)
            if not new_status:
                logger.error(f"Invalid decision type: {decision_type}")
                return False
            
            # Update submission status
            success = await self.submission_service.update_status(
                submission_id,
                new_status,
                moderator_id
            )
            
            if success:
                # Log admin action
                await self._log_action(
                    action_type=ActionType.APPROVE_PUBLISH if decision_type == 'approve_publish'
                    else ActionType.APPROVE_ONLY if decision_type == 'approve_only'
                    else ActionType.REJECT,
                    admin_user_id=moderator_id,
                    submission_id=submission_id,
                    target_user_id=submission.user_id
                )
                
                logger.info(
                    f"Decision made: {decision_type} by admin {moderator_id}",
                    extra={'submission_id': str(submission_id), 'user_id': moderator_id}
                )
            
            return success
    
    async def cancel_publication(self, submission_id: uuid.UUID, admin_id: int) -> bool:
        """Cancel scheduled publication.
        
        Args:
            submission_id: Submission UUID
            admin_id: Admin user ID
            
        Returns:
            True if cancelled successfully
        """
        submission = await self.submission_service.get_submission(submission_id)
        
        if not submission or submission.status != SubmissionStatus.SCHEDULED:
            return False
        
        # Update status to approved (not published)
        success = await self.submission_service.update_status(
            submission_id,
            SubmissionStatus.ACCEPTED_NOT_PUBLISHED,
            admin_id
        )
        
        if success:
            await self._log_action(
                action_type=ActionType.CANCEL_PUBLICATION,
                admin_user_id=admin_id,
                submission_id=submission_id,
                target_user_id=submission.user_id
            )
        
        return success
    
    async def _log_action(
        self,
        action_type: ActionType,
        admin_user_id: int,
        submission_id: Optional[uuid.UUID] = None,
        target_user_id: Optional[int] = None,
        additional_context: Optional[str] = None
    ) -> None:
        """Log admin action to database.
        
        Args:
            action_type: Type of action
            admin_user_id: Admin user ID
            submission_id: Submission UUID (optional)
            target_user_id: Target user ID (optional)
            additional_context: Additional context (optional)
        """
        async with get_db_manager().session() as session:
            log_entry = AdminActionLog(
                action_type=action_type,
                admin_user_id=admin_user_id,
                submission_id=submission_id,
                target_user_id=target_user_id,
                additional_context=additional_context
            )
            session.add(log_entry)
            await session.commit()


# Global decision manager instance
decision_manager: Optional[DecisionManager] = None


def get_decision_manager() -> DecisionManager:
    """Get global decision manager instance.
    
    Returns:
        DecisionManager instance
    """
    global decision_manager
    if decision_manager is None:
        decision_manager = DecisionManager()
    return decision_manager
