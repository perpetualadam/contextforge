"""
Tests for the Terminal Executor service.
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.terminal_executor.app import app, CommandRequest, ALLOWED_COMMANDS, DANGEROUS_PATTERNS


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCommandValidation:
    """Test command validation logic."""
    
    def test_allowed_commands(self):
        """Test that allowed commands pass validation."""
        valid_commands = [
            "npm install",
            "python -m pytest",
            "git status",
            "docker ps",
            "ls -la",
            "grep -r 'pattern' .",
        ]
        
        for command in valid_commands:
            request = CommandRequest(command=command)
            assert request.command == command
    
    def test_dangerous_commands_rejected(self):
        """Test that dangerous commands are rejected."""
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf *",
            "chmod 777 /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
            "shutdown now",
            "reboot",
            "kill -9 1",
        ]
        
        for command in dangerous_commands:
            with pytest.raises(ValueError):
                CommandRequest(command=command)
    
    def test_disallowed_commands_rejected(self):
        """Test that commands not in allowed list are rejected."""
        disallowed_commands = [
            "nc -l 1234",  # netcat
            "telnet example.com",
            "ssh user@host",
            "ftp example.com",
        ]
        
        for command in disallowed_commands:
            with pytest.raises(ValueError):
                CommandRequest(command=command)
    
    def test_empty_command_rejected(self):
        """Test that empty commands are rejected."""
        with pytest.raises(ValueError):
            CommandRequest(command="")
        
        with pytest.raises(ValueError):
            CommandRequest(command="   ")


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "terminal-executor"
        assert "timestamp" in data
        assert "active_processes" in data


class TestAllowedCommandsEndpoint:
    """Test allowed commands endpoint."""
    
    def test_get_allowed_commands(self, client):
        """Test getting allowed commands list."""
        response = client.get("/allowed-commands")
        assert response.status_code == 200
        
        data = response.json()
        assert "allowed_commands" in data
        assert "dangerous_patterns" in data
        assert isinstance(data["allowed_commands"], list)
        assert isinstance(data["dangerous_patterns"], list)
        
        # Check that some expected commands are in the list
        assert "npm" in data["allowed_commands"]
        assert "python" in data["allowed_commands"]
        assert "git" in data["allowed_commands"]


class TestCommandExecution:
    """Test command execution functionality."""
    
    def test_execute_simple_command(self, client):
        """Test executing a simple command."""
        response = client.post("/execute", json={
            "command": "echo 'Hello World'",
            "timeout": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["command"] == "echo 'Hello World'"
        assert data["exit_code"] == 0
        assert "Hello World" in data["stdout"]
        assert data["stderr"] == ""
        assert data["execution_time"] > 0
        assert "timestamp" in data
    
    def test_execute_command_with_working_directory(self, client):
        """Test executing command with specific working directory."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            response = client.post("/execute", json={
                "command": "pwd",
                "working_directory": temp_dir,
                "timeout": 10
            })
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["exit_code"] == 0
            assert temp_dir in data["stdout"]
    
    def test_execute_failing_command(self, client):
        """Test executing a command that fails."""
        response = client.post("/execute", json={
            "command": "python -c 'import nonexistent_module'",
            "timeout": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["command"] == "python -c 'import nonexistent_module'"
        assert data["exit_code"] != 0
        assert "ModuleNotFoundError" in data["stderr"] or "ImportError" in data["stderr"]
    
    def test_execute_command_with_environment(self, client):
        """Test executing command with custom environment variables."""
        response = client.post("/execute", json={
            "command": "python -c 'import os; print(os.environ.get(\"TEST_VAR\", \"not_found\"))'",
            "environment": {"TEST_VAR": "test_value"},
            "timeout": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exit_code"] == 0
        assert "test_value" in data["stdout"]
    
    def test_invalid_working_directory(self, client):
        """Test that invalid working directory is rejected."""
        response = client.post("/execute", json={
            "command": "echo test",
            "working_directory": "/nonexistent/directory",
            "timeout": 10
        })
        
        assert response.status_code == 422
        assert "Working directory does not exist" in response.json()["detail"][0]["msg"]
    
    def test_dangerous_command_rejected(self, client):
        """Test that dangerous commands are rejected."""
        response = client.post("/execute", json={
            "command": "rm -rf /tmp/test",
            "timeout": 10
        })
        
        assert response.status_code == 422
        assert "dangerous pattern" in response.json()["detail"][0]["msg"]
    
    def test_disallowed_command_rejected(self, client):
        """Test that disallowed commands are rejected."""
        response = client.post("/execute", json={
            "command": "nc -l 1234",
            "timeout": 10
        })
        
        assert response.status_code == 422
        assert "not in the allowed list" in response.json()["detail"][0]["msg"]


class TestProcessManagement:
    """Test process management functionality."""
    
    def test_get_processes_empty(self, client):
        """Test getting processes when none are running."""
        response = client.get("/processes")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_kill_nonexistent_process(self, client):
        """Test killing a process that doesn't exist."""
        response = client.delete("/processes/99999")
        assert response.status_code == 404
        assert "Process not found" in response.json()["detail"]


class TestStreamingExecution:
    """Test streaming command execution."""
    
    def test_execute_stream_endpoint_exists(self, client):
        """Test that streaming endpoint exists and accepts requests."""
        # Note: Full streaming test would require more complex setup
        # This just tests that the endpoint exists and validates input
        response = client.post("/execute-stream", json={
            "command": "echo test",
            "timeout": 5
        })
        
        # Should return streaming response or validation error
        assert response.status_code in [200, 422]


@pytest.mark.asyncio
class TestAsyncFunctionality:
    """Test async functionality."""
    
    async def test_command_validation_async(self):
        """Test command validation in async context."""
        # Test that validation works in async context
        request = CommandRequest(command="echo test")
        assert request.command == "echo test"
        
        with pytest.raises(ValueError):
            CommandRequest(command="rm -rf /")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
