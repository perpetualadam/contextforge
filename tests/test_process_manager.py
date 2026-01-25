"""
Tests for ContextForge Process Manager tools.

Copyright (c) 2025 ContextForge
"""

import os
import sys
import pytest
import tempfile
import shutil
import time
from pathlib import Path

from services.tools.process_manager import (
    ProcessManager,
    LaunchProcessRequest,
    ProcessInfo,
    ProcessResult,
    ProcessState,
    get_process_manager
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def manager(temp_workspace):
    """Create a ProcessManager instance with temp workspace."""
    return ProcessManager(workspace_root=temp_workspace)


class TestLaunchProcess:
    """Tests for process launching functionality."""
    
    def test_launch_simple_command(self, manager, temp_workspace):
        """Test launching a simple command."""
        if sys.platform == 'win32':
            cmd = 'echo Hello World'
        else:
            cmd = 'echo "Hello World"'
        
        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True,
            max_wait_seconds=10
        )
        
        result = manager.launch_process(request)
        
        assert result.success
        assert "Hello" in result.output
        assert result.return_code == 0
        assert result.state == ProcessState.COMPLETED
    
    def test_launch_failing_command(self, manager, temp_workspace):
        """Test launching a command that fails."""
        if sys.platform == 'win32':
            cmd = 'exit 1'
        else:
            cmd = 'exit 1'
        
        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True,
            max_wait_seconds=10
        )
        
        result = manager.launch_process(request)
        
        assert not result.success
        assert result.return_code == 1
        assert result.state == ProcessState.FAILED
    
    def test_launch_background_process(self, manager, temp_workspace):
        """Test launching a background process."""
        if sys.platform == 'win32':
            cmd = 'ping -n 10 127.0.0.1'
        else:
            cmd = 'sleep 10'
        
        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=False
        )
        
        result = manager.launch_process(request)
        
        assert result.success
        assert result.state == ProcessState.RUNNING
        
        # Clean up
        manager.kill_process(result.terminal_id)
    
    def test_launch_invalid_cwd(self, manager, temp_workspace):
        """Test launching with invalid working directory."""
        request = LaunchProcessRequest(
            command='echo test',
            cwd=os.path.join(temp_workspace, 'nonexistent'),
            wait=True
        )
        
        result = manager.launch_process(request)
        
        assert not result.success
        assert "not found" in result.message.lower()
    
    def test_launch_with_timeout(self, manager, temp_workspace):
        """Test process timeout."""
        if sys.platform == 'win32':
            cmd = 'ping -n 100 127.0.0.1'
        else:
            cmd = 'sleep 100'
        
        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True,
            max_wait_seconds=1
        )
        
        result = manager.launch_process(request)
        
        assert result.success  # Timeout is not a failure
        assert result.state == ProcessState.TIMEOUT
        
        # Clean up
        manager.kill_process(result.terminal_id)


class TestReadProcess:
    """Tests for reading process output."""
    
    def test_read_completed_process(self, manager, temp_workspace):
        """Test reading output from completed process."""
        if sys.platform == 'win32':
            cmd = 'echo Line1 && echo Line2'
        else:
            cmd = 'echo "Line1" && echo "Line2"'
        
        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True
        )
        
        launch_result = manager.launch_process(request)
        read_result = manager.read_process(launch_result.terminal_id)
        
        assert read_result.success
        assert "Line1" in read_result.output
        assert "Line2" in read_result.output
    
    def test_read_nonexistent_terminal(self, manager):
        """Test reading from non-existent terminal."""
        result = manager.read_process(9999)

        assert not result.success
        assert "not found" in result.message.lower()


class TestWriteProcess:
    """Tests for writing to process stdin."""

    def test_write_to_terminated_process(self, manager, temp_workspace):
        """Test writing to a terminated process."""
        if sys.platform == 'win32':
            cmd = 'echo done'
        else:
            cmd = 'echo done'

        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True
        )

        launch_result = manager.launch_process(request)
        write_result = manager.write_process(launch_result.terminal_id, "input\n")

        assert not write_result.success
        assert "terminated" in write_result.message.lower()

    def test_write_nonexistent_terminal(self, manager):
        """Test writing to non-existent terminal."""
        result = manager.write_process(9999, "test")

        assert not result.success
        assert "not found" in result.message.lower()


class TestKillProcess:
    """Tests for killing processes."""

    def test_kill_running_process(self, manager, temp_workspace):
        """Test killing a running process."""
        if sys.platform == 'win32':
            cmd = 'ping -n 100 127.0.0.1'
        else:
            cmd = 'sleep 100'

        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=False
        )

        launch_result = manager.launch_process(request)
        time.sleep(0.5)  # Let process start

        kill_result = manager.kill_process(launch_result.terminal_id)

        assert kill_result.success
        assert kill_result.state == ProcessState.KILLED

    def test_kill_already_terminated(self, manager, temp_workspace):
        """Test killing an already terminated process."""
        if sys.platform == 'win32':
            cmd = 'echo done'
        else:
            cmd = 'echo done'

        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True
        )

        launch_result = manager.launch_process(request)
        kill_result = manager.kill_process(launch_result.terminal_id)

        assert kill_result.success
        assert "already terminated" in kill_result.message.lower()

    def test_kill_nonexistent_terminal(self, manager):
        """Test killing non-existent terminal."""
        result = manager.kill_process(9999)

        assert not result.success
        assert "not found" in result.message.lower()


class TestListProcesses:
    """Tests for listing processes."""

    def test_list_empty(self, manager):
        """Test listing when no processes exist."""
        result = manager.list_processes()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_with_processes(self, manager, temp_workspace):
        """Test listing with active processes."""
        if sys.platform == 'win32':
            cmd = 'echo test'
        else:
            cmd = 'echo test'

        request = LaunchProcessRequest(
            command=cmd,
            cwd=temp_workspace,
            wait=True
        )

        manager.launch_process(request)
        result = manager.list_processes()

        assert len(result) == 1
        assert isinstance(result[0], ProcessInfo)
        assert result[0].command == cmd


class TestFactoryFunction:
    """Tests for the get_process_manager factory function."""

    def test_get_manager(self, temp_workspace):
        """Test getting a manager instance."""
        manager = get_process_manager(temp_workspace)

        assert isinstance(manager, ProcessManager)
        assert manager.workspace_root == Path(temp_workspace)

