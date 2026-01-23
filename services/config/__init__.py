"""
ContextForge Unified Configuration Module.

Provides centralized configuration management with typed access to all settings.
Loads configuration from environment variables with sensible defaults.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_bool(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_int(key: str, default: int) -> int:
    """Get integer value from environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    """Get float value from environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_list(key: str, default: List[str] = None) -> List[str]:
    """Get list value from comma-separated environment variable."""
    if default is None:
        default = []
    value = os.getenv(key, "")
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class LLMConfig:
    """LLM configuration settings."""
    priority: List[str] = field(default_factory=lambda: ["local", "cloud"])
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llama2-13b-code"
    lm_studio_url: str = "http://localhost:1234/v1/chat/completions"
    cloud_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_model: str = "deepseek-chat"
    timeout: int = 60
    max_tokens: int = 512
    temperature: float = 0.7


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    db_type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    user: str = "contextforge"
    password: str = "yourpassword"
    database: str = "contextforge_db"
    url: str = ""
    use_postgres: bool = False
    
    @property
    def connection_url(self) -> str:
        """Get the database connection URL."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration settings."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    url: str = ""
    prefix: str = "contextforge:"
    cache_ttl: int = 3600
    use_redis: bool = False
    
    @property
    def connection_url(self) -> str:
        """Get the Redis connection URL."""
        if self.url:
            return self.url
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class IndexingConfig:
    """Search and indexing configuration."""
    chunk_size: int = 1024
    chunk_overlap: int = 100
    max_chunk_size: int = 2048
    min_chunk_size: int = 128
    embedding_model: str = "all-mpnet-base-v2"
    code_embedding_model: str = "microsoft/codebert-base"
    use_code_embeddings: bool = True
    embedding_dim: int = 768
    faiss_index_type: str = "HNSW"
    faiss_hnsw_neighbors: int = 32
    faiss_nprobe: int = 10
    faiss_index_path: str = "data/vector_index/faiss_index.index"
    hybrid_search_enabled: bool = True
    dense_weight: float = 0.7
    lexical_weight: float = 0.3
    recency_boost_enabled: bool = True
    recency_boost_factor: float = 0.1
    vector_top_k: int = 10
    rerank_enabled: bool = True
    rerank_top_k: int = 50


@dataclass
class PrivacyConfig:
    """Privacy and logging configuration."""
    privacy_mode: bool = True
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    log_file: str = "logs/contextforge.log"
    log_to_file: bool = False


@dataclass
class SecurityConfig:
    """Security configuration."""
    api_key_enabled: bool = False
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    max_file_size_mb: int = 50


@dataclass
class WebSearchConfig:
    """Web search configuration."""
    enabled: bool = False
    provider: str = "google"
    api_key: str = ""
    cache_ttl: int = 86400
    max_results: int = 5


@dataclass
class AutoTerminalConfig:
    """Auto-terminal configuration."""
    enabled: bool = True
    timeout: int = 30
    max_output: int = 10000
    safe_only: bool = True
    whitelist: List[str] = field(default_factory=lambda: [
        "git status",
        "git log --oneline -10",
        "pytest",
        "python -m unittest",
        "npm test",
        "npm run test",
        "ls",
        "pwd",
        "cat package.json",
        "python --version",
        "node --version",
        "npm --version"
    ])


@dataclass
class AgentConfig:
    """Agent orchestration configuration."""
    max_concurrent: int = 4
    heartbeat_interval: int = 10
    task_timeout: int = 300
    retry_attempts: int = 3


@dataclass
class ScalingConfig:
    """Scaling configuration for large repositories."""
    parallel_indexing_enabled: bool = True
    module_level_parallelism: bool = True
    max_indexing_workers: int = 4
    batch_size: int = 100
    incremental_index_enabled: bool = True
    index_watch_enabled: bool = False
    index_refresh_interval: int = 86400
    git_integration_enabled: bool = True


@dataclass
class VCSConfig:
    """Version Control System (VCS) provider configuration.

    Supports GitHub, GitLab (including self-hosted), and Bitbucket.
    """
    # Default provider (auto-detected from remote URL if not set)
    provider: str = ""  # "github", "gitlab", or "bitbucket"

    # GitHub
    github_token: str = ""

    # GitLab (supports both gitlab.com and self-hosted)
    gitlab_token: str = ""
    gitlab_url: str = "https://gitlab.com"

    # Bitbucket
    bitbucket_token: str = ""
    bitbucket_username: str = ""


