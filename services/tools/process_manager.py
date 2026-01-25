"""
ContextForge Process Manager - Process launching and management tools.

Provides process management capabilities:
- launch-process: Start new processes (waiting or background)
- read-process: Read output from processes
- write-process: Write input to processes
- kill-process: Terminate processes
- list-processes: List all managed processes

Copyright (c) 2025 ContextForge
"""

import os
import sys
import signal
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """State of a managed process."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"


@dataclass
class LaunchProcessRequest:
    """Request to launch a new process."""
    command: str
    cwd: str
    wait: bool = True
    max_wait_seconds: float = 600  # 10 minutes default
    env: Optional[Dict[str, str]] = None
    shell: bool = True


@dataclass
class ProcessInfo:
    """Information about a managed process."""
    terminal_id: int
    command: str
    cwd: str
    state: ProcessState
    return_code: Optional[int] = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    output: str = ""
    error: str = ""


@dataclass
class ProcessResult:
    """Result of a process operation."""
    success: bool
    terminal_id: int
    message: str
    output: str = ""
    return_code: Optional[int] = None
    state: Optional[ProcessState] = None


class ProcessManager:
    """
    Process manager for launching and managing subprocesses.
    
    Provides:
    - Process launching with wait/background modes
    - Output reading and input writing
    - Process termination
    - Process listing
    """
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize process manager.
        
        Args:
            workspace_root: Root directory for relative paths
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._processes: Dict[int, Tuple[subprocess.Popen, ProcessInfo]] = {}
        self._next_terminal_id = 1
        self._lock = threading.Lock()
        self._output_threads: Dict[int, threading.Thread] = {}
        self._output_queues: Dict[int, Queue] = {}
    
    def _get_next_terminal_id(self) -> int:
        """Get the next available terminal ID."""
        with self._lock:
            terminal_id = self._next_terminal_id
            self._next_terminal_id += 1
            return terminal_id
    
    def _resolve_cwd(self, cwd: str) -> Path:
        """Resolve working directory path."""
        p = Path(cwd)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _output_reader(self, terminal_id: int, stream, queue: Queue):
        """Thread function to read output from a process stream."""
        try:
            for line in iter(stream.readline, ''):
                if line:
                    queue.put(line)
                else:
                    break
        except Exception as e:
            logger.debug(f"Output reader for terminal {terminal_id} ended: {e}")
        finally:
            stream.close()
    
    def launch_process(self, request: LaunchProcessRequest) -> ProcessResult:
        """
        Launch a new process.
        
        Args:
            request: LaunchProcessRequest with command and options
            
        Returns:
            ProcessResult with terminal ID and status
        """
        terminal_id = self._get_next_terminal_id()
        cwd = self._resolve_cwd(request.cwd)
        
        # Validate working directory
        if not cwd.exists():
            return ProcessResult(
                success=False,
                terminal_id=terminal_id,
                message=f"Working directory not found: {cwd}"
            )
        
        try:
            # Prepare environment
            env = os.environ.copy()
            if request.env:
                env.update(request.env)
            
            # Determine shell based on platform
            if sys.platform == 'win32':
                shell_cmd = request.command
            else:
                shell_cmd = request.command
            
            # Launch process
            process = subprocess.Popen(
                shell_cmd,
                shell=request.shell,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Create process info
            info = ProcessInfo(
                terminal_id=terminal_id,
                command=request.command,
                cwd=str(cwd),
                state=ProcessState.RUNNING
            )

            # Store process
            with self._lock:
                self._processes[terminal_id] = (process, info)

            # Set up output queue and reader thread
            output_queue = Queue()
            self._output_queues[terminal_id] = output_queue

            reader_thread = threading.Thread(
                target=self._output_reader,
                args=(terminal_id, process.stdout, output_queue),
                daemon=True
            )
            reader_thread.start()
            self._output_threads[terminal_id] = reader_thread

            if request.wait:
                # Wait for process to complete
                output_lines = []
                start_time = time.time()

                while True:
                    # Check if process completed
                    return_code = process.poll()

                    # Collect output
                    while True:
                        try:
                            line = output_queue.get_nowait()
                            output_lines.append(line)
                        except Empty:
                            break

                    if return_code is not None:
                        # Process completed
                        info.state = ProcessState.COMPLETED if return_code == 0 else ProcessState.FAILED
                        info.return_code = return_code
                        info.end_time = datetime.now().isoformat()
                        info.output = ''.join(output_lines)

                        return ProcessResult(
                            success=return_code == 0,
                            terminal_id=terminal_id,
                            message=f"Process completed with return code {return_code}",
                            output=info.output,
                            return_code=return_code,
                            state=info.state
                        )

                    # Check timeout
                    if time.time() - start_time > request.max_wait_seconds:
                        info.state = ProcessState.TIMEOUT
                        info.output = ''.join(output_lines)

                        return ProcessResult(
                            success=True,
                            terminal_id=terminal_id,
                            message=f"Process still running after {request.max_wait_seconds}s timeout",
                            output=info.output,
                            state=info.state
                        )

                    time.sleep(0.1)
            else:
                # Background process - return immediately
                return ProcessResult(
                    success=True,
                    terminal_id=terminal_id,
                    message=f"Background process started",
                    state=ProcessState.RUNNING
                )

        except Exception as e:
            logger.error(f"Error launching process: {e}")
            return ProcessResult(
                success=False,
                terminal_id=terminal_id,
                message=f"Error: {e}"
            )

    def read_process(
        self,
        terminal_id: int,
        wait: bool = False,
        max_wait_seconds: float = 60
    ) -> ProcessResult:
        """
        Read output from a process.

        Args:
            terminal_id: Terminal ID to read from
            wait: Whether to wait for process completion
            max_wait_seconds: Maximum time to wait

        Returns:
            ProcessResult with output
        """
        with self._lock:
            if terminal_id not in self._processes:
                return ProcessResult(
                    success=False,
                    terminal_id=terminal_id,
                    message=f"Terminal {terminal_id} not found"
                )

            process, info = self._processes[terminal_id]

        output_queue = self._output_queues.get(terminal_id)
        output_lines = []

        if wait:
            start_time = time.time()
            while True:
                # Collect output
                while output_queue:
                    try:
                        line = output_queue.get_nowait()
                        output_lines.append(line)
                    except Empty:
                        break

                # Check if process completed
                return_code = process.poll()
                if return_code is not None:
                    info.state = ProcessState.COMPLETED if return_code == 0 else ProcessState.FAILED
                    info.return_code = return_code
                    info.end_time = datetime.now().isoformat()
                    break

                # Check timeout
                if time.time() - start_time > max_wait_seconds:
                    break

                time.sleep(0.1)
        else:
            # Just collect available output
            while output_queue:
                try:
                    line = output_queue.get_nowait()
                    output_lines.append(line)
                except Empty:
                    break

        new_output = ''.join(output_lines)
        info.output += new_output

        return ProcessResult(
            success=True,
            terminal_id=terminal_id,
            message=f"Read {len(output_lines)} lines",
            output=info.output,
            return_code=info.return_code,
            state=info.state
        )

    def write_process(self, terminal_id: int, input_text: str) -> ProcessResult:
        """
        Write input to a process.

        Args:
            terminal_id: Terminal ID to write to
            input_text: Text to write to stdin

        Returns:
            ProcessResult with status
        """
        with self._lock:
            if terminal_id not in self._processes:
                return ProcessResult(
                    success=False,
                    terminal_id=terminal_id,
                    message=f"Terminal {terminal_id} not found"
                )

            process, info = self._processes[terminal_id]

        # Check if process is still running
        if process.poll() is not None:
            return ProcessResult(
                success=False,
                terminal_id=terminal_id,
                message="Process has already terminated",
                state=info.state
            )

        try:
            process.stdin.write(input_text)
            process.stdin.flush()

            return ProcessResult(
                success=True,
                terminal_id=terminal_id,
                message=f"Wrote {len(input_text)} characters",
                state=info.state
            )
        except Exception as e:
            logger.error(f"Error writing to process: {e}")
            return ProcessResult(
                success=False,
                terminal_id=terminal_id,
                message=f"Error: {e}"
            )

    def kill_process(self, terminal_id: int) -> ProcessResult:
        """
        Kill a process.

        Args:
            terminal_id: Terminal ID to kill

        Returns:
            ProcessResult with status
        """
        with self._lock:
            if terminal_id not in self._processes:
                return ProcessResult(
                    success=False,
                    terminal_id=terminal_id,
                    message=f"Terminal {terminal_id} not found"
                )

            process, info = self._processes[terminal_id]

        # Check if already terminated
        if process.poll() is not None:
            return ProcessResult(
                success=True,
                terminal_id=terminal_id,
                message="Process already terminated",
                return_code=info.return_code,
                state=info.state
            )

        try:
            # Try graceful termination first
            process.terminate()

            # Wait briefly for termination
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill
                process.kill()
                process.wait(timeout=5)

            info.state = ProcessState.KILLED
            info.return_code = process.returncode
            info.end_time = datetime.now().isoformat()

            return ProcessResult(
                success=True,
                terminal_id=terminal_id,
                message="Process killed",
                return_code=info.return_code,
                state=info.state
            )
        except Exception as e:
            logger.error(f"Error killing process: {e}")
            return ProcessResult(
                success=False,
                terminal_id=terminal_id,
                message=f"Error: {e}"
            )

    def list_processes(self) -> List[ProcessInfo]:
        """
        List all managed processes.

        Returns:
            List of ProcessInfo for all processes
        """
        with self._lock:
            result = []
            for terminal_id, (process, info) in self._processes.items():
                # Update state if process has completed
                return_code = process.poll()
                if return_code is not None and info.state == ProcessState.RUNNING:
                    info.state = ProcessState.COMPLETED if return_code == 0 else ProcessState.FAILED
                    info.return_code = return_code
                    info.end_time = datetime.now().isoformat()

                result.append(info)

            return result


# Factory function
_manager_instance: Optional[ProcessManager] = None


def get_process_manager(workspace_root: str = None) -> ProcessManager:
    """
    Get or create a ProcessManager instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        ProcessManager instance
    """
    global _manager_instance
    if _manager_instance is None or workspace_root is not None:
        _manager_instance = ProcessManager(workspace_root=workspace_root)
    return _manager_instance