"""
ContextForge Persistence Service API.

Provides REST API for session, query, and metrics persistence.

Copyright (c) 2025 ContextForge
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import get_session_store, get_query_history, get_metrics_store
from .models import Session, SessionStatus, QueryRecord, MetricRecord, MetricType

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ContextForge Persistence Service",
    description="Long-term persistence for sessions, queries, and metrics",
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

# Request/Response Models
class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None
    metadata: Optional[Dict] = None

class UpdateSessionRequest(BaseModel):
    context: Optional[Dict] = None
    metadata: Optional[Dict] = None

class CreateQueryRequest(BaseModel):
    session_id: Optional[str] = None
    query: str
    response: Optional[str] = None
    contexts_used: int = 0
    web_results_used: int = 0
    llm_backend: Optional[str] = None
    latency_ms: int = 0
    metadata: Optional[Dict] = None

class FeedbackRequest(BaseModel):
    feedback: str  # positive, negative, neutral
    feedback_text: Optional[str] = None

class RecordMetricRequest(BaseModel):
    metric_type: MetricType
    value: float
    tags: Optional[Dict[str, str]] = None
    metadata: Optional[Dict] = None

class HealthResponse(BaseModel):
    status: str
    backend: str
    timestamp: datetime


# Health endpoint
@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    backend = "postgresql" if os.getenv("USE_POSTGRES", "false").lower() in ("true", "1") else "memory"
    return HealthResponse(status="healthy", backend=backend, timestamp=datetime.utcnow())


# Session endpoints
@app.post("/sessions", response_model=Session)
async def create_session(request: CreateSessionRequest):
    """Create a new session."""
    store = get_session_store()
    return store.create_session(user_id=request.user_id, metadata=request.metadata)


@app.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session by ID."""
    store = get_session_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.patch("/sessions/{session_id}", response_model=Session)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session context/metadata."""
    store = get_session_store()
    session = store.update_session(session_id, context=request.context, metadata=request.metadata)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """Close a session."""
    store = get_session_store()
    if not store.close_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "closed"}


@app.get("/sessions", response_model=List[Session])
async def list_sessions(
    user_id: Optional[str] = Query(None),
    status: Optional[SessionStatus] = Query(None)
):
    """List sessions with optional filters."""
    store = get_session_store()
    return store.list_sessions(user_id=user_id, status=status)


# Query history endpoints
@app.post("/queries", response_model=QueryRecord)
async def create_query(request: CreateQueryRequest):
    """Record a new query."""
    history = get_query_history()
    record = QueryRecord(
        session_id=request.session_id,
        query=request.query,
        response=request.response,
        contexts_used=request.contexts_used,
        web_results_used=request.web_results_used,
        llm_backend=request.llm_backend,
        latency_ms=request.latency_ms,
        metadata=request.metadata or {}
    )
    return history.add_query(record)


@app.get("/queries/{query_id}", response_model=QueryRecord)
async def get_query(query_id: str):
    """Get query by ID."""
    history = get_query_history()
    query = history.get_query(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    return query


@app.get("/queries", response_model=List[QueryRecord])
async def list_queries(
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """List queries with optional session filter."""
    history = get_query_history()
    return history.list_queries(session_id=session_id, limit=limit)


@app.post("/queries/{query_id}/feedback")
async def add_query_feedback(query_id: str, request: FeedbackRequest):
    """Add feedback to a query."""
    history = get_query_history()
    if not history.add_feedback(query_id, request.feedback, request.feedback_text):
        raise HTTPException(status_code=404, detail="Query not found")
    return {"status": "feedback recorded"}


# Metrics endpoints
@app.post("/metrics", response_model=MetricRecord)
async def record_metric(request: RecordMetricRequest):
    """Record a new metric."""
    store = get_metrics_store()
    return store.record_metric(
        metric_type=request.metric_type,
        value=request.value,
        tags=request.tags,
        metadata=request.metadata
    )


@app.get("/metrics", response_model=List[MetricRecord])
async def get_metrics(
    metric_type: Optional[MetricType] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, le=10000)
):
    """Get metrics with optional filters."""
    store = get_metrics_store()
    return store.get_metrics(
        metric_type=metric_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )


@app.get("/metrics/aggregated")
async def get_aggregated_metrics(
    metric_type: MetricType,
    aggregation: str = Query("avg", regex="^(avg|sum|min|max|count)$"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None)
):
    """Get aggregated metric value."""
    store = get_metrics_store()
    result = store.get_aggregated(
        metric_type=metric_type,
        aggregation=aggregation,
        start_time=start_time,
        end_time=end_time
    )
    return {"metric_type": metric_type.value, "aggregation": aggregation, "value": result}


# Dashboard summary endpoint
@app.get("/dashboard/summary")
async def get_dashboard_summary():
    """Get summary statistics for dashboard."""
    history = get_query_history()
    metrics_store = get_metrics_store()
    session_store = get_session_store()

    # Get recent queries
    recent_queries = history.list_queries(limit=10)

    # Get active sessions count
    active_sessions = len(session_store.list_sessions(status=SessionStatus.ACTIVE))

    # Get metric summaries
    avg_latency = metrics_store.get_aggregated(MetricType.QUERY_LATENCY, "avg")
    error_rate = metrics_store.get_aggregated(MetricType.ERROR_RATE, "avg")
    cache_hit = metrics_store.get_aggregated(MetricType.CACHE_HIT_RATE, "avg")

    return {
        "active_sessions": active_sessions,
        "recent_queries_count": len(recent_queries),
        "avg_query_latency_ms": avg_latency,
        "error_rate_percent": error_rate,
        "cache_hit_rate_percent": cache_hit,
        "timestamp": datetime.utcnow()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)

