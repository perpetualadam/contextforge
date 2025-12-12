"""
ContextForge MCP Server - Application entry point.

This module provides the main entry point for running the MCP server
with different transport options (stdio, HTTP).

Copyright (c) 2025 ContextForge
"""

import sys
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ContextForge MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (for Claude Desktop)
  python -m services.mcp_server.app stdio
  
  # Run with HTTP transport
  python -m services.mcp_server.app http --port 8010
  
  # Run with SSE transport
  python -m services.mcp_server.app sse --port 8010
"""
    )
    
    parser.add_argument(
        "transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        nargs="?",
        help="Transport type (default: stdio)"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (for http/sse transport)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8010,
        help="Port to bind to (for http/sse transport)"
    )
    
    parser.add_argument(
        "--name",
        default="contextforge",
        help="Server name"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    return parser.parse_args()


def run_stdio(name: str) -> None:
    """Run the MCP server with stdio transport."""
    from .server import create_mcp_server_with_config

    logger.info(f"Starting ContextForge MCP server '{name}' with stdio transport")
    mcp = create_mcp_server_with_config(name)
    # FastMCP.run() is synchronous - it internally calls anyio.run()
    mcp.run(transport="stdio")


def run_http(name: str, host: str, port: int) -> None:
    """Run the MCP server with HTTP transport."""
    from .server import create_mcp_server_with_config

    logger.info(f"Starting ContextForge MCP server '{name}' on http://{host}:{port}")
    mcp = create_mcp_server_with_config(name, host=host, port=port)

    # FastMCP.run() is synchronous - it internally calls anyio.run()
    mcp.run(transport="streamable-http")


def run_sse(name: str, host: str, port: int) -> None:
    """Run the MCP server with SSE transport."""
    from .server import create_mcp_server_with_config

    logger.info(f"Starting ContextForge MCP server '{name}' on http://{host}:{port} (SSE)")
    mcp = create_mcp_server_with_config(name, host=host, port=port)

    # FastMCP.run() is synchronous - it internally calls anyio.run()
    mcp.run(transport="sse")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.transport == "stdio":
            run_stdio(args.name)
        elif args.transport == "http":
            run_http(args.name, args.host, args.port)
        elif args.transport == "sse":
            run_sse(args.name, args.host, args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

