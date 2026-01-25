"""
ContextForge Hierarchical Retrieval Service.

Implements multi-level context retrieval:
1. Module-level embeddings → fast filter
2. File-level embeddings → select relevant files  
3. Function-level embeddings → final context for LLM
4. Optional: test outcomes + git history + commit hashes

Copyright (c) 2025 ContextForge
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ContextLevel(str, Enum):
    """Hierarchical context levels."""
    MODULE = "module"
    FILE = "file"
    FUNCTION = "function"
    CHUNK = "chunk"


@dataclass
class ContextResult:
    """Result from context retrieval."""
    content: str
    level: ContextLevel
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    module_name: Optional[str] = None
    function_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None


@dataclass
class RetrievalRequest:
    """Request for hierarchical retrieval."""
    query: str
    top_k: int = 10
    levels: List[ContextLevel] = field(default_factory=lambda: [
        ContextLevel.MODULE, ContextLevel.FILE, ContextLevel.FUNCTION
    ])
    include_tests: bool = False
    include_git_history: bool = False
    max_context_tokens: int = 4096
    filters: Dict[str, Any] = field(default_factory=dict)


class HierarchicalRetriever:
    """
    Hierarchical context retriever.
    
    Implements a multi-stage retrieval strategy:
    1. Module-level: Fast filtering to identify relevant modules
    2. File-level: Select most relevant files within modules
    3. Function-level: Extract specific functions and code blocks
    
    This approach is efficient for large codebases (500k+ LOC).
    """
    
    def __init__(self):
        from services.config import get_config
        self._config = get_config()
        self._vector_index = None
        self._cache = None
    
    @property
    def vector_index(self):
        """Lazy load vector index."""
        if self._vector_index is None:
            from services.vector_index.index import VectorIndex
            self._vector_index = VectorIndex()
        return self._vector_index
    
    @property
    def cache(self):
        """Lazy load cache."""
        if self._cache is None:
            from services.cache import get_cache
            self._cache = get_cache()
        return self._cache
    
    def retrieve(self, request: RetrievalRequest) -> List[ContextResult]:
        """
        Perform hierarchical retrieval.
        
        Args:
            request: RetrievalRequest with query and parameters
            
        Returns:
            List of ContextResult ordered by relevance
        """
        # Check cache first
        cached = self.cache.get_results(
            request.query, 
            request.top_k,
            levels=[l.value for l in request.levels]
        )
        if cached:
            return [ContextResult(**r) for r in cached]
        
        results = []
        
        # Stage 1: Module-level retrieval
        if ContextLevel.MODULE in request.levels:
            module_results = self._retrieve_modules(request.query, top_k=5)
            relevant_modules = [r.module_name for r in module_results if r.module_name]
            logger.debug(f"Module filter: {len(relevant_modules)} modules")
        else:
            relevant_modules = None
        
        # Stage 2: File-level retrieval
        if ContextLevel.FILE in request.levels:
            file_results = self._retrieve_files(
                request.query, 
                top_k=request.top_k * 2,
                modules=relevant_modules
            )
            relevant_files = [r.file_path for r in file_results if r.file_path]
            results.extend(file_results[:request.top_k // 2])
            logger.debug(f"File filter: {len(relevant_files)} files")
        else:
            relevant_files = None
        
        # Stage 3: Function-level retrieval
        if ContextLevel.FUNCTION in request.levels:
            function_results = self._retrieve_functions(
                request.query,
                top_k=request.top_k,
                files=relevant_files,
                modules=relevant_modules
            )
            results.extend(function_results)
        
        # Include test context if requested
        if request.include_tests:
            test_results = self._retrieve_test_context(request.query, top_k=3)
            results.extend(test_results)
        
        # Include git history if requested
        if request.include_git_history:
            git_results = self._retrieve_git_context(request.query, top_k=3)
            results.extend(git_results)
        
        # Sort by score and deduplicate
        results = self._deduplicate_and_rank(results)
        results = results[:request.top_k]
        
        # Cache results
        self.cache.set_results(
            request.query,
            [self._result_to_dict(r) for r in results],
            request.top_k,
            levels=[l.value for l in request.levels]
        )

        return results

    def _retrieve_modules(self, query: str, top_k: int = 5) -> List[ContextResult]:
        """Retrieve at module level for fast filtering."""
        results = self.vector_index.search(query, top_k=top_k)

        module_results = []
        seen_modules = set()

        for r in results:
            module = r.get("metadata", {}).get("module_name")
            if module and module not in seen_modules:
                seen_modules.add(module)
                module_results.append(ContextResult(
                    content=f"Module: {module}",
                    level=ContextLevel.MODULE,
                    score=r.get("score", 0.0),
                    module_name=module,
                    metadata=r.get("metadata", {})
                ))

        return module_results

    def _retrieve_files(self, query: str, top_k: int = 10,
                        modules: List[str] = None) -> List[ContextResult]:
        """Retrieve at file level."""
        filters = {}
        if modules:
            filters["module_name"] = modules

        results = self.vector_index.search(query, top_k=top_k, filters=filters)

        file_results = []
        seen_files = set()

        for r in results:
            file_path = r.get("metadata", {}).get("file_path")
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                file_results.append(ContextResult(
                    content=r.get("content", ""),
                    level=ContextLevel.FILE,
                    score=r.get("score", 0.0),
                    file_path=file_path,
                    module_name=r.get("metadata", {}).get("module_name"),
                    metadata=r.get("metadata", {})
                ))

        return file_results

    def _retrieve_functions(self, query: str, top_k: int = 10,
                           files: List[str] = None,
                           modules: List[str] = None) -> List[ContextResult]:
        """Retrieve at function/chunk level for precise context."""
        filters = {}
        if files:
            filters["file_path"] = files
        elif modules:
            filters["module_name"] = modules

        results = self.vector_index.search(query, top_k=top_k, filters=filters)

        function_results = []
        for r in results:
            meta = r.get("metadata", {})
            function_results.append(ContextResult(
                content=r.get("content", ""),
                level=ContextLevel.FUNCTION if meta.get("function_name") else ContextLevel.CHUNK,
                score=r.get("score", 0.0),
                file_path=meta.get("file_path"),
                module_name=meta.get("module_name"),
                function_name=meta.get("function_name"),
                start_line=meta.get("start_line"),
                end_line=meta.get("end_line"),
                metadata=meta
            ))

        return function_results

    def _retrieve_test_context(self, query: str, top_k: int = 3) -> List[ContextResult]:
        """Retrieve related test outcomes."""
        try:
            from services.metrics.test_correlation import CorrelationTracker
            tracker = CorrelationTracker()

            # Find tests related to the query terms
            correlations = tracker.get_correlations(query)

            results = []
            for corr in correlations[:top_k]:
                results.append(ContextResult(
                    content=f"Test: {corr.get('test_name')}\nOutcome: {corr.get('outcome')}",
                    level=ContextLevel.CHUNK,
                    score=corr.get("relevance", 0.5),
                    file_path=corr.get("file_path"),
                    metadata={"type": "test_outcome", **corr}
                ))
            return results
        except Exception as e:
            logger.warning(f"Failed to retrieve test context: {e}")
            return []

    def _retrieve_git_context(self, query: str, top_k: int = 3) -> List[ContextResult]:
        """Retrieve related git history context."""
        try:
            import subprocess

            # Search commit messages for query terms
            terms = query.lower().split()[:3]  # Use first 3 terms
            search_pattern = "|".join(terms)

            cmd = ["git", "log", "--oneline", "-n", str(top_k * 2),
                   f"--grep={search_pattern}", "-i"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return []

            results = []
            for line in result.stdout.strip().split("\n")[:top_k]:
                if line:
                    parts = line.split(" ", 1)
                    commit_hash = parts[0]
                    message = parts[1] if len(parts) > 1 else ""
                    results.append(ContextResult(
                        content=f"Commit {commit_hash}: {message}",
                        level=ContextLevel.CHUNK,
                        score=0.3,  # Lower score for git context
                        metadata={"type": "git_commit", "commit_hash": commit_hash}
                    ))
            return results
        except Exception as e:
            logger.warning(f"Failed to retrieve git context: {e}")
            return []

    def _deduplicate_and_rank(self, results: List[ContextResult]) -> List[ContextResult]:
        """Deduplicate results and rank by score."""
        seen = set()
        unique = []

        for r in sorted(results, key=lambda x: x.score, reverse=True):
            # Create unique key from file + function + line
            key = (r.file_path, r.function_name, r.start_line)
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    def _result_to_dict(self, result: ContextResult) -> Dict[str, Any]:
        """Convert ContextResult to dictionary for caching."""
        return {
            "content": result.content,
            "level": result.level.value,
            "score": result.score,
            "metadata": result.metadata,
            "file_path": result.file_path,
            "module_name": result.module_name,
            "function_name": result.function_name,
            "start_line": result.start_line,
            "end_line": result.end_line
        }


def semantic_search(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Perform semantic search using the vector index.

    This is a convenience function for simple semantic search.
    """
    retriever = HierarchicalRetriever()
    request = RetrievalRequest(
        query=query,
        top_k=top_k,
        levels=[ContextLevel.FUNCTION]
    )
    results = retriever.retrieve(request)
    return [retriever._result_to_dict(r) for r in results]


def lexical_filter(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Apply lexical filtering to semantic search results.

    Boosts results that contain exact query terms.
    """
    query_terms = set(query.lower().split())

    def score_lexical_match(result: Dict[str, Any]) -> float:
        content = result.get("content", "").lower()
        matches = sum(1 for term in query_terms if term in content)
        return matches / len(query_terms) if query_terms else 0

    # Add lexical boost to score
    for result in results:
        lexical_score = score_lexical_match(result)
        result["lexical_score"] = lexical_score
        result["combined_score"] = result.get("score", 0) * 0.7 + lexical_score * 0.3

    # Re-sort by combined score
    results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    return results


# Singleton instance
_retriever: Optional[HierarchicalRetriever] = None


def get_retriever() -> HierarchicalRetriever:
    """Get singleton retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HierarchicalRetriever()
    return _retriever

