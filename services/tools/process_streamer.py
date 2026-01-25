"""
ContextForge Process Streamer - Real-time process output streaming.

Provides streaming capabilities for process output:
- Async iteration over output lines
- Callback-based notifications
- Output buffering with size limits
- PTY support for interactive processes

Copyright (c) 2025 ContextForge
"""

import os
import sys
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, List, Optional, Iterator
from enum import Enum
from queue import Queue, Empty
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """Configuration for process streaming."""
    command: str
    cwd: str
    env: Optional[Dict[str, str]] = None
    max_buffer_lines: int = 10000
    line_callback: Optional[Callable[[str], None]] = None
    shell: bool = True


@dataclass
class StreamLine:
    """A single line of output from a process."""
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    line_number: int = 0


class ProcessStreamer:
    """
    Real-time process output streamer.
    
    Provides line-by-line streaming of process output with
    configurable buffering and callbacks.
    """
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize process streamer.
        
        Args:
            workspace_root: Root directory for relative paths
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._streams: Dict[int, Dict] = {}
        self._next_stream_id = 1
        self._lock = threading.Lock()
    
    def _resolve_cwd(self, cwd: str) -> Path:
        """Resolve working directory path."""
        p = Path(cwd)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _reader_thread(self, stream_id: int, stream, line_queue: Queue, config: StreamConfig) -> None:
        """Thread function to read lines from a stream."""
        line_number = 0
        try:
            for line in iter(stream.readline, ''):
                if not line:
                    break
                
                line_number += 1
                stream_line = StreamLine(
                    text=line.rstrip('\n\r'),
                    line_number=line_number
                )
                
                # Add to queue
                line_queue.put(stream_line)
                
                # Call callback if provided
                if config.line_callback:
                    try:
                        config.line_callback(stream_line.text)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        
        except Exception as e:
            logger.debug(f"Reader thread for stream {stream_id} ended: {e}")
        finally:
            stream.close()
    
    def start_stream(self, config: StreamConfig) -> int:
        """
        Start streaming a process.
        
        Args:
            config: Stream configuration
            
        Returns:
            Stream ID
        """
        cwd = self._resolve_cwd(config.cwd)
        
        if not cwd.exists():
            raise ValueError(f"Working directory not found: {cwd}")
        
        # Prepare environment
        env = os.environ.copy()
        if config.env:
            env.update(config.env)
        
        # Launch process
        process = subprocess.Popen(
            config.command,
            shell=config.shell,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        with self._lock:
            stream_id = self._next_stream_id
            self._next_stream_id += 1
            
            line_queue = Queue()
            buffer = deque(maxlen=config.max_buffer_lines)
            
            # Start reader thread
            reader = threading.Thread(
                target=self._reader_thread,
                args=(stream_id, process.stdout, line_queue, config),
                daemon=True
            )
            reader.start()
            
            self._streams[stream_id] = {
                'process': process,
                'config': config,
                'queue': line_queue,
                'buffer': buffer,
                'reader': reader,
                'start_time': datetime.now().isoformat()
            }

            return stream_id

    def read_lines(
        self,
        stream_id: int,
        max_lines: int = 100,
        timeout: float = 0.1
    ) -> List[StreamLine]:
        """
        Read available lines from a stream.

        Args:
            stream_id: Stream ID
            max_lines: Maximum lines to return
            timeout: Wait timeout for first line

        Returns:
            List of StreamLine objects
        """
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return []

        queue = stream_info['queue']
        buffer = stream_info['buffer']
        lines = []

        # First try with timeout
        try:
            line = queue.get(timeout=timeout)
            lines.append(line)
            buffer.append(line)
        except Empty:
            pass

        # Get remaining lines without blocking
        while len(lines) < max_lines:
            try:
                line = queue.get_nowait()
                lines.append(line)
                buffer.append(line)
            except Empty:
                break

        return lines

    def iter_lines(self, stream_id: int) -> Iterator[StreamLine]:
        """
        Iterate over lines from a stream.

        Yields lines as they become available.
        Blocks until process completes or is stopped.

        Args:
            stream_id: Stream ID

        Yields:
            StreamLine objects
        """
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return

        process = stream_info['process']
        queue = stream_info['queue']
        buffer = stream_info['buffer']

        while True:
            # Check if process is done
            if process.poll() is not None:
                # Drain remaining queue
                while True:
                    try:
                        line = queue.get_nowait()
                        buffer.append(line)
                        yield line
                    except Empty:
                        break
                return

            # Get next line
            try:
                line = queue.get(timeout=0.1)
                buffer.append(line)
                yield line
            except Empty:
                continue

    def get_buffer(self, stream_id: int) -> List[StreamLine]:
        """
        Get all buffered lines from a stream.

        Args:
            stream_id: Stream ID

        Returns:
            List of buffered StreamLine objects
        """
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return []

        return list(stream_info['buffer'])

    def write_input(self, stream_id: int, text: str) -> bool:
        """
        Write input to a streaming process.

        Args:
            stream_id: Stream ID
            text: Text to write

        Returns:
            True if successful
        """
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return False

        process = stream_info['process']
        if process.poll() is not None:
            return False

        try:
            process.stdin.write(text)
            process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"Error writing to stream {stream_id}: {e}")
            return False

    def stop_stream(self, stream_id: int) -> bool:
        """
        Stop a streaming process.

        Args:
            stream_id: Stream ID

        Returns:
            True if stopped
        """
        with self._lock:
            stream_info = self._streams.get(stream_id)
            if not stream_info:
                return False

            process = stream_info['process']

            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error stopping stream {stream_id}: {e}")

            del self._streams[stream_id]
            return True

    def is_running(self, stream_id: int) -> bool:
        """Check if a stream's process is still running."""
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return False
        return stream_info['process'].poll() is None

    def get_return_code(self, stream_id: int) -> Optional[int]:
        """Get the return code of a completed process."""
        stream_info = self._streams.get(stream_id)
        if not stream_info:
            return None
        return stream_info['process'].poll()

    def list_streams(self) -> List[Dict]:
        """List all active streams."""
        with self._lock:
            result = []
            for sid, info in self._streams.items():
                result.append({
                    'stream_id': sid,
                    'command': info['config'].command,
                    'cwd': info['config'].cwd,
                    'running': info['process'].poll() is None,
                    'start_time': info['start_time'],
                    'buffer_size': len(info['buffer'])
                })
            return result


# Factory function
_streamer_instance: Optional[ProcessStreamer] = None


def get_process_streamer(workspace_root: str = None) -> ProcessStreamer:
    """
    Get or create a ProcessStreamer instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        ProcessStreamer instance
    """
    global _streamer_instance
    if _streamer_instance is None or workspace_root is not None:
        _streamer_instance = ProcessStreamer(workspace_root=workspace_root)
    return _streamer_instance