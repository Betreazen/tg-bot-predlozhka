"""Health check utilities."""

import asyncio
import logging
import sys

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


async def _probe() -> bool:
    """Standalone health probe used by the Docker HEALTHCHECK.

    Runs in a fresh process where the global managers are not initialized, so it
    builds its own short-lived connections from config and checks them.

    Returns:
        True if both PostgreSQL and Redis are reachable.
    """
    from dotenv import load_dotenv

    from bot.utils.config import config_loader
    from bot.utils.database import init_db_manager
    from bot.utils.redis_manager import init_redis_manager

    load_dotenv()
    config = config_loader.load_config()

    db = init_db_manager(config.database)
    redis = init_redis_manager(config.redis)

    db_ok = redis_ok = False
    try:
        await db.connect()
        db_ok = await db.health_check()
    except Exception as e:
        logger.error(f"Probe DB connect failed: {e}")
    try:
        await redis.connect()
        redis_ok = await redis.health_check()
    except Exception as e:
        logger.error(f"Probe Redis connect failed: {e}")
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass
        try:
            await redis.disconnect()
        except Exception:
            pass

    return db_ok and redis_ok


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(_probe()) else 1)
