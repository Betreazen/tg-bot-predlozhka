"""Statistics aggregation service."""

import logging
from typing import Dict, Any, Optional

from sqlalchemy import select, func, distinct

from bot.models.database import Submission, SubmissionStatus, User
from bot.utils.database import get_db_manager
from bot.utils.config import config_loader
from bot.utils.time import (
    current_local_year_month,
    local_month_to_utc_range,
    local_year_to_utc_range,
)

logger = logging.getLogger(__name__)

# Statuses that count as "approved" (kept or published).
_APPROVED_STATUSES = (
    SubmissionStatus.APPROVED,
    SubmissionStatus.ACCEPTED_NOT_PUBLISHED,
    SubmissionStatus.PUBLISHED,
    SubmissionStatus.SCHEDULED,
)


class StatisticsService:
    """Service for aggregating and calculating statistics."""

    def __init__(self):
        """Initialize statistics service."""
        self.db = get_db_manager()

    @property
    def config(self):
        """Current config (read live so reload() takes effect)."""
        return config_loader.load_config()

    def current_year_month(self) -> tuple[int, int]:
        """Get the current (year, month) in the configured timezone."""
        return current_local_year_month(self.config.rate_limits.timezone)

    async def get_current_month_stats(self) -> Dict[str, Any]:
        """Get statistics for current month.

        Returns:
            Dictionary with statistics
        """
        year, month = self.current_year_month()
        return await self.get_monthly_stats(year, month)

    async def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """Get statistics for specific month.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)

        Returns:
            Dictionary with comprehensive statistics
        """
        tz = self.config.rate_limits.timezone
        start, end = local_month_to_utc_range(year, month, tz)

        async with self.db.session() as session:
            in_period = (
                Submission.submission_timestamp >= start,
                Submission.submission_timestamp < end,
            )

            # Single pass over submissions using conditional aggregation.
            agg_stmt = select(
                func.count(Submission.submission_id),
                func.count(Submission.submission_id).filter(
                    Submission.status.in_(_APPROVED_STATUSES)
                ),
                func.count(Submission.submission_id).filter(
                    Submission.status == SubmissionStatus.PUBLISHED
                ),
                func.count(Submission.submission_id).filter(
                    Submission.status == SubmissionStatus.REJECTED
                ),
                func.count(distinct(Submission.user_id)),
            ).where(*in_period)
            total, approved, published, rejected, unique_users = (
                await session.execute(agg_stmt)
            ).one()

            # User-table aggregates (new users in period + total blocked).
            user_agg_stmt = select(
                func.count(User.user_id).filter(
                    User.registration_timestamp >= start,
                    User.registration_timestamp < end,
                ),
                func.count(User.user_id).filter(User.is_blocked.is_(True)),
            )
            new_users, blocked_users = (await session.execute(user_agg_stmt)).one()

            # Per-admin decision counts.
            admin_stats_stmt = (
                select(
                    Submission.moderator_id,
                    func.count(Submission.submission_id).label('decision_count'),
                )
                .where(*in_period, Submission.moderator_id.isnot(None))
                .group_by(Submission.moderator_id)
            )
            admin_stats_raw = (await session.execute(admin_stats_stmt)).all()

            # Resolve moderator usernames from the users table.
            moderator_ids = [mid for mid, _ in admin_stats_raw]
            username_map = await self._get_usernames(session, moderator_ids)

            admin_stats = [
                {
                    'user_id': moderator_id,
                    'username': username_map.get(moderator_id) or f"ID:{moderator_id}",
                    'decision_count': count,
                }
                for moderator_id, count in admin_stats_raw
            ]

        approval_rate = (approved / total * 100) if total > 0 else 0
        publication_rate = (published / approved * 100) if approved > 0 else 0
        rejection_rate = (rejected / total * 100) if total > 0 else 0

        return {
            'year': year,
            'month': month,
            'period': f"{year}-{month:02d}",
            'total_submissions': total,
            'approved': approved,
            'published': published,
            'rejected': rejected,
            'unique_users': unique_users,
            'new_users': new_users,
            'blocked_users': blocked_users,
            'admin_stats': admin_stats,
            'approval_rate': round(approval_rate, 1),
            'publication_rate': round(publication_rate, 1),
            'rejection_rate': round(rejection_rate, 1),
        }

    async def get_yearly_stats(self, year: int) -> Dict[str, Any]:
        """Get statistics for entire year.

        Args:
            year: Year (e.g., 2024)

        Returns:
            Dictionary with yearly statistics
        """
        tz = self.config.rate_limits.timezone
        start, end = local_year_to_utc_range(year, tz)

        async with self.db.session() as session:
            in_period = (
                Submission.submission_timestamp >= start,
                Submission.submission_timestamp < end,
            )

            agg_stmt = select(
                func.count(Submission.submission_id),
                func.count(Submission.submission_id).filter(
                    Submission.status.in_(_APPROVED_STATUSES)
                ),
                func.count(Submission.submission_id).filter(
                    Submission.status == SubmissionStatus.PUBLISHED
                ),
                func.count(Submission.submission_id).filter(
                    Submission.status == SubmissionStatus.REJECTED
                ),
            ).where(*in_period)
            total, approved, published, rejected = (
                await session.execute(agg_stmt)
            ).one()

            # Monthly breakdown by truncating the timestamp to month.
            month_col = func.date_trunc('month', Submission.submission_timestamp)
            monthly_stmt = (
                select(month_col.label('month'), func.count(Submission.submission_id))
                .where(*in_period)
                .group_by(month_col)
                .order_by(month_col)
            )
            monthly_breakdown = {
                row[0].month: row[1]
                for row in (await session.execute(monthly_stmt)).all()
            }

        return {
            'year': year,
            'total_submissions': total,
            'approved': approved,
            'published': published,
            'rejected': rejected,
            'monthly_breakdown': monthly_breakdown,
            'approval_rate': round((approved / total * 100) if total > 0 else 0, 1),
            'publication_rate': round((published / approved * 100) if approved > 0 else 0, 1),
        }

    @staticmethod
    async def _get_usernames(session, user_ids: list[int]) -> dict[int, Optional[str]]:
        """Map user_id -> username for the given IDs within a session.

        Args:
            session: Active AsyncSession.
            user_ids: User IDs to look up.

        Returns:
            Dict of user_id to username.
        """
        if not user_ids:
            return {}
        stmt = select(User.user_id, User.username).where(User.user_id.in_(user_ids))
        result = await session.execute(stmt)
        return {row.user_id: row.username for row in result}


# Global statistics service instance
statistics_service: Optional[StatisticsService] = None


def get_statistics_service() -> StatisticsService:
    """Get global statistics service instance.

    Returns:
        StatisticsService instance
    """
    global statistics_service
    if statistics_service is None:
        statistics_service = StatisticsService()
    return statistics_service
