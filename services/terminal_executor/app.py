"""
ContextForge Terminal Executor Service - Safe command execution with streaming output.
Provides secure terminal command execution with real-time output streaming.
"""

import os
import asyncio
import subprocess
import signal
import time
import json
import re
import shlex
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path
from collections import OrderedDict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import structlog

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

# Security configuration
ALLOWED_COMMANDS = {
    # Development tools
    'npm', 'yarn', 'pnpm', 'node', 'python', 'python3', 'pip', 'pip3',
    'poetry', 'conda', 'cargo', 'rustc', 'go', 'java', 'javac', 'mvn',
    'gradle', 'make', 'cmake', 'gcc', 'g++', 'clang',
    
    # Version control
    'git', 'svn', 'hg',
    
    # File operations (safe subset)
    'ls', 'dir', 'cat', 'head', 'tail', 'find', 'grep', 'awk', 'sed',
    'wc', 'sort', 'uniq', 'cut', 'tr',
    
    # System info (read-only)
    'ps', 'top', 'htop', 'df', 'du', 'free', 'uname', 'whoami', 'id',
    'env', 'printenv', 'which', 'where', 'type',
    
    # Docker (safe subset)
    'docker', 'docker-compose',
    
    # Testing
    'pytest', 'jest', 'mocha', 'phpunit', 'rspec',
    
    # Linting and formatting
    'eslint', 'prettier', 'black', 'flake8', 'mypy', 'pylint',
    'rustfmt', 'gofmt',
    
    # Package managers
    'apt', 'yum', 'brew', 'choco', 'pacman',
}

DANGEROUS_PATTERNS = [
    r'\brm\s+(-rf?|--recursive|--force)',  # rm -rf
    r'\bsudo\b',  # sudo commands
    r'\bsu\b',    # switch user
    r'>\s*/dev/',  # redirect to device files
    r'\bchmod\s+777',  # dangerous permissions
    r'\bchown\b',  # change ownership
    r'\bmkfs\b',   # format filesystem
    r'\bdd\s+if=',  # disk operations
    r'\bfdisk\b',  # disk partitioning
    r'\breboot\b', # system reboot
    r'\bshutdown\b',  # system shutdown
    r'\bhalt\b',   # system halt
    r'\bkill\s+-9',  # force kill
    r'\bkillall\b',  # kill all processes
    r'\bpkill\b',   # kill processes by name
    r'&&.*rm\b',    # chained rm commands
    r';\s*rm\b',    # sequential rm commands
    r'\|\s*rm\b',   # piped rm commands
]

# Security limits
MAX_CONCURRENT_PROCESSES = int(os.getenv("MAX_CONCURRENT_PROCESSES", "10"))
MAX_TIMEOUT_SECONDS = int(os.getenv("MAX_TIMEOUT_SECONDS", "300"))
MIN_TIMEOUT_SECONDS = 1


def parse_command_safely(command: str) -> List[str]:
    """
    Safely parse a command string into a list of arguments.
    This prevents shell injection by avoiding shell interpretation.
    """
    try:
        # Use shlex to properly parse the command
        args = shlex.split(command)
        if not args:
            raise ValueError("Empty command")
        return args
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {e}")


def validate_command_args(args: List[str]) -> None:
    """
    Validate command arguments after parsing.
    Checks for shell metacharacters that could indicate injection attempts.
    """
    shell_metacharacters = ['|', '&', ';', '$', '`', '(', ')', '{', '}', '<', '>', '\n', '\r']

    for arg in args:
        for char in shell_metacharacters:
            if char in arg:
                raise ValueError(f"Command contains disallowed shell metacharacter: {char}")


# Request/Response models
class CommandRequest(BaseModel):
    command: str = Field(..., description="Command to execute", max_length=4096)
    working_directory: Optional[str] = Field(None, description="Working directory for command execution", max_length=1024)
    timeout: Optional[int] = Field(30, description="Timeout in seconds", ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    stream: bool = Field(False, description="Stream output in real-time")

    @validator('command')
    def validate_command(cls, v):
        if not v or not v.strip():
            raise ValueError("Command cannot be empty")

        # Check for dangerous patterns BEFORE parsing
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f"Command contains dangerous pattern")

        # Safely parse the command to prevent shell injection
        try:
            args = parse_command_safely(v)
        except ValueError as e:
            raise ValueError(f"Invalid command: {e}")

        # Validate parsed arguments for shell metacharacters
        validate_command_args(args)

        # Check if command starts with allowed command
        if args:
            base_command = args[0].split('/')[-1].split('\\')[-1]  # Handle paths on both Unix and Windows
            if base_command not in ALLOWED_COMMANDS:
                raise ValueError(f"Command '{base_command}' is not in the allowed list")

        return v

    @validator('working_directory')
    def validate_working_directory(cls, v):
        if v:
            # Prevent path traversal attacks
            path = Path(v).resolve()

            # Check for path traversal attempts
            if '..' in v:
                raise ValueError("Path traversal not allowed")

            if not path.exists():
                raise ValueError(f"Working directory does not exist: {v}")
            if not path.is_dir():
                raise ValueError(f"Working directory is not a directory: {v}")
        return v

