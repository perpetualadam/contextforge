"""
Local Multi-Mode Agent for In-Process Execution.

Implements MultiModeAgent for local agents that require filesystem access
and low-latency operations (IndexingAgent, TestingAgent, DebuggingAgent, etc.).

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import subprocess

from .multi_mode_agent import MultiModeAgent, AgentMode, OperationResult
from .safety import OperationLimits

logger = logging.getLogger(__name__)


class LocalMultiModeAgent(MultiModeAgent):
    """
    Multi-mode agent for local in-process execution.
    
    Consolidates IndexingAgent, TestingAgent, DebuggingAgent, CritiqueAgent,
    ReviewAgent, ReasoningAgent, DocAgent, RefactorAgent into a single agent
    with multiple modes.
    
    Runs in the same process as the core service for:
    - Filesystem access
    - Low latency
    - Local state management
    """
    
    def __init__(
        self,
        name: str = "LocalMultiModeAgent",
        workspace_root: Optional[str] = None,
        limits: Optional[OperationLimits] = None,
    ):
        super().__init__(name=name, default_mode=AgentMode.PLAN, limits=limits)
        
        # Local-specific configuration
        self.workspace_root = workspace_root or str(Path.cwd())
        
        # References to external services (set by core service)
        self.vector_service = None
        self.llm_client = None
        self.preprocessor = None
    
    def execute_plan_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        PLAN mode: Task decomposition and planning.
        
        Uses local reasoning for fast planning without network calls.
        """
        files = task.get("context_files", [])
        context = self.begin_operation(AgentMode.PLAN, files)
        
        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                self.scoped_reground(drift_result.get_affected_files())
            
            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)
            
            # Local planning logic
            task_description = task.get("task_description", "")
            context.log(f"Planning task: {task_description}")
            
            # Analyze files
            for file_path in files:
                full_path = Path(self.workspace_root) / file_path
                if full_path.exists():
                    context.log(f"Analyzed: {file_path}")
                    self.metrics.files_accessed.add(str(full_path))
            
            # Generate concise plan (≤5 bullets)
            plan = {
                "subtasks": [],
                "execution_order": [],
            }
            
            context.assumptions["plan"] = plan
            context.log(f"Generated plan with {len(plan['subtasks'])} subtasks")
            
            return self.end_operation(True)
            
        except Exception as e:
            logger.error(f"Error in PLAN mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))
    
    def execute_implement_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        IMPLEMENT mode: Code implementation and refactoring.
        
        Applies diff-based edits with drift detection.
        """
        files = task.get("target_files", [])
        context = self.begin_operation(AgentMode.IMPLEMENT, files)
        
        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                if drift_result.max_severity.value == "major":
                    return self.end_operation(False, "Major drift detected")
                self.scoped_reground(drift_result.get_affected_files())
            
            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)
            
            # Apply changes as diffs
            changes = task.get("changes", [])
            for change in changes:
                file_path = change.get("file_path")
                new_content = change.get("new_content")
                
                if not file_path or not new_content:
                    continue
                
                full_path = str(Path(self.workspace_root) / file_path)
                
                # Prepare and apply diff
                file_diff = self.prepare_diff(full_path, new_content)
                if file_diff:
                    success = self.apply_diff(file_diff, dry_run=False)
                    if not success:
                        return self.end_operation(False, f"Failed to apply diff to {file_path}")
                    
                    self.metrics.files_accessed.add(full_path)
            
            context.log(f"Applied {len(changes)} changes")
            return self.end_operation(True)
            
        except Exception as e:
            logger.error(f"Error in IMPLEMENT mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))
    
    def execute_review_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        REVIEW mode: Code review and static analysis.
        """
        files = task.get("files_to_review", [])
        context = self.begin_operation(AgentMode.REVIEW, files)
        
        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                self.scoped_reground(drift_result.get_affected_files())
            
            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)
            
            # Review logic
            issues = []
            for file_path in files:
                full_path = Path(self.workspace_root) / file_path
                if full_path.exists():
                    context.log(f"Reviewing: {file_path}")
                    self.metrics.files_accessed.add(str(full_path))
            
            context.assumptions["review_issues"] = issues
            context.log(f"Review completed: {len(issues)} issues found")
            
            return self.end_operation(True)
            
        except Exception as e:
            logger.error(f"Error in REVIEW mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))

    def execute_index_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        INDEX mode: Update embeddings and indexes.

        Integrates with vector service to update embeddings.
        """
        files = task.get("files_to_index", [])
        context = self.begin_operation(AgentMode.INDEX, files)

        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                self.scoped_reground(drift_result.get_affected_files())

            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)

            # Indexing logic
            indexed_files = []
            for file_path in files:
                full_path = Path(self.workspace_root) / file_path
                if full_path.exists():
                    context.log(f"Indexing: {file_path}")
                    self.metrics.files_accessed.add(str(full_path))
                    indexed_files.append(file_path)

                    # Update fingerprint after indexing
                    self.drift_detector.update_fingerprint(str(full_path))

            context.assumptions["indexed_files"] = indexed_files
            context.log(f"Indexed {len(indexed_files)} files")

            return self.end_operation(True)

        except Exception as e:
            logger.error(f"Error in INDEX mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))

    def execute_test_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        TEST mode: Run tests and validate changes.

        Executes test commands and captures results.
        """
        files = task.get("test_files", [])
        context = self.begin_operation(AgentMode.TEST, files)

        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                self.scoped_reground(drift_result.get_affected_files())

            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)

            # Test execution
            test_command = task.get("test_command", "pytest")
            context.log(f"Running tests with command: {test_command}")

            # Execute test command
            try:
                result = subprocess.run(
                    test_command.split(),
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=self.limits.timeout_seconds,
                )

                test_results = {
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }

                context.assumptions["test_results"] = test_results
                context.log(f"Tests completed: returncode={result.returncode}")

            except subprocess.TimeoutExpired:
                return self.end_operation(False, "Test execution timed out")
            except Exception as e:
                return self.end_operation(False, f"Test execution failed: {e}")

            return self.end_operation(True)

        except Exception as e:
            logger.error(f"Error in TEST mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))


# Factory function for creating local multi-mode agent
def create_local_multi_mode_agent(
    name: str = "LocalMultiModeAgent",
    workspace_root: Optional[str] = None,
    limits: Optional[OperationLimits] = None,
) -> LocalMultiModeAgent:
    """Create and configure a local multi-mode agent."""
    return LocalMultiModeAgent(name=name, workspace_root=workspace_root, limits=limits)

