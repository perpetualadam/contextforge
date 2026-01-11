"""
Retrieval Accuracy Metrics.

Measures and tracks the quality of code retrieval results.

Copyright (c) 2025 ContextForge
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


class RetrievalResult(BaseModel):
    """Single retrieval result."""
    chunk_id: str
    content: str
    score: float
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class RetrievalEvaluation(BaseModel):
    """Evaluation of retrieval quality."""
    eval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    retrieved: List[RetrievalResult]
    relevant_ids: List[str]  # IDs marked as actually relevant
    
    # Computed metrics
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    mrr: Optional[float] = None  # Mean Reciprocal Rank
    ndcg: Optional[float] = None  # Normalized Discounted Cumulative Gain
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict = Field(default_factory=dict)


class RetrievalAccuracyTracker:
    """Tracks and computes retrieval accuracy metrics."""
    
    def __init__(self):
        self._evaluations: List[RetrievalEvaluation] = []
    
    def evaluate(self, query: str, retrieved: List[RetrievalResult],
                 relevant_ids: List[str]) -> RetrievalEvaluation:
        """Evaluate retrieval quality for a query."""
        evaluation = RetrievalEvaluation(
            query=query,
            retrieved=retrieved,
            relevant_ids=relevant_ids
        )
        
        retrieved_ids = [r.chunk_id for r in retrieved]
        relevant_set = set(relevant_ids)
        
        # Precision: fraction of retrieved that are relevant
        if retrieved_ids:
            true_positives = sum(1 for rid in retrieved_ids if rid in relevant_set)
            evaluation.precision = true_positives / len(retrieved_ids)
        else:
            evaluation.precision = 0.0
        
        # Recall: fraction of relevant that were retrieved
        if relevant_ids:
            true_positives = sum(1 for rid in retrieved_ids if rid in relevant_set)
            evaluation.recall = true_positives / len(relevant_ids)
        else:
            evaluation.recall = 1.0 if not retrieved_ids else 0.0
        
        # F1 Score: harmonic mean of precision and recall
        if evaluation.precision + evaluation.recall > 0:
            evaluation.f1_score = (2 * evaluation.precision * evaluation.recall) / \
                                  (evaluation.precision + evaluation.recall)
        else:
            evaluation.f1_score = 0.0
        
        # Mean Reciprocal Rank: 1/rank of first relevant result
        evaluation.mrr = 0.0
        for i, rid in enumerate(retrieved_ids):
            if rid in relevant_set:
                evaluation.mrr = 1.0 / (i + 1)
                break
        
        # NDCG (Normalized Discounted Cumulative Gain)
        evaluation.ndcg = self._compute_ndcg(retrieved_ids, relevant_set)
        
        self._evaluations.append(evaluation)
        return evaluation
    
    def _compute_ndcg(self, retrieved_ids: List[str], relevant_set: set, k: int = 10) -> float:
        """Compute NDCG@k."""
        import math
        
        # DCG: sum of (relevance / log2(rank + 1))
        dcg = 0.0
        for i, rid in enumerate(retrieved_ids[:k]):
            relevance = 1.0 if rid in relevant_set else 0.0
            dcg += relevance / math.log2(i + 2)  # +2 because log2(1) = 0
        
        # Ideal DCG: all relevant items at top
        ideal_order = sorted(range(len(retrieved_ids[:k])), 
                            key=lambda i: retrieved_ids[i] in relevant_set, reverse=True)
        idcg = 0.0
        for rank, i in enumerate(ideal_order):
            relevance = 1.0 if retrieved_ids[i] in relevant_set else 0.0
            idcg += relevance / math.log2(rank + 2)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def get_aggregate_metrics(self, 
                              since: datetime = None) -> Dict[str, Optional[float]]:
        """Get aggregate metrics over evaluations."""
        evals = self._evaluations
        if since:
            evals = [e for e in evals if e.timestamp >= since]
        
        if not evals:
            return {
                "avg_precision": None,
                "avg_recall": None,
                "avg_f1": None,
                "avg_mrr": None,
                "avg_ndcg": None,
                "total_evaluations": 0
            }
        
        return {
            "avg_precision": sum(e.precision or 0 for e in evals) / len(evals),
            "avg_recall": sum(e.recall or 0 for e in evals) / len(evals),
            "avg_f1": sum(e.f1_score or 0 for e in evals) / len(evals),
            "avg_mrr": sum(e.mrr or 0 for e in evals) / len(evals),
            "avg_ndcg": sum(e.ndcg or 0 for e in evals) / len(evals),
            "total_evaluations": len(evals)
        }
    
    def get_evaluations(self, limit: int = 100) -> List[RetrievalEvaluation]:
        """Get recent evaluations."""
        return self._evaluations[-limit:]


# Singleton instance
_tracker = None

def get_retrieval_tracker() -> RetrievalAccuracyTracker:
    """Get singleton retrieval accuracy tracker."""
    global _tracker
    if _tracker is None:
        _tracker = RetrievalAccuracyTracker()
    return _tracker

