"""
In-process retrieval instrumentation: latency samples, cache stats aggregation,
rerank lift tracking. Safe for multi-threaded FastAPI; no secrets.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional

_MAX_LAT = 5000
_MAX_STAGE = 2000


class RetrievalMetrics:
    """Singleton-style metrics for the API gateway / retrieval path."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_ms: Deque[float] = deque(maxlen=_MAX_LAT)
        self._dense_ms: Deque[float] = deque(maxlen=_MAX_STAGE)
        self._lexical_ms: Deque[float] = deque(maxlen=_MAX_STAGE)
        self._fusion_ms: Deque[float] = deque(maxlen=_MAX_STAGE)
        self._rerank_ms: Deque[float] = deque(maxlen=_MAX_STAGE)
        self._rag_retrieve_ms: Deque[float] = deque(maxlen=_MAX_LAT)
        # Rank delta: negative means rerank moved a better doc up (improvement)
        self._rerank_mean_rank_delta: Deque[float] = deque(maxlen=500)
        self._queries = 0

    def record_vector_search(
        self,
        total_ms: float,
        stages: Optional[Dict[str, float]] = None,
        rerank_rank_delta: Optional[float] = None,
    ) -> None:
        with self._lock:
            self._total_ms.append(total_ms)
            self._queries += 1
            if stages:
                if "dense_ms" in stages:
                    self._dense_ms.append(stages["dense_ms"])
                if "lexical_ms" in stages:
                    self._lexical_ms.append(stages["lexical_ms"])
                if "fusion_ms" in stages:
                    self._fusion_ms.append(stages["fusion_ms"])
                if "rerank_ms" in stages:
                    self._rerank_ms.append(stages["rerank_ms"])
            if rerank_rank_delta is not None:
                self._rerank_mean_rank_delta.append(rerank_rank_delta)

    def record_rag_retrieve(self, ms: float) -> None:
        with self._lock:
            self._rag_retrieve_ms.append(ms)

    @staticmethod
    def _histogram(samples: List[float], buckets: List[float]) -> Dict[str, Any]:
        if not samples:
            return {"count": 0, "buckets": {f"<={b}": 0 for b in buckets}, "p50": None, "p95": None, "p99": None}
        s = sorted(samples)
        n = len(s)

        def pct(p: float) -> float:
            return s[min(int(n * p), n - 1)]

        hist: Dict[str, int] = {}
        prev = 0.0
        for b in buckets:
            c = sum(1 for x in s if prev < x <= b)
            hist[f"({prev},{b}]"] = c
            prev = b
        hist[f">{buckets[-1]}"] = sum(1 for x in s if x > buckets[-1])
        return {
            "count": n,
            "buckets": hist,
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "min": s[0],
            "max": s[-1],
        }

    def snapshot(self, cache_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            total = list(self._total_ms)
            buckets = [5.0, 15.0, 50.0, 100.0, 300.0, 1000.0]
            out: Dict[str, Any] = {
                "vector_search_total_ms": self._histogram(total, buckets),
                "vector_search_queries": self._queries,
                "stages_ms": {
                    "dense": self._histogram(list(self._dense_ms), buckets),
                    "lexical": self._histogram(list(self._lexical_ms), buckets),
                    "fusion": self._histogram(list(self._fusion_ms), buckets),
                    "rerank": self._histogram(list(self._rerank_ms), buckets),
                },
                "rag_retrieve_ms": self._histogram(list(self._rag_retrieve_ms), buckets),
            }
            rd = list(self._rerank_mean_rank_delta)
            if rd:
                out["rerank_mean_rank_delta"] = {
                    "count": len(rd),
                    "mean": sum(rd) / len(rd),
                    "note": "negative_mean_suggests_rerank_improved_top_relevance",
                }
        if cache_stats:
            out["retrieval_cache"] = cache_stats
        return out

    def reset(self) -> None:
        with self._lock:
            self._total_ms.clear()
            self._dense_ms.clear()
            self._lexical_ms.clear()
            self._fusion_ms.clear()
            self._rerank_ms.clear()
            self._rag_retrieve_ms.clear()
            self._rerank_mean_rank_delta.clear()
            self._queries = 0


_metrics: Optional[RetrievalMetrics] = None


def get_retrieval_metrics() -> RetrievalMetrics:
    global _metrics
    if _metrics is None:
        _metrics = RetrievalMetrics()
    return _metrics
