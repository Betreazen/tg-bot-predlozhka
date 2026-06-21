"""Configuration loader with environment variable substitution."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class TelegramConfig(BaseModel):
    """Telegram configuration."""
    bot_token: str
    channel_id: int
    admin_chat_id: int
    error_chat_id: int


class DatabaseConfig(BaseModel):
    """Database configuration."""
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    pool_size: int = 10
    echo: bool = False


class RedisConfig(BaseModel):
    """Redis configuration."""
    host: str
    port: int = 6379
    password: str
    db: int = 0
    decode_responses: bool = True


class RateLimitsConfig(BaseModel):
    """Rate limits configuration."""
    submissions_per_day: int = 2
    timezone: str = "Europe/Moscow"
    reset_time: str = "00:00"


class PublicationConfig(BaseModel):
    """Publication configuration."""
    delay_minutes: int = 2
    include_footer: bool = False
    footer_text: str = ""
    include_hashtags: bool = False
    hashtags: list[str] = Field(default_factory=list)
    max_file_size_mb: int = 200


class FeaturesConfig(BaseModel):
    """Features configuration."""
    enable_statistics: bool = True
    enable_user_notes: bool = True
    enable_blocking: bool = True
    require_confirmation: bool = True


class AdministratorConfig(BaseModel):
    """Administrator configuration."""
    user_id: int
    username: str
    note: str = ""


class StatisticsConfig(BaseModel):
    """Statistics configuration."""
    retention_years: int = 2


class ErrorHandlingConfig(BaseModel):
    """Error handling configuration."""
    max_retry_attempts: int = 2
    retry_delay_seconds: int = 30


class Config(BaseModel):
    """Main configuration model."""
    telegram: TelegramConfig
    database: DatabaseConfig
    redis: RedisConfig
    rate_limits: RateLimitsConfig
    publication: PublicationConfig
    features: FeaturesConfig
    administrators: list[AdministratorConfig] = Field(default_factory=list)
    statistics: StatisticsConfig
    error_handling: ErrorHandlingConfig


class Messages(BaseModel):
    """Messages configuration."""
    user: Dict[str, Any]
    notifications: Dict[str, str]
    admin: Dict[str, Any]
    statistics: Dict[str, Any]


class ConfigLoader:
    """Configuration loader with environment variable substitution."""
    
    ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')
    
    def __init__(self, config_dir: str = "config"):
        """Initialize config loader.

        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self._config: Config | None = None
        self._messages: Messages | None = None
        self._admin_ids: set[int] | None = None

    @staticmethod
    def _parse_admin_ids() -> set[int]:
        """Parse administrator user IDs from the ADMIN_IDS env variable.

        Returns:
            Set of admin Telegram user IDs (empty if unset).
        """
        raw = os.getenv("ADMIN_IDS", "")
        ids: set[int] = set()
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except ValueError:
                raise ValueError(
                    f"Invalid ADMIN_IDS entry: {part!r} (expected integer user IDs)"
                )
        return ids

    def get_admin_ids(self) -> list[int]:
        """Get list of administrator user IDs.

        IDs come from the ADMIN_IDS environment variable, merged with any
        administrators declared in ``config.json`` (for backwards compat).

        Returns:
            List of admin user IDs
        """
        if self._admin_ids is None:
            ids = self._parse_admin_ids()
            # Merge any administrators declared in config.json.
            try:
                config = self.load_config()
                ids.update(admin.user_id for admin in config.administrators)
            except Exception:
                # Config may be unavailable during early validation; env wins.
                pass
            self._admin_ids = ids
        return list(self._admin_ids)
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in data.
        
        Args:
            data: Data to process
            
        Returns:
            Data with environment variables substituted
        """
        if isinstance(data, str):
            def replace_env_var(match: re.Match) -> str:
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    raise ValueError(f"Environment variable {var_name} is not set")
                return value
            
            return self.ENV_VAR_PATTERN.sub(replace_env_var, data)
        elif isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        else:
            return data
    
    def _load_json_file(self, filename: str) -> Dict[str, Any]:
        """Load and parse JSON file.
        
        Args:
            filename: Name of the JSON file
            
        Returns:
            Parsed JSON data with environment variables substituted
        """
        file_path = self.config_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self._substitute_env_vars(data)
    
    def load_config(self) -> Config:
        """Load main configuration.
        
        Returns:
            Loaded configuration object
        """
        if self._config is None:
            data = self._load_json_file("config.json")
            self._config = Config(**data)
        return self._config
    
    def load_messages(self) -> Messages:
        """Load messages configuration.
        
        Returns:
            Loaded messages object
        """
        if self._messages is None:
            data = self._load_json_file("messages.json")
            self._messages = Messages(**data)
        return self._messages
    
    def reload(self) -> None:
        """Reload configuration from files."""
        self._config = None
        self._messages = None
        self._admin_ids = None
        self.load_config()
        self.load_messages()

    def is_admin(self, user_id: int) -> bool:
        """Check if user is administrator.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is admin, False otherwise
        """
        return user_id in self.get_admin_ids()


# Global config loader instance
config_loader = ConfigLoader()
