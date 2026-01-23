"""
ContextForge Documentation Cache.

Caches API documentation, language references, and common code patterns
for offline access.

Copyright (c) 2025 ContextForge
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DocEntry:
    """Documentation cache entry."""
    key: str
    category: str  # 'api', 'language', 'pattern', 'stdlib'
    language: str  # 'python', 'javascript', etc.
    title: str
    content: str
    tags: List[str]
    url: Optional[str] = None


class DocCache:
    """
    Documentation cache for offline access.
    
    Caches:
    - API documentation (Python stdlib, npm packages, etc.)
    - Language references (syntax, common patterns)
    - Code patterns and examples
    - Standard library documentation
    
    Integrates with existing cache infrastructure.
    """
    
    def __init__(self, backend=None):
        """
        Initialize documentation cache.
        
        Args:
            backend: Optional CacheBackend instance (defaults to MemoryCache)
        """
        if backend is None:
            from services.cache import MemoryCache
            backend = MemoryCache()
        
        self._backend = backend
        self._prefix = "doc:"
        self._stats = {"hits": 0, "misses": 0, "entries": 0}
    
    def _key(self, category: str, language: str, identifier: str) -> str:
        """Generate cache key."""
        return f"{self._prefix}{category}:{language}:{identifier}"
    
    def add(self, entry: DocEntry, ttl: int = 86400) -> bool:
        """
        Add documentation entry to cache.
        
        Args:
            entry: DocEntry to cache
            ttl: Time to live in seconds (default: 24 hours)
            
        Returns:
            True if successful
        """
        key = self._key(entry.category, entry.language, entry.key)
        value = json.dumps(asdict(entry))
        
        success = self._backend.set(key, value, ttl)
        if success:
            self._stats["entries"] += 1
            logger.debug(f"Cached doc: {entry.category}/{entry.language}/{entry.key}")
        
        return success
    
    def get(self, category: str, language: str, identifier: str) -> Optional[DocEntry]:
        """
        Get documentation entry from cache.
        
        Args:
            category: Category ('api', 'language', 'pattern', 'stdlib')
            language: Programming language
            identifier: Unique identifier (e.g., 'list.append', 'async-await')
            
        Returns:
            DocEntry if found, None otherwise
        """
        key = self._key(category, language, identifier)
        cached = self._backend.get(key)
        
        if cached:
            self._stats["hits"] += 1
            data = json.loads(cached)
            return DocEntry(**data)
        
        self._stats["misses"] += 1
        return None
    
    def search(self, query: str, language: Optional[str] = None, 
               category: Optional[str] = None, limit: int = 10) -> List[DocEntry]:
        """
        Search documentation cache.
        
        Note: This is a simple implementation. For production, consider
        using a proper search index.
        
        Args:
            query: Search query
            language: Optional language filter
            category: Optional category filter
            limit: Maximum results to return
            
        Returns:
            List of matching DocEntry objects
        """
        # This is a placeholder - in production, you'd want a proper search index
        # For now, we'll return empty list
        logger.warning("DocCache.search() not fully implemented - requires search index")
        return []
    
    def add_python_stdlib(self, module: str, function: str, doc: str, 
                          url: Optional[str] = None) -> bool:
        """
        Add Python standard library documentation.
        
        Args:
            module: Module name (e.g., 'os', 'sys')
            function: Function/class name (e.g., 'path.join')
            doc: Documentation text
            url: Optional URL to official docs
            
        Returns:
            True if successful
        """
        entry = DocEntry(
            key=f"{module}.{function}",
            category="stdlib",
            language="python",
            title=f"{module}.{function}",
            content=doc,
            tags=[module, "stdlib", "python"],
            url=url
        )
        return self.add(entry)

    def add_language_reference(self, language: str, topic: str, content: str,
                               tags: List[str] = None, url: Optional[str] = None) -> bool:
        """
        Add language reference documentation.

        Args:
            language: Programming language
            topic: Topic (e.g., 'async-await', 'decorators')
            content: Documentation content
            tags: Optional tags
            url: Optional URL to reference

        Returns:
            True if successful
        """
        entry = DocEntry(
            key=topic,
            category="language",
            language=language,
            title=topic,
            content=content,
            tags=tags or [language, "reference"],
            url=url
        )
        return self.add(entry)

    def add_code_pattern(self, language: str, pattern_name: str, code: str,
                        description: str, tags: List[str] = None) -> bool:
        """
        Add common code pattern.

        Args:
            language: Programming language
            pattern_name: Pattern name (e.g., 'singleton', 'factory')
            code: Example code
            description: Pattern description
            tags: Optional tags

        Returns:
            True if successful
        """
        content = f"{description}\n\n```{language}\n{code}\n```"

        entry = DocEntry(
            key=pattern_name,
            category="pattern",
            language=language,
            title=pattern_name,
            content=content,
            tags=tags or [language, "pattern"]
        )
        return self.add(entry)

    def add_api_doc(self, language: str, package: str, api_name: str,
                    doc: str, url: Optional[str] = None) -> bool:
        """
        Add API documentation.

        Args:
            language: Programming language
            package: Package/library name
            api_name: API name
            doc: Documentation text
            url: Optional URL to API docs

        Returns:
            True if successful
        """
        entry = DocEntry(
            key=f"{package}.{api_name}",
            category="api",
            language=language,
            title=f"{package}.{api_name}",
            content=doc,
            tags=[package, language, "api"],
            url=url
        )
        return self.add(entry)

    def bulk_add(self, entries: List[DocEntry], ttl: int = 86400) -> int:
        """
        Add multiple documentation entries.

        Args:
            entries: List of DocEntry objects
            ttl: Time to live in seconds

        Returns:
            Number of successfully added entries
        """
        count = 0
        for entry in entries:
            if self.add(entry, ttl):
                count += 1
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "entries": self._stats["entries"],
            "hit_rate": hit_rate
        }

    def clear(self, category: Optional[str] = None, language: Optional[str] = None) -> int:
        """
        Clear documentation cache.

        Args:
            category: Optional category filter
            language: Optional language filter

        Returns:
            Number of entries cleared
        """
        if category and language:
            pattern = f"{self._prefix}{category}:{language}:*"
        elif category:
            pattern = f"{self._prefix}{category}:*"
        elif language:
            pattern = f"{self._prefix}*:{language}:*"
        else:
            pattern = f"{self._prefix}*"

        return self._backend.clear(pattern)


# Singleton instance
_doc_cache: Optional[DocCache] = None


def get_doc_cache(backend=None) -> DocCache:
    """Get singleton documentation cache instance."""
    global _doc_cache
    if _doc_cache is None:
        _doc_cache = DocCache(backend)
    return _doc_cache


def seed_common_docs():
    """Seed cache with common documentation."""
    cache = get_doc_cache()

    # Python stdlib examples
    python_docs = [
        ("os", "path.join", "Join one or more path components intelligently.",
         "https://docs.python.org/3/library/os.path.html#os.path.join"),
        ("os", "listdir", "Return a list containing the names of the entries in the directory.",
         "https://docs.python.org/3/library/os.html#os.listdir"),
        ("json", "dumps", "Serialize obj to a JSON formatted str.",
         "https://docs.python.org/3/library/json.html#json.dumps"),
        ("json", "loads", "Deserialize s (a str instance containing a JSON document) to a Python object.",
         "https://docs.python.org/3/library/json.html#json.loads"),
    ]

    for module, func, doc, url in python_docs:
        cache.add_python_stdlib(module, func, doc, url)

    # Common patterns
    cache.add_code_pattern(
        "python",
        "singleton",
        """class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance""",
        "Singleton pattern ensures only one instance of a class exists.",
        ["design-pattern", "creational"]
    )

    logger.info(f"Seeded {len(python_docs) + 1} documentation entries")


