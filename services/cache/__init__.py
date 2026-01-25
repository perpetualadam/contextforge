"""
ContextForge Cache Service.

Provides Redis-backed caching for retrieval results and session data.
Falls back to in-memory cache when Redis is unavailable.

Copyright (c) 2025 ContextForge
"""

import json
import hashlib
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from threading import Lock
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass
    
    @abstractmethod
    def clear(self, pattern: str = "*") -> int:
        """Clear cache entries matching pattern."""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache implementation for development/testing."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry["expires_at"] and datetime.now(timezone.utc) > entry["expires_at"]:
                del self._cache[key]
                return None
            return entry["value"]

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        with self._lock:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl > 0 else None
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc)
            }
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return self.get(key) is not None
    
    def clear(self, pattern: str = "*") -> int:
        """Clear cache entries matching pattern."""
        with self._lock:
            if pattern == "*":
                count = len(self._cache)
                self._cache.clear()
                return count
            # Simple wildcard matching
            import fnmatch
            keys_to_delete = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def size(self) -> int:
        """Get number of entries in cache."""
        with self._lock:
            return len(self._cache)


class RedisCache(CacheBackend):
    """Redis-backed cache implementation for production use."""
    
    def __init__(self, url: str = None, prefix: str = "contextforge:cache:"):
        from services.config import get_config
        config = get_config()
        
        self._url = url or config.redis.connection_url
        self._prefix = prefix
        self._client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis."""
        try:
            import redis
            self._client = redis.from_url(self._url, decode_responses=True)
            self._client.ping()
            logger.info("Redis cache connected")
        except ImportError:
            logger.warning("Redis package not installed")
            self._client = None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._client is not None
    
    def _key(self, key: str) -> str:
        """Get prefixed key."""
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self._client:
            return None
        try:
            return self._client.get(self._key(key))
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        if not self._client:
            return False
        try:
            if ttl > 0:
                self._client.setex(self._key(key), ttl, value)
            else:
                self._client.set(self._key(key), value)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            return False
        try:
            return self._client.delete(self._key(key)) > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            return False
        try:
            return self._client.exists(self._key(key)) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    def clear(self, pattern: str = "*") -> int:
        """Clear cache entries matching pattern."""
        if not self._client:
            return 0
        try:
            keys = self._client.keys(f"{self._prefix}{pattern}")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0


class RetrievalCache:
    """
    Specialized cache for retrieval results.

    Caches query results to avoid redundant vector searches.
    Supports automatic cache key generation from query parameters.
    """

    def __init__(self, backend: Optional[CacheBackend] = None, ttl: int = 3600):
        from services.config import get_config
        config = get_config()

        if backend:
            self._backend = backend
        elif config.redis.use_redis:
            self._backend = RedisCache(prefix="contextforge:retrieval:")
            if not self._backend.is_available:
                logger.warning("Redis unavailable, falling back to memory cache")
                self._backend = MemoryCache()
        else:
            self._backend = MemoryCache()

        self._default_ttl = ttl
        self._stats = {"hits": 0, "misses": 0}

    def _generate_key(self, query: str, top_k: int = 10, **kwargs) -> str:
        """Generate cache key from query parameters."""
        params = {"query": query, "top_k": top_k, **kwargs}
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()

    def get_results(self, query: str, top_k: int = 10, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """Get cached retrieval results."""
        key = self._generate_key(query, top_k, **kwargs)
        cached = self._backend.get(key)
        if cached:
            self._stats["hits"] += 1
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return json.loads(cached)
        self._stats["misses"] += 1
        return None

    def set_results(self, query: str, results: List[Dict[str, Any]],
                    top_k: int = 10, ttl: int = None, **kwargs) -> bool:
        """Cache retrieval results."""
        key = self._generate_key(query, top_k, **kwargs)
        return self._backend.set(key, json.dumps(results), ttl or self._default_ttl)

    def invalidate(self, query: str = None, top_k: int = 10, **kwargs) -> bool:
        """Invalidate cached results."""
        if query:
            key = self._generate_key(query, top_k, **kwargs)
            return self._backend.delete(key)
        # Clear all retrieval cache
        return self._backend.clear("*") > 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate
        }


# Singleton instances
_cache: Optional[RetrievalCache] = None


def get_cache() -> RetrievalCache:
    """Get singleton cache instance."""
    global _cache
    if _cache is None:
        _cache = RetrievalCache()
    return _cache

