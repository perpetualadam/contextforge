"""
ContextForge MCP Server - Main server implementation.

This module implements the MCP server using the FastMCP high-level API.
It exposes ContextForge's capabilities as MCP tools and resources.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs from environment
VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://localhost:8001")
PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://localhost:8003")
CONNECTOR_URL = os.getenv("CONNECTOR_URL", "http://localhost:8002")
WEB_FETCHER_URL = os.getenv("WEB_FETCHER_URL", "http://localhost:8004")
TERMINAL_EXECUTOR_URL = os.getenv("TERMINAL_EXECUTOR_URL", "http://localhost:8006")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")


def create_mcp_server(name: str = "contextforge") -> FastMCP:
    """
    Create and configure the ContextForge MCP server with default settings.

    Args:
        name: The name of the MCP server

    Returns:
        Configured FastMCP server instance
    """
    return create_mcp_server_with_config(name)


def create_mcp_server_with_config(
    name: str = "contextforge",
    host: str = "127.0.0.1",
    port: int = 8010
) -> FastMCP:
    """
    Create and configure the ContextForge MCP server with custom settings.

    Args:
        name: The name of the MCP server
        host: Host to bind to (for HTTP/SSE transport)
        port: Port to bind to (for HTTP/SSE transport)

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name=name,
        instructions="ContextForge - Local-first context engine and AI assistant pipeline. "
                    "Use the available tools to search codebases, query the RAG pipeline, "
                    "search the web, execute safe terminal commands, and edit files.",
        host=host,
        port=port
    )

    # Register tools
    from .tools import register_tools
    register_tools(mcp)

    # Register file and code manipulation tools
    from .file_tools import register_file_tools
    register_file_tools(mcp)

    # Register resources
    from .resources import register_resources
    register_resources(mcp)

    # Register prompts
    from .prompts import register_prompts
    register_prompts(mcp)

    logger.info(f"ContextForge MCP server '{name}' initialized")
    return mcp


# Lazy-loaded default server instance
_mcp: Optional[FastMCP] = None


def get_mcp_server() -> FastMCP:
    """Get or create the default MCP server instance."""
    global _mcp
    if _mcp is None:
        _mcp = create_mcp_server()
    return _mcp


def main():
    """Entry point for running the MCP server."""
    import asyncio

    mcp = get_mcp_server()
    # Run with stdio transport by default
    asyncio.run(mcp.run())


if __name__ == "__main__":
    main()

