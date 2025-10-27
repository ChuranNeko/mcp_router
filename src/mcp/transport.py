"""Transport layer implementations for MCP."""

from enum import Enum
from typing import Any

from mcp.client.stdio import stdio_client

from mcp import StdioServerParameters

from ..core.logger import get_logger

logger = get_logger(__name__)


class TransportType(Enum):
    """Supported transport types."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


def create_transport(
    transport_type: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> Any:
    """Create appropriate transport based on type.

    Args:
        transport_type: Type of transport (stdio, sse, http)
        command: Command to execute
        args: Command arguments
        env: Environment variables

    Returns:
        Transport context manager

    Raises:
        ValueError: If transport type is not supported
    """
    args = args or []
    env = env or {}

    if transport_type == TransportType.STDIO.value:
        server_params = StdioServerParameters(command=command, args=args, env=env)
        return stdio_client(server_params)
    elif transport_type == TransportType.SSE.value:
        raise NotImplementedError("SSE transport not yet implemented")
    elif transport_type == TransportType.HTTP.value:
        raise NotImplementedError("HTTP transport not yet implemented")
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")
