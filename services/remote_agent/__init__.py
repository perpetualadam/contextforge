"""
ContextForge Remote Agent Service.

This package provides distributed agent capabilities for ContextForge,
enabling horizontal scaling and parallel task processing.

Copyright (c) 2025 ContextForge
"""

import os

__version__ = "0.1.0"

# Check if Redis should be used
USE_REDIS = os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes")


# Lazy imports to avoid circular dependencies
def get_agent_registry(use_redis: bool = None):
    """
    Get the agent registry singleton.

    Args:
        use_redis: If True, use Redis backend. If None, uses USE_REDIS env var.
    """
    if use_redis is None:
        use_redis = USE_REDIS

    if use_redis:
        from .redis_backend import get_redis_registry
        return get_redis_registry()
    else:
        from .registry import get_registry
        return get_registry()


def get_task_queue(use_redis: bool = None):
    """
    Get the task queue singleton.

    Args:
        use_redis: If True, use Redis backend. If None, uses USE_REDIS env var.
    """
    if use_redis is None:
        use_redis = USE_REDIS

    if use_redis:
        from .redis_backend import get_redis_queue
        return get_redis_queue()
    else:
        from .queue import get_task_queue
        return get_task_queue()


def create_agent_worker(agent_id: str = None, capabilities: list = None):
    """Create a new agent worker instance."""
    from .worker import AgentWorker
    return AgentWorker(agent_id=agent_id, capabilities=capabilities)

