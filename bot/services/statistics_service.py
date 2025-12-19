"""Statistics aggregation service."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import select, func, and_, extract, distinct

from bot.models.database import Submission, SubmissionStatus, User
from bot.utils.database import get_db_manager
from bot.utils.config import config_loader

logger = logging.getLogger(__name__)


class StatisticsService:
    """Service for aggregating and calculating statistics."""
    
    def __init__(self):
        """Initialize statistics service."""
        self.db = get_db_manager()
        self.config = config_loader.load_config()
    
    async def get_current_month_stats(self) -> Dict[str, Any]:
        """Get statistics for current month.
        
        Returns:
            Dictionary with statistics
        """
        now = datetime.now()
        return await self.get_monthly_stats(now.year, now.month)
    
    async def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """Get statistics for specific month.
        
        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            
        Returns:
            Dictionary with comprehensive statistics
        """
        async with self.db.session() as session:
            # Base condition for the time period
            time_condition = and_(
                extract('year', Submission.submission_timestamp) == year,
                extract('month', Submission.submission_timestamp) == month
            )
            
            # Total submissions
            total_stmt = select(func.count(Submission.submission_id)).where(time_condition)
            total_result = await session.execute(total_stmt)
            total = total_result.scalar() or 0
            
            # Submissions by status
            approved_stmt = select(func.count(Submission.submission_id)).where(
                and_(
                    time_condition,
                    Submission.status.in_([
                        SubmissionStatus.APPROVED,
                        SubmissionStatus.ACCEPTED_NOT_PUBLISHED,
                        SubmissionStatus.PUBLISHED
                    ])
                )
            )
            approved_result = await session.execute(approved_stmt)
            approved = approved_result.scalar() or 0
            
            published_stmt = select(func.count(Submission.submission_id)).where(
                and_(
                    time_condition,
                    Submission.status == SubmissionStatus.PUBLISHED
                )
            )
            published_result = await session.execute(published_stmt)
            published = published_result.scalar() or 0
            
            rejected_stmt = select(func.count(Submission.submission_id)).where(
                and_(
                    time_condition,
                    Submission.status == SubmissionStatus.REJECTED
                )
            )
            rejected_result = await session.execute(rejected_stmt)
            rejected = rejected_result.scalar() or 0
            
            # Unique users who submitted
            unique_users_stmt = select(
                func.count(distinct(Submission.user_id))
            ).where(time_condition)
            unique_users_result = await session.execute(unique_users_stmt)
            unique_users = unique_users_result.scalar() or 0
            
            # New users in period
            new_users_stmt = select(func.count(User.user_id)).where(
                and_(
                    extract('year', User.registration_timestamp) == year,
                    extract('month', User.registration_timestamp) == month
                )
            )
            new_users_result = await session.execute(new_users_stmt)
            new_users = new_users_result.scalar() or 0
            
            # Blocked users count (total, not just in period)
            blocked_stmt = select(func.count(User.user_id)).where(User.is_blocked == True)
            blocked_result = await session.execute(blocked_stmt)
            blocked_users = blocked_result.scalar() or 0
            
            # Per-admin statistics
            admin_stats_stmt = select(
                Submission.moderator_id,
                func.count(Submission.submission_id).label('decision_count')
            ).where(
                and_(
                    time_condition,
                    Submission.moderator_id.isnot(None)
                )
            ).group_by(Submission.moderator_id)
            
            admin_stats_result = await session.execute(admin_stats_stmt)
            admin_stats_raw = admin_stats_result.all()
            
            # Format admin stats with usernames
            admin_stats = []
            for moderator_id, count in admin_stats_raw:
                # Find admin username from config
                admin_username = None
                for admin in self.config.administrators:
                    if admin.user_id == moderator_id:
                        admin_username = admin.username
                        break
                
                admin_stats.append({
                    'user_id': moderator_id,
                    'username': admin_username or f"ID:{moderator_id}",
                    'decision_count': count
                })
            
            # Calculate rates
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
                'rejection_rate': round(rejection_rate, 1)
            }
    
    async def get_yearly_stats(self, year: int) -> Dict[str, Any]:
        """Get statistics for entire year.
        
        Args:
            year: Year (e.g., 2024)
            
        Returns:
            Dictionary with yearly statistics
        """
        async with self.db.session() as session:
            # Base condition for the year
            year_condition = extract('year', Submission.submission_timestamp) == year
            
            # Total submissions
            total_stmt = select(func.count(Submission.submission_id)).where(year_condition)
            total_result = await session.execute(total_stmt)
            total = total_result.scalar() or 0
            
            # Approved, published, rejected
            approved_stmt = select(func.count(Submission.submission_id)).where(
                and_(
                    year_condition,
                    Submission.status.in_([
                        SubmissionStatus.APPROVED,
                        SubmissionStatus.ACCEPTED_NOT_PUBLISHED,
                        SubmissionStatus.PUBLISHED
                    ])
                )
            )
            approved_result = await session.execute(approved_stmt)
            approved = approved_result.scalar() or 0
            
            published_stmt = select(func.count(Submission.submission_id)).where(
                and_(year_condition, Submission.status == SubmissionStatus.PUBLISHED)
            )
            published_result = await session.execute(published_stmt)
            published = published_result.scalar() or 0
            
            rejected_stmt = select(func.count(Submission.submission_id)).where(
                and_(year_condition, Submission.status == SubmissionStatus.REJECTED)
            )
            rejected_result = await session.execute(rejected_stmt)
            rejected = rejected_result.scalar() or 0
            
            # Monthly breakdown
            monthly_stmt = select(
                extract('month', Submission.submission_timestamp).label('month'),
                func.count(Submission.submission_id).label('count')
            ).where(year_condition).group_by('month').order_by('month')
            
            monthly_result = await session.execute(monthly_stmt)
            monthly_breakdown = {int(row.month): row.count for row in monthly_result}
            
            return {
                'year': year,
                'total_submissions': total,
                'approved': approved,
                'published': published,
                'rejected': rejected,
                'monthly_breakdown': monthly_breakdown,
                'approval_rate': round((approved / total * 100) if total > 0 else 0, 1),
                'publication_rate': round((published / approved * 100) if approved > 0 else 0, 1)
            }


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
