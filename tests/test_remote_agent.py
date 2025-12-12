"""
Tests for Remote Agent system functionality.

Copyright (c) 2025 ContextForge
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Import the modules to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from remote_agent.models import (
    AgentInfo, AgentStatus, TaskInfo, TaskStatus, TaskPriority,
    AgentRegistration, TaskRequest, HeartbeatRequest, TaskResult,
    AgentCapability
)
from remote_agent.registry import AgentRegistry
from remote_agent.queue import TaskQueue
from remote_agent.coordinator import Coordinator
from remote_agent.worker import AgentWorker


class TestAgentModels:
    """Test the Pydantic models."""

    def test_agent_info_defaults(self):
        """Test AgentInfo has correct defaults."""
        agent = AgentInfo()
        assert agent.name == "Remote Agent"
        assert agent.status == AgentStatus.ONLINE
        assert agent.capabilities == []
        assert agent.current_tasks == 0
        assert agent.max_concurrent_tasks == 5
        assert agent.agent_id is not None

    def test_task_info_defaults(self):
        """Test TaskInfo has correct defaults."""
        task = TaskInfo(task_type="test")
        assert task.task_type == "test"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout_seconds == 300
        assert task.task_id is not None

    def test_agent_registration(self):
        """Test AgentRegistration model."""
        reg = AgentRegistration(
            name="Test Agent",
            capabilities=["code_analysis", "rag_query"],
            max_concurrent_tasks=10
        )
        assert reg.name == "Test Agent"
        assert len(reg.capabilities) == 2
        assert reg.max_concurrent_tasks == 10

    def test_task_request(self):
        """Test TaskRequest model."""
        req = TaskRequest(
            task_type="echo",
            payload={"message": "hello"},
            priority=TaskPriority.HIGH
        )
        assert req.task_type == "echo"
        assert req.payload == {"message": "hello"}
        assert req.priority == TaskPriority.HIGH

    def test_heartbeat_request(self):
        """Test HeartbeatRequest model."""
        req = HeartbeatRequest(
            agent_id="test-agent-123",
            status=AgentStatus.BUSY,
            current_tasks=3
        )
        assert req.agent_id == "test-agent-123"
        assert req.status == AgentStatus.BUSY
        assert req.current_tasks == 3


class TestAgentRegistry:
    """Test the AgentRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = AgentRegistry(heartbeat_timeout_seconds=5)

    def test_registry_initialization(self):
        """Test registry initializes correctly."""
        assert self.registry is not None
        assert len(self.registry.list_agents()) == 0

    def test_register_agent(self):
        """Test agent registration."""
        reg = AgentRegistration(
            name="Test Agent",
            capabilities=["code_analysis"]
        )
        agent = self.registry.register(reg)
        
        assert agent.name == "Test Agent"
        assert agent.status == AgentStatus.ONLINE
        assert "code_analysis" in agent.capabilities
        assert len(self.registry.list_agents()) == 1

    def test_deregister_agent(self):
        """Test agent deregistration."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.registry.register(reg)
        
        result = self.registry.deregister(agent.agent_id)
        assert result is True
        assert len(self.registry.list_agents()) == 0

    def test_deregister_nonexistent_agent(self):
        """Test deregistering nonexistent agent."""
        result = self.registry.deregister("nonexistent-id")
        assert result is False

    def test_get_agent(self):
        """Test getting agent by ID."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.registry.register(reg)
        
        retrieved = self.registry.get_agent(agent.agent_id)
        assert retrieved is not None
        assert retrieved.agent_id == agent.agent_id

    def test_get_nonexistent_agent(self):
        """Test getting nonexistent agent."""
        result = self.registry.get_agent("nonexistent-id")
        assert result is None

    def test_list_agents_by_status(self):
        """Test listing agents by status."""
        reg1 = AgentRegistration(name="Agent 1")
        reg2 = AgentRegistration(name="Agent 2")
        
        self.registry.register(reg1)
        self.registry.register(reg2)
        
        online_agents = self.registry.list_agents(status=AgentStatus.ONLINE)
        assert len(online_agents) == 2
        
        busy_agents = self.registry.list_agents(status=AgentStatus.BUSY)
        assert len(busy_agents) == 0

    def test_find_agents_by_capability(self):
        """Test finding agents by capability."""
        reg1 = AgentRegistration(name="Agent 1", capabilities=["code_analysis"])
        reg2 = AgentRegistration(name="Agent 2", capabilities=["web_search"])
        
        self.registry.register(reg1)
        self.registry.register(reg2)
        
        code_agents = self.registry.find_agents_by_capability("code_analysis")
        assert len(code_agents) == 1
        assert code_agents[0].name == "Agent 1"

    def test_find_available_agent(self):
        """Test finding available agent with load balancing."""
        reg1 = AgentRegistration(name="Agent 1", capabilities=["test"])
        reg2 = AgentRegistration(name="Agent 2", capabilities=["test"])

        agent1 = self.registry.register(reg1)
        agent2 = self.registry.register(reg2)

        # Simulate agent1 having more tasks
        self.registry.update_agent_tasks(agent1.agent_id, 3)

        # Should select agent2 (less loaded)
        available = self.registry.find_available_agent(required_capabilities=["test"])
        assert available is not None
        assert available.agent_id == agent2.agent_id

    def test_heartbeat(self):
        """Test processing heartbeat."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.registry.register(reg)

        heartbeat = HeartbeatRequest(
            agent_id=agent.agent_id,
            status=AgentStatus.BUSY,
            current_tasks=5
        )
        result = self.registry.heartbeat(heartbeat)

        assert result is True
        updated = self.registry.get_agent(agent.agent_id)
        assert updated.status == AgentStatus.BUSY
        assert updated.current_tasks == 5

    def test_heartbeat_nonexistent_agent(self):
        """Test heartbeat for nonexistent agent."""
        heartbeat = HeartbeatRequest(agent_id="nonexistent-id")
        result = self.registry.heartbeat(heartbeat)
        assert result is False

    def test_check_health(self):
        """Test health checking marks agents as unhealthy."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.registry.register(reg)

        # Force agent's last_heartbeat to be old
        with self.registry._lock:
            self.registry._agents[agent.agent_id].last_heartbeat = (
                datetime.utcnow() - timedelta(seconds=10)
            )

        unhealthy = self.registry.check_health()
        assert agent.agent_id in unhealthy

        updated = self.registry.get_agent(agent.agent_id)
        assert updated.status == AgentStatus.UNHEALTHY

    def test_get_stats(self):
        """Test getting registry statistics."""
        reg1 = AgentRegistration(name="Agent 1")
        reg2 = AgentRegistration(name="Agent 2")

        self.registry.register(reg1)
        self.registry.register(reg2)

        stats = self.registry.get_stats()
        assert stats["total_agents"] == 2
        assert stats["online"] == 2
        assert stats["busy"] == 0
        assert stats["unhealthy"] == 0


