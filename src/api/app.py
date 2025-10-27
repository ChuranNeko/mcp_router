"""FastAPI application setup."""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.logger import get_logger
from ..mcp.router import MCPRouter
from ..utils.security import SecurityManager
from .routes import create_router

logger = get_logger(__name__)


def create_app(
    mcp_router: MCPRouter,
    security_manager: SecurityManager,
    cors_origin: str = "*",
    title: str = "MCP Router API",
    version: str = "1.0.0"
) -> FastAPI:
    """Create FastAPI application.
    
    Args:
        mcp_router: MCP router instance
        security_manager: Security manager instance
        cors_origin: CORS origin configuration
        title: API title
        version: API version
        
    Returns:
        FastAPI application
    """
    app = FastAPI(
        title=title,
        version=version,
        description="REST API for managing MCP Router instances and tools"
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
    
    api_router = create_router(mcp_router, security_manager)
    app.include_router(api_router, prefix="/api")
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": title,
            "version": version,
            "status": "running"
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    logger.info(f"FastAPI application created: {title} v{version}")
    
    return app

