"""API route handlers."""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..core.exceptions import MCPRouterException
from ..core.logger import get_logger
from ..mcp.router import MCPRouter
from ..utils.security import SecurityManager

logger = get_logger(__name__)


class InstanceConfig(BaseModel):
    """MCP instance configuration model."""

    provider: str = Field(..., description="Provider name")
    name: str = Field(..., description="Instance name")
    type: str = Field(..., description="Transport type (stdio, sse, http)")
    command: str = Field(..., description="Command to execute")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    isActive: bool = Field(default=True, description="Whether instance is active")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class ToolCallRequest(BaseModel):
    """Tool call request model."""

    instance: str = Field(..., description="Instance name")
    tool: str = Field(..., description="Tool name")
    params: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


def create_router(mcp_router: MCPRouter, security_manager: SecurityManager) -> APIRouter:
    """Create API router with all endpoints.

    Args:
        mcp_router: MCP router instance
        security_manager: Security manager instance

    Returns:
        Configured APIRouter
    """
    router = APIRouter()

    async def verify_token(authorization: str | None = Header(None)) -> bool:
        """Verify bearer token from authorization header.

        Args:
            authorization: Authorization header value

        Returns:
            True if valid

        Raises:
            HTTPException: If authentication fails
        """
        try:
            security_manager.validate_bearer_token(authorization)
            return True
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))

    @router.get("/instances", dependencies=[Depends(verify_token)])
    async def list_instances() -> list[dict[str, Any]]:
        """List all MCP instances."""
        try:
            return mcp_router.list()
        except MCPRouterException as e:
            raise HTTPException(status_code=400, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error listing instances: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/instances/{name}", dependencies=[Depends(verify_token)])
    async def get_instance(name: str) -> dict[str, Any]:
        """Get instance details."""
        try:
            instance = mcp_router.client_manager.get_instance(name)
            return instance.to_dict()
        except MCPRouterException as e:
            raise HTTPException(status_code=404, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error getting instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/tools", dependencies=[Depends(verify_token)])
    async def list_all_tools() -> dict[str, list[dict[str, Any]]]:
        """List all tools from all instances."""
        try:
            return mcp_router.help()
        except MCPRouterException as e:
            raise HTTPException(status_code=400, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/tools/{instance_name}", dependencies=[Depends(verify_token)])
    async def list_instance_tools(instance_name: str) -> list[dict[str, Any]]:
        """Get tools for a specific instance."""
        try:
            instance = mcp_router.client_manager.get_instance(instance_name)
            tools = instance.get_tools()
            return list(tools.values())
        except MCPRouterException as e:
            raise HTTPException(status_code=404, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error getting instance tools: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/instances", dependencies=[Depends(verify_token)])
    async def add_instance(config: InstanceConfig) -> dict[str, str]:
        """Add a new MCP instance."""
        try:
            result = await mcp_router.add(config.provider, config.model_dump())
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=400, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error adding instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.patch("/instances/{name}", dependencies=[Depends(verify_token)])
    async def update_instance(name: str, config: InstanceConfig) -> dict[str, str]:
        """Update an existing instance."""
        try:
            await mcp_router.remove(name)
            result = await mcp_router.add(config.provider, config.model_dump())
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=400, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error updating instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/instances/{name}", dependencies=[Depends(verify_token)])
    async def delete_instance(name: str) -> dict[str, str]:
        """Delete an MCP instance."""
        try:
            result = await mcp_router.remove(name)
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=404, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error deleting instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/instances/{name}/enable", dependencies=[Depends(verify_token)])
    async def enable_instance(name: str) -> dict[str, Any]:
        """Enable an MCP instance."""
        try:
            result = await mcp_router.enable(name)
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=404, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error enabling instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/instances/{name}/disable", dependencies=[Depends(verify_token)])
    async def disable_instance(name: str) -> dict[str, Any]:
        """Disable an MCP instance."""
        try:
            result = await mcp_router.disable(name)
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=404, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error disabling instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/call", dependencies=[Depends(verify_token)])
    async def call_tool(request: ToolCallRequest) -> Any:
        """Call a tool on a specific instance."""
        try:
            result = await mcp_router.call(request.instance, request.tool, **request.params)
            return result
        except MCPRouterException as e:
            raise HTTPException(status_code=400, detail=e.to_dict())
        except Exception as e:
            logger.error(f"Error calling tool: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/config", dependencies=[Depends(verify_token)])
    async def get_config() -> dict[str, Any]:
        """Get current configuration (for debugging)."""
        try:
            instances = mcp_router.list()
            return {"instances": instances, "current_instance": mcp_router.get_current_instance()}
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
