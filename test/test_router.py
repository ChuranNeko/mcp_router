"""Tests for MCP router functionality."""

import pytest

from src.core.exceptions import InstanceNotFoundError, ValidationError
from src.mcp.router import MCPRouter
from src.mcp.client import MCPClientManager


@pytest.mark.asyncio
async def test_router_list(router: MCPRouter):
    """Test listing instances."""
    instances = router.list()
    assert isinstance(instances, list)


@pytest.mark.asyncio
async def test_router_help(router: MCPRouter):
    """Test getting help information."""
    help_info = router.help()
    assert isinstance(help_info, dict)


@pytest.mark.asyncio
async def test_router_add_instance(router: MCPRouter):
    """Test adding a new instance."""
    config = {
        "name": "new_test_instance",
        "type": "stdio",
        "command": "echo",
        "args": ["hello"],
        "env": {},
        "isActive": True
    }
    
    result = await router.add("new_provider", config)
    
    assert result["status"] == "success"
    assert result["instance_name"] == "new_test_instance"
    
    instances = router.list()
    instance_names = [inst["name"] for inst in instances]
    assert "new_test_instance" in instance_names


@pytest.mark.asyncio
async def test_router_remove_instance(router: MCPRouter):
    """Test removing an instance."""
    config = {
        "name": "remove_test_instance",
        "type": "stdio",
        "command": "echo",
        "args": ["test"],
        "env": {}
    }
    
    await router.add("remove_provider", config)
    
    result = await router.remove("remove_test_instance")
    
    assert result["status"] == "success"
    assert result["removed"] == "remove_test_instance"
    
    with pytest.raises(InstanceNotFoundError):
        router.client_manager.get_instance("remove_test_instance")


@pytest.mark.asyncio
async def test_router_enable_disable(router: MCPRouter):
    """Test enabling and disabling instances."""
    config = {
        "name": "toggle_test_instance",
        "type": "stdio",
        "command": "echo",
        "args": ["test"],
        "env": {}
    }
    
    await router.add("toggle_provider", config)
    
    result = await router.disable("toggle_test_instance")
    assert result["active"] is False
    
    result = await router.enable("toggle_test_instance")
    assert result["active"] is True


@pytest.mark.asyncio
async def test_router_instance_not_found(router: MCPRouter):
    """Test accessing non-existent instance."""
    with pytest.raises(InstanceNotFoundError):
        await router.use("non_existent_instance")

