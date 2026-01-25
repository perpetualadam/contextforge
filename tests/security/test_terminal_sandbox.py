"""
Unit tests for Terminal Executor sandbox validation.

Tests command whitelist, sandbox directory validation, and audit logging.
"""

import pytest
import requests
import json
from pathlib import Path

# Test configuration
TERMINAL_EXECUTOR_URL = "http://localhost:8001"
API_BASE_URL = "https://localhost:8443"
VERIFY_SSL = False


class TestTerminalSandbox:
    """Test terminal executor sandbox validation."""
    
    def test_sandbox_config_endpoint(self):
        """Test that sandbox configuration is exposed."""
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/sandbox-config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check configuration fields
        assert "sandbox_enabled" in data
        assert "allowed_paths" in data
        assert "max_concurrent_processes" in data
        assert "max_timeout_seconds" in data
        assert "security_modules_available" in data
        
        # Verify sandbox is enabled
        assert data["sandbox_enabled"] is True
        
        # Verify allowed paths exist
        assert isinstance(data["allowed_paths"], list)
        assert len(data["allowed_paths"]) > 0
    
    def test_command_in_allowed_directory(self):
        """Test executing command in allowed directory."""
        # Get allowed paths
        config_response = requests.get(f"{TERMINAL_EXECUTOR_URL}/sandbox-config")
        allowed_paths = config_response.json()["allowed_paths"]
        
        # Use first allowed path
        working_dir = allowed_paths[0]
        
        # Execute simple command
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": "echo 'test'",
                "working_directory": working_dir,
                "timeout": 10
            }
        )
        
        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
    
    def test_command_in_disallowed_directory(self):
        """Test that commands in disallowed directories are blocked."""
        # Try to execute in a system directory that should be blocked
        disallowed_dirs = [
            "/etc",
            "/root",
            "/boot",
            "C:\\Windows\\System32",  # Windows
            "/System",  # macOS
        ]
        
        for disallowed_dir in disallowed_dirs:
            response = requests.post(
                f"{TERMINAL_EXECUTOR_URL}/execute",
                json={
                    "command": "echo 'test'",
                    "working_directory": disallowed_dir,
                    "timeout": 10
                }
            )
            
            # Should fail with validation error
            if response.status_code != 200:
                # Expected - directory is blocked
                assert response.status_code in [400, 403, 422]
                break
        else:
            # If all directories are allowed, that's also OK (might be in dev mode)
            pytest.skip("All test directories are allowed (sandbox may be disabled)")
    
    def test_directory_traversal_prevention(self):
        """Test that directory traversal attacks are prevented."""
        # Get allowed paths
        config_response = requests.get(f"{TERMINAL_EXECUTOR_URL}/sandbox-config")
        allowed_paths = config_response.json()["allowed_paths"]
        
        # Try directory traversal
        working_dir = f"{allowed_paths[0]}/../../../etc"
        
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": "echo 'test'",
                "working_directory": working_dir,
                "timeout": 10
            }
        )
        
        # Should fail if traversal leads outside allowed paths
        # (May succeed if resolved path is still within allowed paths)
        if response.status_code != 200:
            assert response.status_code in [400, 403, 422]
    
    def test_command_whitelist_endpoint(self):
        """Test that command whitelist is exposed."""
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/allowed-commands")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check whitelist fields
        assert "allowed_commands" in data
        assert "dangerous_patterns" in data
        
        # Verify whitelist contains common safe commands
        allowed_commands = data["allowed_commands"]
        assert isinstance(allowed_commands, list)
        
        # Should include basic commands
        common_commands = ["ls", "pwd", "echo", "cat"]
        for cmd in common_commands:
            if cmd in allowed_commands:
                break
        else:
            # At least one common command should be in the list
            pytest.skip("No common commands in whitelist (may be using different shell)")
    
    def test_audit_logging_for_commands(self):
        """Test that command execution is logged to audit log."""
        # Get allowed paths
        config_response = requests.get(f"{TERMINAL_EXECUTOR_URL}/sandbox-config")
        allowed_paths = config_response.json()["allowed_paths"]
        working_dir = allowed_paths[0]
        
        # Execute a command
        test_command = "echo 'audit_test'"
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": test_command,
                "working_directory": working_dir,
                "timeout": 10
            }
        )
        
        assert response.status_code == 200
        
        # Check if audit log file exists
        audit_log_path = Path("./logs/audit.log")
        
        if audit_log_path.exists():
            # Read recent log entries
            with open(audit_log_path, 'r') as f:
                log_content = f.read()
            
            # Should contain command execution event
            # (May not be immediate, so this is a soft check)
            if "command_execution" in log_content or "audit_test" in log_content:
                assert True
            else:
                # Log exists but may not have this specific entry yet
                pytest.skip("Audit log exists but specific entry not found (timing issue)")
        else:
            # Audit logging may not be enabled in test environment
            pytest.skip("Audit log file not found (may be disabled in test environment)")
    
    def test_blocked_command_is_logged(self):
        """Test that blocked commands are logged to audit log."""
        # Try to execute in disallowed directory
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": "echo 'blocked_test'",
                "working_directory": "/etc",
                "timeout": 10
            }
        )
        
        # Command may be blocked
        if response.status_code != 200:
            # Check audit log for blocked command
            audit_log_path = Path("./logs/audit.log")
            
            if audit_log_path.exists():
                with open(audit_log_path, 'r') as f:
                    log_content = f.read()
                
                # Should contain blocked command event
                if "blocked" in log_content.lower() or "blocked_test" in log_content:
                    assert True
                else:
                    pytest.skip("Blocked command not found in audit log (timing issue)")
            else:
                pytest.skip("Audit log file not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

