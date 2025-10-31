"""MCP Router - Main entry point."""

import argparse
import asyncio
import atexit
import json
import signal
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
from src.utils.validator import InputValidator
from src.utils.watcher import FileWatcher

logger = get_logger(__name__)

# 全局变量用于清理
_watcher = None
_client_manager = None
_shutdown_requested = False


def cleanup():
    """同步清理资源（仅处理不需要事件循环的资源）"""
    global _watcher
    if _watcher:
        try:
            _watcher.stop()
        except Exception:
            pass


def signal_handler(signum, frame):
    """处理系统信号 - 第一次优雅关闭，第二次强制退出"""
    global _shutdown_requested

    if _shutdown_requested:
        # 第二次 Ctrl+C - 强制退出
        logger.warning("强制退出...")
        cleanup()
        sys.exit(1)
    else:
        # 第一次 Ctrl+C - 优雅关闭
        logger.info(f"接收到信号 {signum}，正在优雅关闭... (再次按 Ctrl+C 强制退出)")
        _shutdown_requested = True
        raise KeyboardInterrupt


# 注册清理函数
atexit.register(cleanup)

# 注册信号处理（支持两次 Ctrl+C）
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def _extract_name_from_config(data: dict) -> str | None:
    """从配置字典中提取 name 字段。

    Args:
        data: 配置字典（可能是顶层对象或 mcpServers 格式）

    Returns:
        配置中的 name 字段值，如果不存在则返回 None
    """
    if isinstance(data, dict) and "mcpServers" in data and isinstance(data["mcpServers"], dict):
        # mcpServers 格式：遍历子项
        for _key, server_cfg in data["mcpServers"].items():
            if isinstance(server_cfg, dict) and "name" in server_cfg:
                return str(server_cfg["name"])
    elif isinstance(data, dict) and "name" in data:
        # 顶层对象格式：直接读取 name 字段
        return str(data["name"])
    return None


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
    """Run MCP server mode with specified transport.

    Args:
        config: Configuration manager
    """
    global _watcher, _client_manager

    transport_type = config.get("server.transport_type", "stdio")
    logger.info(f"Starting MCP Router in SERVER mode ({transport_type})...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    _client_manager = client_manager
    router = MCPRouter(client_manager)

    watcher = None
    watcher_queue = None

    if config.get("watcher.enabled", True):
        watcher = FileWatcher(
            watch_path=data_path,
            debounce_delay=config.get("watcher.debounce_delay", 1.0),
        )
        _watcher = watcher
        watcher_queue = watcher.start()

    # 初始化并启动 MCP 服务器（立即启动，不等待客户端加载）
    allow_management = config.get("server.allow_instance_management", False)
    server = MCPServer(
        router,
        name="mcp_router",
        allow_instance_management=allow_management,
        transport_type=transport_type,
    )
    logger.info(
        f"MCP Server ready - starting service... (management: {allow_management}, transport: {transport_type})"
    )

    async def load_clients_in_background():
        """在后台加载客户端配置"""
        try:
            await client_manager.load_configurations()
            logger.info("All MCP client instances loaded in background")
        except Exception as e:
            logger.error(f"Error loading MCP clients: {e}", exc_info=True)

    # 并发运行：服务器 + 后台加载客户端 + 配置监视
    host = config.get("server.host", "127.0.0.1")

    if transport_type == "stdio":
        tasks = [server.run(), load_clients_in_background()]
    else:
        # SSE/HTTP需要host和port - 根据传输模式获取对应端口
        port_key = f"server.{transport_type}.port"
        default_ports = {"http": 3000, "sse": 3001}
        port = config.get(port_key, default_ports.get(transport_type, 3000))
        logger.info(f"MCP Server will listen on {host}:{port} ({transport_type} mode)")
        tasks = [server.run(host, port), load_clients_in_background()]

    if watcher_queue:
        tasks.append(poll_watcher_queue(watcher_queue, client_manager))

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down MCP server...")
    finally:
        # 清理资源，使用超时保护确保不会卡住
        cleanup_tasks = []

        if watcher:
            try:
                watcher.stop()
            except Exception as e:
                logger.error(f"Error stopping watcher: {e}")

        if client_manager:
            cleanup_tasks.append(client_manager.shutdown())

        # 等待清理完成，最多等待10秒
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Cleanup timeout, forcing exit")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


async def run_api_server(config: ConfigManager):
    """Run API server mode.

    Args:
        config: Configuration manager
    """
    global _watcher, _client_manager

    from src.api.app import create_app

    logger.info("Starting MCP Router in API mode...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    _client_manager = client_manager
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
        _watcher = watcher
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
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down API server...")
    finally:
        # 清理资源，使用超时保护确保不会卡住
        cleanup_tasks = []

        if watcher:
            try:
                watcher.stop()
            except Exception as e:
                logger.error(f"Error stopping watcher: {e}")

        if client_manager:
            cleanup_tasks.append(client_manager.shutdown())

        # 等待清理完成，最多等待10秒
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Cleanup timeout, forcing exit")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


async def run_combined_mode(config: ConfigManager):
    """Run both MCP server and API server.

    Args:
        config: Configuration manager
    """
    global _watcher, _client_manager

    logger.info("Starting MCP Router in COMBINED mode...")

    timeout = config.get("mcp_client.timeout", 30.0)
    data_path = config.get("watcher.watch_path", "data")

    # 初始化管理器
    client_manager = MCPClientManager(data_path=data_path, timeout=timeout)
    _client_manager = client_manager
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
        _watcher = watcher
        watcher_queue = watcher.start()

    async def run_mcp():
        """Run MCP server."""
        allow_management = config.get("server.allow_instance_management", False)
        transport_type = config.get("server.transport_type", "stdio")
        host = config.get("server.host", "127.0.0.1")

        server = MCPServer(
            router,
            name="mcp_router",
            allow_instance_management=allow_management,
            transport_type=transport_type,
        )
        if transport_type == "stdio":
            await server.run()
        else:
            # 根据传输模式获取对应端口
            port_key = f"server.{transport_type}.port"
            default_ports = {"http": 3000, "sse": 3001}
            port = config.get(port_key, default_ports.get(transport_type, 3000))
            logger.info(f"MCP Server listening on {host}:{port} ({transport_type} mode)")
            await server.run(host, port)

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
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down MCP Router...")
    finally:
        # 清理资源，使用超时保护确保不会卡住
        cleanup_tasks = []

        if watcher:
            try:
                watcher.stop()
            except Exception as e:
                logger.error(f"Error stopping watcher: {e}")

        if client_manager:
            cleanup_tasks.append(client_manager.shutdown())

        # 等待清理完成，最多等待10秒
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Cleanup timeout, forcing exit")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def parse_args_for_help():
    """显示帮助信息"""
    parser = argparse.ArgumentParser(
        description="MCP Router - A routing/proxy system for MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Stdio模式（默认，用于Cursor/Claude Desktop）
  python main.py
  python main.py stdio

  # HTTP模式（多客户端）
  python main.py http

  # SSE模式（实时推送）
  python main.py sse

  # API服务器模式（单独启动，无论配置如何）
  python main.py api

  # 显示帮助信息
  python main.py help

注意：
  - 传输模式默认为stdio
  - API服务器是否启动由config.json中的api.enabled决定（除非使用 api 参数）
  - HTTP/SSE的host和port在config.json中配置
        """,
    )

    parser.add_argument(
        "transport",
        nargs="?",
        default="stdio",
        choices=["stdio", "http", "sse", "api", "help", "add"],
        help="MCP传输模式或命令 (默认: stdio)",
    )

    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        default="config.json",
        help="配置文件路径 (默认: config.json)",
    )

    parser.add_argument(
        "-l",
        "--log-level",
        metavar="LEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "OFF"],
        help="日志级别",
    )

    parser.add_argument("-v", "--version", action="version", version=f"MCP Router v{__version__}")

    parser.print_help()


def parse_args():
    """解析命令行参数，返回(已知参数, 其余位置参数)"""
    parser = argparse.ArgumentParser(
        description="MCP Router - A routing/proxy system for MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Stdio模式（默认，用于Cursor/Claude Desktop）
  python main.py
  python main.py stdio

  # HTTP模式（多客户端）
  python main.py http

  # SSE模式（实时推送）
  python main.py sse

  # API服务器模式（单独启动，无论配置如何）
  python main.py api

  # 显示帮助信息
  python main.py help

注意：
  - 传输模式默认为stdio
  - API服务器是否启动由config.json中的api.enabled决定（除非使用 api 参数）
  - HTTP/SSE的host和port在config.json中配置
        """,
    )

    parser.add_argument(
        "transport",
        nargs="?",
        default="stdio",
        choices=["stdio", "http", "sse", "api", "help", "add"],
        help="MCP传输模式或命令 (默认: stdio)",
    )

    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        default="config.json",
        help="配置文件路径 (默认: config.json)",
    )

    parser.add_argument(
        "-l",
        "--log-level",
        metavar="LEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "OFF"],
        help="日志级别",
    )

    parser.add_argument("-v", "--version", action="version", version=f"MCP Router v{__version__}")

    # 允许在 add 命令后附加位置参数，不作为未知参数报错
    args, extra = parser.parse_known_args()
    return args, extra


def main():
    """Main entry point."""
    try:
        # 解析命令行参数（兼容 add 的附加位置参数）
        args, extra_args = parse_args()

        # 处理 help 命令
        if args.transport == "help":
            parse_args_for_help()
            return

        # 加载配置文件
        config = ConfigManager(args.config)

        # 从命令行获取传输模式
        transport_type = args.transport

        # 处理 add 命令（格式化目标文件夹的 mcp_settings.json 并写入 name 字段）
        if transport_type == "add":
            # 读取附加参数：实例名称、文件夹名称（provider）、可选的显示名称（可为中文）
            if len(extra_args) < 2:
                print("用法: python main.py add <实例名称> <文件夹名称> [显示名称]")
                print("  实例名称: 必须与文件夹名称一致，仅允许 a-zA-Z0-9_-")
                print("  文件夹名称: provider 字段，仅允许 a-zA-Z0-9_-")
                print("  显示名称: 可选，name 字段，可为中文，如不提供则与实例名称相同")
                return

            instance_name = extra_args[0]
            provider_name = extra_args[1]
            display_name = extra_args[2] if len(extra_args) >= 3 else instance_name

            # 硬性规定：文件夹名称为实例名称，且不得包含中文（仅允许 a-zA-Z0-9_-）
            # 先校验 provider 命名合法性（不含中文）
            InputValidator.validate_provider_name(provider_name)
            # 实例名称必须与文件夹名称一致，且也使用 provider 规则校验，保证不含中文
            if instance_name != provider_name:
                raise ValueError(
                    f"实例名称必须与文件夹名称一致: 实例='{instance_name}', 文件夹='{provider_name}'"
                )
            InputValidator.validate_provider_name(instance_name)

            # 校验 provider 目录与文件
            data_dir = Path(config.get("watcher.watch_path", "data"))
            provider_dir = data_dir / provider_name
            settings_path = provider_dir / "mcp_settings.json"

            if not settings_path.exists():
                raise FileNotFoundError(
                    f"未找到配置文件: {settings_path}. 请确保文件存在且命名为 mcp_settings.json"
                )

            # 收集现有实例名称，确保唯一（排除当前文件）
            # 注意：检查的是 name 字段的唯一性（可能包含中文），不是 instance_name
            existing_names: set[str] = set()
            for cfg_file in data_dir.glob("*/mcp_settings.json"):
                # 排除当前正在处理的文件
                if cfg_file == settings_path:
                    continue
                try:
                    content = cfg_file.read_text(encoding="utf-8").strip()
                    if not content:
                        continue
                    data = json.loads(content)
                    name = _extract_name_from_config(data)
                    if name:
                        existing_names.add(name)
                except Exception:
                    # 跳过损坏/非法配置文件
                    continue

            if display_name in existing_names:
                raise ValueError(f"实例名称已存在: {display_name}")

            # 读取目标配置并写入 name 字段
            raw = settings_path.read_text(encoding="utf-8").strip()
            if not raw:
                raise ValueError(f"配置文件为空: {settings_path}")

            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"配置文件 JSON 解析失败: {e}") from e

            updated = False
            server_cfg = None

            # 支持两种输入格式：mcpServers 包装格式 或 顶层对象格式
            if (
                isinstance(obj, dict)
                and "mcpServers" in obj
                and isinstance(obj["mcpServers"], dict)
            ):
                # mcpServers 格式：提取配置对象
                servers = obj["mcpServers"]
                if len(servers) != 1:
                    raise ValueError(
                        f"mcp_settings.json 中的 mcpServers 必须仅包含一个服务条目，当前: {len(servers)}"
                    )
                key = next(iter(servers.keys()))
                server_cfg = servers[key]
                if not isinstance(server_cfg, dict):
                    raise ValueError("mcpServers 项格式非法，应为对象")
                updated = True  # 从 mcpServers 格式转换需要更新
            elif isinstance(obj, dict):
                # 顶层对象格式：直接使用
                server_cfg = dict(obj)
            else:
                raise ValueError("不支持的配置结构，应为对象或包含 mcpServers 的对象")

            # 规范化配置字段（统一输出为顶层对象格式）
            if server_cfg is not None:
                # 确保 name 字段存在且正确（使用 display_name，可为中文）
                if server_cfg.get("name") != display_name:
                    server_cfg["name"] = display_name
                    updated = True

                # 确保 provider 字段存在
                if server_cfg.get("provider") != provider_name:
                    server_cfg["provider"] = provider_name
                    updated = True

                # 将 transport 字段转换为 type 字段（如果存在）
                if "transport" in server_cfg and "type" not in server_cfg:
                    server_cfg["type"] = server_cfg.pop("transport")
                    updated = True
                elif "transport" in server_cfg and "type" in server_cfg:
                    # 如果两者都存在，删除 transport，保留 type
                    server_cfg.pop("transport")
                    updated = True

                # 确保 type 字段存在（必需字段）
                if "type" not in server_cfg:
                    # 默认使用 stdio
                    server_cfg["type"] = "stdio"
                    updated = True
                    logger.warning("配置缺少 type 字段，已设置为默认值 'stdio'")

                # 确保 isActive 字段存在（默认 true）
                if "isActive" not in server_cfg:
                    server_cfg["isActive"] = True
                    updated = True

                # 统一输出为顶层对象格式（项目标准格式）
                # 按标准字段顺序重新组织：name, type, command, args, env, isActive, provider
                ordered_obj = {}
                field_order = ["name", "type", "command", "args", "env", "isActive", "provider"]

                # 按顺序添加字段
                for field in field_order:
                    if field in server_cfg:
                        ordered_obj[field] = server_cfg[field]

                # 添加其他未列出的字段（metadata等）
                for key, value in server_cfg.items():
                    if key not in field_order:
                        ordered_obj[key] = value

                obj = ordered_obj

            # 总是写入规范化后的配置，确保字段顺序正确
            settings_path.write_text(
                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if updated:
                logger.info(
                    f"已更新 {settings_path}，规范化配置完成 (name: '{display_name}', provider: '{provider_name}')"
                )
            else:
                logger.info(
                    f"{settings_path} 配置已规范化，字段顺序已调整 (name: '{display_name}')"
                )

            return

        # 处理 api 命令（单独启动 API 服务器）
        if transport_type == "api":
            # API 模式下使用 "api" 作为日志文件名标识
            log_mode = "api"
        else:
            # 其他模式使用传输类型作为日志文件名标识
            log_mode = transport_type

        # 日志配置（命令行优先，传入log_mode用于日志文件命名）
        log_level = args.log_level or config.get("logging.level", "INFO")
        setup_logging(
            level=log_level,
            log_format=config.get("logging.format"),
            log_directory=config.get("logging.directory", "logs"),
            transport_mode=log_mode,  # 传递模式给日志系统
        )

        logger.info("=" * 60)
        logger.info(f"MCP Router v{__version__}")
        logger.info("=" * 60)

        # 如果是 api 命令，直接启动 API 服务器
        if transport_type == "api":
            logger.info("Mode: API ONLY (forced by command line)")
            asyncio.run(run_api_server(config))
            return

        # 确定运行模式
        # MCP服务器始终启动（使用命令行指定的传输模式）
        server_enabled = True
        # API服务器根据配置文件决定
        api_enabled = config.get("api.enabled", False)

        if server_enabled and api_enabled:
            mode = "combined"
        else:
            mode = "server"

        # 显示运行模式
        if mode == "combined":
            logger.info(f"Mode: COMBINED (MCP Server [{transport_type}] + API)")
        else:
            logger.info(f"Mode: MCP SERVER ({transport_type})")

        # 覆盖配置文件中的传输类型
        config._config["server"]["transport_type"] = transport_type

        # 运行对应模式
        if mode == "combined":
            asyncio.run(run_combined_mode(config))
        else:
            asyncio.run(run_mcp_server(config))

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
