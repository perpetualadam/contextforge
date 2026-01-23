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


class GrokAdapter(BaseAdapter):
    """Grok (xAI) API adapter - Elon Musk's AI with real-time knowledge."""

    def __init__(self):
        super().__init__("grok")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = getattr(_config.llm, 'grok_api_key', '') or os.getenv("GROK_API_KEY", "")
        else:
            self.api_key = os.getenv("GROK_API_KEY", "")
        self.base_url = os.getenv("GROK_API_URL", "https://api.x.ai/v1/chat/completions")
        self.default_model = os.getenv("GROK_MODEL", "grok-beta")

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Grok API key not configured")

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
            safe_log_error("Grok generation failed", e)
            raise LLMError(f"Grok generation failed: {mask_sensitive_data(str(e))}")


class MistralAdapter(BaseAdapter):
    """Mistral AI API adapter - European AI with strong performance."""

    def __init__(self):
        super().__init__("mistral")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = getattr(_config.llm, 'mistral_api_key', '') or os.getenv("MISTRAL_API_KEY", "")
        else:
            self.api_key = os.getenv("MISTRAL_API_KEY", "")
        self.base_url = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")
        self.default_model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Mistral API key not configured")

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
            safe_log_error("Mistral generation failed", e)
            raise LLMError(f"Mistral generation failed: {mask_sensitive_data(str(e))}")


class GroqAdapter(BaseAdapter):
    """Groq API adapter - Ultra-fast inference with LPU technology."""

    def __init__(self):
        super().__init__("groq")
        # Use unified config if available
        if CONFIG_AVAILABLE and _config:
            self.api_key = getattr(_config.llm, 'groq_api_key', '') or os.getenv("GROQ_API_KEY", "")
        else:
            self.api_key = os.getenv("GROQ_API_KEY", "")
        self.base_url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.default_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Groq API key not configured")

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
            safe_log_error("Groq generation failed", e)
            raise LLMError(f"Groq generation failed: {mask_sensitive_data(str(e))}")


class LLMClient:
    """Main LLM client with adapter priority and fallback support."""

    # Provider metadata with model information
    PROVIDER_INFO = {
        "ollama": {
            "name": "Ollama",
            "type": "local",
            "description": "Local LLM server with various open-source models",
            "default_models": ["llama3.2", "mistral", "codellama", "llama2-13b-code"],
            "supports_custom_models": True
        },
        "lm_studio": {
            "name": "LM Studio",
            "type": "local",
            "description": "Local LLM server with GUI for model management",
            "default_models": ["local-model"],
            "supports_custom_models": True
        },
        "openai": {
            "name": "OpenAI",
            "type": "cloud",
            "description": "OpenAI GPT models (GPT-4, GPT-3.5)",
            "default_models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
            "supports_custom_models": False
        },
        "anthropic": {
            "name": "Anthropic",
            "type": "cloud",
            "description": "Anthropic Claude models",
            "default_models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-3-5-sonnet-20241022"],
            "supports_custom_models": False
        },
        "deepseek": {
            "name": "DeepSeek",
            "type": "cloud",
            "description": "DeepSeek open-source LLM with competitive performance",
            "default_models": ["deepseek-chat", "deepseek-coder"],
            "supports_custom_models": False
        },
        "grok": {
            "name": "Grok (xAI)",
            "type": "cloud",
            "description": "Elon Musk's xAI with real-time knowledge and humor",
            "default_models": ["grok-beta", "grok-vision-beta"],
            "supports_custom_models": False
        },
        "mistral": {
            "name": "Mistral AI",
            "type": "cloud",
            "description": "European AI with strong multilingual performance",
            "default_models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "open-mistral-7b"],
            "supports_custom_models": False
        },
        "groq": {
            "name": "Groq",
            "type": "cloud",
            "description": "Ultra-fast inference with LPU technology",
            "default_models": ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
            "supports_custom_models": False
        }
    }

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
            "deepseek": DeepSeekAdapter,
            "grok": GrokAdapter,
            "mistral": MistralAdapter,
            "groq": GroqAdapter
        }

        for name, adapter_class in adapter_classes.items():
            try:
                self.adapters[name] = adapter_class()
                logger.info(f"Initialized {name} adapter")
            except Exception as e:
                # Use safe logging to prevent API key exposure
                logger.warning(f"Failed to initialize {name} adapter: {mask_sensitive_data(str(e))}")

    def generate(self, prompt: str, model: Optional[str] = None,
                max_tokens: int = DEFAULT_MAX_TOKENS, provider: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate text using specified provider or fallback to priority order.

        Args:
            prompt: The prompt to send to the LLM
            model: Model name to use (provider-specific)
            max_tokens: Maximum tokens to generate
            provider: Specific provider to use (e.g., "openai", "ollama"). If None, uses priority order.
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with 'text' and 'meta' keys
        """
        last_error = None

        # If specific provider requested, try only that provider
        if provider:
            if provider not in self.adapters:
                raise LLMError(f"Provider '{provider}' not found. Available: {list(self.adapters.keys())}")

            adapter = self.adapters[provider]

            if not adapter.is_available():
                raise LLMError(f"Provider '{provider}' is not available or not configured")

            try:
                logger.info(f"Using specified provider: {provider}")
                result = adapter.generate(prompt, model, max_tokens, **kwargs)
                logger.info(f"Successfully generated with {provider}")
                return result
            except Exception as e:
                safe_log_error(f"Provider {provider} failed", e)
                raise LLMError(f"Provider '{provider}' failed: {mask_sensitive_data(str(e))}")

        # Otherwise, try adapters in priority order
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

    def get_provider_details(self) -> List[Dict[str, Any]]:
        """
        Get detailed information about all providers.

        Returns:
            List of provider details with availability, models, and metadata
        """
        providers = []

        for provider_id, info in self.PROVIDER_INFO.items():
            adapter = self.adapters.get(provider_id)
            is_available = adapter.is_available() if adapter else False

            provider_detail = {
                "id": provider_id,
                "name": info["name"],
                "type": info["type"],
                "description": info["description"],
                "available": is_available,
                "models": info["default_models"],
                "supports_custom_models": info["supports_custom_models"],
                "is_configured": adapter is not None
            }

            # Add provider-specific default model
            if adapter and is_available:
                if hasattr(adapter, 'default_model'):
                    provider_detail["default_model"] = adapter.default_model

            providers.append(provider_detail)

        return providers

    def set_priority(self, priority: List[str]) -> None:
        """
        Set the priority order for LLM providers.

        Args:
            priority: List of provider IDs in priority order
        """
        # Validate all providers exist
        invalid = [p for p in priority if p not in self.PROVIDER_INFO]
        if invalid:
            raise ValueError(f"Invalid providers: {invalid}. Valid: {list(self.PROVIDER_INFO.keys())}")

        self.priority = priority
        logger.info(f"Updated LLM priority to: {priority}")