class CommandResponse(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    working_directory: str
    timestamp: datetime
    process_id: Optional[int] = None

class StreamChunk(BaseModel):
    type: str  # 'stdout', 'stderr', 'exit', 'error'
    data: str
    timestamp: datetime

class ExecutionStatus(BaseModel):
    process_id: int
    command: str
    status: str  # 'running', 'completed', 'failed', 'timeout'
    start_time: datetime
    working_directory: str

# CORS Configuration - Security hardened
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
ALLOWED_HEADERS = ["Content-Type", "Authorization"]

# Initialize FastAPI app
app = FastAPI(
    title="ContextForge Terminal Executor",
    description="Safe terminal command execution with streaming output",
    version="1.0.0"
)

# Add CORS middleware - Security hardened
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # Set to True only if needed for specific use cases
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
)

# Bounded process tracking to prevent resource exhaustion
class BoundedProcessDict(OrderedDict):
    """OrderedDict with a maximum size limit. Removes oldest entries when full."""
    def __init__(self, max_size: int = MAX_CONCURRENT_PROCESSES, *args, **kwargs):
        self.max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if len(self) >= self.max_size and key not in self:
            # Remove oldest entry
            oldest_key = next(iter(self))
            self.pop(oldest_key)
        super().__setitem__(key, value)

# Global process tracking with bounded size
active_processes: BoundedProcessDict = BoundedProcessDict(MAX_CONCURRENT_PROCESSES)
process_metadata: BoundedProcessDict = BoundedProcessDict(MAX_CONCURRENT_PROCESSES)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "terminal-executor",
        "active_processes": len(active_processes)
    }

@app.get("/allowed-commands")
async def get_allowed_commands():
    """Get list of allowed commands."""
    return {
        "allowed_commands": sorted(list(ALLOWED_COMMANDS)),
        "dangerous_patterns": DANGEROUS_PATTERNS
    }

