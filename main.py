"""MCP Router - Main entry point."""

import asyncio
import socket
import sys
from pathlib import Path

import uvicorn

from src import __version__
from src.core.config import ConfigManager
from src.core.logger import get_logger, setup_logging
from src.mcp.client import MCPClientManager
from src.mcp.router import MCPRouter
from src.mcp.server import MCPServer
from src.utils.security import SecurityManager
from src.utils.watcher import FileWatcher

logger = get_logger(__name__)


def find_available_port(host: str, start_port: int, max_attempts: int = 100) -> int:
    """查找可用端口，从start_port开始递增。

    Args:
        host: 主机地址
        start_port: 起始端口
        max_attempts: 最大尝试次数

    Returns:
        可用的端口号

    Raises:
        RuntimeError: 如果找不到可用端口
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"无法找到可用端口 (尝试范围: {start_port}-{start_port + max_attempts - 1})")


async def poll_watcher_queue(queue, client_manager):
    """Poll watcher queue for file changes without blocking main process.

    Args:
        queue: Multiprocessing queue from watcher subprocess
        client_manager: MCP client manager instance
    """
    while True:
        try:
            # Non-blocking check for events
            if not queue.empty():
                event = queue.get_nowait()
                file_path = event["path"]
                event_type = event["event_type"]

                logger.info(f"Config file {event_type}: {file_path}")

                path = Path(file_path)
                provider = path.parent.name

                # Log only, don't reload to avoid disrupting connections
                if event_type == "deleted":
                    logger.info(
                        f"Config deleted for provider '{provider}' (reload on next restart)"
                    )
                else:
                    logger.info(
                        f"Config updated for provider '{provider}' (reload on next restart)"
                    )

            # Sleep to avoid busy-waiting
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error polling watcher queue: {e}")
            await asyncio.sleep(1)


async def run_mcp_server(config: ConfigManager):
    """Run MCP server mode (stdio).

    Args:
        config: Configuration manager
    """
    logger.info("Starting MCP Router in SERVER mode (stdio)...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    router = MCPRouter(client_manager)

    watcher = None
    watcher_queue = None

    if config.get("watcher.enabled", True):
        watcher = FileWatcher(
            watch_path=data_path,
            debounce_delay=config.get("watcher.debounce_delay", 1.0),
        )
        watcher_queue = watcher.start()

    # 初始化并启动 MCP 服务器（立即启动，不等待客户端加载）
    allow_management = config.get("server.allow_instance_management", False)
    server = MCPServer(router, name="mcp_router", allow_instance_management=allow_management)
    logger.info(f"MCP Server ready - starting service... (management: {allow_management})")

    async def load_clients_in_background():
        """在后台加载客户端配置"""
        try:
            await client_manager.load_configurations()
            logger.info("All MCP client instances loaded in background")
        except Exception as e:
            logger.error(f"Error loading MCP clients: {e}", exc_info=True)

    # 并发运行：服务器 + 后台加载客户端 + 配置监视
    tasks = [server.run(), load_clients_in_background()]
    if watcher_queue:
        tasks.append(poll_watcher_queue(watcher_queue, client_manager))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down MCP server...")
    finally:
        if watcher:
            watcher.stop()
        await client_manager.shutdown()


async def run_api_server(config: ConfigManager):
    """Run API server mode.

    Args:
        config: Configuration manager
    """
    from src.api.app import create_app

    logger.info("Starting MCP Router in API mode...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    router = MCPRouter(client_manager)

    security_manager = SecurityManager(
        bearer_token=config.get("security.bearer_token"),
        enable_validation=config.get("security.enable_validation", True),
    )

    watcher = None
    watcher_queue = None

    if config.get("watcher.enabled", True):
        watcher = FileWatcher(
            watch_path=data_path,
            debounce_delay=config.get("watcher.debounce_delay", 1.0),
        )
        watcher_queue = watcher.start()

    # 创建 API 应用（立即启动，不等待客户端加载）
    enable_realtime_logs = config.get("api.enable_realtime_logs", False)

    # 如果启用WebSocket实时日志，添加日志处理器
    if enable_realtime_logs:
        from src.utils.websocket_logger import enable_websocket_logging

        enable_websocket_logging(
            level=config.get("logging.level", "INFO"),
            log_format=config.get("logging.format"),
        )
        logger.info("WebSocket realtime logging enabled")

    app = create_app(
        mcp_router=router,
        security_manager=security_manager,
        cors_origin=config.get("api.cors_origin", "*"),
        enable_realtime_logs=enable_realtime_logs,
    )

    host = config.get("api.host", "127.0.0.1")
    start_port = config.get("api.port", 8000)
    auto_find_port = config.get("api.auto_find_port", True)

    # 查找可用端口
    if auto_find_port:
        port = find_available_port(host, start_port)
        if port != start_port:
            logger.warning(f"端口 {start_port} 不可用，使用端口 {port}")
    else:
        port = start_port

    logger.info(f"API server ready at {host}:{port} - starting service...")

    uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uvicorn_config)

    async def load_clients_in_background():
        """在后台加载客户端配置"""
        try:
            await client_manager.load_configurations()
            logger.info("All MCP client instances loaded in background")
        except Exception as e:
            logger.error(f"Error loading MCP clients: {e}", exc_info=True)

    # 并发运行：API 服务器 + 后台加载客户端 + 配置监视
    tasks = [server.serve(), load_clients_in_background()]
    if watcher_queue:
        tasks.append(poll_watcher_queue(watcher_queue, client_manager))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down API server...")
    finally:
        if watcher:
            watcher.stop()
        await client_manager.shutdown()


async def run_combined_mode(config: ConfigManager):
    """Run both MCP server and API server.

    Args:
        config: Configuration manager
    """
    logger.info("Starting MCP Router in COMBINED mode...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    router = MCPRouter(client_manager)

    security_manager = SecurityManager(
        bearer_token=config.get("security.bearer_token"),
        enable_validation=config.get("security.enable_validation", True),
    )

    watcher = None
    watcher_queue = None

    if config.get("watcher.enabled", True):
        watcher = FileWatcher(
            watch_path=data_path,
            debounce_delay=config.get("watcher.debounce_delay", 1.0),
        )
        watcher_queue = watcher.start()

    async def run_mcp():
        """Run MCP stdio server."""
        allow_management = config.get("server.allow_instance_management", False)
        server = MCPServer(router, name="mcp_router", allow_instance_management=allow_management)
        await server.run()

    async def run_api():
        """Run API server."""
        from src.api.app import create_app

        enable_realtime_logs = config.get("api.enable_realtime_logs", False)

        # 如果启用WebSocket实时日志，添加日志处理器
        if enable_realtime_logs:
            from src.utils.websocket_logger import enable_websocket_logging

            enable_websocket_logging(
                level=config.get("logging.level", "INFO"),
                log_format=config.get("logging.format"),
            )
            logger.info("WebSocket realtime logging enabled")

        app = create_app(
            mcp_router=router,
            security_manager=security_manager,
            cors_origin=config.get("api.cors_origin", "*"),
            enable_realtime_logs=enable_realtime_logs,
        )

        host = config.get("api.host", "127.0.0.1")
        start_port = config.get("api.port", 8000)
        auto_find_port = config.get("api.auto_find_port", True)

        # 查找可用端口
        if auto_find_port:
            port = find_available_port(host, start_port)
            if port != start_port:
                logger.warning(f"端口 {start_port} 不可用，使用端口 {port}")
        else:
            port = start_port

        logger.info(f"API server listening on {host}:{port}")

        uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(uvicorn_config)
        await server.serve()

    # MCP Server + API立即启动，不等待客户端加载
    logger.info("MCP Server + API ready - starting services...")

    async def load_clients_in_background():
        """在后台加载客户端配置"""
        try:
            await client_manager.load_configurations()
            logger.info("All MCP client instances loaded in background")
        except Exception as e:
            logger.error(f"Error loading MCP clients: {e}", exc_info=True)

    tasks = [run_mcp(), run_api(), load_clients_in_background()]
    if watcher_queue:
        tasks.append(poll_watcher_queue(watcher_queue, client_manager))

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down MCP Router...")
    finally:
        if watcher:
            watcher.stop()
        await client_manager.shutdown()


def main():
    """Main entry point."""
    try:
        config = ConfigManager("config.json")

        # Minecraft风格日志配置
        setup_logging(
            level=config.get("logging.level", "INFO"),
            log_format=config.get("logging.format"),
            log_directory=config.get("logging.directory", "logs"),
        )

        logger.info("=" * 60)
        logger.info(f"MCP Router v{__version__}")
        logger.info("=" * 60)

        api_enabled = config.get("api.enabled", False)
        server_enabled = config.get("server.enabled", True)

        if server_enabled and api_enabled:
            logger.info("Mode: COMBINED (MCP Server + API)")
            asyncio.run(run_combined_mode(config))
        elif server_enabled:
            logger.info("Mode: MCP SERVER (stdio)")
            asyncio.run(run_mcp_server(config))
        elif api_enabled:
            logger.info("Mode: API ONLY")
            asyncio.run(run_api_server(config))
        else:
            logger.error("No mode enabled! Please enable either 'server' or 'api' in config.json")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
