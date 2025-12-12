"""
ContextForge MCP Tools - Tool definitions for the MCP server.

This module defines the tools that are exposed through the MCP protocol,
allowing AI assistants to interact with ContextForge's capabilities.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from typing import Optional, List, Dict, Any

import httpx

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Service URLs
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
TERMINAL_EXECUTOR_URL = os.getenv("TERMINAL_EXECUTOR_URL", "http://localhost:8006")

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


def register_tools(mcp: FastMCP) -> None:
    """Register all ContextForge tools with the MCP server."""
    
    @mcp.tool()
    async def query_rag(
        question: str,
        enable_web_search: bool = True,
        max_tokens: int = 512
    ) -> str:
        """
        Query the RAG (Retrieval-Augmented Generation) pipeline.
        
        This tool searches the indexed codebase and optionally the web,
        then generates an answer using the configured LLM.
        
        Args:
            question: The question to answer
            enable_web_search: Whether to include web search results
            max_tokens: Maximum tokens in the response
            
        Returns:
            The generated answer with sources
        """
        try:
            result = await _make_request(
                "POST",
                f"{API_GATEWAY_URL}/query",
                json={
                    "question": question,
                    "enable_web_search": enable_web_search,
                    "max_tokens": max_tokens
                }
            )
            
            answer = result.get("answer", "No answer generated")
            sources = result.get("sources", [])
            
            response = f"**Answer:**\n{answer}\n\n"
            if sources:
                response += "**Sources:**\n"
                for source in sources[:5]:
                    response += f"- {source.get('title', 'Unknown')}: {source.get('url', 'N/A')}\n"
            
            return response
            
        except httpx.HTTPError as e:
            logger.error(f"RAG query failed: {e}")
            return f"Error querying RAG pipeline: {str(e)}"
    
    @mcp.tool()
    async def search_web(
        query: str,
        num_results: int = 5,
        fetch_content: bool = False
    ) -> str:
        """
        Search the web for information.
        
        Args:
            query: The search query
            num_results: Number of results to return (1-10)
            fetch_content: Whether to fetch full page content
            
        Returns:
            Search results with titles, URLs, and snippets
        """
        try:
            result = await _make_request(
                "POST",
                f"{API_GATEWAY_URL}/search",
                json={
                    "query": query,
                    "num_results": min(max(num_results, 1), 10),
                    "fetch_content": fetch_content
                }
            )
            
            results = result.get("results", [])
            if not results:
                return "No search results found."
            
            response = f"**Search Results for:** {query}\n\n"
            for i, r in enumerate(results, 1):
                response += f"{i}. **{r.get('title', 'No title')}**\n"
                response += f"   URL: {r.get('url', 'N/A')}\n"
                response += f"   {r.get('snippet', 'No description')}\n\n"
            
            return response
            
        except httpx.HTTPError as e:
            logger.error(f"Web search failed: {e}")
            return f"Error searching web: {str(e)}"
    
    @mcp.tool()
    async def search_codebase(
        query: str,
        top_k: int = 10
    ) -> str:
        """
        Search the indexed codebase using semantic search.
        
        Args:
            query: The search query (natural language)
            top_k: Number of results to return
            
        Returns:
            Relevant code snippets and their locations
        """
        try:
            result = await _make_request(
                "POST",
                f"{API_GATEWAY_URL}/vector/search",
                json={"query": query, "top_k": top_k}
            )
            
            results = result.get("results", [])
            if not results:
                return "No matching code found in the index."
            
            response = f"**Codebase Search Results:**\n\n"
            for i, r in enumerate(results, 1):
                response += f"{i}. **{r.get('file_path', 'Unknown file')}**\n"
                response += f"   Score: {r.get('score', 0):.3f}\n"
                content = r.get('content', '')[:200]
                response += f"   ```\n   {content}...\n   ```\n\n"

            return response

        except httpx.HTTPError as e:
            logger.error(f"Codebase search failed: {e}")
            return f"Error searching codebase: {str(e)}"

    @mcp.tool()
    async def ingest_repository(
        path: str,
        recursive: bool = True,
        file_patterns: Optional[List[str]] = None
    ) -> str:
        """
        Ingest files from a directory into the vector index.

        Args:
            path: Path to the directory to ingest
            recursive: Whether to recursively process subdirectories
            file_patterns: Optional list of file patterns to include (e.g., ["*.py", "*.js"])

        Returns:
            Summary of ingested files
        """
        try:
            result = await _make_request(
                "POST",
                f"{API_GATEWAY_URL}/ingest",
                json={
                    "path": path,
                    "recursive": recursive,
                    "file_patterns": file_patterns
                }
            )

            files_processed = result.get("files_processed", 0)
            chunks_created = result.get("chunks_created", 0)

            return f"**Ingestion Complete:**\n- Files processed: {files_processed}\n- Chunks created: {chunks_created}"

        except httpx.HTTPError as e:
            logger.error(f"Repository ingestion failed: {e}")
            return f"Error ingesting repository: {str(e)}"

    @mcp.tool()
    async def execute_command(
        command: str,
        timeout: int = 30
    ) -> str:
        """
        Execute a safe terminal command.

        Only whitelisted commands are allowed for security.
        Allowed commands include: python, pip, git, ls, cat, grep, find, etc.

        Args:
            command: The command to execute
            timeout: Maximum execution time in seconds (5-300)

        Returns:
            Command output (stdout and stderr)
        """
        try:
            result = await _make_request(
                "POST",
                f"{TERMINAL_EXECUTOR_URL}/execute",
                json={
                    "command": command,
                    "timeout": min(max(timeout, 5), 300)
                }
            )

            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            exit_code = result.get("exit_code", -1)

            response = f"**Exit Code:** {exit_code}\n\n"
            if stdout:
                response += f"**Output:**\n```\n{stdout}\n```\n\n"
            if stderr:
                response += f"**Errors:**\n```\n{stderr}\n```"

            return response

        except httpx.HTTPError as e:
            logger.error(f"Command execution failed: {e}")
            return f"Error executing command: {str(e)}"

    @mcp.tool()
    async def get_llm_adapters() -> str:
        """
        List available LLM adapters and their status.

        Returns:
            List of available LLM backends (Ollama, OpenAI, Anthropic, etc.)
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/llm/adapters")

            adapters = result.get("available_adapters", [])
            priority = result.get("priority", [])

            response = "**Available LLM Adapters:**\n\n"
            for adapter in adapters:
                status = "✓" if adapter in priority else "○"
                response += f"- {status} {adapter}\n"

            response += f"\n**Priority Order:** {' → '.join(priority)}"
            return response

        except httpx.HTTPError as e:
            logger.error(f"Failed to get LLM adapters: {e}")
            return f"Error getting LLM adapters: {str(e)}"

    @mcp.tool()
    async def get_system_health() -> str:
        """
        Check the health status of all ContextForge services.

        Returns:
            Health status of each service component
        """
        try:
            result = await _make_request("GET", f"{API_GATEWAY_URL}/health")

            status = result.get("status", "unknown")
            components = result.get("components", {})

            response = f"**System Status:** {status.upper()}\n\n"
            response += "**Components:**\n"

            for name, info in components.items():
                comp_status = info.get("status", "unknown")
                icon = "✓" if comp_status == "healthy" else "✗"
                response += f"- {icon} {name}: {comp_status}\n"

            return response

        except httpx.HTTPError as e:
            logger.error(f"Health check failed: {e}")
            return f"Error checking system health: {str(e)}"

    @mcp.tool()
    async def generate_text(
        prompt: str,
        max_tokens: int = 512,
        model: Optional[str] = None
    ) -> str:
        """
        Generate text using the configured LLM.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in the response
            model: Optional specific model to use

        Returns:
            Generated text response
        """
        try:
            result = await _make_request(
                "POST",
                f"{API_GATEWAY_URL}/llm/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "model": model
                }
            )

            text = result.get("text", "No response generated")
            meta = result.get("meta", {})
            backend = meta.get("backend", "unknown")

            return f"**Response (via {backend}):**\n\n{text}"

        except httpx.HTTPError as e:
            logger.error(f"Text generation failed: {e}")
            return f"Error generating text: {str(e)}"

