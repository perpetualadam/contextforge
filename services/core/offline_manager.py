"""
ContextForge Offline Manager.

Manages offline mode detection, local LLM health checks, and offline status API.

Copyright (c) 2025 ContextForge
"""

import logging
import time
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OfflineStatus(Enum):
    """Offline mode status."""
    ONLINE = "online"           # Internet available, cloud LLM accessible
    OFFLINE = "offline"         # No internet, using local LLM only
    DEGRADED = "degraded"       # Internet available but cloud LLM unavailable
    LOCAL_ONLY = "local_only"   # User-forced local mode


@dataclass
class LocalLLMStatus:
    """Status of a local LLM backend."""
    name: str
    available: bool
    url: str
    models: List[str] = None
    error: Optional[str] = None
    latency_ms: int = 0


@dataclass
class OfflineCapabilities:
    """Offline mode capabilities."""
    status: OfflineStatus
    internet_available: bool
    cloud_llm_available: bool
    local_llm_backends: List[LocalLLMStatus]
    recommended_action: str


class OfflineManager:
    """
    Manages offline mode detection and local LLM health checks.
    
    Features:
    - Auto-detect internet connectivity
    - Health check for local LLM backends (Ollama, LM Studio)
    - Provide offline status API
    - Automatic fallback when cloud unavailable
    """
    
    def __init__(self):
        """Initialize offline manager."""
        self._last_check: Optional[float] = None
        self._check_interval = 60  # Re-check every 60 seconds
        self._cached_status: Optional[OfflineCapabilities] = None
        
        # Local LLM backend configurations
        self._local_backends = [
            {
                'name': 'ollama',
                'url': 'http://localhost:11434',
                'health_endpoint': '/api/tags',
                'models_key': 'models'
            },
            {
                'name': 'lm_studio',
                'url': 'http://localhost:1234',
                'health_endpoint': '/v1/models',
                'models_key': 'data'
            }
        ]
    
    def get_status(self, force_refresh: bool = False) -> OfflineCapabilities:
        """
        Get current offline capabilities.
        
        Args:
            force_refresh: Force re-check even if cache is valid
            
        Returns:
            OfflineCapabilities with current status
        """
        # Use cached status if available and fresh
        if not force_refresh and self._cached_status and not self._should_recheck():
            return self._cached_status
        
        # Perform fresh check
        internet_available = self._check_internet()
        cloud_llm_available = self._check_cloud_llm() if internet_available else False
        local_backends = self._check_local_backends()
        
        # Determine overall status
        status = self._determine_status(internet_available, cloud_llm_available, local_backends)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(status, local_backends)
        
        self._cached_status = OfflineCapabilities(
            status=status,
            internet_available=internet_available,
            cloud_llm_available=cloud_llm_available,
            local_llm_backends=local_backends,
            recommended_action=recommendation
        )
        
        self._last_check = time.time()
        return self._cached_status
    
    def _should_recheck(self) -> bool:
        """Check if we should re-verify status."""
        if self._last_check is None:
            return True
        elapsed = time.time() - self._last_check
        return elapsed > self._check_interval
    
    def _check_internet(self) -> bool:
        """Check if internet is available."""
        try:
            response = requests.get("https://www.google.com", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_cloud_llm(self) -> bool:
        """Check if cloud LLM is available."""
        from services.config import get_config
        config = get_config()
        
        # Check if any cloud API key is configured
        has_keys = any([
            config.llm.openai_api_key,
            config.llm.anthropic_api_key,
            config.llm.gemini_api_key,
            config.llm.deepseek_api_key
        ])
        
        return has_keys

    def _check_local_backends(self) -> List[LocalLLMStatus]:
        """Check health of all local LLM backends."""
        results = []

        for backend in self._local_backends:
            status = self._check_backend_health(backend)
            results.append(status)

        return results

    def _check_backend_health(self, backend: Dict[str, Any]) -> LocalLLMStatus:
        """
        Check health of a single local LLM backend.

        Args:
            backend: Backend configuration dict

        Returns:
            LocalLLMStatus with health information
        """
        start_time = time.time()

        try:
            url = f"{backend['url']}{backend['health_endpoint']}"
            response = requests.get(url, timeout=5)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                models = []

                # Extract model list
                if backend['models_key'] in data:
                    models_data = data[backend['models_key']]
                    if isinstance(models_data, list):
                        # Ollama format: list of dicts with 'name' key
                        if models_data and isinstance(models_data[0], dict):
                            models = [m.get('name', m.get('id', '')) for m in models_data]
                        else:
                            models = models_data

                return LocalLLMStatus(
                    name=backend['name'],
                    available=True,
                    url=backend['url'],
                    models=models,
                    latency_ms=latency_ms
                )
            else:
                return LocalLLMStatus(
                    name=backend['name'],
                    available=False,
                    url=backend['url'],
                    error=f"HTTP {response.status_code}"
                )

        except requests.exceptions.Timeout:
            return LocalLLMStatus(
                name=backend['name'],
                available=False,
                url=backend['url'],
                error="Connection timeout"
            )
        except requests.exceptions.ConnectionError:
            return LocalLLMStatus(
                name=backend['name'],
                available=False,
                url=backend['url'],
                error="Connection refused (not running?)"
            )
        except Exception as e:
            return LocalLLMStatus(
                name=backend['name'],
                available=False,
                url=backend['url'],
                error=str(e)
            )

    def _determine_status(
        self,
        internet_available: bool,
        cloud_llm_available: bool,
        local_backends: List[LocalLLMStatus]
    ) -> OfflineStatus:
        """Determine overall offline status."""
        # Check if any local backend is available
        has_local_llm = any(b.available for b in local_backends)

        if not internet_available:
            return OfflineStatus.OFFLINE

        if internet_available and cloud_llm_available:
            return OfflineStatus.ONLINE

        if internet_available and not cloud_llm_available and has_local_llm:
            return OfflineStatus.DEGRADED

        return OfflineStatus.OFFLINE

    def _generate_recommendation(
        self,
        status: OfflineStatus,
        local_backends: List[LocalLLMStatus]
    ) -> str:
        """Generate recommended action based on status."""
        if status == OfflineStatus.ONLINE:
            return "All systems operational. Cloud and local LLMs available."

        if status == OfflineStatus.OFFLINE:
            has_local = any(b.available for b in local_backends)
            if has_local:
                return "Offline mode. Using local LLM only."
            else:
                return "No LLM available. Please start Ollama or LM Studio, or connect to internet."

        if status == OfflineStatus.DEGRADED:
            return "Cloud LLM unavailable. Using local LLM as fallback."

        return "Unknown status"

    def get_available_backend(self) -> Optional[LocalLLMStatus]:
        """
        Get the first available local LLM backend.

        Returns:
            LocalLLMStatus of first available backend, or None
        """
        status = self.get_status()
        for backend in status.local_llm_backends:
            if backend.available:
                return backend
        return None

    def is_offline(self) -> bool:
        """Check if currently in offline mode."""
        status = self.get_status()
        return status.status in [OfflineStatus.OFFLINE, OfflineStatus.LOCAL_ONLY]

    def to_dict(self) -> Dict[str, Any]:
        """Convert current status to dictionary."""
        status = self.get_status()
        return {
            "status": status.status.value,
            "internet_available": status.internet_available,
            "cloud_llm_available": status.cloud_llm_available,
            "local_backends": [
                {
                    "name": b.name,
                    "available": b.available,
                    "url": b.url,
                    "models": b.models or [],
                    "error": b.error,
                    "latency_ms": b.latency_ms
                }
                for b in status.local_llm_backends
            ],
            "recommendation": status.recommended_action
        }


# Singleton instance
_offline_manager: Optional[OfflineManager] = None


def get_offline_manager() -> OfflineManager:
    """Get singleton offline manager instance."""
    global _offline_manager
    if _offline_manager is None:
        _offline_manager = OfflineManager()
    return _offline_manager


