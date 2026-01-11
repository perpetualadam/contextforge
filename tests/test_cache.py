"""
Tests for the ContextForge cache service.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMemoryCache:
    """Test the in-memory cache implementation."""
    
    def test_set_and_get(self):
        """Test basic set and get operations."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        
        assert cache.get("key1") == "value1"
    
    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        
        assert cache.get("nonexistent") is None
    
    def test_delete(self):
        """Test deleting a key."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        
        assert cache.delete("key1") == True
        assert cache.get("key1") is None
    
    def test_delete_nonexistent(self):
        """Test deleting a key that doesn't exist."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        
        assert cache.delete("nonexistent") == False
    
    def test_exists(self):
        """Test checking if key exists."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        
        assert cache.exists("key1") == True
        assert cache.exists("nonexistent") == False
    
    def test_clear_all(self):
        """Test clearing all cache entries."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        count = cache.clear()
        
        assert count == 2
        assert cache.size() == 0
    
    def test_clear_pattern(self):
        """Test clearing cache entries by pattern."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("query:1", "value1")
        cache.set("query:2", "value2")
        cache.set("other:1", "value3")
        
        count = cache.clear("query:*")
        
        assert count == 2
        assert cache.exists("other:1") == True
    
    def test_size(self):
        """Test getting cache size."""
        from services.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert cache.size() == 2


class TestRetrievalCache:
    """Test the retrieval cache."""
    
    def test_cache_results(self):
        """Test caching and retrieving results."""
        from services.cache import RetrievalCache, MemoryCache
        
        cache = RetrievalCache(backend=MemoryCache())
        results = [{"id": 1, "score": 0.9}]
        
        cache.set_results("test query", results, top_k=10)
        cached = cache.get_results("test query", top_k=10)
        
        assert cached == results
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        from services.cache import RetrievalCache, MemoryCache
        
        cache = RetrievalCache(backend=MemoryCache())
        
        assert cache.get_results("unknown query") is None
    
    def test_cache_key_generation(self):
        """Test that different parameters generate different keys."""
        from services.cache import RetrievalCache, MemoryCache
        
        cache = RetrievalCache(backend=MemoryCache())
        results1 = [{"id": 1}]
        results2 = [{"id": 2}]
        
        cache.set_results("query", results1, top_k=5)
        cache.set_results("query", results2, top_k=10)
        
        assert cache.get_results("query", top_k=5) == results1
        assert cache.get_results("query", top_k=10) == results2
    
    def test_invalidate(self):
        """Test cache invalidation."""
        from services.cache import RetrievalCache, MemoryCache
        
        cache = RetrievalCache(backend=MemoryCache())
        cache.set_results("test query", [{"id": 1}])
        
        cache.invalidate("test query")
        
        assert cache.get_results("test query") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        from services.cache import RetrievalCache, MemoryCache
        
        cache = RetrievalCache(backend=MemoryCache())
        cache.set_results("query1", [{"id": 1}])
        
        # Hit
        cache.get_results("query1")
        # Miss
        cache.get_results("query2")
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

