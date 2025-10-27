"""MCP Server implementation."""

from collections.abc import Sequence
from typing import Any

from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp.server import Server

from ..core.logger import get_logger
from .router import MCPRouter

logger = get_logger(__name__)


class MCPServer:
    """MCP Server that exposes router tools to LLMs."""

    def __init__(self, router: MCPRouter, name: str = "mcp_router"):
        """Initialize MCP server.

        Args:
            router: MCP router instance
            name: Server name
        """
        self.router = router
        self.name = name
        self.server = Server(name)

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available router tools."""
            tools = [
                Tool(
                    name="mcp.router.use",
                    description="Use a specific MCP instance and return its available tools",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Name of the MCP instance to use",
                            }
                        },
                        "required": ["instance_name"],
                    },
                ),
                Tool(
                    name="mcp.router.list",
                    description="List all registered MCP client instances",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="mcp.router.help",
                    description="Get help information for all available tools across all instances",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="mcp.router.add",
                    description="Add a new MCP configuration dynamically",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "provider_name": {
                                "type": "string",
                                "description": "Provider name (alphanumeric and underscores only)",
                            },
                            "config": {
                                "type": "object",
                                "description": "MCP configuration object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string", "enum": ["stdio", "sse", "http"]},
                                    "command": {"type": "string"},
                                    "args": {"type": "array", "items": {"type": "string"}},
                                    "env": {"type": "object"},
                                    "isActive": {"type": "boolean"},
                                },
                                "required": ["name", "type", "command"],
                            },
                        },
                        "required": ["provider_name", "config"],
                    },
                ),
                Tool(
                    name="mcp.router.call",
                    description="Call a tool on a specific instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Name of the instance",
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to call",
                            },
                            "arguments": {"type": "object", "description": "Tool arguments"},
                        },
                        "required": ["instance_name", "tool_name"],
                    },
                ),
                Tool(
                    name="mcp.router.remove",
                    description="Remove an MCP configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Name of instance to remove",
                            }
                        },
                        "required": ["instance_name"],
                    },
                ),
                Tool(
                    name="mcp.router.disable",
                    description="Disable an MCP instance without removing its configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Name of instance to disable",
                            }
                        },
                        "required": ["instance_name"],
                    },
                ),
                Tool(
                    name="mcp.router.enable",
                    description="Enable a previously disabled MCP instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Name of instance to enable",
                            }
                        },
                        "required": ["instance_name"],
                    },
                ),
            ]

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                logger.info(f"Received tool call: {name}")

                result = None

                if name == "mcp.router.use":
                    result = await self.router.use(arguments["instance_name"])
                elif name == "mcp.router.list":
                    result = self.router.list()
                elif name == "mcp.router.help":
                    result = self.router.help()
                elif name == "mcp.router.add":
                    result = await self.router.add(arguments["provider_name"], arguments["config"])
                elif name == "mcp.router.call":
                    call_result = await self.router.call(
                        arguments["instance_name"],
                        arguments["tool_name"],
                        **arguments.get("arguments", {}),
                    )
                    # Extract content from CallToolResult
                    if hasattr(call_result, "content"):
                        # Convert content list to serializable format
                        result = []
                        for content_item in call_result.content:
                            if hasattr(content_item, "text"):
                                result.append({"type": "text", "text": content_item.text})
                            elif hasattr(content_item, "data"):
                                result.append({"type": "image", "data": content_item.data})
                            else:
                                result.append(str(content_item))
                    else:
                        result = str(call_result)
                elif name == "mcp.router.remove":
                    result = await self.router.remove(arguments["instance_name"])
                elif name == "mcp.router.disable":
                    result = await self.router.disable(arguments["instance_name"])
                elif name == "mcp.router.enable":
                    result = await self.router.enable(arguments["instance_name"])
                else:
                    raise ValueError(f"Unknown tool: {name}")

                import json

                result_text = json.dumps(result, ensure_ascii=False, indent=2)

                return [TextContent(type="text", text=result_text)]
            except Exception as e:
                logger.error(f"Error handling tool call '{name}': {e}")
                error_text = json.dumps(
                    {"error": str(e), "code": getattr(e, "code", "INTERNAL_ERROR")},
                    ensure_ascii=False,
                )
                return [TextContent(type="text", text=error_text)]

    async def run(self) -> None:
        """Run the MCP server using stdio transport."""
        logger.info(f"Starting MCP server '{self.name}' with stdio transport...")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )

    def get_server(self) -> Server:
        """Get underlying MCP server instance.

        Returns:
            MCP Server instance
        """
        return self.server
