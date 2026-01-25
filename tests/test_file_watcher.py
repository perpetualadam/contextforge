"""
Tests for ContextForge File Watcher.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
import tempfile
import shutil
import time
from pathlib import Path

from services.tools.file_watcher import (
    FileWatcher,
    FileEvent,
    FileEventType,
    WatchConfig,
    get_file_watcher
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def watcher(temp_workspace):
    """Create a FileWatcher instance with temp workspace."""
    return FileWatcher(workspace_root=temp_workspace)


class TestFileWatcher:
    """Tests for file watching functionality."""
    
    def test_start_watch(self, watcher, temp_workspace):
        """Test starting a file watch."""
        config = WatchConfig(path=temp_workspace)
        
        watch_id = watcher.start_watch(config)
        
        assert watch_id > 0
        assert len(watcher.list_watches()) == 1
        
        # Clean up
        watcher.stop_watch(watch_id)
    
    def test_stop_watch(self, watcher, temp_workspace):
        """Test stopping a file watch."""
        config = WatchConfig(path=temp_workspace)
        watch_id = watcher.start_watch(config)
        
        result = watcher.stop_watch(watch_id)
        
        assert result is True
        assert len(watcher.list_watches()) == 0
    
    def test_detect_file_creation(self, watcher, temp_workspace):
        """Test detecting new file creation."""
        config = WatchConfig(
            path=temp_workspace,
            debounce_seconds=0.1
        )
        watch_id = watcher.start_watch(config)
        
        # Wait for initial scan
        time.sleep(0.5)
        
        # Create a new file
        test_file = Path(temp_workspace) / "new_file.txt"
        test_file.write_text("Hello")
        
        # Wait for detection
        time.sleep(1.5)
        
        events = watcher.get_events(watch_id)
        
        assert len(events) >= 1
        assert any(e.event_type == FileEventType.CREATED for e in events)
        
        # Clean up
        watcher.stop_watch(watch_id)
    
    def test_detect_file_modification(self, watcher, temp_workspace):
        """Test detecting file modification."""
        # Create initial file
        test_file = Path(temp_workspace) / "existing.txt"
        test_file.write_text("Initial content")
        
        config = WatchConfig(
            path=temp_workspace,
            debounce_seconds=0.1
        )
        watch_id = watcher.start_watch(config)
        
        # Wait for initial scan
        time.sleep(0.5)
        
        # Modify the file
        test_file.write_text("Modified content")
        
        # Wait for detection
        time.sleep(1.5)
        
        events = watcher.get_events(watch_id)
        
        assert len(events) >= 1
        assert any(e.event_type == FileEventType.MODIFIED for e in events)
        
        # Clean up
        watcher.stop_watch(watch_id)
    
    def test_detect_file_deletion(self, watcher, temp_workspace):
        """Test detecting file deletion."""
        # Create initial file
        test_file = Path(temp_workspace) / "to_delete.txt"
        test_file.write_text("To be deleted")
        
        config = WatchConfig(
            path=temp_workspace,
            debounce_seconds=0.1
        )
        watch_id = watcher.start_watch(config)
        
        # Wait for initial scan
        time.sleep(0.5)
        
        # Delete the file
        test_file.unlink()
        
        # Wait for detection
        time.sleep(1.5)
        
        events = watcher.get_events(watch_id)
        
        assert len(events) >= 1
        assert any(e.event_type == FileEventType.DELETED for e in events)
        
        # Clean up
        watcher.stop_watch(watch_id)
    
    def test_pattern_filtering(self, watcher, temp_workspace):
        """Test that patterns filter watched files."""
        config = WatchConfig(
            path=temp_workspace,
            patterns=["*.py"],
            debounce_seconds=0.1
        )
        watch_id = watcher.start_watch(config)
        
        # Wait for initial scan
        time.sleep(0.5)
        
        # Create a non-matching file
        txt_file = Path(temp_workspace) / "not_watched.txt"
        txt_file.write_text("Text file")
        
        # Create a matching file
        py_file = Path(temp_workspace) / "watched.py"
        py_file.write_text("# Python file")
        
        # Wait for detection
        time.sleep(1.5)
        
        events = watcher.get_events(watch_id)
        
        # Should only have event for .py file
        py_events = [e for e in events if "watched.py" in e.path]
        txt_events = [e for e in events if "not_watched.txt" in e.path]
        
        assert len(py_events) >= 1
        assert len(txt_events) == 0
        
        # Clean up
        watcher.stop_watch(watch_id)

