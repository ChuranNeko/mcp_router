"""MCP Server implementation."""

from collections.abc import Sequence
from typing import Any

from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp.server import Server

from ..core.logger import get_logger
from .router import MCPRouter

logger = get_logger(__name__)

# 可选的SSE/HTTP传输支持
try:
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    logger.warning("SSE transport not available. Install mcp[sse] for SSE support.")


class MCPServer:
    """MCP Server that exposes router tools to LLMs."""

    def __init__(
        self,
        router: MCPRouter,
        name: str = "mcp_router",
        allow_instance_management: bool = False,
        transport_type: str = "stdio",
    ):
        """Initialize MCP server.

        Args:
            router: MCP router instance
            name: Server name
            allow_instance_management: Whether to allow LLM to manage instances (add/remove/enable/disable)
            transport_type: Transport type (stdio, sse, http)
        """
        self.router = router
        self.name = name
        self.allow_instance_management = allow_instance_management
        self.transport_type = transport_type
        self.server = Server(name)

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP server handlers."""

        # 定义处理器函数，同时保存引用供 HTTP 模式使用
        async def list_tools_impl() -> list[Tool]:
            """List all available router tools."""
            # 基础只读工具（总是可用）
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
                    description=(
                        "List all registered MCP client instances with their names and providers. "
                        "Use the 'name' field (or 'provider' field) when calling tools."
                    ),
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="mcp.router.help",
                    description="Get help information for all available tools across all instances",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="mcp.router.call",
                    description=(
                        "Call a tool on a specific instance. "
                        "Use either the full instance name or provider name as instance_name. "
                        "Use mcp.router.help to see available tools for each instance."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_name": {
                                "type": "string",
                                "description": "Instance name or provider name (e.g., 'napcat_api_doc' or full instance name)",
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
            ]

            # 管理工具（仅当允许时才添加）
            if self.allow_instance_management:
                management_tools = [
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
                                        "type": {
                                            "type": "string",
                                            "enum": ["stdio", "sse", "http"],
                                        },
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
                tools.extend(management_tools)

            return tools

        # 保存引用供 HTTP 模式使用
        self._list_tools_impl = list_tools_impl

        # 注册到 MCP server
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return await list_tools_impl()

        async def call_tool_impl(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                logger.info(f"Received tool call: {name}")

                # 检查管理工具权限
                management_tools = {
                    "mcp.router.add",
                    "mcp.router.remove",
                    "mcp.router.enable",
                    "mcp.router.disable",
                }
                if name in management_tools and not self.allow_instance_management:
                    raise PermissionError(
                        f"Instance management is disabled. Tool '{name}' is not available. "
                        "Enable 'server.allow_instance_management' in config.json to use this tool."
                    )

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

        # 保存引用供 HTTP 模式使用
        self._call_tool_impl = call_tool_impl

        # 注册到 MCP server
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
            return await call_tool_impl(name, arguments)

    async def run(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Run the MCP server using specified transport.

        Args:
            host: Host address (for SSE/HTTP)
            port: Port number (for SSE/HTTP)
        """
        if self.transport_type == "stdio":
            logger.info(f"Starting MCP server '{self.name}' with stdio transport...")
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream, write_stream, self.server.create_initialization_options()
                )
        elif self.transport_type in ["sse", "http", "http+sse"]:
            # 检查SSE依赖
            if self.transport_type in ["sse", "http+sse"] and not SSE_AVAILABLE:
                raise RuntimeError(
                    "SSE transport is not available. "
                    "Please install with: pip install 'mcp[sse]' or use transport_type='stdio'"
                )

            import uvicorn
            from starlette.requests import Request
            from starlette.responses import JSONResponse

            routes = []

            # SSE传输端点
            if self.transport_type in ["sse", "http+sse"]:
                from mcp.server.sse import SseServerTransport

                logger.info(f"Enabling SSE transport on {host}:{port}/sse")
                sse_transport = SseServerTransport("/messages")

                async def handle_sse(request):
                    async with sse_transport.connect_sse(
                        request.scope, request.receive, request._send
                    ) as streams:
                        await self.server.run(
                            streams[0], streams[1], self.server.create_initialization_options()
                        )

                # 使用ASGI接口直接处理POST消息
                async def handle_post_message_asgi(scope, receive, send):
                    """ASGI endpoint处理SSE的POST消息"""
                    await sse_transport.handle_post_message(scope, receive, send)

                routes.extend(
                    [
                        Route("/sse", endpoint=handle_sse),
                        # 使用Mount来包装ASGI app
                        Mount("/messages", app=handle_post_message_asgi, name="messages"),
                    ]
                )

            # HTTP传输端点
            if self.transport_type in ["http", "http+sse"]:
                logger.info(f"Enabling HTTP transport on {host}:{port}/mcp")

                # 用于存储会话状态
                _session_initialized = False

                async def handle_http(request: Request):
                    """Handle HTTP JSON-RPC requests."""
                    nonlocal _session_initialized
                    try:
                        data = await request.json()
                        method = data.get("method")
                        params = data.get("params", {})
                        request_id = data.get("id")

                        logger.debug(f"HTTP request: method={method}, id={request_id}")

                        # 处理 initialize 方法
                        if method == "initialize":
                            _session_initialized = True
                            result = {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {
                                    "tools": {"listChanged": False},
                                    "resources": {"subscribe": False, "listChanged": False},
                                    "prompts": {"listChanged": False},
                                },
                                "serverInfo": {"name": self.name, "version": "1.0.0"},
                            }
                            logger.info("MCP session initialized via HTTP")
                            return JSONResponse(
                                {"jsonrpc": "2.0", "id": request_id, "result": result}
                            )

                        # 处理 notifications/initialized (不需要响应)
                        if method == "notifications/initialized":
                            logger.debug("Received initialized notification")
                            return JSONResponse({"jsonrpc": "2.0"})

                        # 其他方法需要先初始化
                        if not _session_initialized and method not in ["ping"]:
                            return JSONResponse(
                                {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32002,
                                        "message": "Session not initialized. Call 'initialize' first.",
                                    },
                                },
                                status_code=400,
                            )

                        # 处理 ping
                        if method == "ping":
                            return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": {}})

                        # 处理 tools/list
                        if method == "tools/list":
                            tools = await self._list_tools_impl()
                            result = {"tools": [tool.model_dump() for tool in tools]}

                        # 处理 tools/call
                        elif method == "tools/call":
                            tool_name = params.get("name")
                            arguments = params.get("arguments", {})
                            call_result = await self._call_tool_impl(
                                tool_name, arguments
                            )
                            result = {"content": [c.model_dump() for c in call_result]}

                        # 处理 resources/list
                        elif method == "resources/list":
                            result = {"resources": []}

                        # 处理 prompts/list
                        elif method == "prompts/list":
                            result = {"prompts": []}

                        else:
                            return JSONResponse(
                                {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32601,
                                        "message": f"Method not found: {method}",
                                    },
                                },
                                status_code=400,
                            )

                        return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})

                    except Exception as e:
                        logger.error(f"Error handling HTTP request: {e}", exc_info=True)
                        return JSONResponse(
                            {
                                "jsonrpc": "2.0",
                                "id": data.get("id", None),
                                "error": {"code": -32603, "message": str(e)},
                            },
                            status_code=500,
                        )

                routes.append(Route("/mcp", endpoint=handle_http, methods=["POST"]))

            # 创建Starlette应用
            starlette_app = Starlette(debug=True, routes=routes)

            logger.info(f"Starting MCP server '{self.name}' on {host}:{port}")
            logger.info(f"Available endpoints: {[route.path for route in routes]}")

            # 配置uvicorn，让它不要干扰我们的日志系统
            config = uvicorn.Config(
                starlette_app,
                host=host,
                port=port,
                log_config=None,  # 完全禁用uvicorn的日志配置
                access_log=False,  # 禁用访问日志
            )

            # 创建服务器但不让它配置日志
            server = uvicorn.Server(config)

            # uvicorn的serve()会尝试配置日志，我们需要阻止它
            # 通过设置config.configure_logging = False来实现
            server.config.configure_logging = False

            logger.info(f"Uvicorn server configured on http://{host}:{port}")
            await server.serve()
        else:
            raise ValueError(f"Unsupported transport type: {self.transport_type}")

    def get_server(self) -> Server:
        """Get underlying MCP server instance.

        Returns:
            MCP Server instance
        """
        return self.server
