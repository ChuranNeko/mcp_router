"""MCP client management."""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import ClientSession

from ..core.exceptions import (
    ConfigurationError,
    InstanceNotFoundError,
    ToolNotFoundError,
)
from ..core.exceptions import (
    TimeoutError as MCPTimeoutError,
)
from ..core.logger import get_logger
from ..utils.validator import InputValidator
from .transport import create_transport

logger = get_logger(__name__)


class MCPClientInstance:
    """Represents a single MCP client instance."""

    def __init__(
        self,
        name: str,
        provider: str,
        command: str,
        args: list[str],
        transport_type: str = "stdio",
        env: dict[str, str] | None = None,
        is_active: bool = True,
        metadata: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ):
        """Initialize MCP client instance.

        Args:
            name: Instance name
            provider: Provider name
            command: Command to execute
            args: Command arguments
            transport_type: Transport type (stdio, sse, http)
            env: Environment variables
            is_active: Whether instance is active
            metadata: Additional metadata
            timeout: Operation timeout in seconds
        """
        self.name = name
        self.provider = provider
        self.command = command
        self.args = args
        self.transport_type = transport_type
        self.env = env or {}
        self.is_active = is_active
        self.metadata = metadata or {}
        self.timeout = timeout

        self._session: ClientSession | None = None
        self._read_stream = None
        self._write_stream = None
        self._transport = None
        self._tools: dict[str, Any] = {}
        self._connected = False

    async def connect(self) -> None:
        """Connect to MCP server."""
        if self._connected:
            logger.warning(f"Instance '{self.name}' already connected")
            return

        try:
            logger.info(f"Connecting to instance '{self.name}'...")

            self._transport = create_transport(
                self.transport_type, self.command, self.args, self.env
            )

            self._read_stream, self._write_stream = await asyncio.wait_for(
                self._transport.__aenter__(), timeout=self.timeout
            )

            self._session = ClientSession(self._read_stream, self._write_stream)
            await asyncio.wait_for(self._session.__aenter__(), timeout=self.timeout)

            await self._session.initialize()

            await self._fetch_tools()

            self._connected = True
            logger.info(
                f"Instance '{self.name}' connected successfully with {len(self._tools)} tools"
            )
        except asyncio.TimeoutError:
            raise MCPTimeoutError(self.timeout)
        except Exception as e:
            logger.error(f"Failed to connect to instance '{self.name}': {e}")
            raise ConfigurationError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if not self._connected:
            return

        try:
            if self._session:
                await self._session.__aexit__(None, None, None)

            if self._transport:
                await self._transport.__aexit__(None, None, None)

            self._connected = False
            self._tools = {}
            self._transport = None
            logger.info(f"Instance '{self.name}' disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting instance '{self.name}': {e}")

    async def _fetch_tools(self) -> None:
        """Fetch available tools from MCP server."""
        if not self._session:
            raise ConfigurationError("Not connected to MCP server")

        try:
            result = await asyncio.wait_for(self._session.list_tools(), timeout=self.timeout)

            self._tools = {}
            for tool in result.tools:
                self._tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }

            logger.debug(f"Fetched {len(self._tools)} tools from '{self.name}'")
        except asyncio.TimeoutError:
            raise MCPTimeoutError(self.timeout)
        except Exception as e:
            logger.error(f"Failed to fetch tools from '{self.name}': {e}")
            raise

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool on this instance.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ToolNotFoundError: If tool not found
            MCPTimeoutError: If operation times out
        """
        if not self._connected or not self._session:
            raise ConfigurationError(f"Instance '{self.name}' not connected")

        if not self.is_active:
            raise ConfigurationError(f"Instance '{self.name}' is not active")

        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name, self.name)

        try:
            logger.info(f"Calling tool '{tool_name}' on instance '{self.name}'")

            result = await asyncio.wait_for(
                self._session.call_tool(tool_name, arguments or {}), timeout=self.timeout
            )

            logger.debug(f"Tool '{tool_name}' completed successfully")
            return result
        except asyncio.TimeoutError:
            raise MCPTimeoutError(self.timeout)
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            raise

    def get_tools(self) -> dict[str, Any]:
        """Get available tools.

        Returns:
            Dictionary of available tools
        """
        return self._tools.copy()

    def is_connected(self) -> bool:
        """Check if instance is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "provider": self.provider,
            "active": self.is_active,
            "connected": self._connected,
            "transport_type": self.transport_type,
            "tools_count": len(self._tools),
            "metadata": self.metadata,
        }


