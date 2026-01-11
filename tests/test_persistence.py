"""
Tests for Persistence Service.
"""

import pytest
from datetime import datetime
import sys
import os

# Add the services directory to path for importing
services_path = os.path.join(os.path.dirname(__file__), '..', 'services')
if services_path not in sys.path:
    sys.path.insert(0, services_path)

from persistence.models import (
    Session, QueryRecord, MetricRecord, MetricType, RetrievalFeedback,
    ContextSnapshot
)
from persistence.memory_backend import (
    MemoryDatabase, MemorySessionStore, MemoryQueryHistory, MemoryMetricsStore,
    get_memory_db, get_memory_session_store, get_memory_query_history, get_memory_metrics_store
)


class TestModels:
    """Test Pydantic models."""

    def test_session_model(self):
        """Test Session model creation."""
        session = Session(
            session_id="test-123",
            user_id="user-1",
            metadata={"source": "test"}
        )
        assert session.session_id == "test-123"
        assert session.user_id == "user-1"
        assert session.metadata == {"source": "test"}
        assert session.created_at is not None

    def test_query_record_model(self):
        """Test QueryRecord model creation."""
        query = QueryRecord(
            query_id="q-123",
            session_id="s-123",
            query="How does auth work?",
            response="Auth works by...",
            contexts_used=3,
            web_results_used=2,
            llm_backend="mock",
            latency_ms=150
        )
        assert query.query_id == "q-123"
        assert query.latency_ms == 150

    def test_metric_record_model(self):
        """Test MetricRecord model creation."""
        metric = MetricRecord(
            metric_id="m-123",
            metric_type=MetricType.QUERY_LATENCY,
            value=125.5,
            tags={"backend": "mock"}
        )
        assert metric.metric_type == MetricType.QUERY_LATENCY
        assert metric.value == 125.5


class TestMemoryDatabase:
    """Test in-memory database operations."""

    def test_singleton_pattern(self):
        """Test that get_memory_db returns singleton."""
        db1 = get_memory_db()
        db2 = get_memory_db()
        assert db1 is db2

    def test_database_clear(self):
        """Test database clear method."""
        db = MemoryDatabase()
        db._sessions["test-1"] = {"id": "test-1"}
        assert "test-1" in db._sessions
        db.clear()
        assert "test-1" not in db._sessions


class TestMemorySessionStore:
    """Test in-memory session store."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create fresh instance for each test
        self.store = MemorySessionStore()
        self.store._sessions.clear()

    def test_create_session(self):
        """Test session creation."""
        session = self.store.create_session(user_id="user-1", metadata={"test": True})
        assert session.user_id == "user-1"
        assert session.session_id is not None
        assert session.metadata == {"test": True}

    def test_get_session(self):
        """Test session retrieval."""
        created = self.store.create_session(user_id="user-1")
        retrieved = self.store.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_get_nonexistent_session(self):
        """Test retrieval of nonexistent session."""
        result = self.store.get_session("nonexistent")
        assert result is None

    def test_update_session(self):
        """Test session update."""
        session = self.store.create_session()
        updated = self.store.update_session(session.session_id, metadata={"new": "data"})
        assert updated is not None
        assert updated.metadata.get("new") == "data"

    def test_list_sessions(self):
        """Test listing all sessions."""
        self.store.create_session(user_id="user-1")
        self.store.create_session(user_id="user-2")
        sessions = self.store.list_sessions()
        assert len(sessions) >= 2

    def test_list_sessions_by_user(self):
        """Test listing sessions by user."""
        self.store.create_session(user_id="user-1")
        self.store.create_session(user_id="user-1")
        self.store.create_session(user_id="user-2")
        sessions = self.store.list_sessions(user_id="user-1")
        assert len(sessions) == 2
        assert all(s.user_id == "user-1" for s in sessions)


class TestMemoryQueryHistory:
    """Test in-memory query history."""

    def setup_method(self):
        """Set up test fixtures."""
        self.history = MemoryQueryHistory()
        self.history._queries.clear()

    def test_add_query(self):
        """Test adding a query."""
        record = QueryRecord(
            session_id="s-1",
            query="How does auth work?",
            response="Auth works by...",
            contexts_used=3,
            llm_backend="mock"
        )
        query = self.history.add_query(record)
        assert query.session_id == "s-1"
        assert query.query_id is not None

    def test_get_query(self):
        """Test retrieving a query."""
        record = QueryRecord(
            query="Test query",
            response="Test response"
        )
        added = self.history.add_query(record)
        retrieved = self.history.get_query(added.query_id)
        assert retrieved is not None
        assert retrieved.query == "Test query"

    def test_list_queries_by_session(self):
        """Test listing queries by session."""
        self.history.add_query(QueryRecord(session_id="s-1", query="Q1"))
        self.history.add_query(QueryRecord(session_id="s-1", query="Q2"))
        self.history.add_query(QueryRecord(session_id="s-2", query="Q3"))
        queries = self.history.list_queries(session_id="s-1")
        assert len(queries) == 2

