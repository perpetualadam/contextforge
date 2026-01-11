"""
Redis Backend - Provides Redis-based persistence for agent registry and task queue.

Copyright (c) 2025 ContextForge
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from threading import Lock

from services.utils import utc_now

logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "contextforge:")

# Key prefixes
AGENTS_KEY = f"{REDIS_PREFIX}agents"
TASKS_KEY = f"{REDIS_PREFIX}tasks"
RESULTS_KEY = f"{REDIS_PREFIX}results"
PENDING_QUEUE_KEY = f"{REDIS_PREFIX}pending_queue"


def get_redis_client():
    """Get Redis client, returns None if Redis is not available."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except ImportError:
        logger.warning("Redis package not installed. Using in-memory storage.")
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Using in-memory storage.")
        return None


class RedisAgentRegistry:
    """
    Redis-backed agent registry for production use.
    
    Provides persistent storage for agent information across restarts.
    """
    
    def __init__(self, heartbeat_timeout_seconds: int = 30):
        self._redis = get_redis_client()
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self._lock = Lock()
        
        if self._redis:
            logger.info("Redis agent registry initialized")
        else:
            logger.warning("Redis not available, falling back to in-memory registry")
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis is not None
    
    def _agent_key(self, agent_id: str) -> str:
        """Get Redis key for an agent."""
        return f"{AGENTS_KEY}:{agent_id}"
    
    def _serialize_agent(self, agent) -> str:
        """Serialize agent to JSON."""
        data = agent.model_dump(mode="json")
        return json.dumps(data)
    
    def _deserialize_agent(self, data: str):
        """Deserialize agent from JSON."""
        from .models import AgentInfo, AgentStatus
        obj = json.loads(data)
        # Convert ISO format back to datetime
        if obj.get("last_heartbeat"):
            obj["last_heartbeat"] = datetime.fromisoformat(obj["last_heartbeat"])
        # Convert status string to enum
        if obj.get("status"):
            obj["status"] = AgentStatus(obj["status"])
        return AgentInfo(**obj)
    
    def register(self, registration) -> "AgentInfo":
        """Register a new agent."""
        from .models import AgentInfo
        
        agent = AgentInfo(
            name=registration.name,
            endpoint=registration.endpoint,
            capabilities=registration.capabilities,
            max_concurrent_tasks=registration.max_concurrent_tasks,
            metadata=registration.metadata,
        )
        
        if self._redis:
            self._redis.hset(AGENTS_KEY, agent.agent_id, self._serialize_agent(agent))
        
        logger.info(f"Agent registered: {agent.agent_id} ({agent.name})")
        return agent
    
    def deregister(self, agent_id: str) -> bool:
        """Deregister an agent."""
        if self._redis:
            result = self._redis.hdel(AGENTS_KEY, agent_id)
            if result:
                logger.info(f"Agent deregistered: {agent_id}")
                return True
            return False
        return False
    
    def get_agent(self, agent_id: str) -> Optional["AgentInfo"]:
        """Get agent by ID."""
        if self._redis:
            data = self._redis.hget(AGENTS_KEY, agent_id)
            if data:
                return self._deserialize_agent(data)
        return None
    
    def list_agents(self, status=None) -> List["AgentInfo"]:
        """List all agents, optionally filtered by status."""
        agents = []
        if self._redis:
            all_data = self._redis.hgetall(AGENTS_KEY)
            for data in all_data.values():
                agent = self._deserialize_agent(data)
                if status is None or agent.status == status:
                    agents.append(agent)
        return agents
    
    def find_agents_by_capability(self, capability: str) -> List["AgentInfo"]:
        """Find agents with a specific capability."""
        from .models import AgentStatus
        return [
            a for a in self.list_agents()
            if capability in a.capabilities and a.status == AgentStatus.ONLINE
        ]
    
    def find_available_agent(self, required_capabilities: List[str] = None) -> Optional["AgentInfo"]:
        """Find an available agent, optionally with required capabilities."""
        from .models import AgentStatus
        
        candidates = [
            a for a in self.list_agents()
            if a.status == AgentStatus.ONLINE
            and a.current_tasks < a.max_concurrent_tasks
        ]
        
        if required_capabilities:
            candidates = [
                a for a in candidates
                if all(cap in a.capabilities for cap in required_capabilities)
            ]
        
        if not candidates:
            return None

        return min(candidates, key=lambda a: a.current_tasks)

    def heartbeat(self, request) -> bool:
        """Process agent heartbeat."""
        if not self._redis:
            return False

        agent = self.get_agent(request.agent_id)
        if not agent:
            return False

        agent.last_heartbeat = utc_now()
        agent.status = request.status
        agent.current_tasks = request.current_tasks
        agent.metadata.update(request.metadata)

        self._redis.hset(AGENTS_KEY, agent.agent_id, self._serialize_agent(agent))
        return True

    def update_agent_tasks(self, agent_id: str, delta: int) -> bool:
        """Update agent's current task count."""
        agent = self.get_agent(agent_id)
        if agent:
            agent.current_tasks = max(0, agent.current_tasks + delta)
            if self._redis:
                self._redis.hset(AGENTS_KEY, agent_id, self._serialize_agent(agent))
            return True
        return False

    def check_health(self) -> List[str]:
        """Check agent health and mark unhealthy agents."""
        from .models import AgentStatus

        now = datetime.utcnow()
        unhealthy = []

        for agent in self.list_agents():
            if agent.status == AgentStatus.ONLINE:
                if now - agent.last_heartbeat > self._heartbeat_timeout:
                    agent.status = AgentStatus.UNHEALTHY
                    if self._redis:
                        self._redis.hset(AGENTS_KEY, agent.agent_id, self._serialize_agent(agent))
                    unhealthy.append(agent.agent_id)
                    logger.warning(f"Agent marked unhealthy: {agent.agent_id}")

        return unhealthy

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        from .models import AgentStatus

        agents = self.list_agents()
        total = len(agents)
        online = sum(1 for a in agents if a.status == AgentStatus.ONLINE)
        busy = sum(1 for a in agents if a.status == AgentStatus.BUSY)
        unhealthy = sum(1 for a in agents if a.status == AgentStatus.UNHEALTHY)
        total_tasks = sum(a.current_tasks for a in agents)

        return {
            "total_agents": total,
            "online": online,
            "busy": busy,
            "unhealthy": unhealthy,
            "offline": total - online - busy - unhealthy,
            "total_active_tasks": total_tasks,
            "backend": "redis" if self._redis else "memory",
        }


