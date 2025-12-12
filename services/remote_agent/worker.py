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
        self.register_handler("terminal_execution", self._handle_terminal_execution)
        self.register_handler("document_ingestion", self._handle_document_ingestion)
        self.register_handler("vector_search", self._handle_vector_search)
        self.register_handler("llm_generation", self._handle_llm_generation)
        self.register_handler("batch_processing", self._handle_batch_processing)
    
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

    async def _handle_terminal_execution(self, payload: Dict[str, Any]) -> Any:
        """
        Handle terminal command execution tasks.

        Payload:
            command: str - The command to execute
            working_directory: str (optional) - Working directory
            timeout: int (optional) - Timeout in seconds (default: 30)
            environment: dict (optional) - Environment variables
        """
        import asyncio
        import subprocess
        import shlex
        import os

        command = payload.get("command", "")
        working_directory = payload.get("working_directory", os.getcwd())
        timeout = payload.get("timeout", 30)
        environment = payload.get("environment", {})

        if not command:
            return {"error": "No command provided"}

        # Security: Only allow whitelisted commands
        allowed_commands = {
            'npm', 'yarn', 'pnpm', 'node', 'python', 'python3', 'pip', 'pip3',
            'poetry', 'cargo', 'go', 'make', 'git', 'ls', 'dir', 'cat', 'type',
            'echo', 'pwd', 'cd', 'mkdir', 'touch', 'grep', 'find', 'head', 'tail',
            'pytest', 'jest', 'mocha', 'vitest', 'tsc', 'eslint', 'prettier',
        }

        try:
            # Parse command to get base command
            if os.name == 'nt':  # Windows
                args = command.split()
            else:
                args = shlex.split(command)

            if not args:
                return {"error": "Empty command"}

            base_command = args[0].split('/')[-1].split('\\')[-1]
            if base_command not in allowed_commands:
                return {"error": f"Command '{base_command}' is not allowed"}

            # Prepare environment
            env = os.environ.copy()
            env.update(environment)

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "error": f"Command timed out after {timeout}s",
                    "exit_code": -1,
                }

            return {
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "exit_code": process.returncode,
                "success": process.returncode == 0,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _handle_document_ingestion(self, payload: Dict[str, Any]) -> Any:
        """
        Handle document ingestion tasks.

        Payload:
            path: str - Path to file or directory to ingest
            recursive: bool (optional) - Recursively process directories
            file_types: list (optional) - List of file extensions to process
        """
        try:
            from services.connector.filesystem import FileSystemConnector
            from services.preprocessor.chunkers import get_chunker

            path = payload.get("path", "")
            recursive = payload.get("recursive", True)
            file_types = payload.get("file_types", [".py", ".js", ".ts", ".md"])

            if not path:
                return {"error": "No path provided"}

            connector = FileSystemConnector()
            files = connector.list_files(path, recursive=recursive)

            # Filter by file types
            filtered_files = [
                f for f in files
                if any(f.endswith(ext) for ext in file_types)
            ]

            processed = []
            errors = []

            for file_path in filtered_files:
                try:
                    content = connector.read_file(file_path)
                    ext = "." + file_path.split(".")[-1] if "." in file_path else ""
                    chunker = get_chunker(ext)
                    chunks = chunker.chunk(content)
                    processed.append({
                        "file": file_path,
                        "chunks": len(chunks),
                    })
                except Exception as e:
                    errors.append({"file": file_path, "error": str(e)})

            return {
                "processed_files": len(processed),
                "total_chunks": sum(p["chunks"] for p in processed),
                "files": processed,
                "errors": errors,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _handle_vector_search(self, payload: Dict[str, Any]) -> Any:
        """
        Handle vector similarity search tasks.

        Payload:
            query: str - Search query
            top_k: int (optional) - Number of results (default: 5)
            threshold: float (optional) - Similarity threshold (default: 0.7)
        """
        try:
            # Try to use vector index if available
            try:
                from services.vector_index.index import VectorIndex

                query = payload.get("query", "")
                top_k = payload.get("top_k", 5)
                threshold = payload.get("threshold", 0.7)

                if not query:
                    return {"error": "No query provided"}

                index = VectorIndex()
                results = index.search(query, top_k=top_k, threshold=threshold)

                return {
                    "query": query,
                    "results": results,
                    "count": len(results),
                }
            except ImportError:
                return {
                    "error": "Vector index not available (sentence-transformers not installed)",
                    "fallback": "Use web_search or rag_query instead",
                }

        except Exception as e:
            return {"error": str(e)}

    async def _handle_llm_generation(self, payload: Dict[str, Any]) -> Any:
        """
        Handle LLM text generation tasks.

        Payload:
            prompt: str - The prompt to generate from
            max_tokens: int (optional) - Maximum tokens to generate
            temperature: float (optional) - Sampling temperature
            adapter: str (optional) - Specific adapter to use
        """
        try:
            from services.api_gateway.llm_adapter import LLMClient

            prompt = payload.get("prompt", "")
            max_tokens = payload.get("max_tokens", 1024)
            temperature = payload.get("temperature", 0.7)
            adapter = payload.get("adapter")

            if not prompt:
                return {"error": "No prompt provided"}

            client = LLMClient()

            if adapter:
                # Use specific adapter
                response = await client.generate(
                    prompt,
                    adapter_name=adapter,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            else:
                # Use default fallback chain
                response = await client.generate(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

            return {
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "response": response,
                "adapter_used": adapter or "auto",
            }

        except Exception as e:
            return {"error": str(e)}

    async def _handle_batch_processing(self, payload: Dict[str, Any]) -> Any:
        """
        Handle batch processing of multiple tasks.

        Payload:
            tasks: list - List of task definitions
                Each task: {task_type: str, payload: dict}
            parallel: bool (optional) - Run tasks in parallel (default: True)
            stop_on_error: bool (optional) - Stop on first error (default: False)
        """
        tasks = payload.get("tasks", [])
        parallel = payload.get("parallel", True)
        stop_on_error = payload.get("stop_on_error", False)

        if not tasks:
            return {"error": "No tasks provided"}

        results = []
        errors = []

        async def process_single(task_def: Dict[str, Any], index: int):
            task_type = task_def.get("task_type", "")
            task_payload = task_def.get("payload", {})

            handler = self._task_handlers.get(task_type)
            if not handler:
                return {
                    "index": index,
                    "task_type": task_type,
                    "error": f"Unknown task type: {task_type}",
                }

            try:
                result = await handler(task_payload)
                return {
                    "index": index,
                    "task_type": task_type,
                    "result": result,
                    "success": "error" not in result,
                }
            except Exception as e:
                return {
                    "index": index,
                    "task_type": task_type,
                    "error": str(e),
                }

        if parallel:
            # Run all tasks in parallel
            task_coroutines = [
                process_single(task_def, i)
                for i, task_def in enumerate(tasks)
            ]
            all_results = await asyncio.gather(*task_coroutines, return_exceptions=True)

            for result in all_results:
                if isinstance(result, Exception):
                    errors.append({"error": str(result)})
                elif "error" in result:
                    errors.append(result)
                else:
                    results.append(result)
        else:
            # Run tasks sequentially
            for i, task_def in enumerate(tasks):
                result = await process_single(task_def, i)

                if "error" in result:
                    errors.append(result)
                    if stop_on_error:
                        break
                else:
                    results.append(result)

        return {
            "total_tasks": len(tasks),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

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

