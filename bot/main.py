"""Main bot application entry point."""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.utils.config import config_loader
from bot.utils.database import init_db_manager
from bot.utils.redis_manager import init_redis_manager
from bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main bot entry point."""
    
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    setup_logging(log_level="INFO")
    
    logger.info("Starting Telegram UGC Bot...")
    
    try:
        # Load configuration
        config = config_loader.load_config()
        messages = config_loader.load_messages()
        
        logger.info("Configuration loaded successfully")
        
        # Initialize database manager
        db_manager = init_db_manager(config.database)
        await db_manager.connect()
        
        # Create tables (if not exists)
        await db_manager.create_tables()
        
        # Initialize Redis manager
        redis_manager = init_redis_manager(config.redis)
        await redis_manager.connect()
        
        # Create FSM storage
        storage = RedisStorage(redis_manager.get_client())
        
        # Initialize bot and dispatcher
        bot = Bot(
            token=config.telegram.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher(storage=storage)
        
        # Register handlers
        from bot.handlers import user_handlers, admin_handlers, statistics_handlers
        dp.include_router(user_handlers.router)
        dp.include_router(admin_handlers.router)
        dp.include_router(statistics_handlers.router)
        
        logger.info("Bot handlers registered")
        
        # Run recovery service to restore pending tasks
        from bot.services.recovery_service import get_recovery_service
        recovery_service = get_recovery_service()
        await recovery_service.recover_pending_tasks(bot)
        
        # Send startup notification to admin chat
        try:
            startup_message = messages.admin.get("bot_started", "🤖 Bot started successfully")
            await bot.send_message(
                chat_id=config.telegram.admin_chat_id,
                text=startup_message
            )
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
        
        # Start polling
        logger.info("Bot started and polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("Shutting down bot...")
        
        try:
            if 'db_manager' in locals():
                await db_manager.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting database: {e}")
        
        try:
            if 'redis_manager' in locals():
                await redis_manager.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting Redis: {e}")
        
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
