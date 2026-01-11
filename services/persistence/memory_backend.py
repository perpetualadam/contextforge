"""
In-Memory Backend for Persistence.

Provides fallback storage when PostgreSQL is not available.

Copyright (c) 2025 ContextForge
"""

import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional

from .models import (
    Session, SessionStatus, QueryRecord, MetricRecord, MetricType,
    RetrievalFeedback, TestCorrelation, ContextSnapshot
)

logger = logging.getLogger(__name__)

# Singleton instances
_memory_db = None
_session_store = None
_query_history = None
_metrics_store = None


class MemoryDatabase:
    """In-memory database for development/testing."""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._queries: Dict[str, QueryRecord] = {}
        self._metrics: List[MetricRecord] = []
        self._feedback: Dict[str, RetrievalFeedback] = {}
        self._correlations: Dict[str, TestCorrelation] = {}
        self._snapshots: Dict[str, ContextSnapshot] = {}
        self._lock = Lock()
        logger.info("In-memory database initialized")
    
    def clear(self):
        """Clear all data."""
        with self._lock:
            self._sessions.clear()
            self._queries.clear()
            self._metrics.clear()
            self._feedback.clear()
            self._correlations.clear()
            self._snapshots.clear()


class MemorySessionStore:
    """In-memory session store."""
    
    def __init__(self, session_timeout_hours: int = 24):
        self._sessions: Dict[str, Session] = {}
        self._lock = Lock()
        self._timeout = timedelta(hours=session_timeout_hours)
    
    def create_session(self, user_id: str = None, metadata: Dict = None) -> Session:
        """Create a new session."""
        session = Session(
            user_id=user_id,
            expires_at=datetime.utcnow() + self._timeout,
            metadata=metadata or {}
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.expires_at and session.expires_at < datetime.utcnow():
                session.status = SessionStatus.EXPIRED
            return session
    
    def update_session(self, session_id: str, context: Dict = None, metadata: Dict = None) -> Optional[Session]:
        """Update session context/metadata."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.updated_at = datetime.utcnow()
                if context:
                    session.context.update(context)
                if metadata:
                    session.metadata.update(metadata)
            return session
    
    def close_session(self, session_id: str) -> bool:
        """Close a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = SessionStatus.CLOSED
                return True
            return False
    
    def list_sessions(self, user_id: str = None, status: SessionStatus = None) -> List[Session]:
        """List sessions with optional filters."""
        with self._lock:
            sessions = list(self._sessions.values())
            if user_id:
                sessions = [s for s in sessions if s.user_id == user_id]
            if status:
                sessions = [s for s in sessions if s.status == status]
            return sessions
    
    def cleanup_expired(self) -> int:
        """Clean up expired sessions."""
        now = datetime.utcnow()
        count = 0
        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if s.expires_at and s.expires_at < now
            ]
            for sid in expired:
                del self._sessions[sid]
                count += 1
        return count


class MemoryQueryHistory:
    """In-memory query history store."""
    
    def __init__(self, max_records: int = 10000):
        self._queries: Dict[str, QueryRecord] = {}
        self._lock = Lock()
        self._max_records = max_records
    
    def add_query(self, record: QueryRecord) -> QueryRecord:
        """Add a query record."""
        with self._lock:
            # Enforce max size
            if len(self._queries) >= self._max_records:
                oldest = min(self._queries.values(), key=lambda q: q.created_at)
                del self._queries[oldest.query_id]
            self._queries[record.query_id] = record
        return record
    
    def get_query(self, query_id: str) -> Optional[QueryRecord]:
        """Get query by ID."""
        return self._queries.get(query_id)
    
    def list_queries(self, session_id: str = None, limit: int = 100) -> List[QueryRecord]:
        """List queries with optional session filter."""
        with self._lock:
            queries = list(self._queries.values())
            if session_id:
                queries = [q for q in queries if q.session_id == session_id]
            queries.sort(key=lambda q: q.created_at, reverse=True)
            return queries[:limit]
    
    def add_feedback(self, query_id: str, feedback: str, feedback_text: str = None) -> bool:
        """Add feedback to a query."""
        with self._lock:
            query = self._queries.get(query_id)
            if query:
                query.feedback = feedback
                query.feedback_text = feedback_text
                return True
            return False


class MemoryMetricsStore:
    """In-memory metrics store."""

    def __init__(self, max_records: int = 100000):
        self._metrics: List[MetricRecord] = []
        self._lock = Lock()
        self._max_records = max_records

    def record_metric(self, metric_type: MetricType, value: float,
                      tags: Dict[str, str] = None, metadata: Dict = None) -> MetricRecord:
        """Record a metric."""
        record = MetricRecord(
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )
        with self._lock:
            if len(self._metrics) >= self._max_records:
                self._metrics = self._metrics[-(self._max_records // 2):]
            self._metrics.append(record)
        return record

    def get_metrics(self, metric_type: MetricType = None,
                    start_time: datetime = None, end_time: datetime = None,
                    tags: Dict[str, str] = None, limit: int = 1000) -> List[MetricRecord]:
        """Get metrics with optional filters."""
        with self._lock:
            metrics = self._metrics.copy()

        if metric_type:
            metrics = [m for m in metrics if m.metric_type == metric_type]
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        if tags:
            metrics = [m for m in metrics if all(m.tags.get(k) == v for k, v in tags.items())]

        return metrics[-limit:]

    def get_aggregated(self, metric_type: MetricType,
                       aggregation: str = "avg",
                       start_time: datetime = None,
                       end_time: datetime = None) -> Optional[float]:
        """Get aggregated metric value."""
        metrics = self.get_metrics(metric_type, start_time, end_time, limit=100000)
        if not metrics:
            return None

        values = [m.value for m in metrics]
        if aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "sum":
            return sum(values)
        elif aggregation == "min":
            return min(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "count":
            return float(len(values))
        return None


def get_memory_db() -> MemoryDatabase:
    """Get singleton memory database."""
    global _memory_db
    if _memory_db is None:
        _memory_db = MemoryDatabase()
    return _memory_db


def get_memory_session_store() -> MemorySessionStore:
    """Get singleton session store."""
    global _session_store
    if _session_store is None:
        _session_store = MemorySessionStore()
    return _session_store


def get_memory_query_history() -> MemoryQueryHistory:
    """Get singleton query history."""
    global _query_history
    if _query_history is None:
        _query_history = MemoryQueryHistory()
    return _query_history


def get_memory_metrics_store() -> MemoryMetricsStore:
    """Get singleton metrics store."""
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = MemoryMetricsStore()
    return _metrics_store

