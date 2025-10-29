"""Logging system for MCP Router."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

_loggers = {}


class StdioNoiseFilter(logging.Filter):
    """过滤MCP客户端stdio通信中的已知噪音错误"""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out known harmless errors from MCP stdio communication.

        Args:
            record: Log record to filter

        Returns:
            False if record should be filtered out, True otherwise
        """
        # 完全过滤掉MCP客户端的JSON解析错误（由子进程的非JSON输出引起）
        if record.name == "mcp.client.stdio":
            msg = record.getMessage()
            # 已知的harmless错误模式
            harmless_patterns = [
                "Failed to parse JSONRPC message from server",
                "Invalid JSON: expected value",
                "Apifox MCP Server",
                "请阅读帮助文档",
            ]
            # 完全过滤掉包含这些模式的消息
            if any(pattern in msg for pattern in harmless_patterns):
                return False

        return True


def setup_logging(
    level: str = "INFO",
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_directory: str = "logs",
    transport_mode: str = "stdio",
) -> None:
    """Setup logging configuration with Minecraft-style log rotation.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF)
        log_format: Log message format
        log_directory: Directory to store log files
        transport_mode: Transport mode for log file naming (stdio/http/sse/http+sse)
    """
    if level == "OFF":
        logging.disable(logging.CRITICAL)
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 移除现有的handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(log_format)

    # 创建噪音过滤器
    noise_filter = StdioNoiseFilter()

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(noise_filter)  # 添加过滤器到处理器
    root_logger.addHandler(console_handler)

    # Minecraft风格的日志文件
    log_dir = Path(log_directory)
    log_dir.mkdir(parents=True, exist_ok=True)

    latest_log = log_dir / "latest.txt"

    # 如果latest.txt存在，备份为时间戳文件（不带传输模式，因为是旧日志）
    if latest_log.exists():
        # 获取文件的修改时间
        mtime = latest_log.stat().st_mtime
        timestamp = datetime.fromtimestamp(mtime)
        # 格式：YY.MM.DD-HH-MM.txt
        backup_name = timestamp.strftime("%y.%m.%d-%H-%M.txt")
        backup_path = log_dir / backup_name

        # 如果同名备份已存在，添加序号
        counter = 1
        while backup_path.exists():
            backup_name = timestamp.strftime(f"%y.%m.%d-%H-%M-{counter}.txt")
            backup_path = log_dir / backup_name
            counter += 1

        # 移动旧日志
        shutil.move(str(latest_log), str(backup_path))

    # 生成新的日志文件名（带传输模式）
    now = datetime.now()
    timestamp = now.strftime("%y.%m.%d-%H-%M")

    # 如果同一分钟内有多个日志文件，添加序号
    timestamped_log = log_dir / f"{timestamp}-{transport_mode}.txt"
    counter = 1
    while timestamped_log.exists():
        timestamped_log = log_dir / f"{timestamp}-{transport_mode}-{counter}.txt"
        counter += 1

    # 创建文件处理器 - latest.txt和时间戳日志
    file_handler = logging.FileHandler(latest_log, mode="w", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(noise_filter)  # 添加过滤器到文件处理器
    root_logger.addHandler(file_handler)

    timestamped_handler = logging.FileHandler(timestamped_log, mode="w", encoding="utf-8")
    timestamped_handler.setLevel(numeric_level)
    timestamped_handler.setFormatter(formatter)
    timestamped_handler.addFilter(noise_filter)
    root_logger.addHandler(timestamped_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]
