"""
Tests for ContextForge Process Streamer.

Copyright (c) 2025 ContextForge
"""

import os
import sys
import pytest
import tempfile
import shutil
import time
from pathlib import Path

from services.tools.process_streamer import (
    ProcessStreamer,
    StreamConfig,
    StreamLine,
    get_process_streamer
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def streamer(temp_workspace):
    """Create a ProcessStreamer instance with temp workspace."""
    return ProcessStreamer(workspace_root=temp_workspace)


class TestProcessStreamer:
    """Tests for process streaming functionality."""
    
    def test_start_stream(self, streamer, temp_workspace):
        """Test starting a stream."""
        if sys.platform == 'win32':
            cmd = 'echo Hello'
        else:
            cmd = 'echo "Hello"'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        
        stream_id = streamer.start_stream(config)
        
        assert stream_id > 0
        time.sleep(0.5)
        
        # Should complete quickly
        assert not streamer.is_running(stream_id)
    
    def test_read_lines(self, streamer, temp_workspace):
        """Test reading lines from a stream."""
        if sys.platform == 'win32':
            cmd = 'echo Line1 && echo Line2 && echo Line3'
        else:
            cmd = 'echo "Line1" && echo "Line2" && echo "Line3"'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        time.sleep(0.5)
        
        lines = streamer.read_lines(stream_id)
        
        assert len(lines) >= 1
        assert all(isinstance(l, StreamLine) for l in lines)
    
    def test_iter_lines(self, streamer, temp_workspace):
        """Test iterating over lines."""
        if sys.platform == 'win32':
            cmd = 'echo A && echo B'
        else:
            cmd = 'echo "A" && echo "B"'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        lines = list(streamer.iter_lines(stream_id))
        
        assert len(lines) >= 2
    
    def test_get_buffer(self, streamer, temp_workspace):
        """Test getting buffered output."""
        if sys.platform == 'win32':
            cmd = 'echo Buffered'
        else:
            cmd = 'echo "Buffered"'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        time.sleep(0.5)
        
        # Read to buffer
        streamer.read_lines(stream_id)
        
        buffer = streamer.get_buffer(stream_id)
        
        assert len(buffer) >= 1
    
    def test_stop_stream(self, streamer, temp_workspace):
        """Test stopping a stream."""
        if sys.platform == 'win32':
            cmd = 'ping -n 100 127.0.0.1'
        else:
            cmd = 'sleep 100'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        time.sleep(0.5)
        assert streamer.is_running(stream_id)
        
        result = streamer.stop_stream(stream_id)
        
        assert result is True
        assert stream_id not in [s['stream_id'] for s in streamer.list_streams()]
    
    def test_return_code(self, streamer, temp_workspace):
        """Test getting return code."""
        if sys.platform == 'win32':
            cmd = 'echo done'
        else:
            cmd = 'echo done'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        time.sleep(0.5)
        
        # Wait for completion
        while streamer.is_running(stream_id):
            time.sleep(0.1)
        
        rc = streamer.get_return_code(stream_id)
        
        assert rc == 0
    
    def test_list_streams(self, streamer, temp_workspace):
        """Test listing streams."""
        if sys.platform == 'win32':
            cmd = 'echo test'
        else:
            cmd = 'echo test'
        
        config = StreamConfig(command=cmd, cwd=temp_workspace)
        stream_id = streamer.start_stream(config)
        
        streams = streamer.list_streams()
        
        assert len(streams) == 1
        assert streams[0]['stream_id'] == stream_id
        assert streams[0]['command'] == cmd


class TestLineCallback:
    """Tests for line callback functionality."""
    
    def test_callback_invoked(self, streamer, temp_workspace):
        """Test that callbacks are invoked for each line."""
        received_lines = []
        
        def callback(line: str):
            received_lines.append(line)
        
        if sys.platform == 'win32':
            cmd = 'echo CallbackTest'
        else:
            cmd = 'echo "CallbackTest"'
        
        config = StreamConfig(
            command=cmd,
            cwd=temp_workspace,
            line_callback=callback
        )
        stream_id = streamer.start_stream(config)
        
        time.sleep(0.5)
        
        assert len(received_lines) >= 1
        assert any("CallbackTest" in line for line in received_lines)

