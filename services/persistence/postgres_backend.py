"""
PostgreSQL Backend for Persistence.

Provides production-ready persistent storage.

Copyright (c) 2025 ContextForge
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from .models import (
    Session, SessionStatus, QueryRecord, MetricRecord, MetricType,
    RetrievalFeedback, TestCorrelation, ContextSnapshot
)

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://contextforge:contextforge@localhost:5432/contextforge")

# Singleton instances
_postgres_db = None
_session_store = None
_query_history = None
_metrics_store = None


def get_connection():
    """Get PostgreSQL connection."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except ImportError:
        logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


class PostgresDatabase:
    """PostgreSQL database manager."""
    
    def __init__(self):
        self._initialized = False
        self.initialize_schema()
    
    def initialize_schema(self):
        """Initialize database schema."""
        if self._initialized:
            return
        
        schema_sql = """
        -- Sessions table
        CREATE TABLE IF NOT EXISTS sessions (
            session_id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            status VARCHAR(20) DEFAULT 'active',
            metadata JSONB DEFAULT '{}',
            context JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        
        -- Query history table
        CREATE TABLE IF NOT EXISTS query_history (
            query_id VARCHAR(36) PRIMARY KEY,
            session_id VARCHAR(36) REFERENCES sessions(session_id) ON DELETE SET NULL,
            query TEXT NOT NULL,
            response TEXT,
            contexts_used INTEGER DEFAULT 0,
            web_results_used INTEGER DEFAULT 0,
            llm_backend VARCHAR(50),
            latency_ms INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB DEFAULT '{}',
            feedback VARCHAR(20),
            feedback_text TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_queries_session ON query_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_queries_created ON query_history(created_at);
        
        -- Metrics table
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id VARCHAR(36) PRIMARY KEY,
            metric_type VARCHAR(50) NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags JSONB DEFAULT '{}',
            metadata JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type);
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
        
        -- Retrieval feedback table
        CREATE TABLE IF NOT EXISTS retrieval_feedback (
            feedback_id VARCHAR(36) PRIMARY KEY,
            query_id VARCHAR(36) REFERENCES query_history(query_id) ON DELETE CASCADE,
            query TEXT NOT NULL,
            retrieved_chunks JSONB DEFAULT '[]',
            relevant_chunks JSONB DEFAULT '[]',
            precision DOUBLE PRECISION,
            recall DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Test correlations table
        CREATE TABLE IF NOT EXISTS test_correlations (
            correlation_id VARCHAR(36) PRIMARY KEY,
            test_name VARCHAR(500) NOT NULL,
            file_path VARCHAR(1000) NOT NULL,
            commit_hash VARCHAR(40),
            passed BOOLEAN NOT NULL,
            error_message TEXT,
            suggested_fix TEXT,
            fix_applied BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_test_file ON test_correlations(file_path);
        CREATE INDEX IF NOT EXISTS idx_test_passed ON test_correlations(passed);
        
        -- Context snapshots table
        CREATE TABLE IF NOT EXISTS context_snapshots (
            snapshot_id VARCHAR(36) PRIMARY KEY,
            session_id VARCHAR(36) REFERENCES sessions(session_id) ON DELETE SET NULL,
            query TEXT NOT NULL,
            contexts JSONB DEFAULT '[]',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            project_path VARCHAR(1000),
            git_branch VARCHAR(255),
            git_commit VARCHAR(40)
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_session ON context_snapshots(session_id);

        -- Embeddings metadata table (vectors stored in FAISS, metadata here)
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            chunk_id VARCHAR(36) UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            function_name TEXT,
            class_name TEXT,
            module_name TEXT,
            chunk_type VARCHAR(50) DEFAULT 'code',
            content_hash VARCHAR(64),
            commit_hash VARCHAR(40),
            embedding_version VARCHAR(20) DEFAULT '1.0',
            language VARCHAR(20),
            start_line INTEGER,
            end_line INTEGER,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_embeddings_file_path ON embeddings(file_path);
        CREATE INDEX IF NOT EXISTS idx_embeddings_module_name ON embeddings(module_name);
        CREATE INDEX IF NOT EXISTS idx_embeddings_commit_hash ON embeddings(commit_hash);
        CREATE INDEX IF NOT EXISTS idx_embeddings_function ON embeddings(function_name);
        CREATE INDEX IF NOT EXISTS idx_embeddings_content_hash ON embeddings(content_hash);
        CREATE INDEX IF NOT EXISTS idx_embeddings_version ON embeddings(embedding_version);

        -- Module index table for hierarchical context
        CREATE TABLE IF NOT EXISTS module_index (
            id SERIAL PRIMARY KEY,
            module_name VARCHAR(500) UNIQUE NOT NULL,
            module_path TEXT NOT NULL,
            file_count INTEGER DEFAULT 0,
            function_count INTEGER DEFAULT 0,
            class_count INTEGER DEFAULT 0,
            total_lines INTEGER DEFAULT 0,
            last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            commit_hash VARCHAR(40),
            embedding_id INTEGER,
            metadata JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_module_name ON module_index(module_name);
        CREATE INDEX IF NOT EXISTS idx_module_path ON module_index(module_path);

        -- File index table for hierarchical context
        CREATE TABLE IF NOT EXISTS file_index (
            id SERIAL PRIMARY KEY,
            file_path TEXT UNIQUE NOT NULL,
            module_name VARCHAR(500),
            file_name VARCHAR(255),
            language VARCHAR(20),
            line_count INTEGER DEFAULT 0,
            function_count INTEGER DEFAULT 0,
            class_count INTEGER DEFAULT 0,
            last_modified TIMESTAMP,
            last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            commit_hash VARCHAR(40),
            content_hash VARCHAR(64),
            embedding_id INTEGER,
            metadata JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_file_module ON file_index(module_name);
        CREATE INDEX IF NOT EXISTS idx_file_language ON file_index(language);
        CREATE INDEX IF NOT EXISTS idx_file_content_hash ON file_index(content_hash);

        -- Indexing history for incremental updates
        CREATE TABLE IF NOT EXISTS indexing_history (
            id SERIAL PRIMARY KEY,
            operation VARCHAR(50) NOT NULL,
            file_path TEXT,
            module_name VARCHAR(500),
            commit_hash VARCHAR(40),
            files_indexed INTEGER DEFAULT 0,
            chunks_created INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'completed',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_indexing_commit ON indexing_history(commit_hash);
        CREATE INDEX IF NOT EXISTS idx_indexing_status ON indexing_history(status);
        """
        
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
            conn.close()
            self._initialized = True
            logger.info("PostgreSQL schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise


class PostgresSessionStore:
    """PostgreSQL session store."""

    def __init__(self, session_timeout_hours: int = 24):
        self._timeout = timedelta(hours=session_timeout_hours)

    def create_session(self, user_id: str = None, metadata: Dict = None) -> Session:
        """Create a new session."""
        session = Session(
            user_id=user_id,
            expires_at=datetime.utcnow() + self._timeout,
            metadata=metadata or {}
        )

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sessions (session_id, user_id, created_at, updated_at,
                                         expires_at, status, metadata, context)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session.session_id, session.user_id, session.created_at,
                    session.updated_at, session.expires_at, session.status.value,
                    json.dumps(session.metadata), json.dumps(session.context)
                ))
            conn.commit()
        finally:
            conn.close()
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
                if row:
                    return Session(
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        expires_at=row['expires_at'],
                        status=SessionStatus(row['status']),
                        metadata=row['metadata'] or {},
                        context=row['context'] or {}
                    )
        finally:
            conn.close()
        return None

    def update_session(self, session_id: str, context: Dict = None,
                       metadata: Dict = None) -> Optional[Session]:
        """Update session context/metadata."""
        session = self.get_session(session_id)
        if not session:
            return None

        if context:
            session.context.update(context)
        if metadata:
            session.metadata.update(metadata)
        session.updated_at = datetime.utcnow()

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sessions SET updated_at = %s, context = %s, metadata = %s
                    WHERE session_id = %s
                """, (session.updated_at, json.dumps(session.context),
                      json.dumps(session.metadata), session_id))
            conn.commit()
        finally:
            conn.close()
        return session

    def close_session(self, session_id: str) -> bool:
        """Close a session."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sessions SET status = %s WHERE session_id = %s
                """, (SessionStatus.CLOSED.value, session_id))
                affected = cur.rowcount
            conn.commit()
            return affected > 0
        finally:
            conn.close()

    def list_sessions(self, user_id: str = None,
                      status: SessionStatus = None) -> List[Session]:
        """List sessions with optional filters."""
        conn = get_connection()
        try:
            query = "SELECT * FROM sessions WHERE 1=1"
            params = []
            if user_id:
                query += " AND user_id = %s"
                params.append(user_id)
            if status:
                query += " AND status = %s"
                params.append(status.value)
            query += " ORDER BY created_at DESC LIMIT 100"

            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [Session(
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    expires_at=row['expires_at'],
                    status=SessionStatus(row['status']),
                    metadata=row['metadata'] or {},
                    context=row['context'] or {}
                ) for row in rows]
        finally:
            conn.close()


class PostgresQueryHistory:
    """PostgreSQL query history store."""

    def add_query(self, record: QueryRecord) -> QueryRecord:
        """Add a query record."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO query_history (query_id, session_id, query, response,
                        contexts_used, web_results_used, llm_backend, latency_ms,
                        created_at, metadata, feedback, feedback_text)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record.query_id, record.session_id, record.query, record.response,
                    record.contexts_used, record.web_results_used, record.llm_backend,
                    record.latency_ms, record.created_at, json.dumps(record.metadata),
                    record.feedback, record.feedback_text
                ))
            conn.commit()
        finally:
            conn.close()
        return record

    def get_query(self, query_id: str) -> Optional[QueryRecord]:
        """Get query by ID."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM query_history WHERE query_id = %s", (query_id,))
                row = cur.fetchone()
                if row:
                    return QueryRecord(**row)
        finally:
            conn.close()
        return None

    def list_queries(self, session_id: str = None, limit: int = 100) -> List[QueryRecord]:
        """List queries with optional session filter."""
        conn = get_connection()
        try:
            query = "SELECT * FROM query_history WHERE 1=1"
            params = []
            if session_id:
                query += " AND session_id = %s"
                params.append(session_id)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [QueryRecord(**row) for row in rows]
        finally:
            conn.close()

    def add_feedback(self, query_id: str, feedback: str, feedback_text: str = None) -> bool:
        """Add feedback to a query."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE query_history SET feedback = %s, feedback_text = %s
                    WHERE query_id = %s
                """, (feedback, feedback_text, query_id))
                affected = cur.rowcount
            conn.commit()
            return affected > 0
        finally:
            conn.close()


class PostgresMetricsStore:
    """PostgreSQL metrics store."""

    def record_metric(self, metric_type: MetricType, value: float,
                      tags: Dict[str, str] = None, metadata: Dict = None) -> MetricRecord:
        """Record a metric."""
        record = MetricRecord(
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO metrics (metric_id, metric_type, value, timestamp, tags, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    record.metric_id, record.metric_type.value, record.value,
                    record.timestamp, json.dumps(record.tags), json.dumps(record.metadata)
                ))
            conn.commit()
        finally:
            conn.close()
        return record

    def get_metrics(self, metric_type: MetricType = None,
                    start_time: datetime = None, end_time: datetime = None,
                    tags: Dict[str, str] = None, limit: int = 1000) -> List[MetricRecord]:
        """Get metrics with optional filters."""
        conn = get_connection()
        try:
            query = "SELECT * FROM metrics WHERE 1=1"
            params = []

            if metric_type:
                query += " AND metric_type = %s"
                params.append(metric_type.value)
            if start_time:
                query += " AND timestamp >= %s"
                params.append(start_time)
            if end_time:
                query += " AND timestamp <= %s"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [MetricRecord(
                    metric_id=row['metric_id'],
                    metric_type=MetricType(row['metric_type']),
                    value=row['value'],
                    timestamp=row['timestamp'],
                    tags=row['tags'] or {},
                    metadata=row['metadata'] or {}
                ) for row in rows]
        finally:
            conn.close()

    def get_aggregated(self, metric_type: MetricType, aggregation: str = "avg",
                       start_time: datetime = None, end_time: datetime = None) -> Optional[float]:
        """Get aggregated metric value."""
        agg_map = {"avg": "AVG", "sum": "SUM", "min": "MIN", "max": "MAX", "count": "COUNT"}
        agg_func = agg_map.get(aggregation, "AVG")

        conn = get_connection()
        try:
            query = f"SELECT {agg_func}(value) as result FROM metrics WHERE metric_type = %s"
            params = [metric_type.value]

            if start_time:
                query += " AND timestamp >= %s"
                params.append(start_time)
            if end_time:
                query += " AND timestamp <= %s"
                params.append(end_time)

            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return float(row['result']) if row and row['result'] else None
        finally:
            conn.close()


def get_postgres_db() -> PostgresDatabase:
    """Get singleton PostgreSQL database."""
    global _postgres_db
    if _postgres_db is None:
        _postgres_db = PostgresDatabase()
    return _postgres_db


def get_postgres_session_store() -> PostgresSessionStore:
    """Get singleton session store."""
    global _session_store
    if _session_store is None:
        _session_store = PostgresSessionStore()
    return _session_store


def get_postgres_query_history() -> PostgresQueryHistory:
    """Get singleton query history."""
    global _query_history
    if _query_history is None:
        _query_history = PostgresQueryHistory()
    return _query_history


def get_postgres_metrics_store() -> PostgresMetricsStore:
    """Get singleton metrics store."""
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = PostgresMetricsStore()
    return _metrics_store