class TestTaskQueue:
    """Test the TaskQueue functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.queue = TaskQueue(max_queue_size=100)

    def test_queue_initialization(self):
        """Test queue initializes correctly."""
        assert self.queue is not None
        stats = self.queue.get_stats()
        assert stats["total_tasks"] == 0

    def test_submit_task(self):
        """Test submitting a task."""
        request = TaskRequest(task_type="echo", payload={"msg": "hello"})
        task = self.queue.submit(request)

        assert task.task_type == "echo"
        assert task.status == TaskStatus.QUEUED
        assert task.payload == {"msg": "hello"}

    def test_get_task(self):
        """Test getting a task by ID."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)

        retrieved = self.queue.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_get_nonexistent_task(self):
        """Test getting nonexistent task."""
        result = self.queue.get_task("nonexistent-id")
        assert result is None

    def test_get_next_task(self):
        """Test getting next task from queue."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)

        next_task = self.queue.get_next_task()
        assert next_task is not None
        assert next_task.task_id == task.task_id
        assert next_task.status == TaskStatus.RUNNING

    def test_get_next_task_priority_order(self):
        """Test tasks are returned in priority order."""
        low = TaskRequest(task_type="low", priority=TaskPriority.LOW)
        high = TaskRequest(task_type="high", priority=TaskPriority.HIGH)

        low_task = self.queue.submit(low)
        high_task = self.queue.submit(high)

        # High priority should come first
        next_task = self.queue.get_next_task()
        assert next_task.task_id == high_task.task_id

    def test_complete_task(self):
        """Test completing a task."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)

        # Start the task
        self.queue.get_next_task()

        result = self.queue.complete_task(task.task_id, result={"success": True})
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"success": True}

    def test_complete_task_with_error(self):
        """Test completing a task with error."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)
        self.queue.get_next_task()

        result = self.queue.complete_task(task.task_id, error="Something failed")
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert result.error == "Something failed"

    def test_cancel_task(self):
        """Test cancelling a task."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)

        result = self.queue.cancel_task(task.task_id)
        assert result is True

        cancelled = self.queue.get_task(task.task_id)
        assert cancelled.status == TaskStatus.CANCELLED

    def test_cancel_completed_task(self):
        """Test cannot cancel completed task."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)
        self.queue.get_next_task()
        self.queue.complete_task(task.task_id, result="done")

        result = self.queue.cancel_task(task.task_id)
        assert result is False

    def test_list_tasks(self):
        """Test listing tasks."""
        for i in range(5):
            self.queue.submit(TaskRequest(task_type=f"test-{i}"))

        tasks = self.queue.list_tasks()
        assert len(tasks) == 5

    def test_list_tasks_by_status(self):
        """Test listing tasks by status."""
        self.queue.submit(TaskRequest(task_type="test-1"))
        task2 = self.queue.submit(TaskRequest(task_type="test-2"))
        self.queue.get_next_task()  # Starts test-1 (higher priority or first)

        running = self.queue.list_tasks(status=TaskStatus.RUNNING)
        queued = self.queue.list_tasks(status=TaskStatus.QUEUED)

        assert len(running) == 1
        assert len(queued) == 1

    def test_assign_task(self):
        """Test assigning task to agent."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)

        result = self.queue.assign_task(task.task_id, "agent-123")
        assert result is True

        updated = self.queue.get_task(task.task_id)
        assert updated.assigned_agent == "agent-123"

    def test_get_result(self):
        """Test getting task result."""
        request = TaskRequest(task_type="test")
        task = self.queue.submit(request)
        self.queue.get_next_task()
        self.queue.complete_task(task.task_id, result="done")

        result = self.queue.get_result(task.task_id)
        assert result is not None
        assert result.result == "done"

    def test_get_stats(self):
        """Test getting queue statistics."""
        self.queue.submit(TaskRequest(task_type="test-1"))
        self.queue.submit(TaskRequest(task_type="test-2"))
        self.queue.get_next_task()

        stats = self.queue.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["running"] == 1
        assert stats["queued"] == 1

    def test_queue_full(self):
        """Test queue rejects when full."""
        small_queue = TaskQueue(max_queue_size=2)
        small_queue.submit(TaskRequest(task_type="test-1"))
        small_queue.submit(TaskRequest(task_type="test-2"))

        with pytest.raises(ValueError, match="queue is full"):
            small_queue.submit(TaskRequest(task_type="test-3"))


