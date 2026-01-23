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

    def test_vcs_config_default(self):
        """Test VCS configuration default values."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        # VCS defaults - all empty by default
        assert config.vcs.provider == ""
        assert config.vcs.github_token == ""
        assert config.vcs.gitlab_token == ""
        assert config.vcs.gitlab_url == "https://gitlab.com"
        assert config.vcs.bitbucket_token == ""
        assert config.vcs.bitbucket_username == ""

    @patch.dict(os.environ, {
        "VCS_PROVIDER": "github",
        "GITHUB_TOKEN": "ghp_test_token_123"
    })
    def test_vcs_config_github(self):
        """Test VCS configuration for GitHub."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        assert config.vcs.provider == "github"
        assert config.vcs.github_token == "ghp_test_token_123"

    @patch.dict(os.environ, {
        "VCS_PROVIDER": "gitlab",
        "GITLAB_TOKEN": "glpat_test_token_456",
        "GITLAB_URL": "https://gitlab.mycompany.com"
    })
    def test_vcs_config_gitlab(self):
        """Test VCS configuration for GitLab (including self-hosted)."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        assert config.vcs.provider == "gitlab"
        assert config.vcs.gitlab_token == "glpat_test_token_456"
        assert config.vcs.gitlab_url == "https://gitlab.mycompany.com"

    @patch.dict(os.environ, {
        "VCS_PROVIDER": "bitbucket",
        "BITBUCKET_TOKEN": "bb_app_password_789",
        "BITBUCKET_USERNAME": "testuser"
    })
    def test_vcs_config_bitbucket(self):
        """Test VCS configuration for Bitbucket."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        assert config.vcs.provider == "bitbucket"
        assert config.vcs.bitbucket_token == "bb_app_password_789"
        assert config.vcs.bitbucket_username == "testuser"

    def test_deepseek_config_default(self):
        """Test DeepSeek LLM configuration default values."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        # DeepSeek defaults
        assert config.llm.deepseek_api_key == ""
        assert "deepseek.com" in config.llm.deepseek_api_url
        assert config.llm.deepseek_model == "deepseek-chat"

    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "sk-test-deepseek-key",
        "DEEPSEEK_MODEL": "deepseek-coder"
    })
    def test_deepseek_config_from_env(self):
        """Test DeepSeek configuration loads from environment."""
        from services.config import get_config, ContextForgeConfig
        ContextForgeConfig.reset()

        config = get_config()

        assert config.llm.deepseek_api_key == "sk-test-deepseek-key"
        assert config.llm.deepseek_model == "deepseek-coder"

