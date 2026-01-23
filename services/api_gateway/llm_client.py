"""
LLM Client with pluggable backends and fallback support.
Supports local (Ollama, LM Studio) and remote (OpenAI, Anthropic, Mistral) LLMs.
"""

import os
import sys
import time
import json
import logging
import re
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Add parent directory to path for services imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# Try to use unified config, fallback to env vars
try:
    from services.config import get_config
    _config = get_config()
    DEFAULT_TIMEOUT = _config.llm.timeout
    DEFAULT_MAX_TOKENS = _config.llm.max_tokens
    DEFAULT_TEMPERATURE = _config.llm.temperature
    CONFIG_AVAILABLE = True
except ImportError:
    DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
    DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
    DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    _config = None
    CONFIG_AVAILABLE = False


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data like API keys in log messages."""
    if not text:
        return text
    # Mask API keys (common patterns)
    patterns = [
        (r'(sk-[a-zA-Z0-9]{20,})', r'sk-***MASKED***'),  # OpenAI
        (r'(sk-ant-[a-zA-Z0-9]{20,})', r'sk-ant-***MASKED***'),  # Anthropic
        (r'(Bearer\s+)[a-zA-Z0-9\-_]+', r'\1***MASKED***'),  # Bearer tokens
        (r'(x-api-key:\s*)[a-zA-Z0-9\-_]+', r'\1***MASKED***'),  # API keys in headers
        (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9\-_]+', r'\1***MASKED***'),  # Generic API keys
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def safe_log_error(message: str, error: Exception) -> None:
    """Log error with sensitive data masked."""
    error_str = mask_sensitive_data(str(error))
    logger.error(f"{message}: {error_str}")


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class BaseAdapter(ABC):
    """Base class for LLM adapters."""
    
    def __init__(self, name: str):
        self.name = name
        self.timeout = DEFAULT_TIMEOUT
    
    @abstractmethod
    def generate(self, prompt: str, model: Optional[str] = None, 
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        """Generate text from prompt. Returns dict with 'text' and 'meta' keys."""
        pass
    
    def is_available(self) -> bool:
        """Check if this adapter is available/configured."""
        return True


class OllamaAdapter(BaseAdapter):
    """Ollama local LLM adapter."""

    def __init__(self, url: Optional[str] = None):
        super().__init__("ollama")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.url = url or _config.llm.ollama_url
            self.default_model = _config.llm.ollama_model
        else:
            self.url = url or os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
            self.default_model = os.getenv("OLLAMA_MODEL", "mistral")

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.url.replace('/api/generate', '')}/api/tags",
                                  timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        payload = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": kwargs.get("temperature", DEFAULT_TEMPERATURE)
            }
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            return {
                "text": result.get("response", ""),
                "meta": {
                    "backend": self.name,
                    "model": payload["model"],
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens": result.get("eval_count", 0)
                }
            }
        except Exception as e:
            safe_log_error("Ollama generation failed", e)
            raise LLMError(f"Ollama generation failed: {mask_sensitive_data(str(e))}")


class LMStudioAdapter(BaseAdapter):
    """LM Studio local LLM adapter."""

    def __init__(self, url: Optional[str] = None):
        super().__init__("lm_studio")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.url = url or _config.llm.lm_studio_url
        else:
            self.url = url or os.getenv("LM_STUDIO_URL", "http://localhost:8085/generate")

    def is_available(self) -> bool:
        try:
            response = requests.get(self.url.replace("/generate", "/health"), timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", DEFAULT_TEMPERATURE),
            "stop": kwargs.get("stop", [])
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            return {
                "text": result.get("text", ""),
                "meta": {
                    "backend": self.name,
                    "model": model or "lm-studio",
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
            }
        except Exception as e:
            safe_log_error("LM Studio generation failed", e)
            raise LLMError(f"LM Studio generation failed: {mask_sensitive_data(str(e))}")


class OpenAIAdapter(BaseAdapter):
    """OpenAI API adapter."""

    def __init__(self):
        super().__init__("openai")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = _config.llm.openai_api_key
        else:
            self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.default_model = "gpt-3.5-turbo"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("OpenAI API key not configured")

        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", DEFAULT_TEMPERATURE)
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=headers, 
                                   timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            choice = result["choices"][0]
            
            return {
                "text": choice["message"]["content"],
                "meta": {
                    "backend": self.name,
                    "model": result["model"],
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens": result["usage"]["total_tokens"]
                }
            }
        except Exception as e:
            safe_log_error("OpenAI generation failed", e)
            raise LLMError(f"OpenAI generation failed: {mask_sensitive_data(str(e))}")


class AnthropicAdapter(BaseAdapter):
    """Anthropic Claude API adapter."""

    def __init__(self):
        super().__init__("anthropic")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = _config.llm.anthropic_api_key
        else:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.default_model = "claude-3-sonnet-20240229"

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Anthropic API key not configured")

        start_time = time.time()

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers,
                                   timeout=self.timeout)
            response.raise_for_status()

            result = response.json()

            return {
                "text": result["content"][0]["text"],
                "meta": {
                    "backend": self.name,
                    "model": result["model"],
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens": result["usage"]["output_tokens"]
                }
            }
        except Exception as e:
            safe_log_error("Anthropic generation failed", e)
            raise LLMError(f"Anthropic generation failed: {mask_sensitive_data(str(e))}")


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek API adapter - Open source LLM with competitive performance."""

    def __init__(self):
        super().__init__("deepseek")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = getattr(_config.llm, 'deepseek_api_key', '') or os.getenv("DEEPSEEK_API_KEY", "")
        else:
            self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.default_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("DeepSeek API key not configured")

        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", DEFAULT_TEMPERATURE),
            "stream": False
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers,
                                   timeout=self.timeout)
            response.raise_for_status()

            result = response.json()
            choice = result["choices"][0]

            return {
                "text": choice["message"]["content"],
                "meta": {
                    "backend": self.name,
                    "model": result.get("model", model or self.default_model),
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "tokens": result.get("usage", {}).get("total_tokens", 0)
                }
            }
        except Exception as e:
            safe_log_error("DeepSeek generation failed", e)
            raise LLMError(f"DeepSeek generation failed: {mask_sensitive_data(str(e))}")


