"""
ContextForge Remote Agent Service.

This package provides distributed agent capabilities for ContextForge,
enabling horizontal scaling and parallel task processing.

Copyright (c) 2025 ContextForge
"""

__version__ = "0.1.0"

# Lazy imports to avoid circular dependencies
def get_agent_registry():
    """Get the agent registry singleton."""
    from .registry import get_registry
    return get_registry()


def get_task_queue():
    """Get the task queue singleton."""
    from .queue import get_task_queue
    return get_task_queue()


def create_agent_worker(agent_id: str = None, capabilities: list = None):
    """Create a new agent worker instance."""
    from .worker import AgentWorker
    return AgentWorker(agent_id=agent_id, capabilities=capabilities)

