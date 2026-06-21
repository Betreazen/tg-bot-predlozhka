"""User management service."""

import logging
from typing import Optional

from sqlalchemy import select, update

from bot.models.database import User
from bot.utils.database import get_db_manager
from bot.utils.time import utcnow

logger = logging.getLogger(__name__)


class UserService:
    """User management service."""

    def __init__(self):
        """Initialize user service."""
        self.db = get_db_manager()

    async def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Get existing user or create new one.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User first name
            last_name: User last name

        Returns:
            User instance
        """
        async with self.db.session() as session:
            # Try to get existing user
            stmt = select(User).where(User.user_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                # Only overwrite profile fields when Telegram actually provides
                # them, so we never clobber known data with None.
                if username is not None:
                    user.username = username
                if first_name is not None:
                    user.first_name = first_name
                if last_name is not None:
                    user.last_name = last_name
                user.last_interaction_timestamp = utcnow()
                logger.debug(f"Updated user {user_id}", extra={'user_id': user_id})
            else:
                # Create new user
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    registration_timestamp=utcnow(),
                    last_interaction_timestamp=utcnow()
                )
                session.add(user)
                logger.info(f"Created new user {user_id}", extra={'user_id': user_id})

            await session.commit()
            await session.refresh(user)
            return user

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: Telegram user ID

        Returns:
            User instance or None
        """
        async with self.db.session() as session:
            stmt = select(User).where(User.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def is_blocked(self, user_id: int) -> bool:
        """Check whether a user is blocked.

        Args:
            user_id: Telegram user ID

        Returns:
            True if the user exists and is blocked, False otherwise.
        """
        async with self.db.session() as session:
            stmt = select(User.is_blocked).where(User.user_id == user_id)
            result = await session.execute(stmt)
            return bool(result.scalar_one_or_none())

    async def block_user(self, user_id: int) -> bool:
        """Block user.

        Args:
            user_id: Telegram user ID

        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(User)
                .where(User.user_id == user_id)
                .values(is_blocked=True)
            )
            result = await session.execute(stmt)
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"User {user_id} blocked", extra={'user_id': user_id})
            return success

    async def unblock_user(self, user_id: int) -> bool:
        """Unblock user.

        Args:
            user_id: Telegram user ID

        Returns:
            True if successful
        """
        async with self.db.session() as session:
            stmt = (
                update(User)
                .where(User.user_id == user_id)
                .values(is_blocked=False)
            )
            result = await session.execute(stmt)
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"User {user_id} unblocked", extra={'user_id': user_id})
            return success

    async def increment_submission_count(self, user_id: int) -> None:
        """Atomically increment total submission count for user.

        Args:
            user_id: Telegram user ID
        """
        async with self.db.session() as session:
            stmt = (
                update(User)
                .where(User.user_id == user_id)
                .values(total_submissions_count=User.total_submissions_count + 1)
            )
            await session.execute(stmt)
            await session.commit()

    async def get_usernames(self, user_ids: list[int]) -> dict[int, Optional[str]]:
        """Get a mapping of user_id -> username for the given IDs.

        Args:
            user_ids: List of Telegram user IDs

        Returns:
            Dict mapping user_id to username (or None).
        """
        if not user_ids:
            return {}
        async with self.db.session() as session:
            stmt = select(User.user_id, User.username).where(User.user_id.in_(user_ids))
            result = await session.execute(stmt)
            return {row.user_id: row.username for row in result}


# Global user service instance
user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """Get global user service instance.

    Returns:
        UserService instance
    """
    global user_service
    if user_service is None:
        user_service = UserService()
    return user_service
