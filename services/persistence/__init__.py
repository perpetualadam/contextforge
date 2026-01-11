"""
ContextForge Persistence Service.

Provides PostgreSQL-based persistence for:
- Session management
- Query history
- Metrics storage
- Long-term context storage

Copyright (c) 2025 ContextForge
"""

import os

__version__ = "0.1.0"

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://contextforge:contextforge@localhost:5432/contextforge")
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() in ("true", "1", "yes")


def get_database():
    """Get database connection."""
    if USE_POSTGRES:
        from .postgres_backend import get_postgres_db
        return get_postgres_db()
    else:
        from .memory_backend import get_memory_db
        return get_memory_db()


def get_session_store():
    """Get session store."""
    if USE_POSTGRES:
        from .postgres_backend import get_postgres_session_store
        return get_postgres_session_store()
    else:
        from .memory_backend import get_memory_session_store
        return get_memory_session_store()


def get_query_history():
    """Get query history store."""
    if USE_POSTGRES:
        from .postgres_backend import get_postgres_query_history
        return get_postgres_query_history()
    else:
        from .memory_backend import get_memory_query_history
        return get_memory_query_history()


def get_metrics_store():
    """Get metrics store."""
    if USE_POSTGRES:
        from .postgres_backend import get_postgres_metrics_store
        return get_postgres_metrics_store()
    else:
        from .memory_backend import get_memory_metrics_store
        return get_memory_metrics_store()

