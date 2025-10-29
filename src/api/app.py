"""FastAPI application setup."""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .. import __version__
from ..core.logger import get_logger
from ..mcp.router import MCPRouter
from ..utils.security import SecurityManager
from ..utils.websocket_logger import get_websocket_handler
from .routes import create_router

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):
        """Initialize middleware.

        Args:
            app: FastAPI application
            max_size: Maximum request body size in bytes (default: 10MB)
        """
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        """Check request body size."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_size:
                return Response(
                    content=f"Request body too large. Maximum size: {self.max_size} bytes",
                    status_code=413,
                )

        return await call_next(request)


def create_app(
    mcp_router: MCPRouter,
    security_manager: SecurityManager,
    cors_origin: str = "*",
    title: str = "MCP Router API",
    version: str | None = None,
    enable_realtime_logs: bool = False,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        mcp_router: MCP router instance
        security_manager: Security manager instance
        cors_origin: CORS origin configuration
        title: API title
        version: API version (defaults to package version)
        enable_realtime_logs: Whether to enable WebSocket realtime logs

    Returns:
        FastAPI application
    """
    if version is None:
        version = __version__

    app = FastAPI(
        title=title,
        version=version,
        description="REST API for managing MCP Router instances and tools",
    )

    origins = []
    if cors_origin == "*" or cors_origin == "0.0.0.0":
        origins = ["*"]
    elif cors_origin == "127.0.0.1":
        origins = ["http://127.0.0.1", "http://localhost"]
    else:
        origins = [cors_origin]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)

    api_router = create_router(mcp_router, security_manager)
    app.include_router(api_router, prefix="/api")

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"name": title, "version": version, "status": "running"}

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    # WebSocket实时日志端点（如果启用）
    if enable_realtime_logs:

        @app.websocket("/ws")
        async def websocket_logs(websocket: WebSocket):
            """WebSocket端点，提供实时日志流.

            连接到 ws://<host>:<port>/ws 即可接收实时日志
            """
            await websocket.accept()
            ws_handler = get_websocket_handler()
            await ws_handler.add_client(websocket)

            logger.info(f"WebSocket client connected: {websocket.client}")

            try:
                # 保持连接并发送欢迎消息
                await websocket.send_text(
                    f"Connected to {title} v{version} - Realtime Logs\n"
                    f"----------------------------------------\n"
                )

                # 保持连接直到客户端断开
                while True:
                    # 等待客户端消息（主要用于检测断开连接）
                    await websocket.receive_text()

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {websocket.client}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                await ws_handler.remove_client(websocket)

        logger.info("WebSocket realtime logs enabled at /ws")

    logger.info(f"FastAPI application created: {title} v{version}")

    return app
