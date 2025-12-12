"""
Agent Worker - Processes tasks from the queue.

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .models import (
    AgentInfo, AgentStatus, AgentCapability, AgentRegistration,
    TaskInfo, TaskStatus, HeartbeatRequest
)

logger = logging.getLogger(__name__)


class AgentWorker:
    """
    Remote agent worker that processes tasks.
    
    Can run standalone or connect to a coordinator.
    """
    
    def __init__(
        self,
        agent_id: str = None,
        name: str = "Remote Agent",
        capabilities: List[str] = None,
        max_concurrent_tasks: int = 5,
        heartbeat_interval: int = 10,
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.capabilities = capabilities or [
            AgentCapability.CODE_ANALYSIS.value,
            AgentCapability.RAG_QUERY.value,
            AgentCapability.WEB_SEARCH.value,
        ]
        self.max_concurrent_tasks = max_concurrent_tasks
        self.heartbeat_interval = heartbeat_interval
        
        self._status = AgentStatus.OFFLINE
        self._current_tasks: Dict[str, asyncio.Task] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._coordinator_url: Optional[str] = None
        
        # Register default task handlers
        self._register_default_handlers()
        
        logger.info(f"Agent worker created: {self.agent_id}")
    
    def _register_default_handlers(self):
        """Register default task handlers."""
        self.register_handler("echo", self._handle_echo)
        self.register_handler("code_analysis", self._handle_code_analysis)
        self.register_handler("rag_query", self._handle_rag_query)
        self.register_handler("web_search", self._handle_web_search)
        self.register_handler("file_processing", self._handle_file_processing)
    
    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a handler for a task type."""
        self._task_handlers[task_type] = handler
        logger.debug(f"Registered handler for task type: {task_type}")
    
    async def _handle_echo(self, payload: Dict[str, Any]) -> Any:
        """Echo handler for testing."""
        return {"echo": payload, "agent_id": self.agent_id}
    
    async def _handle_code_analysis(self, payload: Dict[str, Any]) -> Any:
        """Handle code analysis tasks."""
        # Import here to avoid circular dependencies
        try:
            from services.preprocessor.chunkers import get_chunker
            
            code = payload.get("code", "")
            language = payload.get("language", "python")
            
            chunker = get_chunker(language)
            chunks = chunker.chunk(code)
            
            return {
                "chunks": len(chunks),
                "language": language,
                "analysis": "Code analyzed successfully",
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_rag_query(self, payload: Dict[str, Any]) -> Any:
        """Handle RAG query tasks."""
        try:
            from services.api_gateway.rag_pipeline import RAGPipeline
            
            question = payload.get("question", "")
            pipeline = RAGPipeline()
            result = await pipeline.query(question)
            
            return {"answer": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_web_search(self, payload: Dict[str, Any]) -> Any:
        """Handle web search tasks."""
        try:
            from services.api_gateway.search_adapter import SearchAdapter
            
            query = payload.get("query", "")
            num_results = payload.get("num_results", 5)
            
            adapter = SearchAdapter()
            results = await adapter.search(query, num_results=num_results)
            
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_file_processing(self, payload: Dict[str, Any]) -> Any:
        """Handle file processing tasks."""
        try:
            from services.connector.filesystem import FileSystemConnector
            
            path = payload.get("path", "")
            connector = FileSystemConnector()
            files = connector.list_files(path)
            
            return {"files": files}
        except Exception as e:
            return {"error": str(e)}
    
    async def process_task(self, task: TaskInfo) -> Any:
        """Process a single task."""
        handler = self._task_handlers.get(task.task_type)
        if not handler:
            raise ValueError(f"No handler for task type: {task.task_type}")
        
        logger.info(f"Processing task: {task.task_id} (type={task.task_type})")
        
        try:
            result = await asyncio.wait_for(
                handler(task.payload),
                timeout=task.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task.task_id} timed out after {task.timeout_seconds}s")
    
    @property
    def status(self) -> AgentStatus:
        """Get current agent status."""
        if not self._running:
            return AgentStatus.OFFLINE
        if len(self._current_tasks) >= self.max_concurrent_tasks:
            return AgentStatus.BUSY
        return AgentStatus.ONLINE
    
    @property
    def current_task_count(self) -> int:
        """Get current number of running tasks."""
        return len(self._current_tasks)
    
    def get_info(self) -> AgentInfo:
        """Get agent information."""
        return AgentInfo(
            agent_id=self.agent_id,
            name=self.name,
            capabilities=self.capabilities,
            status=self.status,
            current_tasks=self.current_task_count,
            max_concurrent_tasks=self.max_concurrent_tasks,
        )

