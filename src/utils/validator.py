"""Input validation utilities."""

import re
from pathlib import Path
from typing import Any

from ..core.exceptions import ValidationError
from ..core.logger import get_logger

# Validation constants
MAX_PROVIDER_NAME_LENGTH = 100
MAX_INSTANCE_NAME_LENGTH = 100
MAX_COMMAND_LENGTH = 1000
MAX_ARG_LENGTH = 1000
MAX_ARGS_COUNT = 100
MAX_ENV_VAR_KEY_LENGTH = 200
MAX_ENV_VAR_VALUE_LENGTH = 2000
MAX_ENV_VARS_COUNT = 100
MAX_METADATA_ENTRIES = 50
MAX_STRING_INPUT_LENGTH = 10000

logger = get_logger(__name__)


class InputValidator:
    """Validates user inputs to prevent security vulnerabilities."""

    PROVIDER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
    INSTANCE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fa5-]+$")

    @classmethod
    def validate_provider_name(cls, name: str) -> str:
        """Validate provider name.

        Args:
            name: Provider name to validate

        Returns:
            Validated provider name

        Raises:
            ValidationError: If validation fails
        """
        if not name:
            raise ValidationError("Provider name cannot be empty")

        if not cls.PROVIDER_NAME_PATTERN.match(name):
            raise ValidationError(
                f"Invalid provider name: '{name}'. "
                "Only alphanumeric characters, underscores, and hyphens are allowed"
            )

        if len(name) > MAX_PROVIDER_NAME_LENGTH:
            raise ValidationError(
                f"Provider name too long (max {MAX_PROVIDER_NAME_LENGTH} characters)"
            )

        return name

    @classmethod
    def validate_instance_name(cls, name: str) -> str:
        """Validate instance name.

        Args:
            name: Instance name to validate

        Returns:
            Validated instance name

        Raises:
            ValidationError: If validation fails
        """
        if not name:
            raise ValidationError("Instance name cannot be empty")

        if not cls.INSTANCE_NAME_PATTERN.match(name):
            raise ValidationError(
                f"Invalid instance name: '{name}'. "
                "Only alphanumeric characters, underscores, hyphens, and Chinese characters are allowed"
            )

        if len(name) > MAX_INSTANCE_NAME_LENGTH:
            raise ValidationError(
                f"Instance name too long (max {MAX_INSTANCE_NAME_LENGTH} characters)"
            )

        return name

    @classmethod
    def validate_path(cls, path: str, base_path: str = "data") -> Path:
        """Validate and resolve file path to prevent path traversal attacks.

        Args:
            path: Path to validate
            base_path: Base directory path

        Returns:
            Resolved and validated Path object

        Raises:
            ValidationError: If validation fails
        """
        try:
            base = Path(base_path).resolve()
            target = (base / path).resolve()

            if not str(target).startswith(str(base)):
                raise ValidationError(
                    f"Path traversal detected: '{path}' is outside base directory"
                )

            return target
        except Exception as e:
            raise ValidationError(f"Invalid path: {e}") from e

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate MCP configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration

        Raises:
            ValidationError: If validation fails
        """
        required_fields = ["provider", "name", "type", "command"]

        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required field: {field}")

        cls.validate_provider_name(config["provider"])
        cls.validate_instance_name(config["name"])

        if config["type"] not in ["stdio", "sse", "http"]:
            raise ValidationError(
                f"Invalid transport type: {config['type']}. Must be one of: stdio, sse, http"
            )

        cls.validate_command(config["command"])
        cls.validate_command_args(config.get("args", []))
        cls.validate_env_vars(config.get("env", {}))

        if "isActive" in config and not isinstance(config["isActive"], bool):
            raise ValidationError("'isActive' must be a boolean")

        if "metadata" in config and config["metadata"] is not None:
            if not isinstance(config["metadata"], dict):
                raise ValidationError("'metadata' must be a dictionary")
            if len(config["metadata"]) > MAX_METADATA_ENTRIES:
                raise ValidationError(f"Too many metadata entries (max {MAX_METADATA_ENTRIES})")

        return config

    @classmethod
    def validate_command(cls, command: str) -> str:
        """Validate command to prevent command injection.

        Args:
            command: Command to validate

        Returns:
            Validated command

        Raises:
            ValidationError: If validation fails
        """
        if not command:
            raise ValidationError("Command cannot be empty")

        dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r"]
        for char in dangerous_chars:
            if char in command:
                raise ValidationError(
                    f"Dangerous character '{char}' detected in command. "
                    "Commands with shell operators are not allowed"
                )

        if len(command) > MAX_COMMAND_LENGTH:
            raise ValidationError(f"Command too long (max {MAX_COMMAND_LENGTH} characters)")

        return command

    @classmethod
    def validate_command_args(cls, args: list[str]) -> list[str]:
        """Validate command arguments to prevent injection.

        Args:
            args: Command arguments to validate

        Returns:
            Validated arguments

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(args, list):
            raise ValidationError("Arguments must be a list")

        if len(args) > MAX_ARGS_COUNT:
            raise ValidationError(f"Too many arguments (max {MAX_ARGS_COUNT})")

        for arg in args:
            if not isinstance(arg, str):
                raise ValidationError("All arguments must be strings")

            if len(arg) > MAX_ARG_LENGTH:
                raise ValidationError(f"Argument too long (max {MAX_ARG_LENGTH} characters)")

            dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r"]
            for char in dangerous_chars:
                if char in arg:
                    raise ValidationError(
                        f"Dangerous character '{char}' detected in argument. "
                        "Arguments with shell operators are not allowed"
                    )

        return args

    @classmethod
    def validate_env_vars(cls, env: dict[str, str]) -> dict[str, str]:
        """Validate environment variables.

        Args:
            env: Environment variables to validate

        Returns:
            Validated environment variables

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(env, dict):
            raise ValidationError("Environment variables must be a dictionary")

        if len(env) > MAX_ENV_VARS_COUNT:
            raise ValidationError(f"Too many environment variables (max {MAX_ENV_VARS_COUNT})")

        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError("Environment variable keys and values must be strings")

            if len(key) > MAX_ENV_VAR_KEY_LENGTH or len(value) > MAX_ENV_VAR_VALUE_LENGTH:
                raise ValidationError(
                    f"Environment variable key or value too long (max key: {MAX_ENV_VAR_KEY_LENGTH}, value: {MAX_ENV_VAR_VALUE_LENGTH})"
                )

            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                raise ValidationError(
                    f"Invalid environment variable name: '{key}'. "
                    "Must start with letter or underscore and contain only alphanumeric characters and underscores"
                )

        return env

    @classmethod
    def sanitize_string_input(cls, data: str, max_length: int = MAX_STRING_INPUT_LENGTH) -> str:
        """Sanitize string input to prevent XSS and injection attacks.

        Args:
            data: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string

        Raises:
            ValidationError: If dangerous patterns are detected
        """
        if not isinstance(data, str):
            raise ValidationError("Input must be a string")

        if len(data) > max_length:
            raise ValidationError(f"Input too long (max {max_length} characters)")

        dangerous_patterns = [
            "<script",
            "javascript:",
            "onerror=",
            "onclick=",
            "onload=",
            "eval(",
            "expression(",
            "<iframe",
            "<object",
            "<embed",
        ]

        data_lower = data.lower()
        for pattern in dangerous_patterns:
            if pattern in data_lower:
                raise ValidationError(
                    f"Dangerous pattern '{pattern}' detected in input. "
                    "Input contains potentially malicious content"
                )

        return data
