"""
Data models for the Remote Agent system.

Copyright (c) 2025 ContextForge
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class AgentCapability(str, Enum):
    """Agent capability types."""
    CODE_ANALYSIS = "code_analysis"
    WEB_SEARCH = "web_search"
    RAG_QUERY = "rag_query"
    FILE_PROCESSING = "file_processing"
    TERMINAL_EXECUTION = "terminal_execution"
    LLM_GENERATION = "llm_generation"


class AgentInfo(BaseModel):
    """Information about a registered agent."""
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Remote Agent"
    endpoint: str = ""
    capabilities: List[str] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.ONLINE
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    current_tasks: int = 0
    max_concurrent_tasks: int = 5
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    """Request to submit a new task."""
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    required_capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskInfo(BaseModel):
    """Information about a task."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    timeout_seconds: int = 300
    required_capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Result of a completed task."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    agent_id: Optional[str] = None


class HeartbeatRequest(BaseModel):
    """Agent heartbeat request."""
    agent_id: str
    status: AgentStatus = AgentStatus.ONLINE
    current_tasks: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentRegistration(BaseModel):
    """Agent registration request."""
    name: str = "Remote Agent"
    endpoint: str = ""
    capabilities: List[str] = Field(default_factory=list)
    max_concurrent_tasks: int = 5
    metadata: Dict[str, Any] = Field(default_factory=dict)

