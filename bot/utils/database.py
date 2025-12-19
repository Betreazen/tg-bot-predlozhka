"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.models.database import Base
from bot.utils.config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None
    
    def _get_database_url(self) -> str:
        """Get database URL from configuration.
        
        Returns:
            Database connection URL
        """
        return (
            f"postgresql+asyncpg://{self.config.user}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        )
    
    async def connect(self) -> None:
        """Initialize database connection."""
        if self._engine is not None:
            logger.warning("Database already connected")
            return
        
        url = self._get_database_url()
        self._engine = create_async_engine(
            url,
            echo=self.config.echo,
            pool_size=self.config.pool_size,
            max_overflow=self.config.pool_size * 2,
            pool_pre_ping=True,
        )
        
        self._session_maker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        logger.info("Database connected successfully")
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self._engine is None:
            logger.warning("Database not connected")
            return
        
        await self._engine.dispose()
        self._engine = None
        self._session_maker = None
        
        logger.info("Database disconnected")
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if self._engine is None:
            raise RuntimeError("Database not connected")
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created")
    
    async def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        if self._engine is None:
            raise RuntimeError("Database not connected")
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.warning("Database tables dropped")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context manager.
        
        Yields:
            AsyncSession instance
        """
        if self._session_maker is None:
            raise RuntimeError("Database not connected")
        
        async with self._session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def health_check(self) -> bool:
        """Check database connection health.
        
        Returns:
            True if database is healthy, False otherwise
        """
        if self._engine is None:
            return False
        
        try:
            async with self._engine.connect() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance.
    
    Returns:
        DatabaseManager instance
    """
    if db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return db_manager


def init_db_manager(config: DatabaseConfig) -> DatabaseManager:
    """Initialize global database manager.
    
    Args:
        config: Database configuration
        
    Returns:
        Initialized DatabaseManager instance
    """
    global db_manager
    db_manager = DatabaseManager(config)
    return db_manager
