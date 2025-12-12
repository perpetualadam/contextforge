#!/usr/bin/env python
"""
Simple script to run the ContextForge MCP server.

Usage:
    python run_mcp.py [transport] [--host HOST] [--port PORT]

    transport: stdio, http, or sse (default: http)
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.mcp_server.server import create_mcp_server_with_config


def main():
    """Run the MCP server (synchronous entry point)."""
    transport = "http"
    host = "0.0.0.0"
    port = 8010

    # Parse command line args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif arg in ("stdio", "http", "sse"):
            transport = arg
            i += 1
        else:
            i += 1

    mcp = create_mcp_server_with_config("contextforge", host=host, port=port)

    print(f"Starting ContextForge MCP server on {host}:{port} with {transport} transport")

    # FastMCP.run() is synchronous - it internally calls anyio.run()
    if transport == "http":
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

