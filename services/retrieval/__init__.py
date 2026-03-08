"""
ContextForge Hierarchical Retrieval Service.

Implements multi-level context retrieval:
1. Module-level embeddings -> fast filter
2. File-level embeddings -> select relevant files
3. Function-level embeddings -> final context for LLM
4. Optional: test outcomes + git history + commit hashes

Copyright (c) 2025 ContextForge
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import requests as http_requests

logger = logging.getLogger(__name__)

VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://vector-index:8001")
VECTOR_SEARCH_TIMEOUT = int(os.getenv("VECTOR_SEARCH_TIMEOUT", "60"))


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
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "32768"))
    filters: Dict[str, Any] = field(default_factory=dict)
    task_scope: Optional[str] = None


class HierarchicalRetriever:
    """
    Hierarchical context retriever.

    Implements a multi-stage retrieval strategy:
    1. Module-level: Fast filtering to identify relevant modules
    2. File-level: Select most relevant files within modules
    3. Function-level: Extract specific functions and code blocks

    Uses HTTP calls to the vector-index service so it works in Docker.
    """

    def __init__(self, vector_index_url: str = None):
        self.vector_index_url = vector_index_url or VECTOR_INDEX_URL

    def _search(self, query: str, top_k: int = 10,
                task_scope: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Search the vector index via HTTP and return the results list."""
        try:
            payload: Dict[str, Any] = {"query": query, "top_k": top_k}
            if task_scope:
                payload["task_scope"] = task_scope
            payload.update(kwargs)

            resp = http_requests.post(
                f"{self.vector_index_url}/search",
                json=payload,
                timeout=VECTOR_SEARCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def retrieve(self, request: RetrievalRequest) -> List[ContextResult]:
        """
        Perform hierarchical retrieval.

        Args:
            request: RetrievalRequest with query and parameters

        Returns:
            List of ContextResult ordered by relevance
        """
        results = []

        # Stage 1: Module-level retrieval
        if ContextLevel.MODULE in request.levels:
            module_results = self._retrieve_modules(
                request.query, top_k=5, task_scope=request.task_scope
            )
            relevant_modules = [r.module_name for r in module_results if r.module_name]
            logger.debug(f"Module filter: {len(relevant_modules)} modules")
        else:
            relevant_modules = None

        # Stage 2: File-level retrieval
        if ContextLevel.FILE in request.levels:
            file_results = self._retrieve_files(
                request.query,
                top_k=request.top_k * 2,
                modules=relevant_modules,
                task_scope=request.task_scope,
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
                modules=relevant_modules,
                task_scope=request.task_scope,
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

        return results

    def retrieve_as_dicts(self, request: RetrievalRequest) -> List[Dict[str, Any]]:
        """Retrieve and return results as plain dicts (RAG-pipeline compatible)."""
        context_results = self.retrieve(request)
        return [
            {
                "text": r.content,
                "score": r.score,
                "meta": r.metadata,
                "content_type": r.metadata.get("content_type", "code"),
                "source": "hierarchical",
            }
            for r in context_results
        ]

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _retrieve_modules(self, query: str, top_k: int = 5,
                          task_scope: str = None) -> List[ContextResult]:
        """Retrieve at module level for fast filtering."""
        search_results = self._search(query, top_k=top_k, task_scope=task_scope)

        module_results = []
        seen_modules = set()

        for r in search_results:
            meta = r.get("meta", {})
            module_context = meta.get("module_context", {})
            module = module_context.get("module_name") or meta.get("module_name", "")
            if module and module not in seen_modules:
                seen_modules.add(module)
                module_results.append(ContextResult(
                    content=f"Module: {module}",
                    level=ContextLevel.MODULE,
                    score=r.get("score", 0.0),
                    module_name=module,
                    metadata=meta,
                ))

        return module_results

    def _retrieve_files(self, query: str, top_k: int = 10,
                        modules: List[str] = None,
                        task_scope: str = None) -> List[ContextResult]:
        """Retrieve at file level, optionally filtered to modules client-side."""
        search_results = self._search(query, top_k=top_k, task_scope=task_scope)

        file_results = []
        seen_files = set()

        for r in search_results:
            meta = r.get("meta", {})
            file_path = meta.get("file_path", "")

            # Client-side module filter
            if modules:
                module_context = meta.get("module_context", {})
                result_module = module_context.get("module_name") or meta.get("module_name", "")
                if result_module and result_module not in modules:
                    continue

            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                file_results.append(ContextResult(
                    content=r.get("text", ""),
                    level=ContextLevel.FILE,
                    score=r.get("score", 0.0),
                    file_path=file_path,
                    module_name=(meta.get("module_context") or {}).get("module_name"),
                    metadata=meta,
                ))

        return file_results

    def _retrieve_functions(self, query: str, top_k: int = 10,
                            files: List[str] = None,
                            modules: List[str] = None,
                            task_scope: str = None) -> List[ContextResult]:
        """Retrieve at function/chunk level for precise context."""
        search_results = self._search(query, top_k=top_k, task_scope=task_scope)

        function_results = []
        for r in search_results:
            meta = r.get("meta", {})
            file_path = meta.get("file_path", "")

            # Client-side file/module filter
            if files and file_path not in files:
                continue
            if modules and not files:
                result_module = (meta.get("module_context") or {}).get("module_name", "")
                if result_module and result_module not in modules:
                    continue

            func_name = meta.get("function_name") or meta.get("symbol_name")
            function_results.append(ContextResult(
                content=r.get("text", ""),
                level=ContextLevel.FUNCTION if func_name else ContextLevel.CHUNK,
                score=r.get("score", 0.0),
                file_path=file_path,
                module_name=(meta.get("module_context") or {}).get("module_name"),
                function_name=func_name,
                start_line=meta.get("start_line"),
                end_line=meta.get("end_line"),
                metadata=meta,
            ))

        return function_results

    def _retrieve_test_context(self, query: str, top_k: int = 3) -> List[ContextResult]:
        """Retrieve related test outcomes."""
        try:
            from services.metrics.test_correlation import CorrelationTracker
            tracker = CorrelationTracker()

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

            terms = query.lower().split()[:3]
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
                        score=0.3,
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
            key = (r.file_path, r.function_name, r.start_line)
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    def _result_to_dict(self, result: ContextResult) -> Dict[str, Any]:
        """Convert ContextResult to dictionary."""
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
    """Perform semantic search using the vector index."""
    retriever = HierarchicalRetriever()
    request = RetrievalRequest(
        query=query,
        top_k=top_k,
        levels=[ContextLevel.FUNCTION]
    )
    results = retriever.retrieve(request)
    return [retriever._result_to_dict(r) for r in results]


def lexical_filter(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Apply lexical filtering to semantic search results."""
    query_terms = set(query.lower().split())

    def score_lexical_match(result: Dict[str, Any]) -> float:
        content = result.get("content", "").lower()
        matches = sum(1 for term in query_terms if term in content)
        return matches / len(query_terms) if query_terms else 0

    for result in results:
        lexical_score = score_lexical_match(result)
        result["lexical_score"] = lexical_score
        result["combined_score"] = result.get("score", 0) * 0.7 + lexical_score * 0.3

    results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    return results


_retriever: Optional[HierarchicalRetriever] = None


def get_retriever() -> HierarchicalRetriever:
    """Get singleton retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HierarchicalRetriever()
    return _retriever
