"""
Prompt Guard for Phase 6: Security Hardening.

Provides prompt injection detection and defense to prevent:
- Prompt injection attacks
- Jailbreak attempts
- Malicious prompt manipulation
- Unauthorized system prompts

Copyright (c) 2025 ContextForge
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


class ThreatLevel(Enum):
    """Threat level for prompts."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PromptValidationResult:
    """Result of prompt validation."""
    allowed: bool
    threat_level: ThreatLevel
    reason: str
    sanitized_prompt: Optional[str] = None
    detected_patterns: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.detected_patterns is None:
            self.detected_patterns = []
        if self.warnings is None:
            self.warnings = []


class PromptGuard:
    """
    Prompt guard for detecting and preventing prompt injection attacks.
    
    Features:
    - Detect prompt injection patterns
    - Identify jailbreak attempts
    - Sanitize user inputs
    - Rate limit suspicious requests
    - Log security events
    """
    
    # Prompt injection patterns
    INJECTION_PATTERNS = {
        'ignore_instructions': [
            r'ignore\s+(all\s+)?(previous|above|prior)\s+instructions',
            r'disregard\s+(all\s+)?(previous|above|prior)\s+instructions',
            r'forget\s+(all\s+)?(previous|above|prior)\s+instructions',
        ],
        'system_override': [
            r'you\s+are\s+now',
            r'new\s+instructions',
            r'system\s*:\s*',
            r'<\s*system\s*>',
            r'\[SYSTEM\]',
        ],
        'role_manipulation': [
            r'act\s+as\s+if',
            r'pretend\s+to\s+be',
            r'roleplay\s+as',
            r'simulate\s+being',
        ],
        'jailbreak': [
            r'DAN\s+mode',
            r'developer\s+mode',
            r'god\s+mode',
            r'unrestricted\s+mode',
            r'bypass\s+restrictions',
        ],
        'prompt_leakage': [
            r'show\s+me\s+your\s+(system\s+)?prompt',
            r'what\s+are\s+your\s+instructions',
            r'reveal\s+your\s+prompt',
            r'print\s+your\s+system\s+message',
        ],
        'code_execution': [
            r'execute\s+code',
            r'run\s+script',
            r'eval\s*\(',
            r'exec\s*\(',
            r'__import__',
        ],
    }
    
    # Suspicious character sequences
    SUSPICIOUS_SEQUENCES = [
        r'<\s*script',  # HTML script tags
        r'javascript\s*:',  # JavaScript protocol
        r'data\s*:',  # Data URLs
        r'vbscript\s*:',  # VBScript protocol
        r'\x00',  # Null bytes
    ]
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_SUSPICIOUS_PER_HOUR = 10
    
    def __init__(self):
        """Initialize prompt guard."""
        self._request_history: Dict[str, List[datetime]] = {}
        self._suspicious_history: Dict[str, List[datetime]] = {}
        self._blocked_users: Dict[str, datetime] = {}
        
        logger.info("PromptGuard initialized")
    
    def validate_prompt(self, prompt: str, user_id: Optional[str] = None) -> PromptValidationResult:
        """
        Validate a prompt before sending to LLM.
        
        Args:
            prompt: User prompt to validate
            user_id: Optional user identifier for rate limiting
            
        Returns:
            PromptValidationResult with validation details
        """
        # Check if user is blocked
        if user_id and self._is_user_blocked(user_id):
            logger.warning("Blocked user attempted request", user_id=user_id)
            return PromptValidationResult(
                allowed=False,
                threat_level=ThreatLevel.CRITICAL,
                reason="User is temporarily blocked due to suspicious activity"
            )
        
        # Check rate limiting
        if user_id and not self._check_rate_limit(user_id):
            logger.warning("Rate limit exceeded", user_id=user_id)
            return PromptValidationResult(
                allowed=False,
                threat_level=ThreatLevel.MEDIUM,
                reason="Rate limit exceeded"
            )
        
        # Detect injection patterns
        detected_patterns = []
        threat_level = ThreatLevel.SAFE
        warnings = []
        
        for category, patterns in self.INJECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, prompt, re.IGNORECASE):
                    detected_patterns.append(f"{category}: {pattern}")

                    # Escalate threat level
                    if category in ['jailbreak', 'code_execution']:
                        threat_level = ThreatLevel.CRITICAL
                    elif category in ['system_override', 'prompt_leakage']:
                        threat_level = ThreatLevel.HIGH
                    elif category in ['ignore_instructions', 'role_manipulation']:
                        if threat_level.value in ['safe', 'low']:
                            threat_level = ThreatLevel.MEDIUM
                    elif threat_level.value in ['safe', 'low']:
                        threat_level = ThreatLevel.MEDIUM

        # Check suspicious sequences
        for pattern in self.SUSPICIOUS_SEQUENCES:
            if re.search(pattern, prompt, re.IGNORECASE):
                detected_patterns.append(f"suspicious_sequence: {pattern}")
                if threat_level == ThreatLevel.SAFE:
                    threat_level = ThreatLevel.LOW
                warnings.append(f"Suspicious sequence detected: {pattern}")

        # Block critical threats
        if threat_level == ThreatLevel.CRITICAL:
            if user_id:
                self._record_suspicious_activity(user_id)

            logger.warning("Critical threat detected", prompt=prompt[:100], patterns=detected_patterns)
            return PromptValidationResult(
                allowed=False,
                threat_level=threat_level,
                reason="Critical security threat detected in prompt",
                detected_patterns=detected_patterns
            )

        # Warn on high threats but allow
        if threat_level == ThreatLevel.HIGH:
            if user_id:
                self._record_suspicious_activity(user_id)
            warnings.append("High-risk prompt detected - proceeding with caution")

        # Sanitize prompt
        sanitized = self._sanitize_prompt(prompt)

        logger.info("Prompt validated", threat=threat_level.value, patterns_count=len(detected_patterns))

        return PromptValidationResult(
            allowed=True,
            threat_level=threat_level,
            reason="Prompt passed validation",
            sanitized_prompt=sanitized,
            detected_patterns=detected_patterns,
            warnings=warnings
        )

    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Sanitize prompt by removing potentially dangerous content.

        Args:
            prompt: Original prompt

        Returns:
            Sanitized prompt
        """
        sanitized = prompt

        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')

        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)

        # Trim
        sanitized = sanitized.strip()

        return sanitized

    def _check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user is within rate limits.

        Args:
            user_id: User identifier

        Returns:
            True if within limits, False otherwise
        """
        now = datetime.utcnow()

        # Initialize history if needed
        if user_id not in self._request_history:
            self._request_history[user_id] = []

        # Clean old requests (older than 1 minute)
        cutoff = now - timedelta(minutes=1)
        self._request_history[user_id] = [
            ts for ts in self._request_history[user_id] if ts > cutoff
        ]

        # Check limit
        if len(self._request_history[user_id]) >= self.MAX_REQUESTS_PER_MINUTE:
            return False

        # Record request
        self._request_history[user_id].append(now)
        return True

    def _record_suspicious_activity(self, user_id: str):
        """
        Record suspicious activity for a user.

        Args:
            user_id: User identifier
        """
        now = datetime.utcnow()

        # Initialize history if needed
        if user_id not in self._suspicious_history:
            self._suspicious_history[user_id] = []

        # Clean old activity (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self._suspicious_history[user_id] = [
            ts for ts in self._suspicious_history[user_id] if ts > cutoff
        ]

        # Record activity
        self._suspicious_history[user_id].append(now)

        # Block user if too many suspicious requests
        if len(self._suspicious_history[user_id]) >= self.MAX_SUSPICIOUS_PER_HOUR:
            self._blocked_users[user_id] = now + timedelta(hours=1)
            logger.warning("User blocked due to suspicious activity", user_id=user_id)

    def _is_user_blocked(self, user_id: str) -> bool:
        """
        Check if user is blocked.

        Args:
            user_id: User identifier

        Returns:
            True if blocked, False otherwise
        """
        if user_id not in self._blocked_users:
            return False

        # Check if block has expired
        if datetime.utcnow() > self._blocked_users[user_id]:
            del self._blocked_users[user_id]
            logger.info("User block expired", user_id=user_id)
            return False

        return True

    def unblock_user(self, user_id: str):
        """Manually unblock a user."""
        if user_id in self._blocked_users:
            del self._blocked_users[user_id]
            logger.info("User manually unblocked", user_id=user_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get prompt guard statistics."""
        return {
            "active_users": len(self._request_history),
            "blocked_users": len(self._blocked_users),
            "suspicious_users": len(self._suspicious_history),
        }


# Singleton instance
_guard_instance: Optional[PromptGuard] = None


def get_prompt_guard() -> PromptGuard:
    """Get singleton PromptGuard instance."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = PromptGuard()
    return _guard_instance

