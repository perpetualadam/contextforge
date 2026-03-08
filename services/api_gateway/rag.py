"""
RAG (Retrieval-Augmented Generation) pipeline for ContextForge.
Combines vector search, web search, and LLM generation.
"""

# Load environment variables early
import pathlib
import sys
from dotenv import load_dotenv
# Find .env file in project root (two levels up from this file)
env_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Add parent directory to path for services imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import requests
from llm_client import LLMClient
from search_adapter import SearchAdapter

logger = logging.getLogger(__name__)

# Try to use unified config, fallback to env vars
try:
    from services.config import get_config
    from services.cache import RetrievalCache, MemoryCache
    _config = get_config()
    CONFIG_AVAILABLE = True

    # Configuration from unified config
    VECTOR_INDEX_URL = _config.services.vector_index
    ENABLE_WEB_SEARCH = _config.web_search.enabled if hasattr(_config, 'web_search') else False
    VECTOR_TOP_K = _config.indexing.vector_top_k
    WEB_SEARCH_RESULTS = 5  # Default, could add to config

    # Initialize retrieval cache
    _retrieval_cache = RetrievalCache(backend=MemoryCache())
except ImportError:
    CONFIG_AVAILABLE = False
    _config = None
    _retrieval_cache = None

    # Fallback to environment variables
    VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://vector-index:8001")
    ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "True").lower() == "true"
    VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "10"))
    WEB_SEARCH_RESULTS = int(os.getenv("WEB_SEARCH_RESULTS", "5"))

# Prompt templates
SYSTEM_PROMPT = """You are "ContextForge Assistant", an expert code assistant. Always follow:
- Do NOT reveal chain-of-thought. Provide concise, factual answers.
- Cite evidence from the provided contexts. Use bracketed citation tokens: [SOURCE n].
- If code is returned, ensure it's syntactically valid in the language specified.
- If asked to modify local files, output only a JSON patch list of file paths and new contents (not raw instructions).
- Respect privacy: mention if an answer required sending content to a remote LLM."""

RAG_TEMPLATE = """SYSTEM: {system_prompt}

USER: Question: {question}

CONTEXTS:
{contexts}

WEB_RESULTS:
{web_results}

INSTRUCTION:
1) Answer the question concisely (max 300 words).
2) If code references are needed, include code blocks.
3) At the end, include a "SOURCES" section listing top 3 contexts and web results used.
4) Output JSON object meta: {{"sources": [...], "backend": "{backend}", "latency_ms": {latency_ms}}}"""


