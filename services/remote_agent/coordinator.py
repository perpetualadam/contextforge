"""
Coordinator - Manages task distribution and agent coordination.

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from threading import Lock

from .models import (
    AgentInfo, AgentStatus, AgentRegistration, HeartbeatRequest,
    TaskInfo, TaskRequest, TaskResult, TaskStatus
)
from .registry import AgentRegistry, get_registry
from .queue import TaskQueue, get_task_queue

logger = logging.getLogger(__name__)

# Singleton instance
_coordinator_instance = None
_coordinator_lock = Lock()


class Coordinator:
    """
    Central coordinator for the remote agent system.
    
    Responsibilities:
    - Accept task submissions
    - Distribute tasks to available agents
    - Track task progress
    - Handle agent registration and health
    """
    
    def __init__(
        self,
        registry: AgentRegistry = None,
        task_queue: TaskQueue = None,
        health_check_interval: int = 10,
    ):
        self.registry = registry or get_registry()
        self.task_queue = task_queue or get_task_queue()
        self.health_check_interval = health_check_interval
        
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._task_distribution_task: Optional[asyncio.Task] = None
        self._task_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = Lock()
        
        logger.info("Coordinator initialized")
    
    async def start(self) -> None:
        """Start the coordinator background tasks."""
        if self._running:
            return
        
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._task_distribution_task = asyncio.create_task(self._task_distribution_loop())
        logger.info("Coordinator started")
    
    async def stop(self) -> None:
        """Stop the coordinator."""
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._task_distribution_task:
            self._task_distribution_task.cancel()
            try:
                await self._task_distribution_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Coordinator stopped")
    
    async def _health_check_loop(self) -> None:
        """Periodically check agent health."""
        while self._running:
            try:
                unhealthy = self.registry.check_health()
                if unhealthy:
                    logger.warning(f"Unhealthy agents detected: {unhealthy}")
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _task_distribution_loop(self) -> None:
        """Distribute tasks to available agents."""
        while self._running:
            try:
                # Find available agents
                agents = self.registry.list_agents(status=AgentStatus.ONLINE)
                
                for agent in agents:
                    if agent.current_tasks >= agent.max_concurrent_tasks:
                        continue
                    
                    # Get next task for this agent
                    task = self.task_queue.get_next_task(capabilities=agent.capabilities)
                    if task:
                        # Assign task to agent
                        self.task_queue.assign_task(task.task_id, agent.agent_id)
                        self.registry.update_agent_tasks(agent.agent_id, 1)
                        
                        # Notify subscribers
                        await self._notify_task_update(task.task_id, task)
                        
                        logger.info(f"Task {task.task_id} assigned to agent {agent.agent_id}")
                
                await asyncio.sleep(0.1)  # Small delay to prevent busy loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task distribution error: {e}")
                await asyncio.sleep(1)
    
    # Agent management
    def register_agent(self, registration: AgentRegistration) -> AgentInfo:
        """Register a new agent."""
        return self.registry.register(registration)
    
    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent."""
        return self.registry.deregister(agent_id)
    
    def agent_heartbeat(self, request: HeartbeatRequest) -> bool:
        """Process agent heartbeat."""
        return self.registry.heartbeat(request)
    
    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentInfo]:
        """List all agents."""
        return self.registry.list_agents(status)
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID."""
        return self.registry.get_agent(agent_id)
    
    # Task management
    def submit_task(self, request: TaskRequest) -> TaskInfo:
        """Submit a new task."""
        return self.task_queue.submit(request)
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Get task by ID."""
        return self.task_queue.get_task(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 100) -> List[TaskInfo]:
        """List tasks."""
        return self.task_queue.list_tasks(status, limit)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        return self.task_queue.cancel_task(task_id)

    def complete_task(self, task_id: str, result: Any = None, error: str = None) -> Optional[TaskResult]:
        """Mark a task as completed."""
        task = self.task_queue.get_task(task_id)
        if task and task.assigned_agent:
            self.registry.update_agent_tasks(task.assigned_agent, -1)

        task_result = self.task_queue.complete_task(task_id, result, error)

        if task_result:
            asyncio.create_task(self._notify_task_update(task_id, task))

        return task_result

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result."""
        return self.task_queue.get_result(task_id)

    # Subscription management
    async def subscribe_to_task(self, task_id: str) -> asyncio.Queue:
        """Subscribe to task updates."""
        with self._lock:
            if task_id not in self._task_subscribers:
                self._task_subscribers[task_id] = set()

            queue = asyncio.Queue()
            self._task_subscribers[task_id].add(queue)
            return queue

    def unsubscribe_from_task(self, task_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from task updates."""
        with self._lock:
            if task_id in self._task_subscribers:
                self._task_subscribers[task_id].discard(queue)

    async def _notify_task_update(self, task_id: str, task: TaskInfo) -> None:
        """Notify subscribers of task update."""
        with self._lock:
            subscribers = self._task_subscribers.get(task_id, set()).copy()

        for queue in subscribers:
            try:
                await queue.put(task)
            except Exception as e:
                logger.error(f"Failed to notify subscriber: {e}")

    # Statistics
    def get_stats(self) -> Dict:
        """Get coordinator statistics."""
        return {
            "agents": self.registry.get_stats(),
            "tasks": self.task_queue.get_stats(),
        }


def get_coordinator() -> Coordinator:
    """Get the singleton coordinator instance."""
    global _coordinator_instance
    with _coordinator_lock:
        if _coordinator_instance is None:
            _coordinator_instance = Coordinator()
        return _coordinator_instance

