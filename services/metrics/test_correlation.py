"""
Test Pass/Fail Correlation Metrics.

Tracks correlation between code changes and test outcomes
to help identify patterns and improve code quality.

Copyright (c) 2025 ContextForge
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """Single test execution result."""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_name: str
    test_file: str
    passed: bool
    duration_ms: int = 0
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CodeChange(BaseModel):
    """Code change that may affect tests."""
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    commit_hash: Optional[str] = None
    change_type: str = "modified"  # added, modified, deleted
    lines_added: int = 0
    lines_removed: int = 0
    functions_changed: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestCorrelationResult(BaseModel):
    """Correlation between code changes and test results."""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code_change: CodeChange
    test_results: List["ExecutionResult"]

    # Correlation metrics
    tests_passed: int = 0
    tests_failed: int = 0
    pass_rate: float = 0.0

    # Identified patterns
    likely_causes: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)
    related_files: List[str] = Field(default_factory=list)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CorrelationTracker:
    """Tracks and analyzes test pass/fail correlations."""

    def __init__(self):
        self._correlations: List[TestCorrelationResult] = []
        self._test_history: Dict[str, List[ExecutionResult]] = defaultdict(list)
        self._file_test_map: Dict[str, List[str]] = defaultdict(list)  # file -> tests

    def record_test_result(self, result: ExecutionResult) -> None:
        """Record a test result."""
        self._test_history[result.test_name].append(result)
        
        # Limit history size
        if len(self._test_history[result.test_name]) > 100:
            self._test_history[result.test_name] = \
                self._test_history[result.test_name][-100:]
    
    def correlate_change(self, change: CodeChange,
                         test_results: List[ExecutionResult]) -> TestCorrelationResult:
        """Correlate a code change with test results."""
        correlation = TestCorrelationResult(
            code_change=change,
            test_results=test_results,
            tests_passed=sum(1 for t in test_results if t.passed),
            tests_failed=sum(1 for t in test_results if not t.passed)
        )
        
        if test_results:
            correlation.pass_rate = correlation.tests_passed / len(test_results)
        
        # Analyze failures to identify likely causes
        failed_tests = [t for t in test_results if not t.passed]
        if failed_tests:
            correlation.likely_causes = self._analyze_failures(change, failed_tests)
            correlation.suggested_fixes = self._suggest_fixes(change, failed_tests)
            correlation.related_files = self._find_related_files(change, failed_tests)
        
        self._correlations.append(correlation)
        
        # Update file-test mapping
        for test in test_results:
            if change.file_path not in self._file_test_map[test.test_name]:
                self._file_test_map[test.test_name].append(change.file_path)
        
        return correlation
    
    def _analyze_failures(self, change: CodeChange,
                          failed_tests: List[ExecutionResult]) -> List[str]:
        """Analyze test failures to identify likely causes."""
        causes = []
        
        # Check for common patterns
        for test in failed_tests:
            if test.error_type:
                if "Import" in test.error_type:
                    causes.append(f"Import error in {change.file_path} - check module dependencies")
                elif "Attribute" in test.error_type:
                    causes.append(f"Missing or renamed attribute in {change.file_path}")
                elif "Type" in test.error_type:
                    causes.append(f"Type mismatch - check function signatures in {change.file_path}")
                elif "Assert" in test.error_type:
                    causes.append(f"Assertion failed - behavior change in {change.file_path}")
        
        # Check historical patterns
        for test in failed_tests:
            history = self._test_history.get(test.test_name, [])
            recent_fails = [h for h in history[-10:] if not h.passed]
            if len(recent_fails) > 3:
                causes.append(f"Test '{test.test_name}' has been flaky recently")
        
        return list(set(causes))[:5]
    
    def _suggest_fixes(self, change: CodeChange,
                       failed_tests: List[ExecutionResult]) -> List[str]:
        """Suggest potential fixes for test failures."""
        suggestions = []
        
        for test in failed_tests:
            if test.error_type:
                if "Import" in test.error_type:
                    suggestions.append("Check that all imports are correctly specified")
                elif "Attribute" in test.error_type:
                    suggestions.append(f"Verify attribute names match in {test.test_file}")
                elif "Timeout" in test.error_type.lower() if test.error_type else False:
                    suggestions.append("Consider increasing test timeout or optimizing code")
        
        if change.functions_changed:
            suggestions.append(f"Review changes to: {', '.join(change.functions_changed)}")
        
        return list(set(suggestions))[:5]
    
    def _find_related_files(self, change: CodeChange,
                            failed_tests: List[ExecutionResult]) -> List[str]:
        """Find files related to the failures."""
        related = set()
        related.add(change.file_path)
        
        for test in failed_tests:
            related.add(test.test_file)
            # Add previously correlated files for this test
            if test.test_name in self._file_test_map:
                related.update(self._file_test_map[test.test_name][:5])
        
        return list(related)[:10]
    
    def get_flaky_tests(self, threshold: float = 0.5, 
                        min_runs: int = 5) -> List[Dict]:
        """Identify flaky tests (inconsistent pass/fail)."""
        flaky = []
        
        for test_name, history in self._test_history.items():
            if len(history) < min_runs:
                continue
            
            recent = history[-20:]
            pass_rate = sum(1 for t in recent if t.passed) / len(recent)
            
            # Flaky if pass rate is between threshold and (1-threshold)
            if threshold <= pass_rate <= (1 - threshold):
                flaky.append({
                    "test_name": test_name,
                    "pass_rate": pass_rate,
                    "total_runs": len(recent),
                    "recent_failures": [t for t in recent if not t.passed][-3:]
                })
        
        return sorted(flaky, key=lambda x: abs(0.5 - x["pass_rate"]))


# Singleton
_tracker = None

def get_test_correlation_tracker() -> CorrelationTracker:
    """Get singleton test correlation tracker."""
    global _tracker
    if _tracker is None:
        _tracker = CorrelationTracker()
    return _tracker

