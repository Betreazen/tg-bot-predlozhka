"""Health check utilities."""

import logging

from bot.utils.database import get_db_manager
from bot.utils.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)


async def check_health() -> bool:
    """Check overall system health.
    
    Returns:
        True if all components are healthy, False otherwise
    """
    try:
        # Check database
        db_manager = get_db_manager()
        db_healthy = await db_manager.health_check()
        
        # Check Redis
        redis_manager = get_redis_manager()
        redis_healthy = await redis_manager.health_check()
        
        if db_healthy and redis_healthy:
            logger.debug("Health check passed")
            return True
        else:
            logger.warning(f"Health check failed: DB={db_healthy}, Redis={redis_healthy}")
            return False
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return False
