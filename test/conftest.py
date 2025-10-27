"""Pytest configuration and fixtures."""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest

from src.core.config import ConfigManager
from src.mcp.client import MCPClientManager
from src.mcp.router import MCPRouter
from src.utils.security import SecurityManager


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> ConfigManager:
    """Create test configuration."""
    config = ConfigManager("config.json")
    return config


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    test_provider = data_dir / "test_provider"
    test_provider.mkdir()
    
    test_config = {
        "provider": "test_provider",
        "name": "test_instance",
        "type": "stdio",
        "command": "echo",
        "args": ["test"],
        "env": {},
        "isActive": True,
        "metadata": {
            "description": "Test instance",
            "version": "1.0.0"
        }
    }
    
    config_file = test_provider / "mcp_settings.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, indent=2)
    
    return data_dir


@pytest.fixture
async def client_manager(test_data_dir: Path) -> AsyncGenerator[MCPClientManager, None]:
    """Create MCP client manager for testing."""
    manager = MCPClientManager(data_path=str(test_data_dir), timeout=10.0)
    yield manager
    await manager.shutdown()


@pytest.fixture
async def router(client_manager: MCPClientManager) -> MCPRouter:
    """Create MCP router for testing."""
    return MCPRouter(client_manager)


@pytest.fixture
def security_manager() -> SecurityManager:
    """Create security manager for testing."""
    return SecurityManager(bearer_token="test_token", enable_validation=True)


@pytest.fixture
def security_manager_no_auth() -> SecurityManager:
    """Create security manager without authentication."""
    return SecurityManager(bearer_token=None, enable_validation=False)

