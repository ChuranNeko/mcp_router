"""WebSocket实时日志广播器."""

import asyncio
import logging
from typing import Set

from fastapi import WebSocket


class WebSocketLogHandler(logging.Handler):
    """日志处理器，将日志广播到所有WebSocket客户端."""

    def __init__(self):
        """初始化WebSocket日志处理器."""
        super().__init__()
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_client(self, websocket: WebSocket) -> None:
        """添加WebSocket客户端.

        Args:
            websocket: WebSocket连接
        """
        async with self._lock:
            self.clients.add(websocket)

    async def remove_client(self, websocket: WebSocket) -> None:
        """移除WebSocket客户端.

        Args:
            websocket: WebSocket连接
        """
        async with self._lock:
            self.clients.discard(websocket)

    def emit(self, record: logging.LogRecord) -> None:
        """发送日志记录到所有WebSocket客户端.

        Args:
            record: 日志记录
        """
        if not self.clients:
            return

        try:
            msg = self.format(record)
            # 在事件循环中异步发送
            asyncio.create_task(self._broadcast(msg))
        except Exception:
            self.handleError(record)

    async def _broadcast(self, message: str) -> None:
        """广播消息到所有客户端.

        Args:
            message: 要广播的消息
        """
        if not self.clients:
            return

        disconnected_clients = set()
        async with self._lock:
            clients_copy = self.clients.copy()

        for client in clients_copy:
            try:
                await client.send_text(message)
            except Exception:
                disconnected_clients.add(client)

        # 移除断开连接的客户端
        if disconnected_clients:
            async with self._lock:
                self.clients -= disconnected_clients


# 全局WebSocket日志处理器实例
_ws_log_handler: WebSocketLogHandler | None = None


def get_websocket_handler() -> WebSocketLogHandler:
    """获取全局WebSocket日志处理器.

    Returns:
        WebSocket日志处理器实例
    """
    global _ws_log_handler
    if _ws_log_handler is None:
        _ws_log_handler = WebSocketLogHandler()
    return _ws_log_handler


def enable_websocket_logging(
    level: str = "INFO",
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> None:
    """启用WebSocket日志广播.

    Args:
        level: 日志级别
        log_format: 日志格式
    """
    handler = get_websocket_handler()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)


def disable_websocket_logging() -> None:
    """禁用WebSocket日志广播."""
    global _ws_log_handler
    if _ws_log_handler is not None:
        root_logger = logging.getLogger()
        root_logger.removeHandler(_ws_log_handler)
        _ws_log_handler = None
