"""
ContextForge API Gateway - Main FastAPI application.
Provides unified API for ingestion, querying, and management.
"""

# Load environment variables from .env file first
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import logging
import hashlib
import secrets
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import requests
import structlog
import base64
import io
from pathlib import Path
from pypdf import PdfReader
from docx import Document
from PIL import Image
import uuid

# Add parent directory to path for services imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag import RAGPipeline
from llm_client import LLMClient
from search_adapter import SearchAdapter

# Import unified configuration
try:
    from services.config import get_config
    _config = get_config()
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    _config = None

# Import remote agent routes
try:
    from agent_routes import router as agent_router, task_router, ws_router
    REMOTE_AGENTS_ENABLED = True
except ImportError:
    REMOTE_AGENTS_ENABLED = False

# Import security modules
try:
    from services.security import (
        SecurityHeadersMiddleware,
        RequestSizeLimitMiddleware,
        AuditLoggingMiddleware,
        CSRFMiddleware,
        get_jwt_manager,
        get_rate_limiter,
        get_audit_logger
    )
    from auth_routes import router as auth_router
    SECURITY_MODULES_ENABLED = True
except ImportError:
    SECURITY_MODULES_ENABLED = False
    logger.warning("Security modules not available - running without enhanced security")

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Service URLs - Use unified config if available, fallback to env vars
if CONFIG_AVAILABLE and _config:
    VECTOR_INDEX_URL = _config.services.vector_index
    PREPROCESSOR_URL = _config.services.preprocessor
    CONNECTOR_URL = _config.services.connector
    WEB_FETCHER_URL = _config.services.web_fetcher
    TERMINAL_EXECUTOR_URL = _config.services.terminal_executor
else:
    VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://vector-index:8001")
    PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://preprocessor:8003")
    CONNECTOR_URL = os.getenv("CONNECTOR_URL", "http://connector:8002")
    WEB_FETCHER_URL = os.getenv("WEB_FETCHER_URL", "http://web-fetcher:8004")
    TERMINAL_EXECUTOR_URL = os.getenv("TERMINAL_EXECUTOR_URL", "http://terminal-executor:8006")

# CORS Configuration - Security hardened
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Content-Type", "Authorization"]

# Security Configuration - Use unified config if available
if CONFIG_AVAILABLE and _config:
    RATE_LIMIT_REQUESTS = _config.security.rate_limit_requests if hasattr(_config, 'security') else 100
    RATE_LIMIT_WINDOW = _config.security.rate_limit_window if hasattr(_config, 'security') else 60
else:
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

API_KEY_ENABLED = os.getenv("API_KEY_ENABLED", "false").lower() == "true"
API_KEYS = set(os.getenv("API_KEYS", "").split(",")) if os.getenv("API_KEYS") else set()
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))  # max file upload size

# Security utilities
security = HTTPBearer(auto_error=False)


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if a request from client_id is allowed."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]

        # Check if under limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # Record this request
        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        now = time.time()
        window_start = now - self.window_seconds
        current_requests = len([
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ])
        return max(0, self.max_requests - current_requests)


# Initialize rate limiter
rate_limiter = RateLimiter()


def get_client_id(request: Request) -> str:
    """Get a unique client identifier from request."""
    # Use X-Forwarded-For if behind proxy, otherwise use client host
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    """Verify API key if authentication is enabled."""
    if not API_KEY_ENABLED:
        return None

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide Authorization: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Hash the provided key for comparison (if keys are stored hashed)
    provided_key = credentials.credentials

    if provided_key not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return provided_key


async def check_rate_limit(request: Request) -> None:
    """Check rate limit for the request."""
    if not RATE_LIMIT_ENABLED:
        return

    client_id = get_client_id(request)

    if not rate_limiter.is_allowed(client_id):
        remaining = rate_limiter.get_remaining(client_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW} seconds.",
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + RATE_LIMIT_WINDOW)
            }
        )


# Initialize Event Bus (Phase 1 integration)
from services.core.event_bus import get_event_bus, Event, EventType
event_bus = get_event_bus()

# Initialize RAG pipeline
rag_pipeline = RAGPipeline()


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    from services.startup_validator import validate_startup
    if not validate_startup():
        logger.error("Startup validation failed - some checks did not pass")
        logger.warning("Continuing with startup despite validation warnings")

    # Publish SERVICE_STARTED event
    await event_bus.publish(Event(
        type=EventType.SERVICE_STARTED,
        payload={"service": "api_gateway"},
        source="api_gateway"
    ))
    logger.info("API Gateway started and event published")

    yield

    # Shutdown (if needed in the future)
    logger.info("API Gateway shutting down")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="ContextForge API Gateway",
    description="Local-first context engine and augment/assistant pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware - Security hardened
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Enable for secure cookie-based auth
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS + ["X-CSRF-Token"],  # Add CSRF token header
)

# Add security middleware if available
if SECURITY_MODULES_ENABLED:
    # Add security headers (CSP, HSTS, etc.)
    app.add_middleware(SecurityHeadersMiddleware)

    # Add request size limits
    app.add_middleware(RequestSizeLimitMiddleware)

    # Add audit logging
    app.add_middleware(AuditLoggingMiddleware)

    # Add CSRF protection
    app.add_middleware(CSRFMiddleware, exempt_paths=[
        "/health",
        "/docs",
        "/openapi.json",
        "/auth/login",
        "/auth/register"
    ])

    logger.info("Security middleware enabled")

# Register authentication routes if available
if SECURITY_MODULES_ENABLED:
    app.include_router(auth_router)
    logger.info("Authentication routes registered")

# Register remote agent routes if available
if REMOTE_AGENTS_ENABLED:
    app.include_router(agent_router)
    app.include_router(task_router)
    app.include_router(ws_router)


# Pydantic models with input validation
class IngestRequest(BaseModel):
    path: str = Field(..., max_length=1024)
    recursive: bool = True
    file_patterns: Optional[List[str]] = Field(None, max_length=50)
    exclude_patterns: Optional[List[str]] = Field(None, max_length=50)

    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        # Prevent path traversal
        if '..' in v:
            raise ValueError("Path traversal not allowed")
        return v


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    max_tokens: int = Field(512, ge=1, le=4096)
    enable_web_search: Optional[bool] = None
    top_k: int = Field(10, ge=1, le=100)
    auto_terminal_mode: bool = False
    auto_terminal_timeout: int = Field(30, ge=1, le=300)
    auto_terminal_whitelist: Optional[List[str]] = Field(None, max_length=50)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    provider: Optional[str] = Field(None, max_length=50)
    num_results: int = Field(5, ge=1, le=50)
    fetch_content: bool = False


class LLMRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=100000)
    model: Optional[str] = Field(None, max_length=100)
    max_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    provider: Optional[str] = Field(None, max_length=50, description="Specific LLM provider to use (e.g., 'openai', 'anthropic', 'ollama')")


class TerminalRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=4096)
    working_directory: Optional[str] = Field(None, max_length=1024)
    timeout: int = Field(30, ge=1, le=300)
    environment: Optional[Dict[str, str]] = None
    stream: bool = False

    @field_validator('working_directory')
    @classmethod
    def validate_working_directory(cls, v):
        if v and '..' in v:
            raise ValueError("Path traversal not allowed")
        return v


class CommandSuggestionRequest(BaseModel):
    task_description: str = Field(..., min_length=1, max_length=5000)
    context: Optional[str] = Field(None, max_length=10000)
    working_directory: Optional[str] = Field(None, max_length=1024)


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    max_tokens: int = 1024
    enable_web_search: bool = False
    enable_context: bool = True
    provider: Optional[str] = Field(None, max_length=50, description="Specific LLM provider to use (e.g., 'openai', 'anthropic', 'ollama')")

class CommitMessageRequest(BaseModel):
    diff: str
    staged_files: List[str]
    branch: str
    recent_commits: List[str]

class CommitMessageResponse(BaseModel):
    message: str
    description: Optional[str] = None
    confidence: float

