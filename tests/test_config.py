"""
Tests for the ContextForge configuration module.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
from unittest.mock import patch


class TestContextForgeConfig:
    """Test the unified configuration module."""
    
    def setup_method(self):
        """Reset singleton before each test."""
        from services.config import ContextForgeConfig
        ContextForgeConfig.reset()
    
    def test_config_singleton(self):
        """Test that config is a singleton."""
        from services.config import get_config, ContextForgeConfig
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
    
    def test_config_default_values(self):
        """Test default configuration values."""
        from services.config import get_config
        
        config = get_config()
        
        # LLM defaults
        assert config.llm.timeout == 60
        assert config.llm.max_tokens == 512
        
        # Database defaults
        assert config.database.db_type == "postgresql"
        assert config.database.port == 5432
        
        # Redis defaults
        assert config.redis.port == 6379
        assert config.redis.cache_ttl == 3600
        
        # Indexing defaults
        assert config.indexing.chunk_size == 1024
        assert config.indexing.hybrid_search_enabled == True
    
    @patch.dict(os.environ, {"LLM_TIMEOUT": "120", "LLM_MAX_TOKENS": "1024"})
    def test_config_loads_from_env(self):
        """Test configuration loads from environment variables."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()
        
        config = get_config()
        
        assert config.llm.timeout == 120
        assert config.llm.max_tokens == 1024
    
    @patch.dict(os.environ, {"USE_POSTGRES": "true", "USE_REDIS": "true"})
    def test_config_boolean_parsing(self):
        """Test boolean environment variable parsing."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()
        
        config = get_config()
        
        assert config.database.use_postgres == True
        assert config.redis.use_redis == True
    
    @patch.dict(os.environ, {"LLM_PRIORITY": "ollama,openai,anthropic"})
    def test_config_list_parsing(self):
        """Test list environment variable parsing."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()
        
        config = get_config()
        
        assert config.llm.priority == ["ollama", "openai", "anthropic"]
    
    def test_database_connection_url(self):
        """Test database connection URL property."""
        from services.config import get_config
        
        config = get_config()
        url = config.database.connection_url
        
        assert "postgresql://" in url
        assert "contextforge" in url
    
    def test_redis_connection_url(self):
        """Test Redis connection URL property."""
        from services.config import get_config
        
        config = get_config()
        url = config.redis.connection_url
        
        assert "redis://" in url
    
    def test_config_reload(self):
        """Test configuration reload."""
        from services.config import get_config, ContextForgeConfig
        
        config = get_config()
        original_timeout = config.llm.timeout
        
        # Modify environment and reload
        with patch.dict(os.environ, {"LLM_TIMEOUT": "999"}):
            config.reload()
            assert config.llm.timeout == 999
    
    def test_auto_terminal_config(self):
        """Test auto-terminal configuration."""
        from services.config import get_config
        
        config = get_config()
        
        assert config.auto_terminal.enabled == True
        assert config.auto_terminal.timeout == 30
        assert config.auto_terminal.safe_only == True
        assert len(config.auto_terminal.whitelist) > 0
    
    def test_scaling_config(self):
        """Test scaling configuration for large repos."""
        from services.config import get_config
        
        config = get_config()
        
        assert config.scaling.parallel_indexing_enabled == True
        assert config.scaling.max_indexing_workers == 4
        assert config.scaling.incremental_index_enabled == True
    
    def test_privacy_config(self):
        """Test privacy configuration."""
        from services.config import get_config
        
        config = get_config()
        
        assert config.privacy.privacy_mode == True
        assert config.privacy.log_level == "INFO"

