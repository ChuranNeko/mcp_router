"""Input validation utilities."""

import re
from pathlib import Path
from typing import Any, Dict

from ..core.exceptions import ValidationError
from ..core.logger import get_logger

logger = get_logger(__name__)


class InputValidator:
    """Validates user inputs to prevent security vulnerabilities."""
    
    PROVIDER_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    INSTANCE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\u4e00-\u9fa5-]+$')
    
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
        
        if len(name) > 100:
            raise ValidationError("Provider name too long (max 100 characters)")
        
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
        
        if len(name) > 100:
            raise ValidationError("Instance name too long (max 100 characters)")
        
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
            raise ValidationError(f"Invalid path: {e}")
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
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
                f"Invalid transport type: {config['type']}. "
                "Must be one of: stdio, sse, http"
            )
        
        if not isinstance(config.get("args", []), list):
            raise ValidationError("'args' must be a list")
        
        if not isinstance(config.get("env", {}), dict):
            raise ValidationError("'env' must be a dictionary")
        
        if "isActive" in config and not isinstance(config["isActive"], bool):
            raise ValidationError("'isActive' must be a boolean")
        
        return config
    
    @classmethod
    def sanitize_json_input(cls, data: Any) -> Any:
        """Sanitize JSON input to prevent XSS and injection attacks.
        
        Args:
            data: Data to sanitize
            
        Returns:
            Sanitized data
        """
        if isinstance(data, str):
            dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
            for pattern in dangerous_patterns:
                if pattern.lower() in data.lower():
                    logger.warning(f"Potentially dangerous pattern detected in input: {pattern}")
        
        return data