class TestAgentWorker:
    """Test the AgentWorker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.worker = AgentWorker(
            name="Test Worker",
            capabilities=["code_analysis", "web_search"],
            max_concurrent_tasks=3
        )

    def test_worker_initialization(self):
        """Test worker initializes correctly."""
        assert self.worker.name == "Test Worker"
        assert self.worker.max_concurrent_tasks == 3
        assert "code_analysis" in self.worker.capabilities
        assert "web_search" in self.worker.capabilities

    def test_worker_has_default_handlers(self):
        """Test worker has default handlers registered."""
        assert "echo" in self.worker._task_handlers
        assert "code_analysis" in self.worker._task_handlers
        assert "rag_query" in self.worker._task_handlers
        assert "web_search" in self.worker._task_handlers

    def test_register_custom_handler(self):
        """Test registering custom handler."""
        async def custom_handler(payload):
            return {"custom": True}

        self.worker.register_handler("custom", custom_handler)
        assert "custom" in self.worker._task_handlers

    @pytest.mark.asyncio
    async def test_handle_echo(self):
        """Test echo handler."""
        result = await self.worker._handle_echo({"message": "hello"})
        assert result["echo"] == {"message": "hello"}
        assert result["agent_id"] == self.worker.agent_id

    @pytest.mark.asyncio
    async def test_process_task(self):
        """Test processing a task."""
        task = TaskInfo(
            task_type="echo",
            payload={"test": "data"}
        )
        result = await self.worker.process_task(task)
        assert result["echo"] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_process_task_unknown_type(self):
        """Test processing task with unknown type."""
        task = TaskInfo(task_type="unknown_type")

        with pytest.raises(ValueError, match="No handler"):
            await self.worker.process_task(task)

    def test_worker_status_offline(self):
        """Test worker status is offline when not running."""
        assert self.worker.status == AgentStatus.OFFLINE

    def test_worker_get_info(self):
        """Test getting worker info."""
        info = self.worker.get_info()
        assert info.name == "Test Worker"
        assert info.agent_id == self.worker.agent_id
        assert info.max_concurrent_tasks == 3


class TestCoordinator:
    """Test the Coordinator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = AgentRegistry()
        self.queue = TaskQueue()
        self.coordinator = Coordinator(
            registry=self.registry,
            task_queue=self.queue,
            health_check_interval=1
        )

    def test_coordinator_initialization(self):
        """Test coordinator initializes correctly."""
        assert self.coordinator is not None
        assert self.coordinator.registry is self.registry
        assert self.coordinator.task_queue is self.queue

    def test_register_agent_via_coordinator(self):
        """Test registering agent through coordinator."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.coordinator.register_agent(reg)

        assert agent.name == "Test Agent"
        assert len(self.coordinator.list_agents()) == 1

    def test_deregister_agent_via_coordinator(self):
        """Test deregistering agent through coordinator."""
        reg = AgentRegistration(name="Test Agent")
        agent = self.coordinator.register_agent(reg)

        result = self.coordinator.deregister_agent(agent.agent_id)
        assert result is True
        assert len(self.coordinator.list_agents()) == 0

    def test_submit_task_via_coordinator(self):
        """Test submitting task through coordinator."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        assert task.task_type == "test"
        assert task.status == TaskStatus.QUEUED

    def test_get_task_via_coordinator(self):
        """Test getting task through coordinator."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        retrieved = self.coordinator.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_cancel_task_via_coordinator(self):
        """Test cancelling task through coordinator."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        result = self.coordinator.cancel_task(task.task_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_complete_task_via_coordinator(self):
        """Test completing task through coordinator."""
        # Start coordinator to have a running event loop
        await self.coordinator.start()

        try:
            # Register an agent
            reg = AgentRegistration(name="Agent")
            agent = self.coordinator.register_agent(reg)

            # Submit and start a task
            request = TaskRequest(task_type="test")
            task = self.coordinator.submit_task(request)

            # Assign to agent
            self.queue.get_next_task()
            self.queue.assign_task(task.task_id, agent.agent_id)
            self.registry.update_agent_tasks(agent.agent_id, 1)

            # Complete task
            result = self.coordinator.complete_task(task.task_id, result="done")
            assert result is not None
            assert result.status == TaskStatus.COMPLETED

            # Agent task count should be decremented
            updated = self.coordinator.get_agent(agent.agent_id)
            assert updated.current_tasks == 0
        finally:
            await self.coordinator.stop()

    def test_get_stats(self):
        """Test getting coordinator statistics."""
        self.coordinator.register_agent(AgentRegistration(name="Agent"))
        self.coordinator.submit_task(TaskRequest(task_type="test"))

        stats = self.coordinator.get_stats()
        assert "agents" in stats
        assert "tasks" in stats
        assert stats["agents"]["total_agents"] == 1
        assert stats["tasks"]["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_coordinator_start_stop(self):
        """Test starting and stopping coordinator."""
        await self.coordinator.start()
        assert self.coordinator._running is True

        await self.coordinator.stop()
        assert self.coordinator._running is False

    @pytest.mark.asyncio
    async def test_subscribe_to_task(self):
        """Test subscribing to task updates."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        queue = await self.coordinator.subscribe_to_task(task.task_id)
        assert queue is not None

        # Cleanup
        self.coordinator.unsubscribe_from_task(task.task_id, queue)


class TestRemoteAgentAPI:
    """Test the Remote Agent API endpoints using direct coordinator access."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton instances for clean tests
        import remote_agent.registry as registry_module
        import remote_agent.queue as queue_module
        import remote_agent.coordinator as coordinator_module

        registry_module._registry_instance = None
        queue_module._queue_instance = None
        coordinator_module._coordinator_instance = None

        # Create coordinator directly for unit tests (without FastAPI lifespan)
        self.registry = AgentRegistry()
        self.queue = TaskQueue()
        self.coordinator = Coordinator(registry=self.registry, task_queue=self.queue)

    def test_register_agent(self):
        """Test agent registration."""
        reg = AgentRegistration(
            name="Test Agent",
            capabilities=["code_analysis"],
            max_concurrent_tasks=5
        )
        agent = self.coordinator.register_agent(reg)

        assert agent.name == "Test Agent"
        assert "agent_id" in agent.model_dump()

    def test_list_agents(self):
        """Test listing agents."""
        self.coordinator.register_agent(AgentRegistration(name="Test Agent"))

        agents = self.coordinator.list_agents()
        assert len(agents) == 1

    def test_deregister_agent(self):
        """Test agent deregistration."""
        agent = self.coordinator.register_agent(AgentRegistration(name="Test Agent"))

        result = self.coordinator.deregister_agent(agent.agent_id)
        assert result is True

        agents = self.coordinator.list_agents()
        assert len(agents) == 0

    def test_submit_task(self):
        """Test task submission."""
        request = TaskRequest(
            task_type="echo",
            payload={"message": "hello"},
            priority=TaskPriority.NORMAL
        )
        task = self.coordinator.submit_task(request)

        assert task.task_type == "echo"
        assert task.status == TaskStatus.QUEUED

    def test_get_task(self):
        """Test getting task."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        retrieved = self.coordinator.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_get_nonexistent_task(self):
        """Test getting nonexistent task returns None."""
        result = self.coordinator.get_task("nonexistent-id")
        assert result is None

    def test_cancel_task(self):
        """Test cancelling task."""
        request = TaskRequest(task_type="test")
        task = self.coordinator.submit_task(request)

        result = self.coordinator.cancel_task(task.task_id)
        assert result is True

        cancelled = self.coordinator.get_task(task.task_id)
        assert cancelled.status == TaskStatus.CANCELLED

    def test_get_stats(self):
        """Test statistics."""
        self.coordinator.register_agent(AgentRegistration(name="Agent"))
        self.coordinator.submit_task(TaskRequest(task_type="test"))

        stats = self.coordinator.get_stats()
        assert "agents" in stats
        assert "tasks" in stats
        assert stats["agents"]["total_agents"] == 1
        assert stats["tasks"]["total_tasks"] == 1

    def test_heartbeat(self):
        """Test agent heartbeat."""
        agent = self.coordinator.register_agent(AgentRegistration(name="Test Agent"))

        heartbeat = HeartbeatRequest(
            agent_id=agent.agent_id,
            status=AgentStatus.BUSY,
            current_tasks=3
        )
        result = self.coordinator.agent_heartbeat(heartbeat)
        assert result is True

        updated = self.coordinator.get_agent(agent.agent_id)
        assert updated.status == AgentStatus.BUSY
        assert updated.current_tasks == 3


class TestRemoteAgentAPIIntegration:
    """Integration tests for Remote Agent API with FastAPI TestClient."""

    @pytest.fixture
    def client(self):
        """Create test client with lifespan."""
        from fastapi.testclient import TestClient
        from remote_agent.app import app

        # Reset singletons
        import remote_agent.registry as registry_module
        import remote_agent.queue as queue_module
        import remote_agent.coordinator as coordinator_module
        import remote_agent.app as app_module

        registry_module._registry_instance = None
        queue_module._queue_instance = None
        coordinator_module._coordinator_instance = None
        app_module.coordinator = None

        # Use TestClient with lifespan context
        with TestClient(app) as client:
            yield client

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_register_agent_endpoint(self, client):
        """Test agent registration endpoint."""
        response = client.post(
            "/agents/register",
            json={
                "name": "Test Agent",
                "capabilities": ["code_analysis"],
                "max_concurrent_tasks": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Agent"
        assert "agent_id" in data

    def test_submit_task_endpoint(self, client):
        """Test task submission endpoint."""
        response = client.post(
            "/tasks/submit",
            json={
                "task_type": "echo",
                "payload": {"message": "hello"},
                "priority": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "echo"
        assert data["status"] == "queued"

    def test_stats_endpoint(self, client):
        """Test statistics endpoint."""
        client.post("/agents/register", json={"name": "Agent"})
        client.post("/tasks/submit", json={"task_type": "test"})

        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "tasks" in data

