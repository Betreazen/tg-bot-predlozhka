"""Redis connection and management."""

import logging
from typing import Any

import redis.asyncio as redis

from bot.utils.config import RedisConfig

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis connection manager."""
    
    def __init__(self, config: RedisConfig):
        """Initialize Redis manager.
        
        Args:
            config: Redis configuration
        """
        self.config = config
        self._client: redis.Redis | None = None
    
    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is not None:
            logger.warning("Redis already connected")
            return
        
        self._client = redis.Redis(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            decode_responses=self.config.decode_responses,
        )
        
        # Test connection
        await self._client.ping()
        logger.info("Redis connected successfully")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is None:
            logger.warning("Redis not connected")
            return
        
        # redis-py 5 renamed close() -> aclose(); fall back for older clients.
        if hasattr(self._client, "aclose"):
            await self._client.aclose()
        else:
            await self._client.close()
        self._client = None
        logger.info("Redis disconnected")
    
    def get_client(self) -> redis.Redis:
        """Get Redis client.
        
        Returns:
            Redis client instance
        """
        if self._client is None:
            raise RuntimeError("Redis not connected")
        return self._client
    
    async def health_check(self) -> bool:
        """Check Redis connection health.
        
        Returns:
            True if Redis is healthy, False otherwise
        """
        if self._client is None:
            return False
        
        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis manager instance
redis_manager: RedisManager | None = None


def get_redis_manager() -> RedisManager:
    """Get global Redis manager instance.
    
    Returns:
        RedisManager instance
    """
    if redis_manager is None:
        raise RuntimeError("Redis manager not initialized")
    return redis_manager


def init_redis_manager(config: RedisConfig) -> RedisManager:
    """Initialize global Redis manager.
    
    Args:
        config: Redis configuration
        
    Returns:
        Initialized RedisManager instance
    """
    global redis_manager
    redis_manager = RedisManager(config)
    return redis_manager