class MCPClientManager:
    """Manages multiple MCP client instances."""

    def __init__(self, data_path: str = "data", timeout: float = 30.0):
        """Initialize MCP client manager.

        Args:
            data_path: Path to data directory containing configurations
            timeout: Default timeout for operations
        """
        self.data_path = Path(data_path)
        self.timeout = timeout
        self._instances: dict[str, MCPClientInstance] = {}

    async def load_configurations(self) -> None:
        """Load all MCP configurations from data directory."""
        if not self.data_path.exists():
            logger.warning(f"Data path does not exist: {self.data_path}")
            self.data_path.mkdir(parents=True, exist_ok=True)
            return

        config_files = list(self.data_path.glob("*/mcp_settings.json"))
        logger.info(f"Found {len(config_files)} configuration files")

        for config_file in config_files:
            try:
                await self._load_config_file(config_file)
            except Exception as e:
                logger.error(f"Failed to load config {config_file}: {e}")

    async def _load_config_file(self, config_path: Path) -> None:
        """Load a single configuration file.

        Args:
            config_path: Path to configuration file
        """
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)

            if "mcpServers" in data:
                for server_name, server_config in data["mcpServers"].items():
                    await self._create_instance_from_config(server_config, config_path.parent.name)
            else:
                await self._create_instance_from_config(data, config_path.parent.name)
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            raise

    async def _create_instance_from_config(self, config: dict[str, Any], provider: str) -> None:
        """Create instance from configuration.

        Args:
            config: Configuration dictionary
            provider: Provider name
        """
        try:
            config["provider"] = config.get("provider", provider)

            validated_config = InputValidator.validate_config(config)

            instance = MCPClientInstance(
                name=validated_config["name"],
                provider=validated_config["provider"],
                command=validated_config["command"],
                args=validated_config.get("args", []),
                transport_type=validated_config.get("type", "stdio"),
                env=validated_config.get("env", {}),
                is_active=validated_config.get("isActive", True),
                metadata=validated_config.get("metadata", {}),
                timeout=self.timeout,
            )

            if instance.is_active:
                await instance.connect()

            self._instances[instance.name] = instance
            logger.info(f"Instance '{instance.name}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to create instance from config: {e}")
            raise

    async def add_instance(
        self, provider: str, config: dict[str, Any], save_to_file: bool = True
    ) -> str:
        """Add a new instance.

        Args:
            provider: Provider name
            config: Instance configuration
            save_to_file: Whether to save configuration to file

        Returns:
            Instance name
        """
        config["provider"] = provider
        validated_config = InputValidator.validate_config(config)

        instance_name = validated_config["name"]

        if instance_name in self._instances:
            raise ConfigurationError(f"Instance '{instance_name}' already exists")

        if save_to_file:
            provider_path = self.data_path / provider
            provider_path.mkdir(parents=True, exist_ok=True)

            config_path = provider_path / "mcp_settings.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(validated_config, f, indent=2, ensure_ascii=False)

        await self._create_instance_from_config(validated_config, provider)

        return instance_name

    async def remove_instance(self, instance_name: str, delete_file: bool = True) -> None:
        """Remove an instance.

        Args:
            instance_name: Name of instance to remove
            delete_file: Whether to delete configuration file
        """
        if instance_name not in self._instances:
            raise InstanceNotFoundError(instance_name)

        instance = self._instances[instance_name]

        await instance.disconnect()

        if delete_file:
            provider_path = self.data_path / instance.provider
            config_path = provider_path / "mcp_settings.json"
            if config_path.exists():
                config_path.unlink()

        del self._instances[instance_name]
        logger.info(f"Instance '{instance_name}' removed")

    async def enable_instance(self, instance_name: str) -> None:
        """Enable an instance.

        Args:
            instance_name: Name of instance to enable
        """
        if instance_name not in self._instances:
            raise InstanceNotFoundError(instance_name)

        instance = self._instances[instance_name]
        instance.is_active = True

        if not instance.is_connected():
            await instance.connect()

        logger.info(f"Instance '{instance_name}' enabled")

    async def disable_instance(self, instance_name: str) -> None:
        """Disable an instance.

        Args:
            instance_name: Name of instance to disable
        """
        if instance_name not in self._instances:
            raise InstanceNotFoundError(instance_name)

        instance = self._instances[instance_name]
        instance.is_active = False

        logger.info(f"Instance '{instance_name}' disabled")

    def get_instance(self, instance_name: str) -> MCPClientInstance:
        """Get an instance by name.

        Args:
            instance_name: Instance name

        Returns:
            MCPClientInstance

        Raises:
            InstanceNotFoundError: If instance not found
        """
        if instance_name not in self._instances:
            raise InstanceNotFoundError(instance_name)

        return self._instances[instance_name]

    def list_instances(self) -> list[dict[str, Any]]:
        """List all instances.

        Returns:
            List of instance dictionaries
        """
        return [instance.to_dict() for instance in self._instances.values()]

    def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """Get all tools from all instances.

        Returns:
            Dictionary mapping instance names to their tools
        """
        result = {}
        for name, instance in self._instances.items():
            if instance.is_active and instance.is_connected():
                tools = instance.get_tools()
                result[name] = list(tools.values())

        return result

    async def shutdown(self) -> None:
        """Shutdown all instances."""
        logger.info("Shutting down all MCP instances...")

        for instance in self._instances.values():
            try:
                await instance.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting instance '{instance.name}': {e}")

        logger.info("All instances shut down")
