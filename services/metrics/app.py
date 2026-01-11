"""
ContextForge Advanced Metrics API.

Provides REST API for advanced metrics tracking and analysis.

Copyright (c) 2025 ContextForge
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .retrieval_accuracy import (
    RetrievalResult, RetrievalEvaluation, get_retrieval_tracker
)
from .test_correlation import (
    TestResult, CodeChange, TestCorrelationResult, get_test_correlation_tracker
)
from .llm_efficiency import (
    LLMRequest, LLMEfficiencyMetrics, get_llm_efficiency_tracker
)

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ContextForge Advanced Metrics",
    description="Advanced metrics for retrieval accuracy, test correlation, and LLM efficiency",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Models
class EvaluateRetrievalRequest(BaseModel):
    query: str
    retrieved: List[RetrievalResult]
    relevant_ids: List[str]


class CorrelateTestsRequest(BaseModel):
    change: CodeChange
    test_results: List[TestResult]


class RecordLLMRequest(BaseModel):
    request: LLMRequest


# Health check
@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# Retrieval Accuracy Endpoints
@app.post("/retrieval/evaluate", response_model=RetrievalEvaluation)
async def evaluate_retrieval(request: EvaluateRetrievalRequest):
    """Evaluate retrieval quality for a query."""
    tracker = get_retrieval_tracker()
    return tracker.evaluate(
        query=request.query,
        retrieved=request.retrieved,
        relevant_ids=request.relevant_ids
    )


@app.get("/retrieval/metrics")
async def get_retrieval_metrics(since_hours: int = Query(24, ge=1, le=720)):
    """Get aggregate retrieval metrics."""
    from datetime import timedelta
    tracker = get_retrieval_tracker()
    since = datetime.utcnow() - timedelta(hours=since_hours)
    return tracker.get_aggregate_metrics(since=since)


@app.get("/retrieval/evaluations", response_model=List[RetrievalEvaluation])
async def get_retrieval_evaluations(limit: int = Query(100, le=1000)):
    """Get recent retrieval evaluations."""
    tracker = get_retrieval_tracker()
    return tracker.get_evaluations(limit=limit)


# Test Correlation Endpoints
@app.post("/tests/record")
async def record_test_result(result: TestResult):
    """Record a test result."""
    tracker = get_test_correlation_tracker()
    tracker.record_test_result(result)
    return {"status": "recorded", "result_id": result.result_id}


@app.post("/tests/correlate", response_model=TestCorrelationResult)
async def correlate_tests(request: CorrelateTestsRequest):
    """Correlate a code change with test results."""
    tracker = get_test_correlation_tracker()
    return tracker.correlate_change(
        change=request.change,
        test_results=request.test_results
    )


@app.get("/tests/flaky")
async def get_flaky_tests(
    threshold: float = Query(0.5, ge=0.1, le=0.9),
    min_runs: int = Query(5, ge=1)
):
    """Get list of flaky tests."""
    tracker = get_test_correlation_tracker()
    return tracker.get_flaky_tests(threshold=threshold, min_runs=min_runs)


# LLM Efficiency Endpoints
@app.post("/llm/record")
async def record_llm_request(request: RecordLLMRequest):
    """Record an LLM request for efficiency tracking."""
    tracker = get_llm_efficiency_tracker()
    tracker.record_request(request.request)
    return {"status": "recorded", "request_id": request.request.request_id}


@app.get("/llm/metrics", response_model=LLMEfficiencyMetrics)
async def get_llm_metrics(period_hours: int = Query(24, ge=1, le=168)):
    """Get LLM efficiency metrics."""
    tracker = get_llm_efficiency_tracker()
    return tracker.get_metrics(period_hours=period_hours)


@app.get("/llm/slow")
async def get_slow_requests(
    threshold_ms: int = Query(5000, ge=100),
    limit: int = Query(10, le=100)
):
    """Get slow LLM requests."""
    tracker = get_llm_efficiency_tracker()
    return tracker.get_slow_requests(threshold_ms=threshold_ms, limit=limit)


@app.get("/llm/failed")
async def get_failed_llm_requests(limit: int = Query(20, le=100)):
    """Get failed LLM requests."""
    tracker = get_llm_efficiency_tracker()
    return tracker.get_failed_requests(limit=limit)


@app.get("/llm/compare")
async def compare_backends():
    """Compare efficiency across LLM backends."""
    tracker = get_llm_efficiency_tracker()
    return tracker.get_backend_comparison()

