"""MCP Router - Core routing logic."""

import builtins
from typing import Any

from ..core.logger import get_logger
from .client import MCPClientManager

logger = get_logger(__name__)


class MCPRouter:
    """Routes MCP tool calls to appropriate client instances."""

    def __init__(self, client_manager: MCPClientManager):
        """Initialize MCP router.

        Args:
            client_manager: MCP client manager instance
        """
        self.client_manager = client_manager
        self._current_instance: str | None = None

    async def use(self, instance_name: str) -> dict[str, Any]:
        """Use a specific MCP instance.

        Args:
            instance_name: Name of instance to use

        Returns:
            Dictionary with instance info and available tools
        """
        instance = self.client_manager.get_instance(instance_name)

        if not instance.is_active:
            logger.warning(f"Instance '{instance_name}' is not active")

        self._current_instance = instance_name
        tools = instance.get_tools()

        logger.info(f"Now using instance: {instance_name}")

        return {
            "instance": instance_name,
            "tools": list(tools.keys()),
            "active": instance.is_active,
        }

    def list(self) -> list[dict[str, Any]]:
        """List all registered MCP client instances.

        Returns:
            List of instance information dictionaries
        """
        return self.client_manager.list_instances()

    def help(self) -> dict[str, builtins.list[dict[str, Any]]]:
        """Get help information for all tools.

        Returns:
            Dictionary mapping instance names to their tool descriptions
        """
        result = {}

        for instance_name, tools in self.client_manager.get_all_tools().items():
            result[instance_name] = tools

        return result

    async def add(self, provider_name: str, config: dict[str, Any]) -> str:
        """Add a new MCP configuration.

        Args:
            provider_name: Provider name
            config: MCP configuration

        Returns:
            Simple status message
        """
        try:
            instance_name = await self.client_manager.add_instance(provider_name, config)
            logger.info(f"Added new instance: {instance_name}")
            return "Done"
        except Exception as e:
            logger.error(f"Failed to add instance: {e}")
            return f"Error: {str(e)}"

    async def call(self, instance_name: str, tool_name: str, **kwargs) -> Any:
        """Call a tool on a specific instance.

        Args:
            instance_name: Name of the instance
            tool_name: Name of the tool to call
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        instance = self.client_manager.get_instance(instance_name)

        result = await instance.call_tool(tool_name, kwargs)

        logger.info(f"Tool '{tool_name}' called on '{instance_name}'")

        return result

    async def remove(self, instance_name: str) -> str:
        """Remove an MCP configuration.

        Args:
            instance_name: Name of instance to remove

        Returns:
            Simple status message
        """
        try:
            await self.client_manager.remove_instance(instance_name)

            if self._current_instance == instance_name:
                self._current_instance = None

            logger.info(f"Removed instance: {instance_name}")
            return "Done"
        except Exception as e:
            logger.error(f"Failed to remove instance: {e}")
            return f"Error: {str(e)}"

    async def disable(self, instance_name: str) -> str:
        """Disable an MCP instance.

        Args:
            instance_name: Name of instance to disable

        Returns:
            Simple status message
        """
        try:
            await self.client_manager.disable_instance(instance_name)
            logger.info(f"Disabled instance: {instance_name}")
            return "Done"
        except Exception as e:
            logger.error(f"Failed to disable instance: {e}")
            return f"Error: {str(e)}"

    async def enable(self, instance_name: str) -> str:
        """Enable an MCP instance.

        Args:
            instance_name: Name of instance to enable

        Returns:
            Simple status message
        """
        try:
            await self.client_manager.enable_instance(instance_name)
            logger.info(f"Enabled instance: {instance_name}")
            return "Done"
        except Exception as e:
            logger.error(f"Failed to enable instance: {e}")
            return f"Error: {str(e)}"

    def get_current_instance(self) -> str | None:
        """Get currently selected instance.

        Returns:
            Current instance name or None
        """
        return self._current_instance