class FileUploadResponse(BaseModel):
    id: str
    name: str
    type: str
    size: int
    data: str  # base64 encoded
    extractedText: Optional[str] = None
    analysisResult: Optional[str] = None

class FileAnalysisRequest(BaseModel):
    fileId: str
    fileName: str
    fileType: str
    data: str  # base64 encoded


class PromptEnhancementRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    style: str = "professional"


class PromptEnhancementResponse(BaseModel):
    original: str
    enhanced: str
    suggestions: List[str]
    improvements: List[str]


class OrchestrationRequest(BaseModel):
    """Request for production orchestration."""
    repo_path: str = Field(..., max_length=1024)
    mode: str = Field("auto", pattern="^(auto|online|offline)$")
    task: str = Field("full_analysis", max_length=100)
    output_format: str = Field("markdown", pattern="^(markdown|json|xml)$")

    @field_validator('repo_path')
    @classmethod
    def validate_repo_path(cls, v):
        if '..' in v:
            raise ValueError("Path traversal not allowed")
        return v


# Health check endpoint (no auth/rate limit for health checks)
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return rag_pipeline.health_check()


@app.get("/offline/status")
async def offline_status():
    """
    Get offline mode status and capabilities.

    Returns information about:
    - Internet connectivity
    - Cloud LLM availability
    - Local LLM backends (Ollama, LM Studio)
    - Recommended actions
    """
    from services.core.offline_manager import get_offline_manager

    manager = get_offline_manager()
    return manager.to_dict()


@app.get("/security/status")
async def security_status():
    """
    Get security status and statistics.

    Returns information about:
    - Command sandbox statistics
    - Prompt guard statistics
    - Recent security events
    - Risk score and recommendations
    """
    from services.core.security_manager import get_security_manager

    manager = get_security_manager()
    return manager.get_security_status()


@app.get("/security/report")
async def security_report():
    """
    Get comprehensive security report.

    Returns detailed security analysis including:
    - Full security status
    - Risk score (0-100)
    - Critical and warning events
    - Security recommendations
    """
    from services.core.security_manager import get_security_manager

    manager = get_security_manager()
    return manager.get_security_report()