@dataclass
class ServiceURLs:
    """Service URL configuration."""
    vector_index: str = "http://localhost:8001"
    preprocessor: str = "http://localhost:8003"
    connector: str = "http://localhost:8002"
    web_fetcher: str = "http://localhost:8004"
    terminal_executor: str = "http://localhost:8006"


@dataclass
class DataConfig:
    """Data directory configuration."""
    data_dir: str = "data"
    repos_dir: str = "data/repos"
    cache_dir: str = "data/cache"
    logs_dir: str = "logs"


class ContextForgeConfig:
    """
    Centralized configuration for ContextForge.

    Loads all settings from environment variables with sensible defaults.
    Provides typed access to configuration values.
    """

    _instance: Optional['ContextForgeConfig'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables."""
        self.llm = LLMConfig(
            priority=_get_list("LLM_PRIORITY", ["local", "cloud"]),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama2-13b-code"),
            lm_studio_url=os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions"),
            cloud_api_key=os.getenv("CLOUD_LLM_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_api_url=os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            timeout=_get_int("LLM_TIMEOUT", 60),
            max_tokens=_get_int("LLM_MAX_TOKENS", 512),
            temperature=_get_float("LLM_TEMPERATURE", 0.7),
        )

        self.database = DatabaseConfig(
            db_type=os.getenv("DB_TYPE", "postgresql"),
            host=os.getenv("DB_HOST", "localhost"),
            port=_get_int("DB_PORT", 5432),
            user=os.getenv("DB_USER", "contextforge"),
            password=os.getenv("DB_PASS", "yourpassword"),
            database=os.getenv("DB_NAME", "contextforge_db"),
            url=os.getenv("DATABASE_URL", ""),
            use_postgres=_get_bool("USE_POSTGRES", False),
        )

        self.redis = RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=_get_int("REDIS_PORT", 6379),
            db=_get_int("REDIS_DB", 0),
            url=os.getenv("REDIS_URL", ""),
            prefix=os.getenv("REDIS_PREFIX", "contextforge:"),
            cache_ttl=_get_int("REDIS_CACHE_TTL", 3600),
            use_redis=_get_bool("USE_REDIS", False),
        )

        self.indexing = IndexingConfig(
            chunk_size=_get_int("CHUNK_SIZE", 1024),
            chunk_overlap=_get_int("CHUNK_OVERLAP", 100),
            max_chunk_size=_get_int("MAX_CHUNK_SIZE", 2048),
            min_chunk_size=_get_int("MIN_CHUNK_SIZE", 128),
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2"),
            code_embedding_model=os.getenv("CODE_EMBEDDING_MODEL", "microsoft/codebert-base"),
            use_code_embeddings=_get_bool("USE_CODE_EMBEDDINGS", True),
            embedding_dim=_get_int("EMBEDDING_DIM", 768),
            faiss_index_type=os.getenv("FAISS_INDEX_TYPE", "HNSW"),
            faiss_hnsw_neighbors=_get_int("FAISS_HNSW_NEIGHBORS", 32),
            faiss_nprobe=_get_int("FAISS_NPROBE", 10),
            faiss_index_path=os.getenv("FAISS_INDEX_PATH", "data/vector_index/faiss_index.index"),
            hybrid_search_enabled=_get_bool("HYBRID_SEARCH_ENABLED", True),
            dense_weight=_get_float("DENSE_WEIGHT", 0.7),
            lexical_weight=_get_float("LEXICAL_WEIGHT", 0.3),
            recency_boost_enabled=_get_bool("RECENCY_BOOST_ENABLED", True),
            recency_boost_factor=_get_float("RECENCY_BOOST_FACTOR", 0.1),
            vector_top_k=_get_int("VECTOR_TOP_K", 10),
            rerank_enabled=_get_bool("RERANK_ENABLED", True),
            rerank_top_k=_get_int("RERANK_TOP_K", 50),
        )

        self.privacy = PrivacyConfig(
            privacy_mode=_get_bool("PRIVACY_MODE", True),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "%(asctime)s - %(levelname)s - %(name)s - %(message)s"),
            log_file=os.getenv("LOG_FILE", "logs/contextforge.log"),
            log_to_file=_get_bool("LOG_TO_FILE", False),
        )

        self.security = SecurityConfig(
            api_key_enabled=_get_bool("API_KEY_ENABLED", False),
            rate_limit_enabled=_get_bool("RATE_LIMIT_ENABLED", True),
            rate_limit_requests=_get_int("RATE_LIMIT_REQUESTS", 100),
            rate_limit_window=_get_int("RATE_LIMIT_WINDOW", 60),
            max_file_size_mb=_get_int("MAX_FILE_SIZE_MB", 50),
        )

        self.web_search = WebSearchConfig(
            enabled=_get_bool("ENABLE_WEB_SEARCH", False),
            provider=os.getenv("WEB_SEARCH_PROVIDER", "google"),
            api_key=os.getenv("WEB_SEARCH_API_KEY", ""),
            cache_ttl=_get_int("WEB_CACHE_TTL", 86400),
            max_results=_get_int("WEB_SEARCH_RESULTS", 5),
        )

        self.auto_terminal = AutoTerminalConfig(
            enabled=_get_bool("AUTO_TERMINAL_MODE", True),
            timeout=_get_int("AUTO_TERMINAL_TIMEOUT", 30),
            max_output=_get_int("AUTO_TERMINAL_MAX_OUTPUT", 10000),
            safe_only=_get_bool("AUTO_TERMINAL_SAFE_ONLY", True),
        )

        self.agent = AgentConfig(
            max_concurrent=_get_int("AGENT_MAX_CONCURRENT", 4),
            heartbeat_interval=_get_int("AGENT_HEARTBEAT_INTERVAL", 10),
            task_timeout=_get_int("AGENT_TASK_TIMEOUT", 300),
            retry_attempts=_get_int("AGENT_RETRY_ATTEMPTS", 3),
        )

        self.scaling = ScalingConfig(
            parallel_indexing_enabled=_get_bool("PARALLEL_INDEXING_ENABLED", True),
            module_level_parallelism=_get_bool("MODULE_LEVEL_PARALLELISM", True),
            max_indexing_workers=_get_int("MAX_INDEXING_WORKERS", 4),
            batch_size=_get_int("BATCH_SIZE", 100),
            incremental_index_enabled=_get_bool("INCREMENTAL_INDEX_ENABLED", True),
            index_watch_enabled=_get_bool("INDEX_WATCH_ENABLED", False),
            index_refresh_interval=_get_int("INDEX_REFRESH_INTERVAL", 86400),
            git_integration_enabled=_get_bool("GIT_INTEGRATION_ENABLED", True),
        )

        self.vcs = VCSConfig(
            provider=os.getenv("VCS_PROVIDER", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            bitbucket_token=os.getenv("BITBUCKET_TOKEN", ""),
            bitbucket_username=os.getenv("BITBUCKET_USERNAME", ""),
        )

        self.services = ServiceURLs(
            vector_index=os.getenv("VECTOR_INDEX_URL", "http://localhost:8001"),
            preprocessor=os.getenv("PREPROCESSOR_URL", "http://localhost:8003"),
            connector=os.getenv("CONNECTOR_URL", "http://localhost:8002"),
            web_fetcher=os.getenv("WEB_FETCHER_URL", "http://localhost:8004"),
            terminal_executor=os.getenv("TERMINAL_EXECUTOR_URL", "http://localhost:8006"),
        )

        self.data = DataConfig(
            data_dir=os.getenv("DATA_DIR", "data"),
            repos_dir=os.getenv("REPOS_DIR", "data/repos"),
            cache_dir=os.getenv("CACHE_DIR", "data/cache"),
            logs_dir=os.getenv("LOGS_DIR", "logs"),
        )

        logger.info(f"Configuration loaded: DB={self.database.db_type}, Redis={self.redis.use_redis}")

    def reload(self):
        """Reload configuration from environment variables."""
        self._initialized = False
        self.__init__()

    @classmethod
    def reset(cls):
        """Reset singleton instance (for testing)."""
        cls._instance = None


def get_config() -> ContextForgeConfig:
    """Get the singleton configuration instance."""
    return ContextForgeConfig()

