"""
Persistence Data Models.

Copyright (c) 2025 ContextForge
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CLOSED = "closed"


class Session(BaseModel):
    """User session model."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class QueryRecord(BaseModel):
    """Query history record."""
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    query: str
    response: Optional[str] = None
    contexts_used: int = 0
    web_results_used: int = 0
    llm_backend: Optional[str] = None
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    feedback: Optional[str] = None  # positive, negative, neutral
    feedback_text: Optional[str] = None


class MetricType(str, Enum):
    """Metric types."""
    RETRIEVAL_ACCURACY = "retrieval_accuracy"
    QUERY_LATENCY = "query_latency"
    LLM_LATENCY = "llm_latency"
    EMBEDDING_LATENCY = "embedding_latency"
    TEST_PASS_RATE = "test_pass_rate"
    INDEX_SIZE = "index_size"
    CACHE_HIT_RATE = "cache_hit_rate"
    ERROR_RATE = "error_rate"


class MetricRecord(BaseModel):
    """Metric record for analytics."""
    metric_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_type: MetricType
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalFeedback(BaseModel):
    """Feedback for retrieval quality."""
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str
    query: str
    retrieved_chunks: List[str] = Field(default_factory=list)
    relevant_chunks: List[str] = Field(default_factory=list)  # User-marked as relevant
    precision: Optional[float] = None
    recall: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TestCorrelation(BaseModel):
    """Test pass/fail correlation with code changes."""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_name: str
    file_path: str
    commit_hash: Optional[str] = None
    passed: bool
    error_message: Optional[str] = None
    suggested_fix: Optional[str] = None
    fix_applied: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContextSnapshot(BaseModel):
    """Snapshot of context for long-term storage."""
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    query: str
    contexts: List[Dict[str, Any]] = Field(default_factory=list)
    response: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    project_path: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None

