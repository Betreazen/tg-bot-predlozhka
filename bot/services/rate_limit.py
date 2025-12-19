"""Rate limiting service using Redis."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz

from bot.utils.config import config_loader
from bot.utils.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)


class RateLimitService:
    """Rate limiting service for user submissions."""
    
    def __init__(self):
        """Initialize rate limit service."""
        self.config = config_loader.load_config()
        self.redis = get_redis_manager()
        self.timezone = pytz.timezone(self.config.rate_limits.timezone)
    
    def _get_user_key(self, user_id: int) -> str:
        """Get Redis key for user submission counter.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Redis key string
        """
        today = datetime.now(self.timezone).strftime('%Y-%m-%d')
        return f"submission_count:{user_id}:{today}"
    
    def _get_seconds_until_midnight(self) -> int:
        """Get seconds until midnight in configured timezone.
        
        Returns:
            Seconds until midnight
        """
        now = datetime.now(self.timezone)
        tomorrow = now + timedelta(days=1)
        midnight = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        return int((midnight - now).total_seconds())
    
    async def check_limit(self, user_id: int) -> tuple[bool, int]:
        """Check if user has exceeded rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (allowed, current_count)
        """
        client = self.redis.get_client()
        key = self._get_user_key(user_id)
        
        try:
            current_count = await client.get(key)
            count = int(current_count) if current_count else 0
            
            allowed = count < self.config.rate_limits.submissions_per_day
            
            logger.debug(
                f"Rate limit check for user {user_id}: {count}/{self.config.rate_limits.submissions_per_day}",
                extra={'user_id': user_id}
            )
            
            return allowed, count
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}", extra={'user_id': user_id})
            # Allow submission if Redis fails (fallback to database check)
            return True, 0
    
    async def increment_count(self, user_id: int) -> int:
        """Increment user submission count.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            New count value
        """
        client = self.redis.get_client()
        key = self._get_user_key(user_id)
        
        try:
            # Increment counter
            new_count = await client.incr(key)
            
            # Set expiration to midnight if this is first submission today
            if new_count == 1:
                ttl = self._get_seconds_until_midnight()
                await client.expire(key, ttl)
            
            logger.info(
                f"Submission count incremented for user {user_id}: {new_count}",
                extra={'user_id': user_id}
            )
            
            return new_count
        except Exception as e:
            logger.error(f"Failed to increment count: {e}", extra={'user_id': user_id})
            return 0
    
    async def get_count(self, user_id: int) -> int:
        """Get current submission count for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Current submission count
        """
        client = self.redis.get_client()
        key = self._get_user_key(user_id)
        
        try:
            current_count = await client.get(key)
            return int(current_count) if current_count else 0
        except Exception as e:
            logger.error(f"Failed to get count: {e}", extra={'user_id': user_id})
            return 0
    
    async def reset_count(self, user_id: int) -> None:
        """Reset submission count for user (admin function).
        
        Args:
            user_id: Telegram user ID
        """
        client = self.redis.get_client()
        key = self._get_user_key(user_id)
        
        try:
            await client.delete(key)
            logger.info(f"Submission count reset for user {user_id}", extra={'user_id': user_id})
        except Exception as e:
            logger.error(f"Failed to reset count: {e}", extra={'user_id': user_id})


# Global rate limit service instance
rate_limit_service: Optional[RateLimitService] = None


def get_rate_limit_service() -> RateLimitService:
    """Get global rate limit service instance.
    
    Returns:
        RateLimitService instance
    """
    global rate_limit_service
    if rate_limit_service is None:
        rate_limit_service = RateLimitService()
    return rate_limit_service
