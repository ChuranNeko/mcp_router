"""Configuration manager for MCP Router."""

import json
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError
from .logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """Manages global configuration for MCP Router."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._config = self._get_default_config()
            self.save()
            return

        try:
            file_size = self.config_path.stat().st_size
            max_size = 10 * 1024 * 1024  # 10MB limit
            if file_size > max_size:
                raise ConfigurationError(
                    f"Config file too large ({file_size} bytes). Maximum allowed: {max_size} bytes"
                )

            with open(self.config_path, encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.warning("Config file is empty, using defaults")
                    self._config = self._get_default_config()
                    self.save()
                    return
                self._config = json.loads(content)
            logger.info(f"Configuration loaded from {self.config_path}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}") from e

    def save(self) -> None:
        """Save configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save config: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key (supports dot notation, e.g., 'api.port')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_all(self) -> dict[str, Any]:
        """Get all configuration.

        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()

    @staticmethod
    def _get_default_config() -> dict[str, Any]:
        """Get default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "api": {
                "enabled": False,
                "port": 8000,
                "host": "127.0.0.1",
                "cors_origin": "*",
                "auto_find_port": True,
                "enable_realtime_logs": False,
            },
            "server": {
                "enabled": True,
                "transport_type": "stdio",
                "allow_instance_management": False,
            },
            "mcp_client": {"enabled": True, "timeout": 30},
            "security": {"bearer_token": "", "enable_validation": True},
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "directory": "logs",
            },
            "watcher": {"enabled": True, "watch_path": "data", "debounce_delay": 1.0},
        }
