"""
Confidence Scoring, Loop Detection, and Token/Resource Limits.

Ensures agent operations are safe, bounded, and auditable.

Copyright (c) 2025 ContextForge
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level categories."""
    CRITICAL = "critical"  # < 40: Stop and request human
    LOW = "low"  # 40-79: Re-read files
    MEDIUM = "medium"  # 80-89: Proceed with caution
    HIGH = "high"  # 90-100: Proceed normally


@dataclass
class FileConfidence:
    """Confidence score for a specific file."""
    
    file_path: str
    score: float  # 0-100
    reasons: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.score < 40:
            return ConfidenceLevel.CRITICAL
        elif self.score < 80:
            return ConfidenceLevel.LOW
        elif self.score < 90:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    def should_reread(self) -> bool:
        """Check if file should be re-read."""
        return self.score < 80
    
    def should_stop(self) -> bool:
        """Check if operation should stop for human confirmation."""
        return self.score < 40


@dataclass
class OperationLimits:
    """Resource limits for an operation."""
    
    max_tool_calls: int = 50
    max_revisions: int = 10
    max_tokens: int = 100000
    max_files_per_operation: int = 20
    max_loop_iterations: int = 5
    timeout_seconds: float = 300.0


@dataclass
class OperationMetrics:
    """Metrics tracked during an operation."""
    
    tool_calls: int = 0
    revisions: int = 0
    tokens_used: int = 0
    files_accessed: Set[str] = field(default_factory=set)
    loop_iterations: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def check_limits(self, limits: OperationLimits) -> Optional[str]:
        """Check if any limits are exceeded. Returns error message or None."""
        if self.tool_calls >= limits.max_tool_calls:
            return f"Tool call limit exceeded: {self.tool_calls}/{limits.max_tool_calls}"
        
        if self.revisions >= limits.max_revisions:
            return f"Revision limit exceeded: {self.revisions}/{limits.max_revisions}"
        
        if self.tokens_used >= limits.max_tokens:
            return f"Token limit exceeded: {self.tokens_used}/{limits.max_tokens}"
        
        if len(self.files_accessed) >= limits.max_files_per_operation:
            return f"File access limit exceeded: {len(self.files_accessed)}/{limits.max_files_per_operation}"
        
        if self.loop_iterations >= limits.max_loop_iterations:
            return f"Loop iteration limit exceeded: {self.loop_iterations}/{limits.max_loop_iterations}"

        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        if elapsed >= limits.timeout_seconds:
            return f"Timeout exceeded: {elapsed:.1f}s/{limits.timeout_seconds}s"
        
        return None


class LoopDetector:
    """Detects infinite loops in agent operations."""
    
    def __init__(self, max_identical_states: int = 3):
        self.max_identical_states = max_identical_states
        self.state_history: List[str] = []
        self.state_counts: Dict[str, int] = {}
    
    def record_state(self, state_data: dict) -> bool:
        """
        Record a state and check for loops.
        
        Args:
            state_data: Dictionary representing current state
        
        Returns:
            True if loop detected, False otherwise
        """
        # Hash the state
        state_str = str(sorted(state_data.items()))
        state_hash = hashlib.md5(state_str.encode()).hexdigest()
        
        # Track state
        self.state_history.append(state_hash)
        self.state_counts[state_hash] = self.state_counts.get(state_hash, 0) + 1
        
        # Check for loop
        if self.state_counts[state_hash] >= self.max_identical_states:
            logger.warning(f"Loop detected: state repeated {self.state_counts[state_hash]} times")
            return True
        
        return False
    
    def reset(self) -> None:
        """Reset loop detection state."""
        self.state_history.clear()
        self.state_counts.clear()


class ConfidenceTracker:
    """Tracks confidence scores for files during operations."""
    
    def __init__(self):
        self.file_confidences: Dict[str, FileConfidence] = {}
    
    def set_confidence(self, file_path: str, score: float, reasons: Optional[List[str]] = None) -> None:
        """Set confidence score for a file."""
        self.file_confidences[file_path] = FileConfidence(
            file_path=file_path,
            score=max(0.0, min(100.0, score)),  # Clamp to 0-100
            reasons=reasons or [],
        )
        logger.debug(f"Confidence for {file_path}: {score:.1f}")
    
    def get_confidence(self, file_path: str) -> Optional[FileConfidence]:
        """Get confidence score for a file."""
        return self.file_confidences.get(file_path)
    
    def adjust_confidence(self, file_path: str, delta: float, reason: str) -> None:
        """Adjust confidence score by delta."""
        current = self.file_confidences.get(file_path)
        if current:
            new_score = max(0.0, min(100.0, current.score + delta))
            current.score = new_score
            current.reasons.append(reason)
            current.last_updated = datetime.now(timezone.utc)
        else:
            self.set_confidence(file_path, 50.0 + delta, [reason])
    
    def get_critical_files(self) -> List[FileConfidence]:
        """Get files with critical confidence levels."""
        return [fc for fc in self.file_confidences.values() if fc.should_stop()]
    
    def get_low_confidence_files(self) -> List[FileConfidence]:
        """Get files with low confidence that should be re-read."""
        return [fc for fc in self.file_confidences.values() if fc.should_reread()]
    
    def get_overall_confidence(self) -> float:
        """Get average confidence across all files."""
        if not self.file_confidences:
            return 100.0
        
        return sum(fc.score for fc in self.file_confidences.values()) / len(self.file_confidences)

