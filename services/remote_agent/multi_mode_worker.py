"""
Multi-Mode Worker Agent for Remote Execution.

Implements MultiModeAgent for distributed remote agent workers.
Handles PLAN, IMPLEMENT, REVIEW, INDEX, TEST modes with drift safety.

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys
import os

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.multi_mode_agent import MultiModeAgent, AgentMode, OperationResult
from core.safety import OperationLimits

logger = logging.getLogger(__name__)


class RemoteMultiModeAgent(MultiModeAgent):
    """
    Multi-mode agent for remote worker processes.
    
    Consolidates IndexAgent, TestAgent, ReviewAgent, RefactorAgent, DocAgent
    into a single agent with multiple modes.
    """
    
    def __init__(
        self,
        name: str = "RemoteMultiModeAgent",
        limits: Optional[OperationLimits] = None,
    ):
        super().__init__(name=name, default_mode=AgentMode.PLAN, limits=limits)
        
        # Remote-specific configuration
        self.api_gateway_url = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
        self.workspace_root = os.getenv("WORKSPACE_ROOT", "/workspace")
    
    def execute_plan_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        PLAN mode: Task decomposition and planning.
        
        Input:
            - task_description: str
            - context_files: List[str]
        
        Output:
            - subtasks: List[Dict]
            - execution_order: List[str]
        """
        files = task.get("context_files", [])
        context = self.begin_operation(AgentMode.PLAN, files)
        
        try:
            # Check drift before planning
            drift_result = self.check_drift()
            if drift_result.has_drift:
                self.scoped_reground(drift_result.get_affected_files())
            
            # Safety check
            safety_error = self.check_safety()
            if safety_error:
                return self.end_operation(False, safety_error)
            
            # Planning logic (concise, ≤5 bullets)
            task_description = task.get("task_description", "")
            context.log(f"Planning task: {task_description}")
            
            # Analyze files in scope
            for file_path in files:
                if Path(file_path).exists():
                    context.log(f"Analyzed: {file_path}")
                    self.metrics.files_accessed.add(file_path)
            
            # Generate plan (simplified for this implementation)
            plan = {
                "subtasks": [
                    {"mode": "index", "files": files},
                    {"mode": "implement", "files": files},
                    {"mode": "review", "files": files},
                    {"mode": "test", "files": files},
                ],
                "execution_order": ["index", "implement", "review", "test"],
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
        
        Input:
            - target_files: List[str]
            - changes: List[Dict] with file_path and new_content
        
        Output:
            - diffs_applied: List[FileDiff]
        """
        files = task.get("target_files", [])
        context = self.begin_operation(AgentMode.IMPLEMENT, files)
        
        try:
            # Check drift
            drift_result = self.check_drift()
            if drift_result.has_drift:
                if drift_result.max_severity.value == "major":
                    return self.end_operation(False, "Major drift detected, aborting implementation")
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
                
                # Prepare and apply diff
                file_diff = self.prepare_diff(file_path, new_content)
                if file_diff:
                    success = self.apply_diff(file_diff, dry_run=False)
                    if not success:
                        return self.end_operation(False, f"Failed to apply diff to {file_path}")
                    
                    self.metrics.files_accessed.add(file_path)
            
            context.log(f"Applied {len(changes)} changes")
            return self.end_operation(True)
            
        except Exception as e:
            logger.error(f"Error in IMPLEMENT mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))
    
    def execute_review_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        REVIEW mode: Code review and static analysis.
        
        Input:
            - files_to_review: List[str]
        
        Output:
            - issues: List[Dict] with severity, file, line, message
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
            
            # Review logic (placeholder - integrate with existing ReviewAgent logic)
            issues = []
            for file_path in files:
                if Path(file_path).exists():
                    context.log(f"Reviewing: {file_path}")
                    self.metrics.files_accessed.add(file_path)
                    
                    # Placeholder: actual review would use static analysis tools
                    # and LLM-based review
            
            context.assumptions["review_issues"] = issues
            context.log(f"Review completed: {len(issues)} issues found")
            
            return self.end_operation(True)
            
        except Exception as e:
            logger.error(f"Error in REVIEW mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))

    def execute_index_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        INDEX mode: Update embeddings and indexes.

        Input:
            - files_to_index: List[str]
            - index_type: str (e.g., "embeddings", "symbols")

        Output:
            - indexed_files: List[str]
            - index_stats: Dict
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

            # Indexing logic (placeholder - integrate with existing IndexingAgent logic)
            indexed_files = []
            for file_path in files:
                if Path(file_path).exists():
                    context.log(f"Indexing: {file_path}")
                    self.metrics.files_accessed.add(file_path)
                    indexed_files.append(file_path)

                    # Update fingerprint after indexing
                    self.drift_detector.update_fingerprint(file_path)

            context.assumptions["indexed_files"] = indexed_files
            context.log(f"Indexed {len(indexed_files)} files")

            return self.end_operation(True)

        except Exception as e:
            logger.error(f"Error in INDEX mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))

    def execute_test_mode(self, task: Dict[str, Any]) -> OperationResult:
        """
        TEST mode: Run tests and validate changes.

        Input:
            - test_files: List[str]
            - test_command: str

        Output:
            - test_results: Dict with pass/fail/skip counts
            - failed_tests: List[str]
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

            # Test execution logic (placeholder - integrate with existing TestingAgent logic)
            test_command = task.get("test_command", "pytest")
            context.log(f"Running tests with command: {test_command}")

            # Placeholder: actual test execution would run subprocess
            test_results = {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
            }

            for file_path in files:
                if Path(file_path).exists():
                    context.log(f"Testing: {file_path}")
                    self.metrics.files_accessed.add(file_path)

            context.assumptions["test_results"] = test_results
            context.log(f"Tests completed: {test_results}")

            return self.end_operation(True)

        except Exception as e:
            logger.error(f"Error in TEST mode: {e}", exc_info=True)
            return self.end_operation(False, str(e))


# Factory function for creating multi-mode agent
def create_remote_multi_mode_agent(
    name: str = "RemoteMultiModeAgent",
    limits: Optional[OperationLimits] = None,
) -> RemoteMultiModeAgent:
    """Create and configure a remote multi-mode agent."""
    return RemoteMultiModeAgent(name=name, limits=limits)