class RAGPipeline:
    """Main RAG pipeline orchestrator."""

    def __init__(self):
        self.llm_client = LLMClient()
        self.search_adapter = SearchAdapter() if ENABLE_WEB_SEARCH else None
        self.vector_index_url = VECTOR_INDEX_URL
        self._cache = _retrieval_cache  # Use global cache if available

    def retrieve_contexts(
        self,
        query: str,
        top_k: int = VECTOR_TOP_K,
        use_cache: bool = True,
        task_scope: Optional[str] = None,
        use_hierarchical: bool = False,
        editor_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant contexts from vector index with optional caching.

        Args:
            query: Search query string.
            top_k: Number of results.
            use_cache: Whether to use the retrieval cache.
            task_scope: Task scope key for task-scoped retrieval
                        (e.g. 'find_bugs', 'explain', 'refactor', 'test').
            use_hierarchical: Use HierarchicalRetriever instead of direct search.
            editor_context: Optional editor state dict with keys like
                ``current_file``, ``current_selection``, ``open_files``,
                ``cursor_line``, ``recent_files``, ``git_diff``.
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get_results(query, top_k=top_k)
            if cached is not None:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached

        try:
            results: List[Dict[str, Any]] = []

            if use_hierarchical:
                results = self._retrieve_hierarchical(query, top_k, task_scope)
            else:
                search_payload: Dict[str, Any] = {"query": query, "top_k": top_k}
                if task_scope and task_scope != "general":
                    search_payload["task_scope"] = task_scope
                    search_payload["expand_graph"] = True

                response = requests.post(
                    f"{self.vector_index_url}/search",
                    json=search_payload,
                    timeout=int(os.getenv("VECTOR_SEARCH_TIMEOUT", "60"))
                )
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

            # Boost / inject editor-context results
            if editor_context:
                results = self._apply_editor_context(results, editor_context)

            # Cache the results
            if use_cache and self._cache and results:
                self._cache.set_results(query, results, top_k=top_k)

            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Hierarchical retrieval helper
    # ------------------------------------------------------------------

    def _retrieve_hierarchical(
        self, query: str, top_k: int, task_scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Delegate retrieval to the HierarchicalRetriever (HTTP-based)."""
        try:
            from services.retrieval import HierarchicalRetriever, RetrievalRequest
            retriever = HierarchicalRetriever(vector_index_url=self.vector_index_url)
            request = RetrievalRequest(query=query, top_k=top_k, task_scope=task_scope)
            return retriever.retrieve_as_dicts(request)
        except Exception as e:
            logger.warning(f"Hierarchical retrieval failed, falling back: {e}")
            return []

    # ------------------------------------------------------------------
    # Editor context helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_editor_context(
        results: List[Dict[str, Any]],
        editor_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Boost and inject results based on editor state."""
        current_file = editor_context.get("current_file")
        open_files = set(editor_context.get("open_files") or [])
        selection = editor_context.get("current_selection")
        git_diff = editor_context.get("git_diff")

        # Boost results whose file matches current file or open tabs
        for r in results:
            file_path = (r.get("meta") or {}).get("file_path", "")
            if current_file and file_path and current_file.endswith(file_path):
                r["score"] = r.get("score", 0) * 1.5
            elif open_files and any(file_path and of.endswith(file_path) for of in open_files):
                r["score"] = r.get("score", 0) * 1.2

        # Prepend selection as highest-priority context
        if selection and selection.strip():
            results.insert(0, {
                "text": selection,
                "score": 2.0,
                "meta": {"source": "editor_selection", "file_path": current_file or ""},
                "content_type": "code",
                "source": "editor",
            })

        # Append git diff as supplementary context
        if git_diff and git_diff.strip():
            results.append({
                "text": git_diff[:4000],
                "score": 0.5,
                "meta": {"source": "git_diff"},
                "content_type": "diff",
                "source": "editor",
            })

        # Re-sort by score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.get_stats()
        return {"enabled": False}

    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear the retrieval cache."""
        if self._cache:
            return self._cache.backend.clear(pattern)
        return 0
    
    def search_web(self, query: str, num_results: int = WEB_SEARCH_RESULTS) -> List[Dict[str, Any]]:
        """Search the web for additional context."""
        if not self.search_adapter:
            return []
        
        try:
            search_result = self.search_adapter.search(
                query, 
                num_results=num_results,
                fetch_content=True
            )
            return search_result.get("results", [])
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    def summarize_contexts(self, contexts: List[Dict[str, Any]], 
                          max_contexts: int = 5) -> List[Dict[str, Any]]:
        """Summarize contexts if there are too many or they're too long."""
        if len(contexts) <= max_contexts:
            return contexts
        sorted_contexts = sorted(contexts, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_contexts[:max_contexts]

    def _budget_contexts(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Trim contexts to fit within the model's context window.

        Replaces naive ``summarize_contexts`` with token-aware budgeting.
        """
        if max_tokens is None:
            max_tokens = int(os.getenv("RAG_CONTEXT_BUDGET", "16384"))

        chars_per_token = 4
        max_chars = max_tokens * chars_per_token

        budgeted: List[Dict[str, Any]] = []
        total_chars = 0

        for ctx in sorted(contexts, key=lambda x: x.get("score", 0), reverse=True):
            text = ctx.get("text", "")
            if total_chars + len(text) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    ctx = {**ctx, "text": text[:remaining] + "\n... (truncated)"}
                    budgeted.append(ctx)
                break
            budgeted.append(ctx)
            total_chars += len(text)

        return budgeted
    
    def format_contexts(self, contexts: List[Dict[str, Any]]) -> str:
        """Format contexts for inclusion in prompt."""
        if not contexts:
            return "No relevant contexts found."
        
        formatted = []
        for i, context in enumerate(contexts):
            meta = context.get("meta", {})
            source = meta.get("file_path") or meta.get("url", "unknown")
            score = context.get("score", 0)
            text = context.get("text", "")
            
            formatted.append(f"[SOURCE {i+1} | {source} | score: {score:.3f}]\n{text}")
        
        return "\n\n".join(formatted)
    
    def format_web_results(self, web_results: List[Dict[str, Any]]) -> str:
        """Format web search results for inclusion in prompt."""
        if not web_results:
            return "No web results found."
        
        formatted = []
        for i, result in enumerate(web_results):
            title = result.get("title", "")
            url = result.get("url", "")
            snippet = result.get("snippet", "")
            
            formatted.append(f"[WEB {i+1}] {title} — {url}\n{snippet}")
        
        return "\n\n".join(formatted)
    
    def compose_prompt(self, question: str, contexts: List[Dict[str, Any]], 
                      web_results: List[Dict[str, Any]], backend: str = "unknown") -> str:
        """Compose the final prompt for the LLM."""
        contexts_text = self.format_contexts(contexts)
        web_text = self.format_web_results(web_results)
        
        return RAG_TEMPLATE.format(
            system_prompt=SYSTEM_PROMPT,
            question=question,
            contexts=contexts_text,
            web_results=web_text,
            backend=backend,
            latency_ms=0  # Will be filled in later
        )
    
    def answer_question(self, question: str,
                       enable_web_search: Optional[bool] = None,
                       max_tokens: int = 512,
                       task_scope: Optional[str] = None,
                       editor_context: Optional[Dict[str, Any]] = None,
                       use_hierarchical: bool = False) -> Dict[str, Any]:
        """Main RAG pipeline: retrieve, search, and generate answer.

        Args:
            question: The user's question.
            enable_web_search: Override web search setting.
            max_tokens: Max tokens for the LLM response.
            task_scope: Task scope key for task-scoped retrieval
                        (e.g. 'find_bugs', 'explain', 'refactor').
            editor_context: Optional editor state dict.
            use_hierarchical: Use HierarchicalRetriever.
        """
        start_time = datetime.now()

        # Step 1: Retrieve contexts from vector index
        logger.info(f"Retrieving contexts for: {question}")
        contexts = self.retrieve_contexts(
            question,
            task_scope=task_scope,
            use_hierarchical=use_hierarchical,
            editor_context=editor_context,
        )
        
        # Step 2: Optionally search the web
        web_results = []
        if (enable_web_search is True) or (enable_web_search is None and ENABLE_WEB_SEARCH):
            logger.info("Searching web for additional context")
            web_results = self.search_web(question)
        
        # Step 3: Budget contexts to fit model window (token-aware)
        contexts = self._budget_contexts(contexts)
        
        # Step 4: Compose prompt
        prompt = self.compose_prompt(question, contexts, web_results)
        
        # Step 5: Generate answer
        logger.info("Generating answer with LLM")
        try:
            llm_response = self.llm_client.generate(prompt, max_tokens=max_tokens)
            
            # Calculate total latency
            end_time = datetime.now()
            total_latency = int((end_time - start_time).total_seconds() * 1000)
            
            # Prepare response
            response = {
                "question": question,
                "answer": llm_response["text"],
                "contexts": contexts,
                "web_results": web_results,
                "meta": {
                    **llm_response["meta"],
                    "total_latency_ms": total_latency,
                    "num_contexts": len(contexts),
                    "num_web_results": len(web_results),
                    "timestamp": start_time.isoformat()
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "question": question,
                "answer": f"I apologize, but I encountered an error generating a response: {e}",
                "contexts": contexts,
                "web_results": web_results,
                "meta": {
                    "error": str(e),
                    "backend": "error",
                    "total_latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "num_contexts": len(contexts),
                    "num_web_results": len(web_results),
                    "timestamp": start_time.isoformat()
                }
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all RAG components."""
        health = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Check vector index
        try:
            response = requests.get(f"{self.vector_index_url}/health", timeout=5)
            health["components"]["vector_index"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": self.vector_index_url
            }
        except Exception as e:
            health["components"]["vector_index"] = {
                "status": "unhealthy",
                "error": str(e),
                "url": self.vector_index_url
            }
        
        # Check LLM adapters
        available_adapters = self.llm_client.list_available_adapters()
        health["components"]["llm_adapters"] = {
            "status": "healthy" if available_adapters else "unhealthy",
            "available": available_adapters
        }
        
        # Check search adapters
        if self.search_adapter:
            available_providers = self.search_adapter.list_available_providers()
            health["components"]["search_providers"] = {
                "status": "healthy" if available_providers else "unhealthy",
                "available": available_providers
            }
        else:
            health["components"]["search_providers"] = {
                "status": "disabled",
                "available": []
            }
        
        # Overall status
        component_statuses = [comp["status"] for comp in health["components"].values()]
        if "unhealthy" in component_statuses:
            health["status"] = "degraded"
        elif all(status in ["healthy", "disabled"] for status in component_statuses):
            health["status"] = "healthy"
        else:
            health["status"] = "unknown"
        
        return health
