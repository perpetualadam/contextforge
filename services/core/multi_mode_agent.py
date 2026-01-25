"""
Multi-Mode Agent Architecture.

Single agent class with multiple operational modes (PLAN, IMPLEMENT, REVIEW, INDEX, TEST).
Integrates drift detection, fingerprinting, diff-based edits, and safety mechanisms.

Copyright (c) 2025 ContextForge
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

from .fingerprint import FileFingerprint, capture_fingerprint
from .drift_detection import DriftDetector, DriftSeverity, DriftDetectionResult
from .diff_engine import DiffEngine, FileDiff
from .safety import (
    ConfidenceTracker, LoopDetector, OperationLimits, OperationMetrics,
    ConfidenceLevel
)

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Result of an internal diagnostic check."""

    passed: bool
    severity: str  # "info", "warning", "error", "critical"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentMode(Enum):
    """Operational modes for multi-mode agent."""
    PLAN = "plan"  # Planning and task decomposition
    IMPLEMENT = "implement"  # Code implementation and refactoring
    REVIEW = "review"  # Code review and static analysis
    INDEX = "index"  # Indexing and embedding updates
    TEST = "test"  # Test execution and validation


@dataclass
class ModeContext:
    """Context shared across modes within a single operation."""
    
    mode: AgentMode
    files_in_scope: Set[str] = field(default_factory=set)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    planned_diffs: List[FileDiff] = field(default_factory=list)
    execution_log: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def log(self, message: str) -> None:
        """Add entry to execution log."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.execution_log.append(f"[{timestamp}] {message}")
        logger.info(message)


@dataclass
class OperationResult:
    """Result of a multi-mode agent operation."""
    
    success: bool
    mode: AgentMode
    files_modified: List[str] = field(default_factory=list)
    diffs_applied: List[FileDiff] = field(default_factory=list)
    drift_detected: Optional[DriftDetectionResult] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    metrics: Optional[OperationMetrics] = None
    error_message: Optional[str] = None
    execution_log: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "mode": self.mode.value,
            "files_modified": self.files_modified,
            "diffs_applied": [d.to_unified_diff() for d in self.diffs_applied],
            "drift_detected": self.drift_detected.has_drift if self.drift_detected else False,
            "confidence_scores": self.confidence_scores,
            "error_message": self.error_message,
            "execution_log": self.execution_log,
        }


class InternalDiagnosticAgent:
    """
    Internal diagnostic and safety module for MultiModeAgent.

    NOT a separate LLM agent - this is an internal safety component that runs
    in the same context as the MultiModeAgent to enforce safety rules.

    Responsibilities:
    - Drift detection & fingerprinting
    - Diff-based safety validation
    - Confidence & loop/token limits
    - Audit logging

    Design:
    - Runs synchronously within MultiModeAgent operations
    - No separate LLM calls - pure validation logic
    - Shares state with parent MultiModeAgent
    """

    def __init__(
        self,
        drift_detector: DriftDetector,
        confidence_tracker: ConfidenceTracker,
        limits: OperationLimits,
        parent_logger: logging.Logger,
    ):
        """
        Initialize internal diagnostic agent.

        Args:
            drift_detector: Shared drift detector from parent agent
            confidence_tracker: Shared confidence tracker from parent agent
            limits: Operation limits for safety checks
            parent_logger: Logger from parent agent
        """
        self.drift_detector = drift_detector
        self.confidence_tracker = confidence_tracker
        self.limits = limits
        self.logger = parent_logger

        # Diagnostic history for audit trail
        self.diagnostic_history: List[DiagnosticResult] = []

    def check_drift(self, file_path: str) -> DiagnosticResult:
        """
        Check if a file has drifted from expected state.

        Safety Rules:
        - NONE/MINOR drift: Pass with info
        - MODERATE drift: Pass with warning, trigger re-read
        - MAJOR drift: Fail with error, require human review
        """
        try:
            # Register file if not tracked
            if file_path not in self.drift_detector.fingerprints:
                self.drift_detector.register_file(file_path)

            # Detect drift
            drift_result = self.drift_detector.detect_drift([file_path])

            if not drift_result.has_drift:
                result = DiagnosticResult(
                    passed=True,
                    severity="info",
                    message=f"No drift detected for {file_path}",
                    details={"file": file_path, "status": "stable"}
                )
            else:
                drift_event = drift_result.drifted_files[0]

                # Map severity to diagnostic result
                if drift_event.severity == DriftSeverity.MINOR:
                    severity, passed = "info", True
                elif drift_event.severity == DriftSeverity.MODERATE:
                    severity, passed = "warning", True
                    self.confidence_tracker.adjust_confidence(
                        file_path, -10.0, "Moderate drift detected"
                    )
                else:  # MAJOR
                    severity, passed = "error", False
                    self.confidence_tracker.adjust_confidence(
                        file_path, -30.0, "Major drift detected"
                    )

                added, removed = drift_event.get_changed_symbols()
                result = DiagnosticResult(
                    passed=passed,
                    severity=severity,
                    message=f"Drift detected: {drift_event.severity.value}",
                    details={
                        "file": file_path,
                        "severity": drift_event.severity.value,
                        "symbols_added": list(added),
                        "symbols_removed": list(removed),
                        "action_required": "re-read" if passed else "human_review"
                    }
                )

            self.diagnostic_history.append(result)
            self.logger.info(f"Drift check: {result.message}")
            return result

        except Exception as e:
            self.logger.error(f"Drift check failed for {file_path}: {e}", exc_info=True)
            result = DiagnosticResult(
                passed=False,
                severity="error",
                message=f"Drift check failed: {str(e)}",
                details={"file": file_path, "error": str(e)}
            )
            self.diagnostic_history.append(result)
            return result

    def check_confidence(self, file_path: str, confidence: Optional[float] = None) -> DiagnosticResult:
        """
        Check if confidence level is sufficient for operations.

        Safety Rules:
        - ≥80: Pass (high/medium confidence)
        - 40-79: Pass with warning, trigger re-read
        - <40: Fail, require human review
        """
        try:
            if confidence is not None:
                self.confidence_tracker.set_confidence(file_path, confidence)

            file_confidence = self.confidence_tracker.get_confidence(file_path)

            # If no confidence set, initialize with default (50.0)
            if file_confidence is None:
                self.confidence_tracker.set_confidence(file_path, 50.0, ["Initial confidence"])
                file_confidence = self.confidence_tracker.get_confidence(file_path)

            if file_confidence.score >= 80:
                severity, passed = "info", True
                message = f"Confidence sufficient: {file_confidence.score:.1f}"
            elif file_confidence.score >= 40:
                severity, passed = "warning", True
                message = f"Low confidence: {file_confidence.score:.1f}, re-read recommended"
            else:
                severity, passed = "critical", False
                message = f"Critical confidence: {file_confidence.score:.1f}, human review required"

            result = DiagnosticResult(
                passed=passed,
                severity=severity,
                message=message,
                details={
                    "file": file_path,
                    "confidence": file_confidence.score,
                    "level": file_confidence.level.value,
                    "action_required": "re-read" if severity == "warning" else ("human_review" if not passed else "none")
                }
            )

            self.diagnostic_history.append(result)
            self.logger.info(f"Confidence check: {result.message}")
            return result

        except Exception as e:
            self.logger.error(f"Confidence check failed for {file_path}: {e}", exc_info=True)
            result = DiagnosticResult(
                passed=False,
                severity="error",
                message=f"Confidence check failed: {str(e)}",
                details={"file": file_path, "error": str(e)}
            )
            self.diagnostic_history.append(result)
            return result

    def check_loop_limits(
        self,
        tool_calls: int,
        revisions: int,
        tokens_used: int = 0,
        files_accessed: int = 0,
        loop_iterations: int = 0,
    ) -> DiagnosticResult:
        """
        Check if operation limits are exceeded.

        Safety Rules:
        - Any limit exceeded: Fail with error
        - >80% of limit: Pass with warning
        - <80% of limit: Pass
        """
        try:
            violations = []
            warnings = []

            checks = [
                ("tool_calls", tool_calls, self.limits.max_tool_calls),
                ("revisions", revisions, self.limits.max_revisions),
                ("tokens", tokens_used, self.limits.max_tokens),
                ("files", files_accessed, self.limits.max_files_per_operation),
                ("loops", loop_iterations, self.limits.max_loop_iterations),
            ]

            for name, current, limit in checks:
                if current >= limit:
                    violations.append(f"{name}: {current}/{limit}")
                elif current >= limit * 0.8:
                    warnings.append(f"{name}: {current}/{limit} (80% threshold)")

            if violations:
                result = DiagnosticResult(
                    passed=False,
                    severity="error",
                    message=f"Operation limits exceeded: {', '.join(violations)}",
                    details={
                        "violations": violations,
                        "tool_calls": tool_calls,
                        "revisions": revisions,
                        "tokens_used": tokens_used,
                        "files_accessed": files_accessed,
                        "loop_iterations": loop_iterations,
                    }
                )
            elif warnings:
                result = DiagnosticResult(
                    passed=True,
                    severity="warning",
                    message=f"Approaching limits: {', '.join(warnings)}",
                    details={
                        "warnings": warnings,
                        "tool_calls": tool_calls,
                        "revisions": revisions,
                        "tokens_used": tokens_used,
                        "files_accessed": files_accessed,
                        "loop_iterations": loop_iterations,
                    }
                )
            else:
                result = DiagnosticResult(
                    passed=True,
                    severity="info",
                    message="All limits within safe range",
                    details={
                        "tool_calls": tool_calls,
                        "revisions": revisions,
                        "tokens_used": tokens_used,
                        "files_accessed": files_accessed,
                        "loop_iterations": loop_iterations,
                    }
                )

            self.diagnostic_history.append(result)
            self.logger.info(f"Limit check: {result.message}")
            return result

        except Exception as e:
            self.logger.error(f"Limit check failed: {e}", exc_info=True)
            result = DiagnosticResult(
                passed=False,
                severity="error",
                message=f"Limit check failed: {str(e)}",
                details={"error": str(e)}
            )
            self.diagnostic_history.append(result)
            return result

    def review_task(
        self,
        files: List[str],
        metrics: OperationMetrics,
        mode: str = "unknown"
    ) -> List[DiagnosticResult]:
        """
        Comprehensive safety review before task execution.

        Args:
            files: Files in scope for the task
            metrics: Current operation metrics
            mode: Agent mode (for logging)

        Returns:
            List of diagnostic results

        Safety Workflow:
        1. Check drift for all files
        2. Check confidence for all files
        3. Check operation limits
        4. Return all results for decision making
        """
        results = []

        self.logger.info(f"Starting diagnostic review for {mode} mode with {len(files)} files")

        # 1. Check drift for all files
        for file_path in files:
            drift_result = self.check_drift(file_path)
            results.append(drift_result)

        # 2. Check confidence for all files
        for file_path in files:
            confidence_result = self.check_confidence(file_path)
            results.append(confidence_result)

        # 3. Check operation limits
        limit_result = self.check_loop_limits(
            tool_calls=metrics.tool_calls,
            revisions=metrics.revisions,
            tokens_used=metrics.tokens_used,
            files_accessed=len(metrics.files_accessed),
            loop_iterations=metrics.loop_iterations,
        )
        results.append(limit_result)

        # Log summary
        critical_count = sum(1 for r in results if r.severity in ("critical", "error") and not r.passed)
        warning_count = sum(1 for r in results if r.severity == "warning")

        self.logger.info(
            f"Diagnostic review completed: {len(results)} checks, "
            f"{critical_count} critical issues, {warning_count} warnings"
        )

        return results

    def has_critical_issues(self, results: List[DiagnosticResult]) -> bool:
        """Check if diagnostic results contain critical issues that block execution."""
        return any(
            r.severity in ("critical", "error") and not r.passed
            for r in results
        )


class MultiModeAgent(ABC):
    """
    Base class for multi-mode agents with integrated diagnostic safety.

    Architecture:
    - Single agent instance per process
    - Multiple operational modes (PLAN, IMPLEMENT, REVIEW, INDEX, TEST)
    - Shared memory/context across modes
    - Integrated InternalDiagnosticAgent for safety checks
    - Drift detection before operations
    - Diff-based edits only
    - Confidence tracking and safety limits

    Safety Integration:
    - All operations go through internal diagnostic checks
    - No separate LLM agent - diagnostics run in same context
    - Automatic drift detection and re-grounding
    - Confidence-based operation gating
    """

    def __init__(
        self,
        name: str,
        default_mode: AgentMode = AgentMode.PLAN,
        limits: Optional[OperationLimits] = None,
    ):
        self.name = name
        self.current_mode = default_mode
        self.limits = limits or OperationLimits()
        
        # Core components
        self.drift_detector = DriftDetector()
        self.diff_engine = DiffEngine()
        self.confidence_tracker = ConfidenceTracker()
        self.loop_detector = LoopDetector()

        # Integrated diagnostic agent (internal safety module)
        self.diagnostics = InternalDiagnosticAgent(
            drift_detector=self.drift_detector,
            confidence_tracker=self.confidence_tracker,
            limits=self.limits,
            parent_logger=logger,
        )

        # Operation state
        self.mode_context: Optional[ModeContext] = None
        self.metrics = OperationMetrics()

        logger.info(f"MultiModeAgent '{name}' initialized in {default_mode.value} mode with integrated diagnostics")
    
    def switch_mode(self, new_mode: AgentMode) -> None:
        """Switch to a different operational mode."""
        if self.current_mode != new_mode:
            logger.info(f"Agent '{self.name}' switching from {self.current_mode.value} to {new_mode.value}")
            self.current_mode = new_mode
    
    def begin_operation(self, mode: AgentMode, files: List[str]) -> ModeContext:
        """
        Begin a new operation in specified mode.
        
        Args:
            mode: Operational mode
            files: Files in scope for this operation
        
        Returns:
            ModeContext for this operation
        """
        self.switch_mode(mode)
        
        # Create new context
        self.mode_context = ModeContext(
            mode=mode,
            files_in_scope=set(files),
        )
        
        # Reset metrics and safety trackers
        self.metrics = OperationMetrics()
        self.loop_detector.reset()
        
        # Register fingerprints for all files in scope
        for file_path in files:
            if Path(file_path).exists():
                self.drift_detector.register_file(file_path)
                self.confidence_tracker.set_confidence(file_path, 100.0, ["Initial state"])
        
        self.mode_context.log(f"Operation started in {mode.value} mode with {len(files)} files")
        
        return self.mode_context
    
    def check_drift(self, files: Optional[List[str]] = None) -> DriftDetectionResult:
        """
        Check for drift in specified files or all files in scope.
        
        Returns:
            DriftDetectionResult with details of any drift
        """
        if not self.mode_context:
            raise RuntimeError("No active operation context")
        
        files_to_check = files or list(self.mode_context.files_in_scope)
        result = self.drift_detector.detect_drift(files_to_check)
        
        if result.has_drift:
            self.mode_context.log(
                f"Drift detected: {len(result.drifted_files)} files changed, "
                f"{len(result.missing_files)} files missing"
            )
            
            # Adjust confidence for drifted files
            for event in result.drifted_files:
                if event.severity == DriftSeverity.MAJOR:
                    self.confidence_tracker.set_confidence(event.file_path, 0.0, ["Major drift detected"])
                elif event.severity == DriftSeverity.MODERATE:
                    self.confidence_tracker.adjust_confidence(event.file_path, -50.0, "Moderate drift detected")
                else:
                    self.confidence_tracker.adjust_confidence(event.file_path, -20.0, "Minor drift detected")
        
        return result

    def scoped_reground(self, drifted_files: Set[str]) -> bool:
        """
        Perform scoped re-grounding for drifted files.

        Only re-reads changed files and their dependents, not entire codebase.

        Args:
            drifted_files: Set of file paths that have drifted

        Returns:
            True if re-grounding successful
        """
        if not self.mode_context:
            raise RuntimeError("No active operation context")

        self.mode_context.log(f"Scoped re-grounding for {len(drifted_files)} files")

        # Update fingerprints for drifted files
        for file_path in drifted_files:
            if Path(file_path).exists():
                self.drift_detector.update_fingerprint(file_path)
                self.confidence_tracker.set_confidence(file_path, 100.0, ["Re-grounded"])
                self.mode_context.log(f"Re-grounded: {file_path}")
            else:
                self.confidence_tracker.set_confidence(file_path, 0.0, ["File missing"])
                self.mode_context.log(f"Missing file: {file_path}")

        return True

    def check_safety(self) -> Optional[str]:
        """
        Check safety constraints using integrated diagnostics.

        Returns:
            Error message if unsafe, None if safe to proceed
        """
        if not self.mode_context:
            return "No active operation context"

        # Run comprehensive diagnostic review
        files = list(self.mode_context.files_in_scope)
        diagnostic_results = self.diagnostics.review_task(
            files=files,
            metrics=self.metrics,
            mode=self.current_mode.value
        )

        # Check for critical issues
        if self.diagnostics.has_critical_issues(diagnostic_results):
            critical_messages = [
                r.message for r in diagnostic_results
                if r.severity in ("critical", "error") and not r.passed
            ]
            return f"Safety check failed: {'; '.join(critical_messages)}"

        # Check for loops (additional check)
        state = {
            "mode": self.current_mode.value,
            "files": sorted(self.mode_context.files_in_scope),
            "iteration": self.metrics.loop_iterations,
        }
        if self.loop_detector.record_state(state):
            return "Infinite loop detected. Operation aborted."

        return None

    def prepare_diff(self, file_path: str, new_content: str) -> Optional[FileDiff]:
        """
        Prepare a diff for a file.

        Args:
            file_path: Path to file
            new_content: Proposed new content

        Returns:
            FileDiff object or None if error
        """
        if not self.mode_context:
            raise RuntimeError("No active operation context")

        # Check drift before preparing diff
        drift_result = self.check_drift([file_path])
        if drift_result.has_drift:
            self.mode_context.log(f"Drift detected before diff preparation for {file_path}")
            # Trigger re-grounding
            self.scoped_reground(drift_result.get_affected_files())

        # Compute diff
        file_diff = self.diff_engine.compute_diff(file_path, new_content)

        if file_diff:
            self.mode_context.planned_diffs.append(file_diff)
            self.mode_context.log(
                f"Prepared diff for {file_path}: "
                f"+{file_diff.total_additions} -{file_diff.total_deletions}"
            )

        return file_diff

    def apply_diff(self, file_diff: FileDiff, dry_run: bool = False) -> bool:
        """
        Apply a diff to a file with safety checks.

        Args:
            file_diff: Diff to apply
            dry_run: If True, validate but don't write

        Returns:
            True if successful
        """
        if not self.mode_context:
            raise RuntimeError("No active operation context")

        # Safety check before applying
        safety_error = self.check_safety()
        if safety_error:
            self.mode_context.log(f"Safety check failed: {safety_error}")
            return False

        # Check drift one more time
        drift_result = self.check_drift([file_diff.file_path])
        if drift_result.has_drift and drift_result.max_severity == DriftSeverity.MAJOR:
            self.mode_context.log(f"Major drift detected, aborting diff application for {file_diff.file_path}")
            return False

        # Apply diff
        success = self.diff_engine.apply_diff(file_diff, dry_run=dry_run)

        if success and not dry_run:
            # Update fingerprint after successful write
            self.drift_detector.update_fingerprint(file_diff.file_path)
            self.mode_context.log(f"Applied diff to {file_diff.file_path}")
            self.metrics.revisions += 1

        return success

    def end_operation(self, success: bool, error_message: Optional[str] = None) -> OperationResult:
        """
        End the current operation and return results.

        Args:
            success: Whether operation succeeded
            error_message: Optional error message if failed

        Returns:
            OperationResult with full details
        """
        if not self.mode_context:
            raise RuntimeError("No active operation context")

        # Collect confidence scores
        confidence_scores = {
            fp: fc.score
            for fp, fc in self.confidence_tracker.file_confidences.items()
        }

        # Collect modified files
        files_modified = [
            diff.file_path for diff in self.mode_context.planned_diffs
        ]

        result = OperationResult(
            success=success,
            mode=self.mode_context.mode,
            files_modified=files_modified,
            diffs_applied=self.mode_context.planned_diffs,
            confidence_scores=confidence_scores,
            metrics=self.metrics,
            error_message=error_message,
            execution_log=self.mode_context.execution_log,
        )

        self.mode_context.log(f"Operation ended: success={success}")

        # Clear context
        self.mode_context = None

        return result

    # Abstract methods for mode-specific implementations

    @abstractmethod
    def execute_plan_mode(self, task: Dict[str, Any]) -> OperationResult:
        """Execute in PLAN mode."""
        pass

    @abstractmethod
    def execute_implement_mode(self, task: Dict[str, Any]) -> OperationResult:
        """Execute in IMPLEMENT mode."""
        pass

    @abstractmethod
    def execute_review_mode(self, task: Dict[str, Any]) -> OperationResult:
        """Execute in REVIEW mode."""
        pass

    @abstractmethod
    def execute_index_mode(self, task: Dict[str, Any]) -> OperationResult:
        """Execute in INDEX mode."""
        pass

    @abstractmethod
    def execute_test_mode(self, task: Dict[str, Any]) -> OperationResult:
        """Execute in TEST mode."""
        pass

    def execute(self, mode: AgentMode, task: Dict[str, Any]) -> OperationResult:
        """
        Execute a task in specified mode.

        Routes to appropriate mode-specific handler.

        Args:
            mode: Operational mode
            task: Task payload

        Returns:
            OperationResult
        """
        self.switch_mode(mode)

        try:
            if mode == AgentMode.PLAN:
                return self.execute_plan_mode(task)
            elif mode == AgentMode.IMPLEMENT:
                return self.execute_implement_mode(task)
            elif mode == AgentMode.REVIEW:
                return self.execute_review_mode(task)
            elif mode == AgentMode.INDEX:
                return self.execute_index_mode(task)
            elif mode == AgentMode.TEST:
                return self.execute_test_mode(task)
            else:
                raise ValueError(f"Unknown mode: {mode}")
        except Exception as e:
            logger.error(f"Error executing {mode.value} mode: {e}", exc_info=True)
            if self.mode_context:
                return self.end_operation(False, str(e))
            else:
                return OperationResult(
                    success=False,
                    mode=mode,
                    error_message=str(e),
                )

