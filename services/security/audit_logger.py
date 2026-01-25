"""
Audit Logging Module.

Provides comprehensive audit logging for security-sensitive operations.

Copyright (c) 2025 ContextForge
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Audit logging configuration
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "true").lower() in ("true", "1", "yes")
AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", "logs/audit.log")
AUDIT_LOG_TO_DB = os.getenv("AUDIT_LOG_TO_DB", "false").lower() in ("true", "1", "yes")


class AuditEventType(str, Enum):
    """Audit event types."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    
    # API events
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Command execution events
    COMMAND_EXECUTED = "command_executed"
    COMMAND_BLOCKED = "command_blocked"
    COMMAND_FAILED = "command_failed"
    
    # Tool/MCP events
    TOOL_CALLED = "tool_called"
    TOOL_ERROR = "tool_error"
    
    # Data events
    DATA_ACCESSED = "data_accessed"
    DATA_MODIFIED = "data_modified"
    DATA_DELETED = "data_deleted"
    
    # Security events
    CSRF_VIOLATION = "csrf_violation"
    INJECTION_ATTEMPT = "injection_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Configuration events
    CONFIG_CHANGED = "config_changed"
    SECRET_ACCESSED = "secret_accessed"


class AuditEvent(BaseModel):
    """Audit event model."""
    event_id: str = Field(default_factory=lambda: f"audit_{int(datetime.utcnow().timestamp() * 1000)}")
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    username: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: str = "success"  # success, failure, blocked
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"  # debug, info, warning, error, critical


class AuditLogger:
    """Audit logger for security events."""
    
    def __init__(self):
        self.enabled = AUDIT_LOG_ENABLED
        self.log_file = AUDIT_LOG_FILE
        self.log_to_db = AUDIT_LOG_TO_DB
        
        # Ensure log directory exists
        if self.enabled and self.log_file:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event."""
        if not self.enabled:
            return
        
        # Log to file
        if self.log_file:
            self._log_to_file(event)
        
        # Log to database (if enabled)
        if self.log_to_db:
            self._log_to_database(event)
        
        # Log to standard logger for critical events
        if event.severity in ("error", "critical"):
            logger.warning(f"AUDIT: {event.event_type.value} - {event.details}")
    
    def _log_to_file(self, event: AuditEvent) -> None:
        """Write audit event to file."""
        try:
            with open(self.log_file, "a") as f:
                log_entry = {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "user_id": event.user_id,
                    "username": event.username,
                    "client_ip": event.client_ip,
                    "user_agent": event.user_agent,
                    "resource": event.resource,
                    "action": event.action,
                    "result": event.result,
                    "severity": event.severity,
                    "details": event.details
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def _log_to_database(self, event: AuditEvent) -> None:
        """Write audit event to database."""
        try:
            # TODO: Implement database logging
            # This would use the persistence service to store audit events
            pass
        except Exception as e:
            logger.error(f"Failed to write audit log to database: {e}")
    
    def log_api_request(
        self,
        user_id: Optional[str],
        username: Optional[str],
        client_ip: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_agent: Optional[str] = None
    ) -> None:
        """Log API request."""
        event = AuditEvent(
            event_type=AuditEventType.API_REQUEST,
            user_id=user_id,
            username=username,
            client_ip=client_ip,
            user_agent=user_agent,
            resource=path,
            action=method,
            result="success" if status_code < 400 else "failure",
            severity="info" if status_code < 400 else "warning",
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms
            }
        )
        self.log_event(event)

    def log_command_execution(
        self,
        user_id: Optional[str],
        username: Optional[str],
        command: str,
        working_dir: str,
        exit_code: int,
        blocked: bool = False
    ) -> None:
        """Log command execution."""
        event_type = AuditEventType.COMMAND_BLOCKED if blocked else AuditEventType.COMMAND_EXECUTED

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            username=username,
            resource=working_dir,
            action="execute_command",
            result="blocked" if blocked else ("success" if exit_code == 0 else "failure"),
            severity="warning" if blocked else "info",
            details={
                "command": command[:200],  # Truncate long commands
                "working_dir": working_dir,
                "exit_code": exit_code,
                "blocked": blocked
            }
        )
        self.log_event(event)

    def log_tool_call(
        self,
        user_id: Optional[str],
        username: Optional[str],
        tool_name: str,
        parameters: Dict[str, Any],
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Log MCP tool call."""
        event = AuditEvent(
            event_type=AuditEventType.TOOL_CALLED if success else AuditEventType.TOOL_ERROR,
            user_id=user_id,
            username=username,
            resource=tool_name,
            action="call_tool",
            result="success" if success else "failure",
            severity="info" if success else "error",
            details={
                "tool_name": tool_name,
                "parameters": parameters,
                "error": error
            }
        )
        self.log_event(event)

    def log_security_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        username: Optional[str],
        client_ip: Optional[str],
        details: Dict[str, Any],
        severity: str = "warning"
    ) -> None:
        """Log security-related event."""
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            username=username,
            client_ip=client_ip,
            result="blocked",
            severity=severity,
            details=details
        )
        self.log_event(event)


# Singleton instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get singleton audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

