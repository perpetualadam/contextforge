"""
Command Sandbox for Phase 6: Security Hardening.

Provides command validation and sandboxing to prevent:
- Dangerous command execution (rm -rf, format, etc.)
- Path traversal attacks (../, ../../, etc.)
- Unauthorized file access
- Command injection

Copyright (c) 2025 ContextForge
"""

import os
import re
from typing import List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class CommandRisk(Enum):
    """Risk level for commands."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CommandValidationResult:
    """Result of command validation."""
    allowed: bool
    risk_level: CommandRisk
    reason: str
    sanitized_command: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class CommandSandbox:
    """
    Command sandbox for validating and restricting dangerous commands.
    
    Features:
    - Blacklist dangerous commands
    - Whitelist safe commands
    - Path traversal prevention
    - Command injection detection
    - Execution logging
    """
    
    # Critical commands that should never be allowed
    CRITICAL_COMMANDS = {
        'rm', 'del', 'format', 'mkfs', 'dd', 'fdisk',
        'shutdown', 'reboot', 'halt', 'poweroff',
        'kill', 'killall', 'pkill',
        'chmod', 'chown', 'chgrp',
        'sudo', 'su', 'doas',
        'curl', 'wget', 'nc', 'netcat',  # Network commands
        'eval', 'exec',  # Code execution
    }
    
    # High-risk commands that require careful validation
    HIGH_RISK_COMMANDS = {
        'mv', 'move', 'cp', 'copy', 'xcopy',
        'git', 'svn', 'hg',  # Version control (can modify files)
        'npm', 'pip', 'cargo', 'go',  # Package managers
        'docker', 'kubectl', 'podman',  # Container commands
    }
    
    # Medium-risk commands
    MEDIUM_RISK_COMMANDS = {
        'cat', 'type', 'more', 'less', 'head', 'tail',
        'grep', 'find', 'locate',
        'tar', 'zip', 'unzip', 'gzip', 'gunzip',
    }
    
    # Safe commands (read-only operations)
    SAFE_COMMANDS = {
        'ls', 'dir', 'pwd', 'cd', 'echo', 'printf',
        'date', 'whoami', 'hostname',
        'git status', 'git log', 'git diff', 'git show',
    }
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.',  # Parent directory
        r'~/',  # Home directory
        r'/etc/',  # System config
        r'/root/',  # Root home
        r'/sys/',  # System files
        r'/proc/',  # Process files
        r'C:\\Windows',  # Windows system
        r'C:\\Program Files',  # Windows programs
    ]
    
    # Command injection patterns
    INJECTION_PATTERNS = [
        r'[;&|`$]',  # Shell metacharacters
        r'\$\(',  # Command substitution
        r'>\s*/',  # Redirect to root
    ]
    
    def __init__(self, workspace_root: Optional[str] = None, allowed_paths: Optional[List[str]] = None):
        """
        Initialize command sandbox.
        
        Args:
            workspace_root: Root directory for file operations (default: current directory)
            allowed_paths: List of allowed paths (default: workspace_root only)
        """
        self.workspace_root = workspace_root or os.getcwd()
        self.allowed_paths = allowed_paths or [self.workspace_root]
        self._execution_log: List[dict] = []
        
        logger.info("CommandSandbox initialized", workspace_root=self.workspace_root)
    
    def validate_command(self, command: str) -> CommandValidationResult:
        """
        Validate a command before execution.
        
        Args:
            command: Command string to validate
            
        Returns:
            CommandValidationResult with validation details
        """
        command = command.strip()
        
        # Extract base command
        base_command = self._extract_base_command(command)
        
        # Check critical commands
        if base_command in self.CRITICAL_COMMANDS:
            logger.warning("Critical command blocked", command=command, base=base_command)
            return CommandValidationResult(
                allowed=False,
                risk_level=CommandRisk.CRITICAL,
                reason=f"Critical command '{base_command}' is not allowed"
            )

        # Check for command injection
        injection_result = self._check_injection(command)
        if not injection_result.allowed:
            return injection_result

        # Check for path traversal
        path_result = self._check_path_traversal(command)
        if not path_result.allowed:
            return path_result

        # Determine risk level
        if base_command in self.HIGH_RISK_COMMANDS:
            risk_level = CommandRisk.HIGH
            warnings = [f"High-risk command '{base_command}' - use with caution"]
        elif base_command in self.MEDIUM_RISK_COMMANDS:
            risk_level = CommandRisk.MEDIUM
            warnings = [f"Medium-risk command '{base_command}'"]
        elif base_command in self.SAFE_COMMANDS or command in self.SAFE_COMMANDS:
            risk_level = CommandRisk.SAFE
            warnings = []
        else:
            risk_level = CommandRisk.LOW
            warnings = [f"Unknown command '{base_command}' - proceeding with caution"]

        logger.info("Command validated", command=command, risk=risk_level.value)

        return CommandValidationResult(
            allowed=True,
            risk_level=risk_level,
            reason="Command passed validation",
            sanitized_command=command,
            warnings=warnings
        )

    def validate_path(self, path: str) -> Tuple[bool, str]:
        """
        Validate a file path.

        Args:
            path: File path to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Normalize path
        try:
            normalized = os.path.normpath(os.path.abspath(path))
        except Exception as e:
            return False, f"Invalid path: {e}"

        # Check if path is within allowed paths
        for allowed_path in self.allowed_paths:
            allowed_normalized = os.path.normpath(os.path.abspath(allowed_path))
            if normalized.startswith(allowed_normalized):
                return True, "Path is within allowed directory"

        return False, f"Path '{path}' is outside allowed directories"

    def log_execution(self, command: str, result: CommandValidationResult, success: bool = True):
        """
        Log command execution.

        Args:
            command: Command that was executed
            result: Validation result
            success: Whether execution succeeded
        """
        log_entry = {
            "command": command,
            "risk_level": result.risk_level.value,
            "allowed": result.allowed,
            "success": success,
            "reason": result.reason,
            "warnings": result.warnings
        }
        self._execution_log.append(log_entry)

        logger.info("Command execution logged", **log_entry)

    def get_execution_log(self) -> List[dict]:
        """Get command execution log."""
        return self._execution_log.copy()

    def clear_log(self):
        """Clear execution log."""
        self._execution_log.clear()
        logger.info("Execution log cleared")

    def _extract_base_command(self, command: str) -> str:
        """Extract base command from command string."""
        # Remove leading/trailing whitespace
        command = command.strip()

        # Split on whitespace and get first token
        parts = command.split()
        if not parts:
            return ""

        base = parts[0]

        # Remove path if present (e.g., /usr/bin/git -> git)
        if '/' in base or '\\' in base:
            base = os.path.basename(base)

        # Remove extension if present (e.g., git.exe -> git)
        base = os.path.splitext(base)[0]

        return base.lower()

    def _check_injection(self, command: str) -> CommandValidationResult:
        """Check for command injection patterns."""
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, command):
                logger.warning("Command injection detected", command=command, pattern=pattern)
                return CommandValidationResult(
                    allowed=False,
                    risk_level=CommandRisk.CRITICAL,
                    reason=f"Potential command injection detected: {pattern}"
                )

        return CommandValidationResult(
            allowed=True,
            risk_level=CommandRisk.SAFE,
            reason="No injection patterns detected"
        )

    def _check_path_traversal(self, command: str) -> CommandValidationResult:
        """Check for path traversal patterns."""
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning("Path traversal detected", command=command, pattern=pattern)
                return CommandValidationResult(
                    allowed=False,
                    risk_level=CommandRisk.HIGH,
                    reason=f"Potential path traversal detected: {pattern}"
                )

        return CommandValidationResult(
            allowed=True,
            risk_level=CommandRisk.SAFE,
            reason="No path traversal detected"
        )


# Singleton instance
_sandbox_instance: Optional[CommandSandbox] = None


def get_command_sandbox(workspace_root: Optional[str] = None) -> CommandSandbox:
    """Get singleton CommandSandbox instance."""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = CommandSandbox(workspace_root=workspace_root)
    return _sandbox_instance

