"""
Metrics Integration for API Gateway.

Provides async metrics recording to persistence and metrics services.

Copyright (c) 2025 ContextForge
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional
import httpx

logger = logging.getLogger(__name__)

# Service URLs
PERSISTENCE_URL = os.getenv("PERSISTENCE_URL", "http://localhost:8015")
METRICS_URL = os.getenv("METRICS_URL", "http://localhost:8017")

# Enable/disable metrics
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")


class MetricsRecorder:
    """Records metrics to persistence and advanced metrics services."""
    
    def __init__(self):
        self._client = None
        self._session_id: Optional[str] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0)
        return self._client
    
    async def ensure_session(self, user_id: str = None) -> Optional[str]:
        """Ensure a session exists and return session ID."""
        if not METRICS_ENABLED:
            return None
        
        if self._session_id:
            return self._session_id
        
        try:
            client = await self._get_client()
            response = await client.post(
                f"{PERSISTENCE_URL}/sessions",
                json={"user_id": user_id, "metadata": {"source": "api_gateway"}}
            )
            if response.status_code == 200:
                data = response.json()
                self._session_id = data.get("session_id")
                return self._session_id
        except Exception as e:
            logger.debug(f"Failed to create session: {e}")
        
        return None
    
    async def record_query(
        self,
        query: str,
        response: str = None,
        contexts_used: int = 0,
        web_results_used: int = 0,
        llm_backend: str = None,
        latency_ms: int = 0,
        metadata: Dict = None
    ) -> Optional[str]:
        """Record a query to persistence service."""
        if not METRICS_ENABLED:
            return None
        
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{PERSISTENCE_URL}/queries",
                json={
                    "session_id": self._session_id,
                    "query": query,
                    "response": response,
                    "contexts_used": contexts_used,
                    "web_results_used": web_results_used,
                    "llm_backend": llm_backend,
                    "latency_ms": latency_ms,
                    "metadata": metadata or {}
                }
            )
            if resp.status_code == 200:
                return resp.json().get("query_id")
        except Exception as e:
            logger.debug(f"Failed to record query: {e}")
        
        return None
    
    async def record_metric(
        self,
        metric_type: str,
        value: float,
        tags: Dict[str, str] = None,
        metadata: Dict = None
    ) -> None:
        """Record a metric to persistence service."""
        if not METRICS_ENABLED:
            return
        
        try:
            client = await self._get_client()
            await client.post(
                f"{PERSISTENCE_URL}/metrics",
                json={
                    "metric_type": metric_type,
                    "value": value,
                    "tags": tags or {},
                    "metadata": metadata or {}
                }
            )
        except Exception as e:
            logger.debug(f"Failed to record metric: {e}")
    
    async def record_llm_request(
        self,
        backend: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int = 0,
        success: bool = True,
        error_message: str = None
    ) -> None:
        """Record LLM request to advanced metrics service."""
        if not METRICS_ENABLED:
            return
        
        try:
            client = await self._get_client()
            await client.post(
                f"{METRICS_URL}/llm/record",
                json={
                    "request": {
                        "backend": backend,
                        "model": model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "latency_ms": latency_ms,
                        "success": success,
                        "error_message": error_message
                    }
                }
            )
        except Exception as e:
            logger.debug(f"Failed to record LLM request: {e}")
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton recorder
_recorder = None


def get_metrics_recorder() -> MetricsRecorder:
    """Get singleton metrics recorder."""
    global _recorder
    if _recorder is None:
        _recorder = MetricsRecorder()
    return _recorder

