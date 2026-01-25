"""
ContextForge File Watcher - Real-time file system monitoring.

Provides file watching capabilities:
- Watch files and directories for changes
- Debounced event handling
- Pattern-based filtering
- Async event notification

Copyright (c) 2025 ContextForge
"""

import os
import time
import logging
import threading
import fnmatch
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from enum import Enum
from queue import Queue

logger = logging.getLogger(__name__)


class FileEventType(Enum):
    """Type of file system event."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileEvent:
    """Represents a file system event."""
    event_type: FileEventType
    path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    old_path: Optional[str] = None  # For move events


@dataclass
class WatchConfig:
    """Configuration for a file watch."""
    path: str
    recursive: bool = True
    patterns: List[str] = field(default_factory=lambda: ["*"])
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.pyc", "__pycache__", ".git", "node_modules", "*.swp", "*.tmp"
    ])
    debounce_seconds: float = 0.5


class FileWatcher:
    """
    File system watcher for monitoring file changes.
    
    Uses polling-based approach for cross-platform compatibility.
    For production use, consider using watchdog library.
    """
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize file watcher.
        
        Args:
            workspace_root: Root directory for relative paths
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._watches: Dict[int, WatchConfig] = {}
        self._file_states: Dict[int, Dict[str, float]] = {}  # path -> mtime
        self._event_queues: Dict[int, Queue] = {}
        self._watch_threads: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}
        self._next_watch_id = 1
        self._lock = threading.Lock()
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to workspace root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _matches_pattern(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any of the patterns."""
        name = os.path.basename(path)
        return any(fnmatch.fnmatch(name, p) for p in patterns)
    
    def _should_watch(self, path: str, config: WatchConfig) -> bool:
        """Check if a file should be watched based on config."""
        if self._matches_pattern(path, config.ignore_patterns):
            return False
        return self._matches_pattern(path, config.patterns)
    
    def _scan_directory(self, path: Path, recursive: bool) -> Dict[str, float]:
        """Scan directory and return file mtimes."""
        result = {}
        try:
            if path.is_file():
                result[str(path)] = path.stat().st_mtime
            elif path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        result[str(item)] = item.stat().st_mtime
                    elif item.is_dir() and recursive:
                        result.update(self._scan_directory(item, recursive))
        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"Error scanning {path}: {e}")
        return result
    
    def _watch_loop(self, watch_id: int) -> None:
        """Main watch loop for a single watch."""
        config = self._watches.get(watch_id)
        if not config:
            return
        
        stop_event = self._stop_events[watch_id]
        event_queue = self._event_queues[watch_id]
        path = self._resolve_path(config.path)
        
        # Initial scan
        current_state = {
            k: v for k, v in self._scan_directory(path, config.recursive).items()
            if self._should_watch(k, config)
        }
        self._file_states[watch_id] = current_state.copy()
        
        last_events: Dict[str, float] = {}  # For debouncing
        
        while not stop_event.is_set():
            try:
                # Scan current state
                new_state = {
                    k: v for k, v in self._scan_directory(path, config.recursive).items()
                    if self._should_watch(k, config)
                }
                
                current_time = time.time()
                old_state = self._file_states[watch_id]
                
                # Detect changes
                for file_path, mtime in new_state.items():
                    if file_path not in old_state:
                        # New file
                        if current_time - last_events.get(file_path, 0) > config.debounce_seconds:
                            event_queue.put(FileEvent(FileEventType.CREATED, file_path))
                            last_events[file_path] = current_time
                    elif mtime > old_state[file_path]:
                        # Modified file
                        if current_time - last_events.get(file_path, 0) > config.debounce_seconds:
                            event_queue.put(FileEvent(FileEventType.MODIFIED, file_path))
                            last_events[file_path] = current_time

                # Detect deleted files
                for file_path in old_state:
                    if file_path not in new_state:
                        if current_time - last_events.get(file_path, 0) > config.debounce_seconds:
                            event_queue.put(FileEvent(FileEventType.DELETED, file_path))
                            last_events[file_path] = current_time

                # Update state
                self._file_states[watch_id] = new_state.copy()

            except Exception as e:
                logger.error(f"Error in watch loop: {e}")

            # Poll interval
            stop_event.wait(1.0)

    def start_watch(self, config: WatchConfig) -> int:
        """
        Start watching a path for changes.

        Args:
            config: Watch configuration

        Returns:
            Watch ID for managing the watch
        """
        with self._lock:
            watch_id = self._next_watch_id
            self._next_watch_id += 1

            self._watches[watch_id] = config
            self._event_queues[watch_id] = Queue()
            self._stop_events[watch_id] = threading.Event()

            thread = threading.Thread(
                target=self._watch_loop,
                args=(watch_id,),
                daemon=True
            )
            thread.start()
            self._watch_threads[watch_id] = thread

            logger.info(f"Started watch {watch_id} on {config.path}")
            return watch_id

    def stop_watch(self, watch_id: int) -> bool:
        """
        Stop a file watch.

        Args:
            watch_id: The watch ID to stop

        Returns:
            True if watch was stopped
        """
        with self._lock:
            if watch_id not in self._watches:
                return False

            self._stop_events[watch_id].set()

            # Wait for thread to finish
            thread = self._watch_threads.get(watch_id)
            if thread:
                thread.join(timeout=2.0)

            # Clean up
            del self._watches[watch_id]
            del self._event_queues[watch_id]
            del self._stop_events[watch_id]
            if watch_id in self._watch_threads:
                del self._watch_threads[watch_id]
            if watch_id in self._file_states:
                del self._file_states[watch_id]

            logger.info(f"Stopped watch {watch_id}")
            return True

    def get_events(self, watch_id: int, max_events: int = 100) -> List[FileEvent]:
        """
        Get pending events from a watch.

        Args:
            watch_id: The watch ID
            max_events: Maximum events to return

        Returns:
            List of file events
        """
        queue = self._event_queues.get(watch_id)
        if not queue:
            return []

        events = []
        while len(events) < max_events:
            try:
                from queue import Empty
                event = queue.get_nowait()
                events.append(event)
            except Empty:
                break

        return events

    def list_watches(self) -> List[Dict]:
        """
        List all active watches.

        Returns:
            List of watch info dictionaries
        """
        with self._lock:
            return [
                {
                    "watch_id": wid,
                    "path": config.path,
                    "recursive": config.recursive,
                    "patterns": config.patterns
                }
                for wid, config in self._watches.items()
            ]


# Factory function
_watcher_instance: Optional[FileWatcher] = None


def get_file_watcher(workspace_root: str = None) -> FileWatcher:
    """
    Get or create a FileWatcher instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        FileWatcher instance
    """
    global _watcher_instance
    if _watcher_instance is None or workspace_root is not None:
        _watcher_instance = FileWatcher(workspace_root=workspace_root)
    return _watcher_instance