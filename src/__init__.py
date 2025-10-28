"""MCP Router - A routing/proxy system for MCP servers."""

try:
    from importlib.metadata import version

    __version__ = version("mcp-router")
except Exception:
    __version__ = "1.0.4"  # Fallback version

__all__ = ["__version__"]