# Ingestion endpoints
@app.post("/ingest")
async def ingest_repository(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Ingest a repository or directory for indexing."""
    # Check rate limit
    await check_rate_limit(http_request)

    # Generate trace ID for event correlation
    trace_id = str(uuid.uuid4())

    try:
        # Publish INDEX_STARTED event
        await event_bus.publish(Event(
            type=EventType.INDEX_STARTED,
            payload={"path": request.path, "recursive": request.recursive},
            source="api_gateway",
            trace_id=trace_id
        ))

        logger.info("Starting repository ingestion", path=request.path, trace_id=trace_id)

        # Step 1: Connect to repository
        connector_response = requests.post(
            f"{CONNECTOR_URL}/connect",
            json={
                "path": request.path,
                "recursive": request.recursive,
                "file_patterns": request.file_patterns,
                "exclude_patterns": request.exclude_patterns
            },
            timeout=30
        )
        connector_response.raise_for_status()
        files_data = connector_response.json()
        
        logger.info("Repository connected", num_files=len(files_data.get("files", [])))
        
        # Step 2: Preprocess files
        preprocessor_response = requests.post(
            f"{PREPROCESSOR_URL}/process",
            json={"files": files_data["files"]},
            timeout=60
        )
        preprocessor_response.raise_for_status()
        chunks_data = preprocessor_response.json()
        
        logger.info("Files preprocessed", num_chunks=len(chunks_data.get("chunks", [])))
        
        # Step 3: Index chunks
        index_response = requests.post(
            f"{VECTOR_INDEX_URL}/index/insert",
            json={"chunks": chunks_data["chunks"]},
            timeout=120
        )
        index_response.raise_for_status()
        index_data = index_response.json()
        
        logger.info("Chunks indexed", indexed_count=index_data.get("indexed_count", 0))

        # Publish INDEX_COMPLETED event
        stats = {
            "files_processed": len(files_data.get("files", [])),
            "chunks_created": len(chunks_data.get("chunks", [])),
            "chunks_indexed": index_data.get("indexed_count", 0)
        }
        await event_bus.publish(Event(
            type=EventType.INDEX_COMPLETED,
            payload={"path": request.path, "stats": stats},
            source="api_gateway",
            trace_id=trace_id
        ))

        return {
            "status": "success",
            "message": "Repository ingested successfully",
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }

    except requests.RequestException as e:
        # Publish INDEX_FAILED event
        await event_bus.publish(Event(
            type=EventType.INDEX_FAILED,
            payload={"path": request.path, "error": str(e)},
            source="api_gateway",
            trace_id=trace_id
        ))
        logger.error("Service request failed during ingestion", error=str(e), trace_id=trace_id)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        # Publish INDEX_FAILED event
        await event_bus.publish(Event(
            type=EventType.INDEX_FAILED,
            payload={"path": request.path, "error": str(e)},
            source="api_gateway",
            trace_id=trace_id
        ))
        logger.error("Ingestion failed", error=str(e), trace_id=trace_id)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@app.get("/ingest/status")
async def get_ingestion_status():
    """Get status of ingested repositories."""
    try:
        response = requests.get(f"{VECTOR_INDEX_URL}/index/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get ingestion status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


# Production Orchestration endpoint
@app.post("/orchestrate")
async def run_orchestration(
    request: OrchestrationRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Run production orchestration on a repository.

    This endpoint provides multi-agent analysis with automatic
    LLM routing (cloud/local) based on connectivity.

    Returns structured analysis in the requested format.
    """
    await check_rate_limit(http_request)

    # Generate trace ID for event correlation
    trace_id = str(uuid.uuid4())

    try:
        # Publish AGENT_STARTED event
        await event_bus.publish(Event(
            type=EventType.AGENT_STARTED,
            payload={
                "repo_path": request.repo_path,
                "mode": request.mode,
                "task": request.task
            },
            source="api_gateway",
            trace_id=trace_id
        ))

        logger.info(
            "Starting orchestration",
            repo_path=request.repo_path,
            mode=request.mode,
            task=request.task,
            trace_id=trace_id
        )

        # Import and run orchestration
        from services.core import production_run

        result = production_run(
            repo_path=request.repo_path,
            mode=request.mode,
            task=request.task,
            output_format=request.output_format
        )

        # Publish AGENT_COMPLETED event
        await event_bus.publish(Event(
            type=EventType.AGENT_COMPLETED,
            payload={
                "repo_path": request.repo_path,
                "success": result.get("success"),
                "duration_ms": result.get("duration_ms")
            },
            source="api_gateway",
            trace_id=trace_id
        ))

        logger.info(
            "Orchestration completed",
            success=result.get("success"),
            duration_ms=result.get("duration_ms"),
            offline_mode=result.get("offline_mode"),
            trace_id=trace_id
        )

        return result

    except Exception as e:
        logger.error("Orchestration failed", error=str(e), trace_id=trace_id)
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {e}")


@app.get("/orchestrate/status")
async def get_orchestration_status():
    """Get current LLM routing status and connectivity."""
    try:
        from services.core import check_internet, LLMRouter

        is_online = check_internet()
        router = LLMRouter(mode="auto")

        return {
            "internet_available": is_online,
            "current_mode": "online" if not router.offline_mode else "offline",
            "backends": {
                "cloud": is_online,
                "ollama": _check_local_llm("ollama"),
                "lm_studio": _check_local_llm("lm_studio")
            }
        }
    except Exception as e:
        logger.error("Failed to get orchestration status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


def _check_local_llm(backend: str) -> bool:
    """Check if local LLM backend is available."""
    import requests as req
    try:
        if backend == "ollama":
            resp = req.get("http://localhost:11434/api/tags", timeout=2)
            return resp.status_code == 200
        elif backend == "lm_studio":
            resp = req.get("http://localhost:1234/v1/models", timeout=2)
            return resp.status_code == 200
    except Exception:
        pass
    return False


# Agent Status endpoints
@app.get("/agents/status")
async def get_agent_status():
    """
    Get status of all registered agents.

    Returns information about:
    - Local vs remote agents
    - Agent capabilities
    - Current LLM mode
    """
    try:
        from services.core import get_enhanced_orchestrator

        orchestrator = get_enhanced_orchestrator()
        return orchestrator.get_agent_status()
    except Exception as e:
        logger.error("Failed to get agent status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {e}")


@app.get("/agents/list")
async def list_all_agents():
    """List all registered agents with their details."""
    try:
        from services.core import list_agents

        return {
            "agents": list_agents(),
            "total": len(list_agents())
        }
    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {e}")


@app.post("/agents/pipeline")
async def run_pipeline(
    request: OrchestrationRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Run the enhanced agent pipeline.

    This uses the new EnhancedOrchestrator with:
    - Incremental code indexing
    - Multi-agent coordination
    - Local/remote agent routing
    """
    await check_rate_limit(http_request)

    try:
        from services.core import run_agent_pipeline
        import asyncio

        logger.info(
            "Starting agent pipeline",
            repo_path=request.repo_path,
            mode=request.mode,
            task=request.task
        )

        result = await run_agent_pipeline(
            repo_path=request.repo_path,
            mode=request.mode,
            task=request.task
        )

        logger.info(
            "Pipeline completed",
            success=result.get("success"),
            duration_ms=result.get("duration_ms"),
            agents_executed=len(result.get("agents_executed", []))
        )

        return result

    except Exception as e:
        logger.error("Pipeline failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")


@app.get("/code-index/stats")
async def get_code_index_stats():
    """Get code index statistics (symbol-based indexing)."""
    try:
        from services.core import get_code_index

        index = get_code_index()
        return index.get_stats()
    except Exception as e:
        logger.error("Failed to get code index stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get code index stats: {e}")


@app.post("/code-index/search")
async def search_code_index(query: str, top_k: int = 10):
    """Search the code index for symbols and code fragments."""
    try:
        from services.core import get_code_index

        index = get_code_index()
        results = index.search(query, top_k=top_k)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error("Code index search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Code index search failed: {e}")


# Query endpoints
@app.post("/query")
async def query_context(
    request: QueryRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Query the context engine for an answer."""
    # Check rate limit
    await check_rate_limit(http_request)

    # Generate trace ID for event correlation
    trace_id = str(uuid.uuid4())

    try:
        # Publish QUERY_RECEIVED event
        await event_bus.publish(Event(
            type=EventType.QUERY_RECEIVED,
            payload={"query": request.query[:100], "auto_terminal_mode": request.auto_terminal_mode},
            source="api_gateway",
            trace_id=trace_id
        ))

        logger.info("Processing query", query=request.query[:100], auto_terminal_mode=request.auto_terminal_mode, trace_id=trace_id)

        response = rag_pipeline.answer_question(
            question=request.query,
            enable_web_search=request.enable_web_search,
            max_tokens=request.max_tokens
        )

        # Auto-terminal execution if enabled
        auto_terminal_results = []
        if request.auto_terminal_mode:
            logger.info("Auto-terminal mode enabled, extracting commands from response")

            # Extract commands from LLM response
            commands = extract_commands_from_response(response["answer"])

            # Filter commands against whitelist
            whitelist = request.auto_terminal_whitelist or []
            for command in commands:
                if is_command_whitelisted(command, whitelist):
                    logger.info("Executing auto-terminal command", command=command)
                    try:
                        # Execute command via terminal executor
                        exec_response = requests.post(
                            f"{TERMINAL_EXECUTOR_URL}/execute",
                            json={
                                "command": command,
                                "timeout": request.auto_terminal_timeout,
                                "stream": False
                            },
                            timeout=request.auto_terminal_timeout + 10
                        )
                        exec_response.raise_for_status()
                        exec_result = exec_response.json()

                        auto_terminal_results.append({
                            "command": command,
                            "exit_code": exec_result["exit_code"],
                            "stdout": exec_result["stdout"],
                            "stderr": exec_result["stderr"],
                            "execution_time": exec_result["execution_time"],
                            "matched_whitelist": True
                        })

                        logger.info("Auto-terminal command executed",
                                   command=command,
                                   exit_code=exec_result["exit_code"])

                    except Exception as e:
                        logger.error("Auto-terminal command failed", command=command, error=str(e))
                        auto_terminal_results.append({
                            "command": command,
                            "exit_code": -1,
                            "stdout": "",
                            "stderr": f"Execution failed: {str(e)}",
                            "execution_time": 0,
                            "matched_whitelist": True
                        })
                else:
                    logger.warning("Command not in whitelist, skipping", command=command)
                    auto_terminal_results.append({
                        "command": command,
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "Command not in whitelist",
                        "execution_time": 0,
                        "matched_whitelist": False
                    })

        # Add auto-terminal results to response
        if auto_terminal_results:
            response["auto_terminal_results"] = auto_terminal_results
            response["meta"]["auto_commands_executed"] = len(auto_terminal_results)

        logger.info("Query processed successfully",
                   backend=response["meta"].get("backend"),
                   latency=response["meta"].get("total_latency_ms"),
                   auto_commands=len(auto_terminal_results),
                   trace_id=trace_id)

        # Publish QUERY_COMPLETED event
        await event_bus.publish(Event(
            type=EventType.QUERY_COMPLETED,
            payload={
                "query": request.query[:100],
                "backend": response["meta"].get("backend"),
                "latency_ms": response["meta"].get("total_latency_ms")
            },
            source="api_gateway",
            trace_id=trace_id
        ))

        return response

    except Exception as e:
        # Publish QUERY_FAILED event
        await event_bus.publish(Event(
            type=EventType.QUERY_FAILED,
            payload={"query": request.query[:100], "error": str(e)},
            source="api_gateway",
            trace_id=trace_id
        ))
        logger.error("Query processing failed", error=str(e), trace_id=trace_id)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


@app.post("/search/vector")
async def search_vector_index(query: str, top_k: int = 10):
    """Search the vector index directly."""
    try:
        response = requests.post(
            f"{VECTOR_INDEX_URL}/search",
            json={"query": query, "top_k": top_k},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Vector search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")


@app.post("/search/web")
async def search_web(request: SearchRequest):
    """Search the web for additional context."""
    try:
        search_adapter = SearchAdapter()
        result = search_adapter.search(
            query=request.query,
            provider=request.provider,
            num_results=request.num_results,
            fetch_content=request.fetch_content
        )
        return result
    except Exception as e:
        logger.error("Web search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Web search failed: {e}")


# LLM endpoints
@app.post("/llm/generate")
async def generate_text(
    request: LLMRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Generate text using the LLM client with optional provider selection."""
    # Check rate limit
    await check_rate_limit(http_request)

    try:
        llm_client = LLMClient()
        response = llm_client.generate(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            provider=request.provider,
            temperature=request.temperature
        )
        return response
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")


@app.get("/llm/providers")
async def list_llm_providers():
    """
    Get detailed information about all LLM providers.

    Returns provider details including:
    - Name and description
    - Type (local/cloud)
    - Availability status
    - Supported models
    - Configuration status
    """
    try:
        llm_client = LLMClient()
        providers = llm_client.get_provider_details()

        return {
            "providers": providers,
            "priority": llm_client.priority,
            "total_providers": len(providers),
            "available_providers": len([p for p in providers if p["available"]])
        }
    except Exception as e:
        logger.error("Failed to list LLM providers", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list providers: {e}")


@app.get("/llm/adapters")
async def list_llm_adapters():
    """List available LLM adapters (legacy endpoint, use /llm/providers instead)."""
    try:
        llm_client = LLMClient()
        return {
            "available_adapters": llm_client.list_available_adapters(),
            "priority": os.getenv("LLM_PRIORITY", "ollama,mock").split(",")
        }
    except Exception as e:
        logger.error("Failed to list LLM adapters", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list adapters: {e}")


class SetPriorityRequest(BaseModel):
    """Request to set LLM provider priority."""
    priority: List[str] = Field(..., description="List of provider IDs in priority order")


@app.post("/llm/priority")
async def set_llm_priority(
    request: SetPriorityRequest,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """
    Set the priority order for LLM providers.

    The first provider in the list will be tried first, then fallback to subsequent providers.
    """
    try:
        llm_client = LLMClient()
        llm_client.set_priority(request.priority)

        return {
            "success": True,
            "priority": request.priority,
            "message": f"LLM priority updated to: {', '.join(request.priority)}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to set LLM priority", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to set priority: {e}")


# Chat endpoints
@app.post("/chat")
async def chat_conversation(
    request: ChatRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Handle multi-turn chat conversation with context awareness."""
    # Check rate limit
    await check_rate_limit(http_request)

    try:
        logger.info("Processing chat request", messages_count=len(request.messages))

        # Get the latest user message
        if not request.messages or request.messages[-1].role != 'user':
            raise HTTPException(status_code=400, detail="Last message must be from user")

        latest_message = request.messages[-1].content

        # Build conversation context from previous messages
        conversation_context = ""
        if len(request.messages) > 1:
            conversation_context = "Previous conversation:\n"
            for msg in request.messages[:-1]:  # Exclude the latest message
                role_label = "User" if msg.role == "user" else "Assistant"
                conversation_context += f"{role_label}: {msg.content}\n"
            conversation_context += "\nCurrent question: "

        # Combine conversation context with the latest message
        enhanced_query = conversation_context + latest_message

        # Use RAG pipeline for context-aware response if enabled
        if request.enable_context:
            response = rag_pipeline.answer_question(
                question=enhanced_query,
                enable_web_search=request.enable_web_search,
                max_tokens=request.max_tokens
            )

            return {
                "response": response["answer"],
                "context_used": len(response.get("contexts", [])),
                "web_results_used": len(response.get("web_results", [])),
                "meta": response.get("meta", {})
            }
        else:
            # Direct LLM generation without RAG context
            llm_client = LLMClient()

            # Format messages for LLM
            prompt = ""
            for msg in request.messages:
                role_label = "Human" if msg.role == "user" else "Assistant"
                prompt += f"{role_label}: {msg.content}\n"
            prompt += "Assistant: "

            llm_response = llm_client.generate(
                prompt=prompt,
                max_tokens=request.max_tokens,
                provider=request.provider,
                temperature=0.7
            )

            return {
                "response": llm_response["text"],
                "context_used": 0,
                "web_results_used": 0,
                "meta": llm_response.get("meta", {})
            }

    except Exception as e:
        logger.error("Chat conversation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# Git Integration endpoints
@app.post("/git/commit-message")
async def generate_commit_message(request: CommitMessageRequest):
    """Generate AI-powered commit message based on diff and context."""
    try:
        logger.info("Generating commit message",
                   staged_files=len(request.staged_files),
                   branch=request.branch,
                   diff_length=len(request.diff))

        # Analyze the diff to understand the changes
        diff_lines = request.diff.split('\n')
        added_lines = [line for line in diff_lines if line.startswith('+') and not line.startswith('+++')]
        removed_lines = [line for line in diff_lines if line.startswith('-') and not line.startswith('---')]

        # Extract file types and patterns
        file_extensions = set()
        for file_path in request.staged_files:
            if '.' in file_path:
                ext = file_path.split('.')[-1].lower()
                file_extensions.add(ext)

        # Build context for LLM
        context_parts = []
        context_parts.append(f"Branch: {request.branch}")
        context_parts.append(f"Files changed: {', '.join(request.staged_files)}")
        context_parts.append(f"File types: {', '.join(file_extensions) if file_extensions else 'mixed'}")
        context_parts.append(f"Lines added: {len(added_lines)}")
        context_parts.append(f"Lines removed: {len(removed_lines)}")

        if request.recent_commits:
            context_parts.append(f"Recent commits: {'; '.join(request.recent_commits[:3])}")

        # Create prompt for commit message generation
        prompt = f"""Generate a concise, conventional commit message for the following changes:

Context:
{chr(10).join(context_parts)}

Diff (first 2000 characters):
{request.diff[:2000]}

Requirements:
1. Use conventional commit format: type(scope): description
2. Types: feat, fix, docs, style, refactor, test, chore
3. Keep the first line under 50 characters
4. Be specific about what changed
5. Use imperative mood (e.g., "add", "fix", "update")

Generate only the commit message, no explanation."""

        # Generate commit message using LLM
        llm_client = LLMClient()
        llm_response = llm_client.generate(
            prompt=prompt,
            max_tokens=200
        )

        commit_message = llm_response["text"].strip()

        # Parse commit message to separate title and description
        lines = commit_message.split('\n')
        title = lines[0].strip()
        description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else None

        # Calculate confidence based on various factors
        confidence = 0.8  # Base confidence

        # Adjust confidence based on diff quality
        if len(request.diff) < 100:
            confidence -= 0.1  # Very small changes are harder to understand
        elif len(request.diff) > 5000:
            confidence -= 0.1  # Very large changes are complex

        # Adjust confidence based on file types
        if len(file_extensions) == 1:
            confidence += 0.1  # Single file type is clearer
        elif len(file_extensions) > 5:
            confidence -= 0.1  # Many file types are complex

        # Adjust confidence based on conventional commit format
        conventional_types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']
        if any(title.lower().startswith(t) for t in conventional_types):
            confidence += 0.1

        # Ensure confidence is within bounds
        confidence = max(0.1, min(1.0, confidence))

        logger.info("Generated commit message",
                   message=title,
                   confidence=confidence,
                   backend=llm_response["meta"]["backend"])

        return CommitMessageResponse(
            message=title,
            description=description,
            confidence=confidence
        )

    except Exception as e:
        logger.error("Commit message generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Commit message generation failed: {e}")


# File Upload and Processing endpoints
@app.post("/prompts/enhance")
async def enhance_prompt(request: PromptEnhancementRequest):
    """Enhance a user prompt with AI suggestions."""
    try:
        # Build enhancement prompt
        enhancement_prompt = f"""You are an expert prompt engineer. Enhance the following user prompt to make it more effective, clear, and specific.

Original prompt:
{request.prompt}

{f'Context: {request.context}' if request.context else ''}

Style: {request.style}

Please provide:
1. An enhanced version of the prompt that is more specific and effective
2. 2-3 specific suggestions for improvement
3. 2-3 key improvements made

Format your response as JSON with keys: enhanced, suggestions, improvements"""

        # Call LLM
        llm_client = LLMClient()
        response = llm_client.generate(
            prompt=enhancement_prompt,
            max_tokens=500,
            temperature=0.7
        )

        # Parse response
        try:
            import json
            response_text = response.get('text', '')

            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)

                return PromptEnhancementResponse(
                    original=request.prompt,
                    enhanced=parsed.get('enhanced', request.prompt),
                    suggestions=parsed.get('suggestions', []),
                    improvements=parsed.get('improvements', [])
                )
        except Exception as parse_error:
            logger.warning(f"Failed to parse LLM response: {parse_error}")

        # Fallback: return basic enhancement
        return PromptEnhancementResponse(
            original=request.prompt,
            enhanced=f"{request.prompt}\n\n[Enhanced with additional context and specificity]",
            suggestions=[
                "Add specific examples or use cases",
                "Include desired output format",
                "Specify any constraints or requirements"
            ],
            improvements=[
                "Made prompt more specific",
                "Added context for better understanding",
                "Included output format guidance"
            ]
        )

    except Exception as e:
        logger.error(f"Prompt enhancement failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    http_request: Request = None,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Upload and process a file for chat context."""
    # Check rate limit
    if http_request:
        await check_rate_limit(http_request)

    try:
        logger.info("File upload started", filename=file.filename, content_type=file.content_type)

        # Read file content
        content = await file.read()

        # Validate file size using configurable limit
        max_size = MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail=f"File size exceeds {MAX_FILE_SIZE_MB}MB limit")

        # Encode to base64
        file_data = base64.b64encode(content).decode('utf-8')

        # Extract text based on file type
        extracted_text = None
        analysis_result = None

        if file.content_type == 'application/pdf':
            extracted_text = extract_text_from_pdf(content)
        elif file.content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
            extracted_text = extract_text_from_docx(content)
        elif file.content_type.startswith('text/'):
            extracted_text = content.decode('utf-8', errors='ignore')
        elif file.content_type.startswith('image/'):
            analysis_result = analyze_image(content)

        # Generate file ID
        file_id = f"file_{str(uuid.uuid4())[:8]}"

        logger.info("File processed successfully",
                   file_id=file_id,
                   filename=file.filename,
                   extracted_text_length=len(extracted_text) if extracted_text else 0)

        return FileUploadResponse(
            id=file_id,
            name=file.filename,
            type=file.content_type,
            size=len(content),
            data=file_data,
            extractedText=extracted_text,
            analysisResult=analysis_result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload failed", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_reader = PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error("PDF extraction failed", error=str(e))
        return ""


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX file."""
    try:
        doc = Document(io.BytesIO(content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error("DOCX extraction failed", error=str(e))
        return ""


# Vision model cache for performance
_vision_model_cache = {}

def analyze_image(content: bytes) -> str:
    """
    Analyze image using tiered vision model strategy.

    Priority order (cost-effective to feature-rich):
    1. CLIP (free, fast, good for general understanding)
    2. BLIP (free, better captions, slightly slower)
    3. Google ViT (free, good classification)
    4. Basic image properties (always available)
    """
    try:
        image = Image.open(io.BytesIO(content))
        # Get image properties
        width, height = image.size
        format_type = image.format
        mode = image.mode

        # Basic image info
        basic_info = f"{format_type} image ({width}x{height}), Color mode: {mode}"

        # Convert PIL image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Try CLIP first (fastest, good results)
        analysis = _try_clip_analysis(image, basic_info)
        if analysis:
            return analysis

        # Try BLIP if CLIP fails (better captions)
        analysis = _try_blip_analysis(image, basic_info)
        if analysis:
            return analysis

        # Try Google ViT if BLIP fails
        analysis = _try_vit_analysis(image, basic_info)
        if analysis:
            return analysis

        # Fallback to basic analysis
        logger.warning("All vision models failed, using basic analysis")
        return f"Image Analysis: {basic_info}"

    except Exception as e:
        logger.error("Image analysis failed", error=str(e))
        return "Image analysis unavailable"


def _try_clip_analysis(image, basic_info: str) -> str:
    """Try CLIP model for image analysis (fastest, free)."""
    try:
        import clip
        import torch

        # Load model from cache or download
        if 'clip' not in _vision_model_cache:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)
            _vision_model_cache['clip'] = (model, preprocess, device)
        else:
            model, preprocess, device = _vision_model_cache['clip']

        # Preprocess image
        image_input = preprocess(image).unsqueeze(0).to(device)

        # Define candidate labels
        candidate_labels = [
            "a photo of a person",
            "a photo of a document",
            "a photo of code",
            "a screenshot",
            "a diagram",
            "a chart",
            "a graph",
            "a table",
            "a photo of nature",
            "a photo of an object",
            "a photo of text",
            "a photo of a building",
            "a photo of a landscape"
        ]

        text_inputs = clip.tokenize(candidate_labels).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_inputs)

            # Normalize features
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            # Calculate similarity
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            values, indices = similarity[0].topk(3)

        # Format results
        top_labels = [candidate_labels[idx] for idx in indices]
        scores = [f"{v:.1%}" for v in values]
        labels = ", ".join([f"{label} ({score})" for label, score in zip(top_labels, scores)])

        analysis = f"Image Analysis: {basic_info}\nContent: {labels}"
        logger.info("Image analysis completed with CLIP model")
        return analysis

    except Exception as e:
        logger.debug(f"CLIP analysis failed: {str(e)}")
        return None


def _try_blip_analysis(image, basic_info: str) -> str:
    """Try BLIP model for image captioning (better descriptions)."""
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration

        # Load model from cache or download
        if 'blip' not in _vision_model_cache:
            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            _vision_model_cache['blip'] = (processor, model)
        else:
            processor, model = _vision_model_cache['blip']

        # Generate caption
        inputs = processor(image, return_tensors="pt")
        out = model.generate(**inputs, max_length=50)
        caption = processor.decode(out[0], skip_special_tokens=True)

        analysis = f"Image Analysis: {basic_info}\nCaption: {caption}"
        logger.info("Image analysis completed with BLIP model")
        return analysis

    except Exception as e:
        logger.debug(f"BLIP analysis failed: {str(e)}")
        return None


def _try_vit_analysis(image, basic_info: str) -> str:
    """Try Google ViT model for image classification (fallback)."""
    try:
        from transformers import pipeline

        # Load model from cache or download
        if 'vit' not in _vision_model_cache:
            classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
            _vision_model_cache['vit'] = classifier
        else:
            classifier = _vision_model_cache['vit']

        # Get predictions
        predictions = classifier(image)
        top_predictions = predictions[:3]
        labels = ", ".join([f"{p['label']} ({p['score']:.1%})" for p in top_predictions])

        analysis = f"Image Analysis: {basic_info}\nClassification: {labels}"
        logger.info("Image analysis completed with ViT model")
        return analysis

    except Exception as e:
        logger.debug(f"ViT analysis failed: {str(e)}")
        return None


# Management endpoints
@app.delete("/index/clear")
async def clear_index():
    """Clear the vector index."""
    try:
        response = requests.delete(f"{VECTOR_INDEX_URL}/index/clear", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to clear index", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {e}")


@app.get("/index/stats")
async def get_index_stats():
    """Get vector index statistics."""
    try:
        response = requests.get(f"{VECTOR_INDEX_URL}/index/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get index stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


# Configuration endpoints
@app.get("/config")
async def get_configuration():
    """Get current configuration."""
    if CONFIG_AVAILABLE and _config:
        return {
            "llm_priority": _config.llm.priority,
            "enable_web_search": _config.web_search.enabled if hasattr(_config, 'web_search') else False,
            "vector_top_k": _config.indexing.vector_top_k,
            "privacy_mode": _config.privacy.privacy_mode,
            "hybrid_search_enabled": _config.indexing.hybrid_search_enabled,
            "services": {
                "vector_index": _config.services.vector_index,
                "preprocessor": _config.services.preprocessor,
                "connector": _config.services.connector,
                "web_fetcher": _config.services.web_fetcher,
                "terminal_executor": _config.services.terminal_executor
            },
            "scaling": {
                "parallel_indexing": _config.scaling.parallel_indexing_enabled,
                "max_workers": _config.scaling.max_indexing_workers,
                "incremental_index": _config.scaling.incremental_index_enabled
            },
            "database": {
                "type": _config.database.db_type,
                "use_postgres": _config.database.use_postgres
            },
            "cache": {
                "use_redis": _config.redis.use_redis
            }
        }
    else:
        # Fallback to environment variables
        return {
            "llm_priority": os.getenv("LLM_PRIORITY", "ollama,mock").split(","),
            "enable_web_search": os.getenv("ENABLE_WEB_SEARCH", "True").lower() == "true",
            "vector_top_k": int(os.getenv("VECTOR_TOP_K", "10")),
            "web_search_results": int(os.getenv("WEB_SEARCH_RESULTS", "5")),
            "privacy_mode": os.getenv("PRIVACY_MODE", "local"),
            "services": {
                "vector_index": VECTOR_INDEX_URL,
                "preprocessor": PREPROCESSOR_URL,
                "connector": CONNECTOR_URL,
                "web_fetcher": WEB_FETCHER_URL,
                "terminal_executor": TERMINAL_EXECUTOR_URL
            }
        }


# Terminal execution endpoints
@app.post("/terminal/execute")
async def execute_terminal_command(
    request: TerminalRequest,
    http_request: Request,
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Execute a terminal command safely."""
    # Check rate limit
    await check_rate_limit(http_request)

    try:
        logger.info("Executing terminal command", command=request.command[:100])

        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": request.command,
                "working_directory": request.working_directory,
                "timeout": request.timeout,
                "environment": request.environment,
                "stream": request.stream
            },
            timeout=request.timeout + 10  # Add buffer for network overhead
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        logger.error("Terminal command timed out", command=request.command)
        raise HTTPException(status_code=408, detail="Command execution timed out")
    except requests.exceptions.RequestException as e:
        logger.error("Terminal command failed", command=request.command, error=str(e))
        raise HTTPException(status_code=500, detail=f"Command execution failed: {e}")


@app.post("/terminal/execute-stream")
async def execute_terminal_command_stream(request: TerminalRequest):
    """Execute a terminal command with streaming output."""
    try:
        logger.info("Streaming terminal command", command=request.command)

        # Forward the streaming request to terminal executor
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute-stream",
            json={
                "command": request.command,
                "working_directory": request.working_directory,
                "timeout": request.timeout,
                "environment": request.environment,
                "stream": True
            },
            stream=True,
            timeout=request.timeout + 10
        )
        response.raise_for_status()

        # Stream the response back to client
        from fastapi.responses import StreamingResponse

        def stream_generator():
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except requests.exceptions.RequestException as e:
        logger.error("Streaming command failed", command=request.command, error=str(e))
        raise HTTPException(status_code=500, detail=f"Streaming execution failed: {e}")


@app.post("/terminal/suggest")
async def suggest_command(request: CommandSuggestionRequest):
    """Suggest terminal commands based on task description using LLM."""
    try:
        logger.info("Generating command suggestions", task=request.task_description)

        # Create a prompt for command suggestion
        context_info = f"\nWorking directory: {request.working_directory}" if request.working_directory else ""
        additional_context = f"\nAdditional context: {request.context}" if request.context else ""

        prompt = f"""You are a helpful assistant that suggests safe terminal commands for development tasks.

Task: {request.task_description}{context_info}{additional_context}

Please suggest 1-3 safe terminal commands that would accomplish this task.
Focus on common development tools like npm, python, git, docker, etc.
Avoid any dangerous commands that could harm the system.
Format your response as a JSON array of command objects with 'command' and 'description' fields.

Example format:
[
  {{"command": "npm install", "description": "Install project dependencies"}},
  {{"command": "npm run build", "description": "Build the project"}}
]"""

        # Use the LLM to generate suggestions
        llm_response = await rag_pipeline.llm_client.generate(
            prompt=prompt,
            max_tokens=512,
            temperature=0.3
        )

        # Try to parse the JSON response
        import json
        try:
            suggestions = json.loads(llm_response["text"])
            if not isinstance(suggestions, list):
                suggestions = [{"command": llm_response["text"], "description": "Generated suggestion"}]
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            suggestions = [{"command": llm_response["text"], "description": "Generated suggestion"}]

        return {
            "task": request.task_description,
            "suggestions": suggestions,
            "llm_backend": llm_response.get("meta", {}).get("backend", "unknown")
        }

    except Exception as e:
        logger.error("Command suggestion failed", task=request.task_description, error=str(e))
        raise HTTPException(status_code=500, detail=f"Command suggestion failed: {e}")


@app.get("/terminal/allowed-commands")
async def get_allowed_commands():
    """Get list of allowed terminal commands."""
    try:
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/allowed-commands", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get allowed commands", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get allowed commands: {e}")


@app.get("/terminal/processes")
async def get_active_processes():
    """Get list of active terminal processes."""
    try:
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/processes", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get active processes", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get processes: {e}")


@app.delete("/terminal/processes/{process_id}")
async def kill_process(process_id: int):
    """Kill an active terminal process."""
    try:
        response = requests.delete(f"{TERMINAL_EXECUTOR_URL}/processes/{process_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to kill process", process_id=process_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to kill process: {e}")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )


# Auto-terminal helper functions
def extract_commands_from_response(response_text: str) -> List[str]:
    """Extract terminal commands from LLM response text."""
    import re

    commands = []

    # First, remove code blocks from text to avoid conflicts with inline patterns
    text_without_blocks = re.sub(r'```(?:bash|shell|terminal|sh).*?```', '', response_text, flags=re.DOTALL | re.IGNORECASE)

    # Pattern 1: Code blocks with bash/shell/terminal
    code_block_pattern = r'```(?:bash|shell|terminal|sh)\s*\n(.*?)\n\s*```'
    code_blocks = re.findall(code_block_pattern, response_text, re.DOTALL | re.IGNORECASE)
    for block in code_blocks:
        # Split by lines and filter out comments and empty lines
        lines = [line.strip() for line in block.split('\n')]
        for line in lines:
            if line and not line.startswith('#') and not line.startswith('//'):
                commands.append(line)

    # Pattern 2: Inline code commands (single backticks) - only from text without code blocks
    inline_pattern = r'`([^`\n]+)`'
    inline_matches = re.findall(inline_pattern, text_without_blocks)
    for match in inline_matches:
        # Only include if it looks like a command (starts with common command words)
        command_starters = ['npm', 'python', 'pip', 'git', 'docker', 'ls', 'cd', 'pwd', 'cat', 'grep', 'find']
        if any(match.strip().startswith(starter) for starter in command_starters):
            commands.append(match.strip())

    # Pattern 3: "Run:" or "Execute:" patterns - exclude code block markers
    run_pattern = r'(?:Run|Execute|Command):\s*`?([^`\n]+)`?'
    run_matches = re.findall(run_pattern, text_without_blocks, re.IGNORECASE)
    for match in run_matches:
        clean_match = match.strip()
        # Only include if it looks like a command (starts with common command words)
        command_starters = ['npm', 'python', 'pip', 'git', 'docker', 'ls', 'cd', 'pwd', 'cat', 'grep', 'find']
        if any(clean_match.startswith(starter) for starter in command_starters):
            commands.append(clean_match)

    # Pattern 4: $ prefixed commands
    dollar_pattern = r'\$\s+([^\n]+)'
    dollar_matches = re.findall(dollar_pattern, response_text)
    for match in dollar_matches:
        commands.append(match.strip())

    # Remove duplicates while preserving order
    unique_commands = []
    seen = set()
    for cmd in commands:
        if cmd not in seen:
            unique_commands.append(cmd)
            seen.add(cmd)

    return unique_commands


def is_command_whitelisted(command: str, whitelist: List[str]) -> bool:
    """Check if a command matches the whitelist patterns."""
    if not whitelist:
        return False

    command = command.strip()

    # Exact match
    if command in whitelist:
        return True

    # Pattern matching - check if command starts with any whitelisted pattern
    for pattern in whitelist:
        # Simple prefix matching
        if command.startswith(pattern):
            return True

        # Allow for common variations (e.g., "npm test" matches "npm run test")
        if pattern.startswith('npm ') and command.startswith('npm '):
            # Extract npm command
            pattern_cmd = pattern.split()[1] if len(pattern.split()) > 1 else ''
            command_cmd = command.split()[1] if len(command.split()) > 1 else ''
            if pattern_cmd == command_cmd:
                return True

        # Allow for python variations
        if pattern.startswith('python ') and command.startswith(('python ', 'python3 ')):
            pattern_args = ' '.join(pattern.split()[1:])
            command_args = ' '.join(command.split()[1:])
            if pattern_args == command_args:
                return True

    return False


# =============================================================================
# Prompt Enhancement Endpoints
# =============================================================================

class PromptEnhanceRequest(BaseModel):
    """Request for prompt enhancement."""
    prompt: str = Field(..., description="Original prompt to enhance")
    context: Optional[str] = Field(None, description="Additional context")
    task_type: Optional[str] = Field("general", description="Task type: code_review, bug_detection, test_generation, etc.")
    code: Optional[str] = Field(None, description="Code to include")
    file_path: Optional[str] = Field(None, description="File path for context gathering")
    include_embeddings: bool = Field(True, description="Include semantic embeddings")
    include_git: bool = Field(True, description="Include git history")
    include_tests: bool = Field(True, description="Include test results")
    max_tokens: int = Field(4096, description="Max tokens for enhanced prompt")


class PromptEnhanceResponse(BaseModel):
    """Response with enhanced prompt."""
    original: str
    enhanced: str
    context_sections: List[str]
    estimated_tokens: int
    task_type: str


@app.post("/prompts/context-enhance", response_model=PromptEnhanceResponse, tags=["prompts"])
async def context_enhance_prompt(request: PromptEnhanceRequest):
    """
    Enhance a prompt with context-aware injection.

    Automatically injects:
    - Module summaries
    - Semantic embeddings
    - Recent test results
    - Git history
    """
    try:
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )

        # Map string task type to enum
        task_type_map = {
            "code_review": TaskType.CODE_REVIEW,
            "bug_detection": TaskType.BUG_DETECTION,
            "test_generation": TaskType.TEST_GENERATION,
            "refactor": TaskType.REFACTOR,
            "documentation": TaskType.DOCUMENTATION,
            "security_audit": TaskType.SECURITY_AUDIT,
            "general": TaskType.GENERAL
        }
        task_type = task_type_map.get(request.task_type, TaskType.GENERAL)

        # Gather context
        aggregator = get_context_aggregator()
        context = await aggregator.gather_context(
            query=request.prompt,
            file_path=request.file_path,
            include_git=request.include_git,
            include_tests=request.include_tests
        )

        # Add custom context
        if request.context:
            context.module_summary = request.context

        # Build enhanced prompt
        builder = PromptBuilder(max_tokens=request.max_tokens)
        enhanced = builder.build_prompt(
            task_type=task_type,
            context=context,
            code=request.code or "",
            query=request.prompt
        )

        # Extract context sections for transparency
        context_sections = []
        if context.module_summary:
            context_sections.append("module_summary")
        if context.file_embeddings:
            context_sections.append("embeddings")
        if context.test_results:
            context_sections.append("test_results")
        if context.git_history:
            context_sections.append("git_history")

        return PromptEnhanceResponse(
            original=request.prompt,
            enhanced=enhanced,
            context_sections=context_sections,
            estimated_tokens=len(enhanced) // 4,
            task_type=task_type.value
        )

    except Exception as e:
        logger.error(f"Prompt enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {e}")


# =============================================================================
# Code Analysis Endpoints
# =============================================================================

class CodeAnalysisRequest(BaseModel):
    """Request for code analysis."""
    file_path: Optional[str] = Field(None, description="Path to file to analyze")
    content: Optional[str] = Field(None, description="Code content to analyze")
    language: str = Field("python", description="Programming language")
    analyzers: Optional[List[str]] = Field(None, description="Specific analyzers to run")


class CodeReviewRequest(BaseModel):
    """Request for AI-powered code review."""
    file_path: Optional[str] = Field(None, description="Path to file")
    content: Optional[str] = Field(None, description="Code content")
    include_static_analysis: bool = Field(True, description="Run static analyzers")
    focus: str = Field("general", description="Review focus: general, security, performance")


@app.post("/analysis/static", tags=["analysis"])
async def run_static_analysis(request: CodeAnalysisRequest):
    """
    Run static analysis on code.

    Runs available analyzers (pylint, flake8, mypy, bandit) and returns findings.
    """
    try:
        from services.code_analysis import get_code_analyzer, AnalyzerType

        if not request.file_path and not request.content:
            raise HTTPException(status_code=400, detail="Either file_path or content required")

        analyzer = get_code_analyzer()

        if request.content:
            results = await analyzer.analyze_content(request.content, request.language)
        else:
            results = await analyzer.analyze_file(request.file_path)

        return {
            "results": [
                {
                    "analyzer": r.analyzer,
                    "type": r.analyzer_type.value,
                    "issues": [
                        {
                            "rule": i.rule,
                            "message": i.message,
                            "line": i.line,
                            "severity": i.severity.value
                        }
                        for i in r.issues
                    ],
                    "summary": r.summary,
                    "error": r.error,
                    "duration_ms": r.duration_ms
                }
                for r in results
            ],
            "formatted": analyzer.format_for_prompt(results)
        }

    except Exception as e:
        logger.error(f"Static analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analysis/review", tags=["analysis"])
async def ai_code_review(request: CodeReviewRequest):
    """
    Perform AI-powered code review.

    Combines static analysis with LLM-powered review suggestions.
    """
    try:
        from services.orchestrator import get_review_agent

        if not request.file_path and not request.content:
            raise HTTPException(status_code=400, detail="Either file_path or content required")

        agent = get_review_agent()

        if request.file_path:
            result = await agent.review_file(
                request.file_path,
                content=request.content,
                include_static_analysis=request.include_static_analysis
            )
        else:
            # Write content to temp file for analysis
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(request.content)
                temp_path = f.name

            try:
                result = await agent.review_file(
                    temp_path,
                    include_static_analysis=request.include_static_analysis
                )
            finally:
                Path(temp_path).unlink(missing_ok=True)

        return result

    except Exception as e:
        logger.error(f"Code review failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analysis/bugs", tags=["analysis"])
async def detect_bugs(request: CodeReviewRequest):
    """
    Specialized bug detection.

    Focuses on finding potential bugs, security issues, and logic errors.
    """
    try:
        from services.orchestrator import get_review_agent

        if not request.file_path and not request.content:
            raise HTTPException(status_code=400, detail="Either file_path or content required")

        agent = get_review_agent()

        if request.file_path:
            result = await agent.detect_bugs(request.file_path, request.content)
        else:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(request.content)
                temp_path = f.name

            try:
                result = await agent.detect_bugs(temp_path)
            finally:
                Path(temp_path).unlink(missing_ok=True)

        return result

    except Exception as e:
        logger.error(f"Bug detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Dependency Analysis Endpoints
# =============================================================================

class DependencyRequest(BaseModel):
    """Request for dependency analysis."""
    file_path: str = Field(..., description="File to analyze")
    analyze_impact: bool = Field(True, description="Include impact analysis")


@app.post("/analysis/dependencies", tags=["analysis"])
async def analyze_dependencies(request: DependencyRequest):
    """
    Analyze file dependencies and potential impact of changes.
    """
    try:
        from services.dependency_graph import get_dependency_graph

        graph = get_dependency_graph()

        # Add file if not already analyzed
        deps = graph.add_file(request.file_path)

        result = {
            "file": request.file_path,
            "imports": graph.get_dependencies(request.file_path),
            "imported_by": graph.get_dependents(request.file_path),
            "dependencies_found": len(deps)
        }

        if request.analyze_impact:
            impact = graph.analyze_impact(request.file_path)
            result["impact"] = {
                "directly_affected": impact.directly_affected,
                "transitively_affected": impact.transitively_affected,
                "test_files_affected": impact.test_files_affected,
                "risk_level": impact.risk_level,
                "summary": impact.summary
            }

        result["formatted"] = graph.format_for_prompt(request.file_path)

        return result

    except Exception as e:
        logger.error(f"Dependency analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/dependency-graph", tags=["analysis"])
async def get_dependency_graph_viz():
    """
    Get the dependency graph for visualization.

    Returns nodes and edges suitable for graph visualization.
    """
    try:
        from services.dependency_graph import get_dependency_graph

        graph = get_dependency_graph()
        module_graph = graph.get_module_graph()

        return {
            **module_graph,
            "mermaid": graph.to_mermaid()
        }

    except Exception as e:
        logger.error(f"Failed to get dependency graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Test Generation Endpoints
# =============================================================================

class TestGenerationRequest(BaseModel):
    """Request for test generation."""
    file_path: Optional[str] = None
    content: Optional[str] = None
    test_framework: str = Field("pytest", description="Test framework to use")
    language: str = Field("python", description="Programming language")


@app.post("/tests/generate", tags=["testing"])
async def generate_tests(request: TestGenerationRequest):
    """
    Generate unit tests for code.
    """
    try:
        from services.orchestrator import get_test_agent

        if not request.file_path and not request.content:
            raise HTTPException(status_code=400, detail="Either file_path or content required")

        agent = get_test_agent()
        result = await agent.generate_tests(
            file_path=request.file_path or "temp_file.py",
            content=request.content,
            test_framework=request.test_framework
        )

        return result

    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TestRunRequest(BaseModel):
    """Request to run tests."""
    test_path: str = Field("tests/", description="Path to test directory or file")
    pattern: Optional[str] = Field(None, description="Test pattern to match")


@app.post("/tests/run", tags=["testing"])
async def run_tests(request: TestRunRequest):
    """
    Run tests and return results.
    """
    try:
        from services.orchestrator import get_test_agent

        agent = get_test_agent()
        result = await agent.run_tests(
            test_path=request.test_path,
            pattern=request.pattern
        )

        return result

    except Exception as e:
        logger.error(f"Test run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Documentation Generation Endpoints
# =============================================================================

class DocGenerationRequest(BaseModel):
    """Request for documentation generation."""
    file_path: Optional[str] = None
    content: Optional[str] = None
    doc_style: str = Field("Google", description="Doc style: Google, NumPy, Sphinx")
    language: str = Field("python", description="Programming language")


@app.post("/docs/generate", tags=["documentation"])
async def generate_docs(request: DocGenerationRequest):
    """
    Generate documentation for code.
    """
    try:
        from services.orchestrator import get_doc_agent

        if not request.file_path and not request.content:
            raise HTTPException(status_code=400, detail="Either file_path or content required")

        agent = get_doc_agent()
        result = await agent.generate_docs(
            file_path=request.file_path or "temp_file.py",
            content=request.content,
            doc_style=request.doc_style
        )

        return result

    except Exception as e:
        logger.error(f"Documentation generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Task List Management Endpoints ==============

class TaskCreateRequest(BaseModel):
    """Request to create a new task."""
    name: str = Field(..., description="Task name")
    description: str = Field("", description="Task description")
    parent_task_id: Optional[str] = Field(None, description="Parent task ID for subtasks")
    after_task_id: Optional[str] = Field(None, description="Insert after this task ID")
    state: str = Field("NOT_STARTED", description="Initial state: NOT_STARTED, IN_PROGRESS, COMPLETE, CANCELLED")


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""
    task_id: str = Field(..., description="Task ID to update")
    name: Optional[str] = Field(None, description="New task name")
    description: Optional[str] = Field(None, description="New task description")
    state: Optional[str] = Field(None, description="New state: NOT_STARTED, IN_PROGRESS, COMPLETE, CANCELLED")


class AddTasksRequest(BaseModel):
    """Request to add multiple tasks."""
    tasks: List[TaskCreateRequest] = Field(..., description="List of tasks to create")


class UpdateTasksRequest(BaseModel):
    """Request to update multiple tasks."""
    tasks: List[TaskUpdateRequest] = Field(..., description="List of task updates")


class ReorganizeTasksRequest(BaseModel):
    """Request to reorganize task list via markdown."""
    markdown: str = Field(..., description="Markdown representation of task list")
    validate_only: bool = Field(False, description="Only validate, don't apply changes")


@app.get("/tasklist", tags=["tasks"])
async def get_tasklist():
    """
    Get the current task list.

    Returns the task list as markdown and structured data.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager, TaskState

        manager = get_tasklist_manager()
        tasks = manager.list_tasks()

        # Calculate stats
        stats = {
            "total": len(tasks),
            "not_started": len([t for t in tasks if t.state == TaskState.NOT_STARTED]),
            "in_progress": len([t for t in tasks if t.state == TaskState.IN_PROGRESS]),
            "complete": len([t for t in tasks if t.state == TaskState.COMPLETE]),
            "cancelled": len([t for t in tasks if t.state == TaskState.CANCELLED])
        }

        return {
            "markdown": manager.to_markdown(),
            "tasks": [t.to_dict() for t in tasks],
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Failed to get task list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasklist/tasks", tags=["tasks"])
async def add_tasks(request: AddTasksRequest):
    """
    Add one or more tasks to the task list.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager, Task, TaskState

        manager = get_tasklist_manager()
        created_tasks = []

        for task_req in request.tasks:
            # Map state string to enum
            state = TaskState.NOT_STARTED
            if task_req.state:
                try:
                    state = TaskState(task_req.state)
                except ValueError:
                    pass

            task = Task(
                task_id=str(uuid.uuid4()),
                name=task_req.name,
                description=task_req.description,
                state=state,
                parent_id=task_req.parent_task_id
            )

            manager.add_task(task)
            created_tasks.append(task.to_dict())

        # Save to disk
        manager.save()

        return {
            "success": True,
            "message": f"Created {len(created_tasks)} task(s)",
            "tasks": created_tasks
        }

    except Exception as e:
        logger.error(f"Failed to add tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/tasklist/tasks", tags=["tasks"])
async def update_tasks(request: UpdateTasksRequest):
    """
    Update one or more tasks.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager, TaskState

        manager = get_tasklist_manager()
        updated_tasks = []

        for update in request.tasks:
            state = None
            if update.state:
                try:
                    state = TaskState(update.state)
                except ValueError:
                    pass

            task = manager.update_task(
                task_id=update.task_id,
                name=update.name,
                description=update.description,
                state=state
            )

            if task:
                updated_tasks.append(task.to_dict())

        # Save to disk
        manager.save()

        return {
            "success": True,
            "message": f"Updated {len(updated_tasks)} task(s)",
            "tasks": updated_tasks
        }

    except Exception as e:
        logger.error(f"Failed to update tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasklist/reorganize", tags=["tasks"])
async def reorganize_tasklist(request: ReorganizeTasksRequest):
    """
    Reorganize the task list from markdown structure.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager, ReorganizeRequest

        manager = get_tasklist_manager()

        result = manager.reorganize(ReorganizeRequest(
            markdown=request.markdown,
            validate_only=request.validate_only
        ))

        if result.success and not request.validate_only:
            manager.save()

        return {
            "success": result.success,
            "message": result.message,
            "tasks_added": result.tasks_added,
            "tasks_moved": result.tasks_moved,
            "tasks_removed": result.tasks_removed,
            "validation_errors": result.validation_errors
        }

    except Exception as e:
        logger.error(f"Failed to reorganize task list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tasklist/tasks/{task_id}", tags=["tasks"])
async def delete_task(task_id: str):
    """
    Delete a task and its subtasks.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager

        manager = get_tasklist_manager()
        removed = manager.remove_task(task_id)

        if removed:
            manager.save()
            return {
                "success": True,
                "message": f"Task {task_id} deleted"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasklist/undo", tags=["tasks"])
async def undo_tasklist():
    """
    Undo the last task list change.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager

        manager = get_tasklist_manager()
        success = manager.undo()

        if success:
            manager.save()
            return {"success": True, "message": "Undo successful"}
        else:
            return {"success": False, "message": "Nothing to undo"}

    except Exception as e:
        logger.error(f"Failed to undo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasklist/redo", tags=["tasks"])
async def redo_tasklist():
    """
    Redo the last undone task list change.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager

        manager = get_tasklist_manager()
        success = manager.redo()

        if success:
            manager.save()
            return {"success": True, "message": "Redo successful"}
        else:
            return {"success": False, "message": "Nothing to redo"}

    except Exception as e:
        logger.error(f"Failed to redo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasklist/templates", tags=["tasks"])
async def get_task_templates():
    """
    Get available task templates.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager

        manager = get_tasklist_manager()
        templates = manager.list_templates()

        return {
            "templates": templates,
            "descriptions": {
                "feature": "Template for implementing new features",
                "bug_fix": "Template for fixing bugs",
                "refactor": "Template for refactoring code",
                "review": "Template for code reviews",
                "release": "Template for release process"
            }
        }

    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasklist/templates/{template_name}", tags=["tasks"])
async def apply_task_template(template_name: str, title: str = "", parent_id: Optional[str] = None):
    """
    Apply a task template.
    """
    try:
        from services.tools.tasklist_manager import get_tasklist_manager

        manager = get_tasklist_manager()
        tasks = manager.apply_template(template_name, title=title, parent_id=parent_id)
        manager.save()

        return {
            "success": True,
            "message": f"Applied template '{template_name}' with {len(tasks)} tasks",
            "tasks": [t.to_dict() for t in tasks]
        }

    except Exception as e:
        logger.error(f"Failed to apply template: {e}")
        raise HTTPException(status_code=500, detail=str(e))