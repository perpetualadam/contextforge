"""
ContextForge MCP Resources - Resource definitions for the MCP server.

This module defines the resources that are exposed through the MCP protocol,
allowing AI assistants to access ContextForge's data and configuration.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from typing import Optional, Dict, Any

import httpx

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Service URLs
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

# HTTP client timeout
HTTP_TIMEOUT = 30.0


async def _make_request(
    method: str,
    url: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make an HTTP request to a ContextForge service."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.request(method, url, json=json, params=params)
        response.raise_for_status()
        return response.json()


def register_resources(mcp: FastMCP) -> None:
    """Register all ContextForge resources with the MCP server."""
    
    @mcp.resource("contextforge://config")
    async def get_configuration() -> str:
        """
        Get the current ContextForge configuration.
        
        Returns the system configuration including LLM priority,
        search settings, and service URLs.
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/config")
            
            config_text = "# ContextForge Configuration\n\n"
            
            config_text += "## LLM Settings\n"
            config_text += f"- Priority: {', '.join(result.get('llm_priority', []))}\n"
            config_text += f"- Privacy Mode: {result.get('privacy_mode', 'local')}\n\n"
            
            config_text += "## Search Settings\n"
            config_text += f"- Web Search Enabled: {result.get('enable_web_search', False)}\n"
            config_text += f"- Vector Top K: {result.get('vector_top_k', 10)}\n"
            config_text += f"- Web Search Results: {result.get('web_search_results', 5)}\n\n"
            
            config_text += "## Service URLs\n"
            services = result.get('services', {})
            for name, url in services.items():
                config_text += f"- {name}: {url}\n"
            
            return config_text
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get configuration: {e}")
            return f"Error getting configuration: {str(e)}"
    
    @mcp.resource("contextforge://health")
    async def get_health_status() -> str:
        """
        Get the current health status of all ContextForge services.
        
        Returns detailed health information for each component.
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/health")
            
            health_text = "# ContextForge Health Status\n\n"
            health_text += f"**Overall Status:** {result.get('status', 'unknown').upper()}\n\n"
            
            health_text += "## Components\n\n"
            components = result.get('components', {})
            for name, info in components.items():
                status = info.get('status', 'unknown')
                icon = "✅" if status == "healthy" else "❌"
                health_text += f"### {icon} {name.replace('_', ' ').title()}\n"
                health_text += f"- Status: {status}\n"
                
                if 'available' in info:
                    health_text += f"- Available: {', '.join(info['available']) or 'None'}\n"
                health_text += "\n"
            
            return health_text
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get health status: {e}")
            return f"Error getting health status: {str(e)}"
    
    @mcp.resource("contextforge://adapters/llm")
    async def get_llm_adapters() -> str:
        """
        Get information about available LLM adapters.
        
        Returns details about each configured LLM backend.
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/llm/adapters")
            
            adapters_text = "# Available LLM Adapters\n\n"
            
            adapters = result.get('available_adapters', [])
            priority = result.get('priority', [])
            
            adapters_text += f"**Priority Order:** {' → '.join(priority)}\n\n"
            
            for adapter in adapters:
                is_primary = adapter == priority[0] if priority else False
                icon = "⭐" if is_primary else "○"
                adapters_text += f"## {icon} {adapter.title()}\n"
                adapters_text += f"- Status: Available\n"
                adapters_text += f"- Priority: {priority.index(adapter) + 1 if adapter in priority else 'N/A'}\n\n"
            
            return adapters_text
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get LLM adapters: {e}")
            return f"Error getting LLM adapters: {str(e)}"
    
    @mcp.resource("contextforge://stats")
    async def get_index_stats() -> str:
        """
        Get statistics about the vector index.
        
        Returns information about indexed documents and chunks.
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/vector/stats")
            
            stats_text = "# Vector Index Statistics\n\n"
            stats_text += f"- Total Documents: {result.get('total_documents', 0)}\n"
            stats_text += f"- Total Chunks: {result.get('total_chunks', 0)}\n"
            stats_text += f"- Index Size: {result.get('index_size_mb', 0):.2f} MB\n"
            stats_text += f"- Last Updated: {result.get('last_updated', 'Never')}\n"
            
            return stats_text
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get index stats: {e}")
            return f"Error getting index stats: {str(e)}"

