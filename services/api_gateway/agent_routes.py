"""
Remote Agent API Routes.

Provides REST API endpoints for agent management and task distribution.

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# Import remote agent components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_agent.models import (
    AgentInfo, AgentStatus, AgentRegistration, HeartbeatRequest,
    TaskInfo, TaskRequest, TaskResult, TaskStatus
)
from remote_agent.coordinator import get_coordinator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/agents", tags=["Remote Agents"])
task_router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ============== Agent Endpoints ==============

@router.post("/register", response_model=AgentInfo)
async def register_agent(registration: AgentRegistration):
    """Register a new remote agent."""
    coordinator = get_coordinator()
    agent = coordinator.register_agent(registration)
    logger.info(f"Agent registered: {agent.agent_id}")
    return agent


@router.delete("/{agent_id}")
async def deregister_agent(agent_id: str):
    """Deregister an agent."""
    coordinator = get_coordinator()
    if not coordinator.deregister_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deregistered", "agent_id": agent_id}


@router.get("", response_model=List[AgentInfo])
async def list_agents(status: Optional[AgentStatus] = None):
    """List all registered agents."""
    coordinator = get_coordinator()
    return coordinator.list_agents(status)


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """Get agent details."""
    coordinator = get_coordinator()
    agent = coordinator.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, request: HeartbeatRequest):
    """Process agent heartbeat."""
    if request.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")
    
    coordinator = get_coordinator()
    if not coordinator.agent_heartbeat(request):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok"}


@router.get("/health", response_model=dict)
async def agents_health():
    """Get health status of all agents."""
    coordinator = get_coordinator()
    stats = coordinator.get_stats()
    return stats["agents"]


# ============== Task Endpoints ==============

@task_router.post("/submit", response_model=TaskInfo)
async def submit_task(request: TaskRequest):
    """Submit a new task for processing."""
    coordinator = get_coordinator()
    try:
        task = coordinator.submit_task(request)
        logger.info(f"Task submitted: {task.task_id}")
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@task_router.get("/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str):
    """Get task details."""
    coordinator = get_coordinator()
    task = coordinator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@task_router.get("/{task_id}/result", response_model=TaskResult)
async def get_task_result(task_id: str):
    """Get task result."""
    coordinator = get_coordinator()
    result = coordinator.get_result(task_id)
    if not result:
        task = coordinator.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            raise HTTPException(status_code=202, detail="Task not yet completed")
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@task_router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or running task."""
    coordinator = get_coordinator()
    if not coordinator.cancel_task(task_id):
        raise HTTPException(status_code=400, detail="Cannot cancel task")
    return {"status": "cancelled", "task_id": task_id}


@task_router.get("", response_model=List[TaskInfo])
async def list_tasks(status: Optional[TaskStatus] = None, limit: int = 100):
    """List tasks."""
    coordinator = get_coordinator()
    return coordinator.list_tasks(status, limit)


@task_router.get("/stats", response_model=dict)
async def task_stats():
    """Get task statistics."""
    coordinator = get_coordinator()
    stats = coordinator.get_stats()
    return stats["tasks"]


# ============== WebSocket Endpoints ==============

ws_router = APIRouter(tags=["WebSocket"])


@ws_router.websocket("/ws/tasks/{task_id}")
async def task_stream(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task updates."""
    await websocket.accept()

    coordinator = get_coordinator()
    task = coordinator.get_task(task_id)

    if not task:
        await websocket.send_json({"error": "Task not found"})
        await websocket.close()
        return

    # Send initial state
    await websocket.send_json(task.model_dump(mode="json"))

    # If already completed, close
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        result = coordinator.get_result(task_id)
        if result:
            await websocket.send_json({"result": result.model_dump(mode="json")})
        await websocket.close()
        return

    # Subscribe to updates
    queue = await coordinator.subscribe_to_task(task_id)

    try:
        while True:
            try:
                # Wait for updates with timeout
                updated_task = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(updated_task.model_dump(mode="json"))

                # Check if task is done
                if updated_task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    result = coordinator.get_result(task_id)
                    if result:
                        await websocket.send_json({"result": result.model_dump(mode="json")})
                    break
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"heartbeat": True})
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    finally:
        coordinator.unsubscribe_from_task(task_id, queue)
        await websocket.close()


@ws_router.websocket("/ws/agents")
async def agents_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time agent status updates."""
    await websocket.accept()

    coordinator = get_coordinator()

    try:
        while True:
            # Send current agent status
            agents = coordinator.list_agents()
            await websocket.send_json({
                "agents": [a.model_dump(mode="json") for a in agents],
                "stats": coordinator.get_stats()["agents"]
            })

            # Wait before next update
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        logger.info("Agent stream WebSocket disconnected")
    finally:
        await websocket.close()

