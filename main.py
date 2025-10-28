"""MCP Router - Main entry point."""

import asyncio
import sys
from pathlib import Path

import uvicorn

from src.core.config import ConfigManager
from src.core.logger import get_logger, setup_logging
from src.mcp.client import MCPClientManager
from src.mcp.router import MCPRouter
from src.mcp.server import MCPServer
from src.utils.security import SecurityManager
from src.utils.watcher import FileWatcher

logger = get_logger(__name__)


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

    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    await client_manager.load_configurations()

    router = MCPRouter(client_manager)

    watcher = None
    watcher_queue = None

    if config.get("watcher.enabled", True):
        watcher = FileWatcher(
            watch_path=data_path,
            debounce_delay=config.get("watcher.debounce_delay", 1.0),
        )
        watcher_queue = watcher.start()
        logger.info("Config watcher isolated in subprocess - main process stable")

    server = MCPServer(router, name="mcp_router")

    async def run_with_watcher():
        """Run server with watcher polling."""
        # Start both server and watcher polling
        await asyncio.gather(
            server.run(),
            poll_watcher_queue(watcher_queue, client_manager)
            if watcher_queue
            else asyncio.sleep(float("inf")),
        )

    try:
        if watcher_queue:
            await run_with_watcher()
        else:
            await server.run()
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

    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    await client_manager.load_configurations()

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
        logger.info("Config watcher isolated in subprocess - main process stable")

    app = create_app(
        mcp_router=router,
        security_manager=security_manager,
        cors_origin=config.get("api.cors_origin", "*"),
    )

    host = config.get("api.host", "127.0.0.1")
    port = config.get("api.port", 8000)

    logger.info(f"API server will listen on {host}:{port}")

    uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uvicorn_config)

    async def run_with_watcher():
        """Run API server with watcher polling."""
        await asyncio.gather(
            server.serve(),
            poll_watcher_queue(watcher_queue, client_manager)
            if watcher_queue
            else asyncio.sleep(float("inf")),
        )

    try:
        if watcher_queue:
            await run_with_watcher()
        else:
            await server.serve()
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

    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    await client_manager.load_configurations()

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
        logger.info("Config watcher isolated in subprocess - main process stable")

    async def run_mcp():
        """Run MCP stdio server."""
        server = MCPServer(router, name="mcp_router")
        await server.run()

    async def run_api():
        """Run API server."""
        from src.api.app import create_app

        app = create_app(
            mcp_router=router,
            security_manager=security_manager,
            cors_origin=config.get("api.cors_origin", "*"),
        )

        host = config.get("api.host", "127.0.0.1")
        port = config.get("api.port", 8000)

        uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(uvicorn_config)
        await server.serve()

    tasks = [run_mcp(), run_api()]
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

        setup_logging(
            level=config.get("logging.level", "INFO"),
            log_format=config.get("logging.format"),
            log_file=config.get("logging.file"),
            max_bytes=config.get("logging.max_bytes", 10485760),
            backup_count=config.get("logging.backup_count", 5),
        )

        logger.info("=" * 60)
        logger.info("MCP Router v1.0.0")
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