class RedisTaskQueue:
    """
    Redis-backed task queue for production use.

    Provides persistent storage for tasks across restarts.
    """

    def __init__(self, max_queue_size: int = 10000):
        self._redis = get_redis_client()
        self._max_queue_size = max_queue_size
        self._lock = Lock()

        if self._redis:
            logger.info("Redis task queue initialized")
        else:
            logger.warning("Redis not available, falling back to in-memory queue")

    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis is not None

    def _task_key(self, task_id: str) -> str:
        """Get Redis key for a task."""
        return f"{TASKS_KEY}:{task_id}"

    def _serialize_task(self, task) -> str:
        """Serialize task to JSON."""
        data = task.model_dump(mode="json")
        return json.dumps(data)

    def _deserialize_task(self, data: str):
        """Deserialize task from JSON."""
        from .models import TaskInfo, TaskStatus, TaskPriority
        obj = json.loads(data)
        # Convert ISO format back to datetime
        for field in ["created_at", "started_at", "completed_at"]:
            if obj.get(field):
                obj[field] = datetime.fromisoformat(obj[field])
        # Convert values back to enums
        if obj.get("status"):
            obj["status"] = TaskStatus(obj["status"])
        if obj.get("priority"):
            obj["priority"] = TaskPriority(obj["priority"])
        return TaskInfo(**obj)

    def submit(self, request) -> "TaskInfo":
        """Submit a new task to the queue."""
        from .models import TaskInfo, TaskStatus

        if self._redis:
            queue_size = self._redis.zcard(PENDING_QUEUE_KEY)
            if queue_size >= self._max_queue_size:
                raise ValueError("Task queue is full")

        task = TaskInfo(
            task_type=request.task_type,
            payload=request.payload,
            priority=request.priority,
            timeout_seconds=request.timeout_seconds,
            required_capabilities=request.required_capabilities,
            metadata=request.metadata,
            status=TaskStatus.QUEUED,
        )

        if self._redis:
            # Store task
            self._redis.hset(TASKS_KEY, task.task_id, self._serialize_task(task))
            # Add to sorted set (priority queue)
            score = -task.priority.value * 1000000 + task.created_at.timestamp()
            self._redis.zadd(PENDING_QUEUE_KEY, {task.task_id: score})

        logger.info(f"Task submitted: {task.task_id} (type={task.task_type})")
        return task

    def get_next_task(self, capabilities: List[str] = None) -> Optional["TaskInfo"]:
        """Get the next task from the queue."""
        from .models import TaskStatus

        if not self._redis:
            return None

        # Get tasks in priority order
        task_ids = self._redis.zrange(PENDING_QUEUE_KEY, 0, 9)  # Get top 10

        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task or task.status != TaskStatus.QUEUED:
                self._redis.zrem(PENDING_QUEUE_KEY, task_id)
                continue

            # Check capabilities
            if capabilities and task.required_capabilities:
                if not all(cap in capabilities for cap in task.required_capabilities):
                    continue

            # Found a suitable task
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            self._redis.hset(TASKS_KEY, task.task_id, self._serialize_task(task))
            self._redis.zrem(PENDING_QUEUE_KEY, task_id)
            return task

        return None

    def get_task(self, task_id: str) -> Optional["TaskInfo"]:
        """Get task by ID."""
        if self._redis:
            data = self._redis.hget(TASKS_KEY, task_id)
            if data:
                return self._deserialize_task(data)
        return None

    def list_tasks(self, status=None, limit: int = 100) -> List["TaskInfo"]:
        """List tasks, optionally filtered by status."""
        tasks = []
        if self._redis:
            all_data = self._redis.hgetall(TASKS_KEY)
            for data in all_data.values():
                task = self._deserialize_task(data)
                if status is None or task.status == status:
                    tasks.append(task)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def complete_task(self, task_id: str, result: Any = None, error: str = None) -> Optional["TaskResult"]:
        """Mark a task as completed."""
        from .models import TaskResult, TaskStatus

        task = self.get_task(task_id)
        if not task:
            return None

        task.completed_at = utc_now()
        task.status = TaskStatus.COMPLETED if not error else TaskStatus.FAILED
        task.result = result
        task.error = error

        duration = 0.0
        if task.started_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        task_result = TaskResult(
            task_id=task_id,
            status=task.status,
            result=result,
            error=error,
            duration_seconds=duration,
            agent_id=task.assigned_agent,
        )

        if self._redis:
            self._redis.hset(TASKS_KEY, task_id, self._serialize_task(task))
            self._redis.hset(RESULTS_KEY, task_id, json.dumps(task_result.model_dump()))

        logger.info(f"Task completed: {task_id} (status={task.status})")
        return task_result

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        from .models import TaskStatus

        task = self.get_task(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = utc_now()

        if self._redis:
            self._redis.hset(TASKS_KEY, task_id, self._serialize_task(task))
            self._redis.zrem(PENDING_QUEUE_KEY, task_id)

        logger.info(f"Task cancelled: {task_id}")
        return True

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent."""
        task = self.get_task(task_id)
        if task:
            task.assigned_agent = agent_id
            if self._redis:
                self._redis.hset(TASKS_KEY, task_id, self._serialize_task(task))
            return True
        return False

    def get_result(self, task_id: str) -> Optional["TaskResult"]:
        """Get task result."""
        from .models import TaskResult, TaskStatus

        if self._redis:
            data = self._redis.hget(RESULTS_KEY, task_id)
            if data:
                obj = json.loads(data)
                if obj.get("status"):
                    obj["status"] = TaskStatus(obj["status"])
                return TaskResult(**obj)
        return None

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        from .models import TaskStatus

        tasks = self.list_tasks(limit=10000)
        total = len(tasks)
        pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        queued = sum(1 for t in tasks if t.status == TaskStatus.QUEUED)
        running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)

        queue_size = 0
        if self._redis:
            queue_size = self._redis.zcard(PENDING_QUEUE_KEY)

        return {
            "total_tasks": total,
            "pending": pending,
            "queued": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "queue_size": queue_size,
            "backend": "redis" if self._redis else "memory",
        }

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove old completed/failed tasks."""
        from .models import TaskStatus

        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0

        for task in self.list_tasks(limit=10000):
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at and task.completed_at < cutoff:
                    if self._redis:
                        self._redis.hdel(TASKS_KEY, task.task_id)
                        self._redis.hdel(RESULTS_KEY, task.task_id)
                    removed += 1

        if removed:
            logger.info(f"Cleaned up {removed} old tasks")
        return removed


# Factory functions to get the appropriate backend
_redis_registry_instance = None
_redis_queue_instance = None
_factory_lock = Lock()


def get_redis_registry(use_redis: bool = True) -> RedisAgentRegistry:
    """Get Redis-backed registry instance."""
    global _redis_registry_instance
    with _factory_lock:
        if _redis_registry_instance is None:
            _redis_registry_instance = RedisAgentRegistry()
        return _redis_registry_instance


def get_redis_queue(use_redis: bool = True) -> RedisTaskQueue:
    """Get Redis-backed queue instance."""
    global _redis_queue_instance
    with _factory_lock:
        if _redis_queue_instance is None:
            _redis_queue_instance = RedisTaskQueue()
        return _redis_queue_instance