@app.post("/execute", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """Execute a command and return the complete result."""
    logger.info("Executing command", command=request.command, working_dir=request.working_directory)

    # Check concurrent process limit
    if len(active_processes) >= MAX_CONCURRENT_PROCESSES:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum concurrent processes ({MAX_CONCURRENT_PROCESSES}) reached. Please wait for existing processes to complete."
        )

    start_time = time.time()
    working_dir = request.working_directory or os.getcwd()

    try:
        # Prepare environment
        env = os.environ.copy()
        if request.environment:
            env.update(request.environment)

        # Safely parse command to prevent shell injection
        args = parse_command_safely(request.command)

        # Execute command using create_subprocess_exec (NOT shell) to prevent injection
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
            env=env
        )

        # Store process info
        active_processes[process.pid] = process
        process_metadata[process.pid] = ExecutionStatus(
            process_id=process.pid,
            command=request.command,
            status="running",
            start_time=datetime.utcnow(),
            working_directory=working_dir
        )
        
        try:
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=request.timeout
            )
            
            execution_time = time.time() - start_time
            
            # Clean up process tracking
            active_processes.pop(process.pid, None)
            if process.pid in process_metadata:
                process_metadata[process.pid].status = "completed" if process.returncode == 0 else "failed"
            
            response = CommandResponse(
                command=request.command,
                exit_code=process.returncode,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                execution_time=execution_time,
                working_directory=working_dir,
                timestamp=datetime.utcnow(),
                process_id=process.pid
            )
            
            logger.info("Command completed", 
                       command=request.command, 
                       exit_code=process.returncode,
                       execution_time=execution_time)
            
            return response
            
        except asyncio.TimeoutError:
            # Kill the process on timeout
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                # Process already terminated
                logger.debug("Process already terminated during timeout cleanup", process_id=process.pid)
            except OSError as e:
                logger.warning("Error killing process during timeout", process_id=process.pid, error=str(e))

            # Clean up
            active_processes.pop(process.pid, None)
            if process.pid in process_metadata:
                process_metadata[process.pid].status = "timeout"

            logger.warning("Command timed out", command=request.command, timeout=request.timeout)
            raise HTTPException(
                status_code=408,
                detail=f"Command timed out after {request.timeout} seconds"
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Validation errors
        logger.warning("Command validation failed", command=request.command, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Command execution failed", command=request.command, error=str(e))
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")

@app.post("/execute-stream")
async def execute_command_stream(request: CommandRequest):
    """Execute a command and stream the output in real-time."""
    logger.info("Streaming command execution", command=request.command)

    # Check concurrent process limit
    if len(active_processes) >= MAX_CONCURRENT_PROCESSES:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum concurrent processes ({MAX_CONCURRENT_PROCESSES}) reached. Please wait for existing processes to complete."
        )

    async def stream_output():
        working_dir = request.working_directory or os.getcwd()
        start_time = time.time()

        try:
            # Prepare environment
            env = os.environ.copy()
            if request.environment:
                env.update(request.environment)

            # Safely parse command to prevent shell injection
            args = parse_command_safely(request.command)

            # Execute command using create_subprocess_exec (NOT shell) to prevent injection
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env
            )

            # Store process info
            active_processes[process.pid] = process
            process_metadata[process.pid] = ExecutionStatus(
                process_id=process.pid,
                command=request.command,
                status="running",
                start_time=datetime.utcnow(),
                working_directory=working_dir
            )
            
            # Stream stdout and stderr
            async def read_stream(stream, stream_type):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    
                    chunk = StreamChunk(
                        type=stream_type,
                        data=line.decode('utf-8', errors='replace'),
                        timestamp=datetime.utcnow()
                    )
                    yield f"data: {chunk.json()}\n\n"
            
            # Create tasks for both streams
            stdout_task = asyncio.create_task(
                asyncio.to_thread(lambda: asyncio.run(read_stream(process.stdout, 'stdout')))
            )
            stderr_task = asyncio.create_task(
                asyncio.to_thread(lambda: asyncio.run(read_stream(process.stderr, 'stderr')))
            )
            
            # Wait for process completion with timeout
            try:
                await asyncio.wait_for(process.wait(), timeout=request.timeout)
                
                # Send final status
                execution_time = time.time() - start_time
                final_chunk = StreamChunk(
                    type='exit',
                    data=json.dumps({
                        'exit_code': process.returncode,
                        'execution_time': execution_time
                    }),
                    timestamp=datetime.utcnow()
                )
                yield f"data: {final_chunk.json()}\n\n"
                
            except asyncio.TimeoutError:
                # Kill process on timeout
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    # Process already terminated
                    logger.debug("Process already terminated during timeout cleanup", process_id=process.pid)
                except OSError as e:
                    logger.warning("Error killing process during timeout", process_id=process.pid, error=str(e))

                error_chunk = StreamChunk(
                    type='error',
                    data=f"Command timed out after {request.timeout} seconds",
                    timestamp=datetime.utcnow()
                )
                yield f"data: {error_chunk.json()}\n\n"
            
            finally:
                # Clean up
                active_processes.pop(process.pid, None)
                process_metadata.pop(process.pid, None)
                
                # Cancel streaming tasks
                stdout_task.cancel()
                stderr_task.cancel()
                
        except Exception as e:
            error_chunk = StreamChunk(
                type='error',
                data=f"Command execution failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
            yield f"data: {error_chunk.json()}\n\n"
    
    return StreamingResponse(
        stream_output(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/processes", response_model=List[ExecutionStatus])
async def get_active_processes():
    """Get list of currently running processes."""
    return list(process_metadata.values())

@app.delete("/processes/{process_id}")
async def kill_process(process_id: int):
    """Kill a running process."""
    if process_id not in active_processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    try:
        process = active_processes[process_id]
        process.kill()
        
        # Clean up
        active_processes.pop(process_id, None)
        if process_id in process_metadata:
            process_metadata[process_id].status = "killed"
        
        logger.info("Process killed", process_id=process_id)
        return {"message": f"Process {process_id} killed successfully"}
        
    except Exception as e:
        logger.error("Failed to kill process", process_id=process_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to kill process: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
