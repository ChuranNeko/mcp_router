"""Tests for security features."""

import pytest

from src.core.exceptions import SecurityError, ValidationError
from src.utils.security import SecurityManager
from src.utils.validator import InputValidator


def test_security_manager_with_token():
    """Test security manager with bearer token."""
    manager = SecurityManager(bearer_token="secret_token", enable_validation=True)
    
    assert manager.validate_bearer_token("Bearer secret_token")
    assert manager.validate_bearer_token("secret_token")
    
    with pytest.raises(SecurityError):
        manager.validate_bearer_token("wrong_token")
    
    with pytest.raises(SecurityError):
        manager.validate_bearer_token(None)


def test_security_manager_without_token():
    """Test security manager without bearer token."""
    manager = SecurityManager(bearer_token=None, enable_validation=True)
    
    assert manager.validate_bearer_token(None)
    assert manager.validate_bearer_token("any_token")


def test_security_manager_disabled():
    """Test security manager with validation disabled."""
    manager = SecurityManager(bearer_token="secret", enable_validation=False)
    
    assert manager.validate_bearer_token(None)
    assert manager.validate_bearer_token("wrong")


def test_token_masking():
    """Test token masking for logging."""
    manager = SecurityManager()
    
    assert manager.mask_token("short") == "***"
    assert manager.mask_token("verylongtoken123") == "very...t123"
    assert manager.mask_token(None) == "None"


def test_validate_provider_name():
    """Test provider name validation."""
    assert InputValidator.validate_provider_name("valid_provider") == "valid_provider"
    assert InputValidator.validate_provider_name("Provider123") == "Provider123"
    
    with pytest.raises(ValidationError):
        InputValidator.validate_provider_name("")
    
    with pytest.raises(ValidationError):
        InputValidator.validate_provider_name("invalid-provider")
    
    with pytest.raises(ValidationError):
        InputValidator.validate_provider_name("invalid provider")
    
    with pytest.raises(ValidationError):
        InputValidator.validate_provider_name("a" * 101)


def test_validate_instance_name():
    """Test instance name validation."""
    assert InputValidator.validate_instance_name("valid_instance") == "valid_instance"
    assert InputValidator.validate_instance_name("Instance123") == "Instance123"
    assert InputValidator.validate_instance_name("中文实例") == "中文实例"
    
    with pytest.raises(ValidationError):
        InputValidator.validate_instance_name("")
    
    with pytest.raises(ValidationError):
        InputValidator.validate_instance_name("invalid-instance")
    
    with pytest.raises(ValidationError):
        InputValidator.validate_instance_name("a" * 101)


def test_validate_path():
    """Test path validation."""
    safe_path = InputValidator.validate_path("provider/file.json", "data")
    assert "data" in str(safe_path)
    
    with pytest.raises(ValidationError):
        InputValidator.validate_path("../../../etc/passwd", "data")


def test_validate_config():
    """Test configuration validation."""
    valid_config = {
        "provider": "test_provider",
        "name": "test_instance",
        "type": "stdio",
        "command": "echo",
        "args": ["test"],
        "env": {},
        "isActive": True
    }
    
    result = InputValidator.validate_config(valid_config)
    assert result["provider"] == "test_provider"
    
    with pytest.raises(ValidationError):
        InputValidator.validate_config({})
    
    with pytest.raises(ValidationError):
        invalid = valid_config.copy()
        invalid["type"] = "invalid"
        InputValidator.validate_config(invalid)
    
    with pytest.raises(ValidationError):
        invalid = valid_config.copy()
        invalid["args"] = "not a list"
        InputValidator.validate_config(invalid)

