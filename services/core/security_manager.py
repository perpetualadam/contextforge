"""
Security Manager for Phase 6: Security Hardening.

Unified interface for all security components:
- Command sandboxing
- Prompt injection defense
- Security event logging
- Security status API

Copyright (c) 2025 ContextForge
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

from services.core.command_sandbox import (
    CommandSandbox, CommandValidationResult, CommandRisk, get_command_sandbox
)
from services.core.prompt_guard import (
    PromptGuard, PromptValidationResult, ThreatLevel, get_prompt_guard
)

logger = structlog.get_logger(__name__)


@dataclass
class SecurityEvent:
    """Security event for logging."""
    timestamp: datetime
    event_type: str  # 'command', 'prompt', 'access'
    severity: str  # 'info', 'warning', 'critical'
    description: str
    details: Dict[str, Any]


class SecurityManager:
    """
    Unified security manager for ContextForge.
    
    Features:
    - Command validation and sandboxing
    - Prompt injection detection
    - Security event logging
    - Security status API
    - Integration with EventBus
    """
    
    def __init__(
        self,
        command_sandbox: Optional[CommandSandbox] = None,
        prompt_guard: Optional[PromptGuard] = None,
        event_bus=None
    ):
        """
        Initialize security manager.
        
        Args:
            command_sandbox: Optional CommandSandbox instance
            prompt_guard: Optional PromptGuard instance
            event_bus: Optional EventBus for publishing security events
        """
        self.command_sandbox = command_sandbox or get_command_sandbox()
        self.prompt_guard = prompt_guard or get_prompt_guard()
        self.event_bus = event_bus
        self._security_events: List[SecurityEvent] = []
        
        logger.info("SecurityManager initialized")
    
    def validate_command(self, command: str) -> CommandValidationResult:
        """
        Validate a command before execution.
        
        Args:
            command: Command to validate
            
        Returns:
            CommandValidationResult
        """
        result = self.command_sandbox.validate_command(command)
        
        # Log security event
        severity = self._risk_to_severity(result.risk_level)
        self._log_security_event(
            event_type="command",
            severity=severity,
            description=f"Command validation: {result.reason}",
            details={
                "command": command,
                "allowed": result.allowed,
                "risk_level": result.risk_level.value,
                "warnings": result.warnings
            }
        )
        
        # Publish to event bus if available
        if self.event_bus and not result.allowed:
            self._publish_security_event("command_blocked", {
                "command": command,
                "reason": result.reason,
                "risk_level": result.risk_level.value
            })
        
        return result
    
    def validate_prompt(self, prompt: str, user_id: Optional[str] = None) -> PromptValidationResult:
        """
        Validate a prompt before sending to LLM.
        
        Args:
            prompt: Prompt to validate
            user_id: Optional user identifier
            
        Returns:
            PromptValidationResult
        """
        result = self.prompt_guard.validate_prompt(prompt, user_id)
        
        # Log security event
        severity = self._threat_to_severity(result.threat_level)
        self._log_security_event(
            event_type="prompt",
            severity=severity,
            description=f"Prompt validation: {result.reason}",
            details={
                "prompt_preview": prompt[:100],
                "user_id": user_id,
                "allowed": result.allowed,
                "threat_level": result.threat_level.value,
                "detected_patterns": result.detected_patterns,
                "warnings": result.warnings
            }
        )
        
        # Publish to event bus if available
        if self.event_bus and not result.allowed:
            self._publish_security_event("prompt_blocked", {
                "user_id": user_id,
                "reason": result.reason,
                "threat_level": result.threat_level.value,
                "patterns": result.detected_patterns
            })
        
        return result
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        """
        Validate a file path.
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        is_valid, reason = self.command_sandbox.validate_path(path)
        
        # Log if invalid
        if not is_valid:
            self._log_security_event(
                event_type="access",
                severity="warning",
                description=f"Path validation failed: {reason}",
                details={"path": path}
            )
        
        return is_valid, reason

    def get_security_status(self) -> Dict[str, Any]:
        """
        Get current security status.

        Returns:
            Dictionary with security status information
        """
        # Get command sandbox stats
        command_log = self.command_sandbox.get_execution_log()
        command_stats = {
            "total_commands": len(command_log),
            "blocked_commands": sum(1 for entry in command_log if not entry["allowed"]),
            "high_risk_commands": sum(1 for entry in command_log if entry["risk_level"] in ["high", "critical"])
        }

        # Get prompt guard stats
        prompt_stats = self.prompt_guard.get_stats()

        # Get recent security events
        recent_events = self._security_events[-10:]  # Last 10 events

        return {
            "command_sandbox": command_stats,
            "prompt_guard": prompt_stats,
            "recent_events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type,
                    "severity": event.severity,
                    "description": event.description
                }
                for event in recent_events
            ],
            "total_security_events": len(self._security_events)
        }

    def get_security_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive security report.

        Returns:
            Dictionary with detailed security report
        """
        status = self.get_security_status()

        # Analyze security events
        critical_events = [e for e in self._security_events if e.severity == "critical"]
        warning_events = [e for e in self._security_events if e.severity == "warning"]

        # Calculate risk score (0-100)
        risk_score = self._calculate_risk_score()

        return {
            "status": status,
            "risk_score": risk_score,
            "critical_events_count": len(critical_events),
            "warning_events_count": len(warning_events),
            "recommendations": self._generate_recommendations(risk_score, critical_events, warning_events)
        }

    def clear_logs(self):
        """Clear all security logs."""
        self.command_sandbox.clear_log()
        self._security_events.clear()
        logger.info("Security logs cleared")

    def _log_security_event(self, event_type: str, severity: str, description: str, details: Dict[str, Any]):
        """Log a security event."""
        event = SecurityEvent(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            severity=severity,
            description=description,
            details=details
        )
        self._security_events.append(event)

        # Log to structlog
        log_func = logger.info
        if severity == "warning":
            log_func = logger.warning
        elif severity == "critical":
            log_func = logger.error

        log_func("Security event", type=event_type, severity=severity, description=description)

    def _publish_security_event(self, event_name: str, data: Dict[str, Any]):
        """Publish security event to event bus."""
        if self.event_bus:
            try:
                # Assuming event bus has a publish method
                self.event_bus.publish(f"security.{event_name}", data)
            except Exception as e:
                logger.error("Failed to publish security event", event=event_name, error=str(e))

    def _risk_to_severity(self, risk: CommandRisk) -> str:
        """Convert CommandRisk to severity level."""
        if risk == CommandRisk.CRITICAL:
            return "critical"
        elif risk == CommandRisk.HIGH:
            return "warning"
        else:
            return "info"

    def _threat_to_severity(self, threat: ThreatLevel) -> str:
        """Convert ThreatLevel to severity level."""
        if threat == ThreatLevel.CRITICAL:
            return "critical"
        elif threat in [ThreatLevel.HIGH, ThreatLevel.MEDIUM]:
            return "warning"
        else:
            return "info"

    def _calculate_risk_score(self) -> int:
        """
        Calculate overall risk score (0-100).

        Returns:
            Risk score where 0 is safest and 100 is most risky
        """
        if not self._security_events:
            return 0

        # Count events by severity
        critical_count = sum(1 for e in self._security_events if e.severity == "critical")
        warning_count = sum(1 for e in self._security_events if e.severity == "warning")

        # Weight critical events more heavily
        score = (critical_count * 10) + (warning_count * 3)

        # Cap at 100
        return min(score, 100)

    def _generate_recommendations(
        self,
        risk_score: int,
        critical_events: List[SecurityEvent],
        warning_events: List[SecurityEvent]
    ) -> List[str]:
        """Generate security recommendations based on events."""
        recommendations = []

        if risk_score > 50:
            recommendations.append("⚠️ High risk score detected - review security logs immediately")

        if critical_events:
            recommendations.append(f"🚨 {len(critical_events)} critical security events detected")
            recommendations.append("Review and address critical threats immediately")

        if warning_events:
            recommendations.append(f"⚠️ {len(warning_events)} warning-level events detected")

        if not recommendations:
            recommendations.append("✅ No significant security concerns detected")

        return recommendations


# Singleton instance
_security_manager_instance: Optional[SecurityManager] = None


def get_security_manager(event_bus=None) -> SecurityManager:
    """Get singleton SecurityManager instance."""
    global _security_manager_instance
    if _security_manager_instance is None:
        _security_manager_instance = SecurityManager(event_bus=event_bus)
    return _security_manager_instance

