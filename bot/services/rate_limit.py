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
        self.redis = get_redis_manager()

    @property
    def config(self):
        """Current config (read live so reload() takes effect)."""
        return config_loader.load_config()

    @property
    def timezone(self):
        """Configured timezone object."""
        return pytz.timezone(self.config.rate_limits.timezone)

    @property
    def limit(self) -> int:
        """Daily submission limit."""
        return self.config.rate_limits.submissions_per_day

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

    def _local_midnight_utc(self) -> datetime:
        """Get the most recent local midnight expressed as naive UTC.

        Returns:
            Naive UTC datetime of the start of the current local day.
        """
        now_local = datetime.now(self.timezone)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(pytz.utc).replace(tzinfo=None)

    async def check_limit(self, user_id: int) -> tuple[bool, int]:
        """Check (read-only) if user is under the rate limit.

        Note:
            This is advisory for early UX feedback. The authoritative,
            race-free enforcement is :meth:`try_acquire`.

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
            return count < self.limit, count
        except Exception as e:
            logger.error(f"Rate limit check failed, falling back to DB: {e}",
                         extra={'user_id': user_id})
            count = await self._db_count(user_id)
            return count < self.limit, count

    async def try_acquire(self, user_id: int) -> tuple[bool, int]:
        """Atomically reserve one submission slot for today.

        Increments first, then rolls back if the limit would be exceeded, so
        concurrent flows cannot bypass the limit (no check-then-act race).

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (allowed, count_after). On Redis failure, falls back to a
            best-effort database count.
        """
        client = self.redis.get_client()
        key = self._get_user_key(user_id)

        try:
            new_count = await client.incr(key)
            if new_count == 1:
                await client.expire(key, self._get_seconds_until_midnight())

            if new_count > self.limit:
                # Roll back the speculative increment.
                await client.decr(key)
                return False, self.limit

            logger.info(
                f"Rate slot acquired for user {user_id}: {new_count}/{self.limit}",
                extra={'user_id': user_id}
            )
            return True, new_count
        except Exception as e:
            logger.error(f"Rate limit acquire failed, falling back to DB: {e}",
                         extra={'user_id': user_id})
            # Fail-closed using the database count so Redis downtime cannot
            # turn into an unlimited-submission window.
            count = await self._db_count(user_id)
            return count < self.limit, count + 1

    async def _db_count(self, user_id: int) -> int:
        """Count today's submissions for a user from the database.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of submissions since local midnight (0 on error).
        """
        try:
            from bot.services.submission_service import get_submission_service
            return await get_submission_service().count_user_submissions_since(
                user_id, self._local_midnight_utc()
            )
        except Exception as e:
            logger.error(f"DB rate-limit fallback failed: {e}", extra={'user_id': user_id})
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
            return await self._db_count(user_id)

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
