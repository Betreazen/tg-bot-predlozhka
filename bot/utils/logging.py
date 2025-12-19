"""Logging configuration and utilities."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Structured log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured fields.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        # Add custom fields if available
        user_id = getattr(record, 'user_id', None)
        submission_id = getattr(record, 'submission_id', None)
        action_type = getattr(record, 'action_type', None)
        component = getattr(record, 'component', record.name)
        
        # Build structured message
        parts = [
            f"[{self.formatTime(record, self.datefmt)}]",
            f"[{record.levelname}]",
            f"[{component}]",
        ]
        
        if user_id:
            parts.append(f"[user:{user_id}]")
        if submission_id:
            parts.append(f"[submission:{submission_id}]")
        if action_type:
            parts.append(f"[action:{action_type}]")
        
        parts.append(record.getMessage())
        
        if record.exc_info:
            parts.append("\n" + self.formatException(record.exc_info))
        
        return " ".join(parts)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Generate log filename with date
    log_file = log_path / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Create formatters
    console_formatter = StructuredFormatter(
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    file_formatter = StructuredFormatter(
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(console_formatter)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from libraries
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    logging.info("Logging configured successfully")


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter with extra context."""
    
    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Process log message with extra context.
        
        Args:
            msg: Log message
            kwargs: Additional keyword arguments
            
        Returns:
            Tuple of message and updated kwargs
        """
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def get_logger(name: str, **extra_context: Any) -> LoggerAdapter:
    """Get logger with extra context.
    
    Args:
        name: Logger name
        **extra_context: Additional context fields
        
    Returns:
        LoggerAdapter instance
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, extra_context)
