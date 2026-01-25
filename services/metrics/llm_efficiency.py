"""
LLM Reasoning Efficiency Metrics.

Tracks and analyzes LLM performance to optimize
token usage, latency, and response quality.

Copyright (c) 2025 ContextForge
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from collections import defaultdict
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


class LLMRequest(BaseModel):
    """Single LLM request."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backend: str  # ollama, openai, anthropic, etc.
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None
    
    # Request details
    query: Optional[str] = None
    context_chunks: int = 0
    
    # Response quality indicators
    response_length: int = 0
    contained_code: bool = False
    contained_explanation: bool = False

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = Field(default_factory=dict)


class LLMEfficiencyMetrics(BaseModel):
    """Aggregated efficiency metrics."""
    period_start: datetime
    period_end: datetime
    
    # Volume metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Token metrics
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    
    # Latency metrics
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Efficiency metrics
    tokens_per_ms: float = 0.0  # Throughput
    success_rate: float = 0.0
    
    # Backend breakdown
    by_backend: Dict[str, Dict] = Field(default_factory=dict)


class LLMEfficiencyTracker:
    """Tracks and analyzes LLM reasoning efficiency."""
    
    def __init__(self):
        self._requests: List[LLMRequest] = []
        self._backend_stats: Dict[str, Dict] = defaultdict(lambda: {
            "requests": 0, "tokens": 0, "latency_sum": 0, "errors": 0
        })
    
    def record_request(self, request: LLMRequest) -> None:
        """Record an LLM request."""
        self._requests.append(request)
        
        # Update backend stats
        stats = self._backend_stats[request.backend]
        stats["requests"] += 1
        stats["tokens"] += request.total_tokens
        stats["latency_sum"] += request.latency_ms
        if not request.success:
            stats["errors"] += 1
        
        # Limit history
        if len(self._requests) > 10000:
            self._requests = self._requests[-10000:]
    
    def get_metrics(self, period_hours: int = 24) -> LLMEfficiencyMetrics:
        """Get efficiency metrics for a time period."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=period_hours)
        
        requests = [r for r in self._requests if r.timestamp >= start_time]
        
        metrics = LLMEfficiencyMetrics(
            period_start=start_time,
            period_end=end_time,
            total_requests=len(requests),
            successful_requests=sum(1 for r in requests if r.success),
            failed_requests=sum(1 for r in requests if not r.success)
        )
        
        if not requests:
            return metrics
        
        # Token metrics
        metrics.total_prompt_tokens = sum(r.prompt_tokens for r in requests)
        metrics.total_completion_tokens = sum(r.completion_tokens for r in requests)
        metrics.avg_prompt_tokens = metrics.total_prompt_tokens / len(requests)
        metrics.avg_completion_tokens = metrics.total_completion_tokens / len(requests)
        
        # Latency metrics
        latencies = sorted([r.latency_ms for r in requests])
        metrics.avg_latency_ms = sum(latencies) / len(latencies)
        metrics.p50_latency_ms = latencies[len(latencies) // 2]
        metrics.p95_latency_ms = latencies[int(len(latencies) * 0.95)]
        metrics.p99_latency_ms = latencies[int(len(latencies) * 0.99)]
        
        # Efficiency
        total_time = sum(r.latency_ms for r in requests if r.latency_ms > 0)
        total_tokens = sum(r.total_tokens for r in requests)
        metrics.tokens_per_ms = total_tokens / total_time if total_time > 0 else 0
        metrics.success_rate = metrics.successful_requests / len(requests)
        
        # Backend breakdown
        backends = set(r.backend for r in requests)
        for backend in backends:
            backend_reqs = [r for r in requests if r.backend == backend]
            metrics.by_backend[backend] = {
                "requests": len(backend_reqs),
                "avg_latency_ms": sum(r.latency_ms for r in backend_reqs) / len(backend_reqs),
                "total_tokens": sum(r.total_tokens for r in backend_reqs),
                "success_rate": sum(1 for r in backend_reqs if r.success) / len(backend_reqs),
                "error_count": sum(1 for r in backend_reqs if not r.success)
            }
        
        return metrics
    
    def get_slow_requests(self, threshold_ms: int = 5000, 
                          limit: int = 10) -> List[LLMRequest]:
        """Get slowest requests."""
        slow = [r for r in self._requests if r.latency_ms >= threshold_ms]
        return sorted(slow, key=lambda r: r.latency_ms, reverse=True)[:limit]
    
    def get_failed_requests(self, limit: int = 20) -> List[LLMRequest]:
        """Get recent failed requests."""
        failed = [r for r in self._requests if not r.success]
        return failed[-limit:]
    
    def get_backend_comparison(self) -> Dict[str, Dict]:
        """Compare efficiency across backends."""
        comparison = {}
        
        for backend, stats in self._backend_stats.items():
            if stats["requests"] > 0:
                comparison[backend] = {
                    "total_requests": stats["requests"],
                    "avg_latency_ms": stats["latency_sum"] / stats["requests"],
                    "avg_tokens": stats["tokens"] / stats["requests"],
                    "error_rate": stats["errors"] / stats["requests"],
                    "efficiency_score": self._compute_efficiency_score(stats)
                }
        
        return comparison
    
    def _compute_efficiency_score(self, stats: Dict) -> float:
        """Compute efficiency score (0-100) for a backend."""
        if stats["requests"] == 0:
            return 0.0
        
        # Factors: low latency, low error rate
        avg_latency = stats["latency_sum"] / stats["requests"]
        error_rate = stats["errors"] / stats["requests"]
        
        # Normalize latency (lower is better, target < 1000ms)
        latency_score = max(0, 100 - (avg_latency / 50))  # Lose points for slow
        
        # Error penalty
        error_penalty = error_rate * 50
        
        return max(0, min(100, latency_score - error_penalty))


# Singleton
_tracker = None

def get_llm_efficiency_tracker() -> LLMEfficiencyTracker:
    """Get singleton LLM efficiency tracker."""
    global _tracker
    if _tracker is None:
        _tracker = LLMEfficiencyTracker()
    return _tracker

