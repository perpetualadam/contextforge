"""
Remote Agent Service - FastAPI application for running agent workers.

This service can run as a standalone agent worker that connects to a coordinator,
or as a coordinator that manages multiple agents.

Copyright (c) 2025 ContextForge
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import (
    AgentInfo, AgentStatus, AgentRegistration, HeartbeatRequest,
    TaskInfo, TaskRequest, TaskResult, TaskStatus
)
from .coordinator import Coordinator, get_coordinator
from .worker import AgentWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
COORDINATOR_MODE = os.getenv("COORDINATOR_MODE", "true").lower() == "true"
WORKER_MODE = os.getenv("WORKER_MODE", "false").lower() == "true"
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8011")
AGENT_NAME = os.getenv("AGENT_NAME", "Remote Agent")
AGENT_CAPABILITIES = os.getenv("AGENT_CAPABILITIES", "code_analysis,rag_query,web_search").split(",")

# Global instances
coordinator: Optional[Coordinator] = None
worker: Optional[AgentWorker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global coordinator, worker
    
    if COORDINATOR_MODE:
        coordinator = get_coordinator()
        await coordinator.start()
        logger.info("Coordinator started")
    
    if WORKER_MODE:
        worker = AgentWorker(
            name=AGENT_NAME,
            capabilities=AGENT_CAPABILITIES,
        )
        # TODO: Register with coordinator and start processing
        logger.info(f"Worker started: {worker.agent_id}")
    
    yield
    
    if coordinator:
        await coordinator.stop()
        logger.info("Coordinator stopped")


# Create FastAPI app
app = FastAPI(
    title="ContextForge Remote Agent Service",
    description="Distributed agent service for ContextForge",
    version="0.1.0",
    lifespan=lifespan,
)


# ============== Health Endpoints ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "coordinator_mode": COORDINATOR_MODE,
        "worker_mode": WORKER_MODE,
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics."""
    if coordinator:
        return coordinator.get_stats()
    return {"error": "Coordinator not running"}


# ============== Agent Endpoints ==============

@app.post("/agents/register", response_model=AgentInfo)
async def register_agent(registration: AgentRegistration):
    """Register a new remote agent."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    return coordinator.register_agent(registration)


@app.delete("/agents/{agent_id}")
async def deregister_agent(agent_id: str):
    """Deregister an agent."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    if not coordinator.deregister_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deregistered", "agent_id": agent_id}


@app.get("/agents")
async def list_agents(status: Optional[AgentStatus] = None):
    """List all registered agents."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    return coordinator.list_agents(status)


@app.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, request: HeartbeatRequest):
    """Process agent heartbeat."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    if request.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")
    if not coordinator.agent_heartbeat(request):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok"}


# ============== Task Endpoints ==============

@app.post("/tasks/submit", response_model=TaskInfo)
async def submit_task(request: TaskRequest):
    """Submit a new task for processing."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    try:
        return coordinator.submit_task(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str):
    """Get task details."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    task = coordinator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """Get task result."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    result = coordinator.get_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or running task."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not running")
    if not coordinator.cancel_task(task_id):
        raise HTTPException(status_code=400, detail="Cannot cancel task")
    return {"status": "cancelled", "task_id": task_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8011"))
    uvicorn.run(app, host="0.0.0.0", port=port)

