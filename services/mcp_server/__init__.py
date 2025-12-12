"""
ContextForge MCP Server - Model Context Protocol implementation.

This module provides an MCP server that exposes ContextForge's capabilities
as tools and resources for AI assistants like Claude Desktop.

Copyright (c) 2025 ContextForge
"""

__all__ = ["create_mcp_server", "get_mcp_server"]
__version__ = "0.1.0"


def create_mcp_server(name: str = "contextforge"):
    """Create and configure the ContextForge MCP server."""
    from .server import create_mcp_server as _create
    return _create(name)


def get_mcp_server():
    """Get or create the default MCP server instance."""
    from .server import get_mcp_server as _get
    return _get()

