"""
Configuration validation for ContextForge.

Validates configuration at startup and provides helpful error messages.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    info: List[str]


class ConfigValidator:
    """Validates ContextForge configuration at startup."""
    
    def __init__(self, config):
        """Initialize validator with config object."""
        self.config = config
    
    def validate_all(self) -> ValidationResult:
        """
        Validate all configuration sections.
        
        Returns:
            ValidationResult with errors, warnings, and info messages
        """
        errors = []
        warnings = []
        info = []
        
        # Validate paths
        path_errors, path_warnings = self._validate_paths()
        errors.extend(path_errors)
        warnings.extend(path_warnings)
        
        # Validate LLM configuration
        llm_errors, llm_warnings, llm_info = self._validate_llm()
        errors.extend(llm_errors)
        warnings.extend(llm_warnings)
        info.extend(llm_info)
        
        # Validate resource limits
        resource_warnings = self._validate_resources()
        warnings.extend(resource_warnings)
        
        # Validate security settings
        security_warnings = self._validate_security()
        warnings.extend(security_warnings)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    def _validate_paths(self) -> Tuple[List[str], List[str]]:
        """Validate file paths and directories."""
        errors = []
        warnings = []
        
        # Check FAISS index directory
        faiss_path = Path(self.config.indexing.faiss_index_path)
        if not faiss_path.parent.exists():
            try:
                faiss_path.parent.mkdir(parents=True, exist_ok=True)
                warnings.append(f"Created FAISS index directory: {faiss_path.parent}")
            except Exception as e:
                errors.append(f"Cannot create FAISS index directory {faiss_path.parent}: {e}")
        
        # Check data directories
        for dir_name in ['data_dir', 'repos_dir', 'cache_dir', 'logs_dir']:
            dir_path = Path(getattr(self.config.data, dir_name))
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    warnings.append(f"Created {dir_name}: {dir_path}")
                except Exception as e:
                    errors.append(f"Cannot create {dir_name} {dir_path}: {e}")
        
        return errors, warnings
    
    def _validate_llm(self) -> Tuple[List[str], List[str], List[str]]:
        """Validate LLM configuration."""
        errors = []
        warnings = []
        info = []
        
        # Check if any LLM backend is configured
        has_local = bool(self.config.llm.ollama_url or self.config.llm.lm_studio_url)
        has_cloud = bool(
            self.config.llm.openai_api_key or 
            self.config.llm.anthropic_api_key or 
            self.config.llm.gemini_api_key or
            self.config.llm.deepseek_api_key
        )
        
        if not has_local and not has_cloud:
            warnings.append(
                "No LLM backend configured. Install Ollama (https://ollama.ai) "
                "or set cloud API keys for LLM features."
            )
        
        # Check priority vs availability
        if "cloud" in self.config.llm.priority and not has_cloud:
            warnings.append(
                "LLM priority includes 'cloud' but no cloud API keys configured. "
                "Will fall back to local LLM if available."
            )
        
        if "local" in self.config.llm.priority and has_local:
            info.append(f"Local LLM configured: {self.config.llm.ollama_url or self.config.llm.lm_studio_url}")
        
        if has_cloud:
            backends = []
            if self.config.llm.openai_api_key: backends.append("OpenAI")
            if self.config.llm.anthropic_api_key: backends.append("Anthropic")
            if self.config.llm.gemini_api_key: backends.append("Gemini")
            if self.config.llm.deepseek_api_key: backends.append("DeepSeek")
            info.append(f"Cloud LLM backends configured: {', '.join(backends)}")
        
        return errors, warnings, info
    
    def _validate_resources(self) -> List[str]:
        """Validate resource limits."""
        warnings = []
        
        # Check indexing workers vs CPU count
        cpu_count = os.cpu_count() or 1
        if self.config.scaling.max_indexing_workers > cpu_count:
            warnings.append(
                f"max_indexing_workers ({self.config.scaling.max_indexing_workers}) "
                f"exceeds CPU count ({cpu_count}). May cause performance degradation."
            )
        
        return warnings
    
    def _validate_security(self) -> List[str]:
        """Validate security settings."""
        warnings = []
        
        if not self.config.security.api_key_enabled:
            warnings.append(
                "API key authentication is disabled. Enable for production deployments."
            )
        
        if not self.config.security.rate_limit_enabled:
            warnings.append(
                "Rate limiting is disabled. Enable for production deployments."
            )
        
        return warnings