class LLMClient:
    """Main LLM client with adapter priority and fallback support."""
    
    def __init__(self, priority_env: str = "LLM_PRIORITY"):
        self.adapters = {}
        self.priority = self._parse_priority(os.getenv(priority_env, "ollama"))
        self._initialize_adapters()
    
    def _parse_priority(self, priority_str: str) -> List[str]:
        """Parse comma-separated priority list."""
        return [name.strip() for name in priority_str.split(",") if name.strip()]
    
    def _initialize_adapters(self):
        """Initialize all available adapters."""
        adapter_classes = {
            "ollama": OllamaAdapter,
            "lm_studio": LMStudioAdapter,
            "openai": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "deepseek": DeepSeekAdapter
        }
        
        for name, adapter_class in adapter_classes.items():
            try:
                self.adapters[name] = adapter_class()
                logger.info(f"Initialized {name} adapter")
            except Exception as e:
                # Use safe logging to prevent API key exposure
                logger.warning(f"Failed to initialize {name} adapter: {mask_sensitive_data(str(e))}")
    
    def generate(self, prompt: str, model: Optional[str] = None, 
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        """Generate text using the first available adapter in priority order."""
        last_error = None
        
        for adapter_name in self.priority:
            if adapter_name not in self.adapters:
                logger.warning(f"Adapter {adapter_name} not available")
                continue
            
            adapter = self.adapters[adapter_name]
            
            if not adapter.is_available():
                logger.info(f"Adapter {adapter_name} not available, trying next")
                continue
            
            try:
                logger.info(f"Attempting generation with {adapter_name}")
                result = adapter.generate(prompt, model, max_tokens, **kwargs)
                logger.info(f"Successfully generated with {adapter_name}")
                return result
            except Exception as e:
                last_error = e
                # Use safe logging to prevent API key exposure
                logger.warning(f"Adapter {adapter_name} failed: {mask_sensitive_data(str(e))}")
                continue

        # If all adapters failed, raise the last error with masked sensitive data
        raise LLMError(f"All LLM adapters failed. Last error: {mask_sensitive_data(str(last_error))}")
    
    def list_available_adapters(self) -> List[str]:
        """List currently available adapters."""
        return [name for name, adapter in self.adapters.items() 
                if adapter.is_available()]
