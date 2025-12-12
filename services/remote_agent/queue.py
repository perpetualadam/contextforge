"""
Task Queue - Manages task submission, scheduling, and result retrieval.

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from threading import Lock
from queue import PriorityQueue
import heapq

from .models import TaskInfo, TaskRequest, TaskResult, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

# Singleton instance
_queue_instance = None
_queue_lock = Lock()


class TaskQueue:
    """
    In-memory task queue for managing distributed tasks.
    
    Provides:
    - Priority-based task scheduling
    - Task status tracking
    - Result storage and retrieval
    - Task cancellation
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self._tasks: Dict[str, TaskInfo] = {}
        self._pending_queue: List[tuple] = []  # (priority, timestamp, task_id)
        self._results: Dict[str, TaskResult] = {}
        self._lock = Lock()
        self._max_queue_size = max_queue_size
        self._task_callbacks: Dict[str, List[Callable]] = {}
        logger.info("Task queue initialized")
    
    def submit(self, request: TaskRequest) -> TaskInfo:
        """Submit a new task to the queue."""
        with self._lock:
            if len(self._pending_queue) >= self._max_queue_size:
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
            
            self._tasks[task.task_id] = task
            
            # Add to priority queue (negative priority for max-heap behavior)
            heapq.heappush(
                self._pending_queue,
                (-task.priority.value, task.created_at.timestamp(), task.task_id)
            )
            
            logger.info(f"Task submitted: {task.task_id} (type={task.task_type}, priority={task.priority})")
            return task
    
    def get_next_task(self, capabilities: List[str] = None) -> Optional[TaskInfo]:
        """Get the next task from the queue."""
        with self._lock:
            # Find a suitable task
            temp_queue = []
            result_task = None
            
            while self._pending_queue:
                item = heapq.heappop(self._pending_queue)
                _, _, task_id = item
                task = self._tasks.get(task_id)
                
                if not task or task.status != TaskStatus.QUEUED:
                    continue
                
                # Check capabilities
                if capabilities and task.required_capabilities:
                    if not all(cap in capabilities for cap in task.required_capabilities):
                        temp_queue.append(item)
                        continue
                
                result_task = task
                break
            
            # Restore skipped tasks
            for item in temp_queue:
                heapq.heappush(self._pending_queue, item)
            
            if result_task:
                result_task.status = TaskStatus.RUNNING
                result_task.started_at = datetime.utcnow()
            
            return result_task
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Get task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 100) -> List[TaskInfo]:
        """List tasks, optionally filtered by status."""
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            # Sort by created_at descending
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]
    
    def complete_task(self, task_id: str, result: Any = None, error: str = None) -> Optional[TaskResult]:
        """Mark a task as completed."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            
            task.completed_at = datetime.utcnow()
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
            
            self._results[task_id] = task_result
            logger.info(f"Task completed: {task_id} (status={task.status}, duration={duration:.2f}s)")
            
            # Trigger callbacks
            self._trigger_callbacks(task_id, task_result)
            
            return task_result
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            logger.info(f"Task cancelled: {task_id}")
            return True
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.assigned_agent = agent_id
                return True
            return False
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result."""
        with self._lock:
            return self._results.get(task_id)

    def add_callback(self, task_id: str, callback: Callable[[TaskResult], None]) -> None:
        """Add a callback for task completion."""
        with self._lock:
            if task_id not in self._task_callbacks:
                self._task_callbacks[task_id] = []
            self._task_callbacks[task_id].append(callback)

    def _trigger_callbacks(self, task_id: str, result: TaskResult) -> None:
        """Trigger callbacks for a completed task."""
        callbacks = self._task_callbacks.pop(task_id, [])
        for callback in callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error for task {task_id}: {e}")

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        with self._lock:
            total = len(self._tasks)
            pending = sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)
            queued = sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)
            running = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
            completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
            cancelled = sum(1 for t in self._tasks.values() if t.status == TaskStatus.CANCELLED)

            return {
                "total_tasks": total,
                "pending": pending,
                "queued": queued,
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "queue_size": len(self._pending_queue),
            }

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove old completed/failed tasks."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0

        with self._lock:
            to_remove = [
                task_id for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                and task.completed_at and task.completed_at < cutoff
            ]

            for task_id in to_remove:
                del self._tasks[task_id]
                self._results.pop(task_id, None)
                removed += 1

        if removed:
            logger.info(f"Cleaned up {removed} old tasks")
        return removed


def get_task_queue() -> TaskQueue:
    """Get the singleton task queue instance."""
    global _queue_instance
    with _queue_lock:
        if _queue_instance is None:
            _queue_instance = TaskQueue()
        return _queue_instance

