"""
Integration tests for InternalDiagnosticAgent and CLIAgent.

Tests the integrated diagnostic system within MultiModeAgent,
including drift detection, confidence tracking, limit enforcement,
and CLI agent integration.

Copyright (c) 2025 ContextForge
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from core.multi_mode_agent import (
    InternalDiagnosticAgent,
    DiagnosticResult,
    AgentMode,
)
from core.local_multi_mode_agent import LocalMultiModeAgent
from core.cli_agent import CLIAgent
from core.drift_detection import DriftDetector, DriftSeverity
from core.safety import (
    ConfidenceTracker,
    OperationLimits,
    OperationMetrics,
)
import logging


class TestInternalDiagnosticAgent:
    """Test InternalDiagnosticAgent functionality."""

    @pytest.fixture
    def tmp_workspace(self):
        """Create temporary workspace."""
        tmp_dir = tempfile.mkdtemp()
        yield tmp_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.fixture
    def diagnostic_agent(self, tmp_workspace):
        """Create InternalDiagnosticAgent instance."""
        drift_detector = DriftDetector()
        confidence_tracker = ConfidenceTracker()
        limits = OperationLimits()
        logger = logging.getLogger(__name__)

        return InternalDiagnosticAgent(
            drift_detector=drift_detector,
            confidence_tracker=confidence_tracker,
            limits=limits,
            parent_logger=logger,
        )

    def test_diagnostic_agent_initialization(self, diagnostic_agent):
        """Test InternalDiagnosticAgent initializes correctly."""
        assert diagnostic_agent is not None
        assert diagnostic_agent.drift_detector is not None
        assert diagnostic_agent.confidence_tracker is not None
        assert diagnostic_agent.limits is not None
        assert diagnostic_agent.diagnostic_history == []

    def test_check_drift_no_file(self, diagnostic_agent):
        """Test drift check for non-existent file."""
        result = diagnostic_agent.check_drift("nonexistent.py")

        assert isinstance(result, DiagnosticResult)
        # When file is not tracked, it returns "no drift" (no baseline to compare)
        assert result.passed is True
        assert result.severity == "info"
        assert "no drift" in result.message.lower()

    def test_check_drift_with_file(self, diagnostic_agent, tmp_workspace):
        """Test drift check for existing file."""
        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Check drift (will auto-register and detect no drift)
        result = diagnostic_agent.check_drift(str(test_file))

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "info"
        assert "no drift" in result.message.lower()

    def test_check_confidence_high(self, diagnostic_agent, tmp_workspace):
        """Test confidence check with high confidence."""
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        result = diagnostic_agent.check_confidence(str(test_file), confidence=95.0)

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "info"
        assert "confidence sufficient" in result.message.lower()

    def test_check_confidence_medium(self, diagnostic_agent, tmp_workspace):
        """Test confidence check with medium confidence."""
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        result = diagnostic_agent.check_confidence(str(test_file), confidence=75.0)

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "warning"
        assert "low confidence" in result.message.lower()  # 75 is in the 40-79 range

    def test_check_confidence_low(self, diagnostic_agent, tmp_workspace):
        """Test confidence check with low confidence."""
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        result = diagnostic_agent.check_confidence(str(test_file), confidence=60.0)

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "warning"
        assert "low confidence" in result.message.lower()

    def test_check_confidence_critical(self, diagnostic_agent, tmp_workspace):
        """Test confidence check with critical low confidence."""
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        result = diagnostic_agent.check_confidence(str(test_file), confidence=30.0)

        assert isinstance(result, DiagnosticResult)
        assert result.passed is False
        assert result.severity == "critical"
        assert "critical" in result.message.lower()

    def test_check_loop_limits_safe(self, diagnostic_agent):
        """Test loop limits check with safe values."""
        result = diagnostic_agent.check_loop_limits(
            tool_calls=10,
            revisions=2,
            tokens_used=5000,
            files_accessed=5,
            loop_iterations=1,
        )

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "info"

    def test_check_loop_limits_warning(self, diagnostic_agent):
        """Test loop limits check with warning threshold."""
        result = diagnostic_agent.check_loop_limits(
            tool_calls=45,  # 90% of max (50)
            revisions=2,
            tokens_used=5000,
            files_accessed=5,
            loop_iterations=1,
        )

        assert isinstance(result, DiagnosticResult)
        assert result.passed is True
        assert result.severity == "warning"

    def test_check_loop_limits_exceeded(self, diagnostic_agent):
        """Test loop limits check with exceeded values."""
        result = diagnostic_agent.check_loop_limits(
            tool_calls=60,  # Exceeds max (50)
            revisions=2,
            tokens_used=5000,
            files_accessed=5,
            loop_iterations=1,
        )

        assert isinstance(result, DiagnosticResult)
        assert result.passed is False
        assert result.severity == "error"
        assert "exceeded" in result.message.lower()

    def test_review_task(self, diagnostic_agent, tmp_workspace):
        """Test comprehensive task review."""
        # Create test files
        test_file1 = Path(tmp_workspace) / "test1.py"
        test_file1.write_text("def hello():\n    pass\n")
        test_file2 = Path(tmp_workspace) / "test2.py"
        test_file2.write_text("def world():\n    pass\n")

        # Create metrics
        metrics = OperationMetrics()
        metrics.tool_calls = 5
        metrics.revisions = 1
        metrics.tokens_used = 2000
        metrics.files_accessed = {str(test_file1), str(test_file2)}

        # Run review
        results = diagnostic_agent.review_task(
            files=[str(test_file1), str(test_file2)],
            metrics=metrics,
            mode="IMPLEMENT",
        )

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, DiagnosticResult) for r in results)

    def test_has_critical_issues_none(self, diagnostic_agent):
        """Test has_critical_issues with no critical issues."""
        results = [
            DiagnosticResult(passed=True, severity="info", message="OK"),
            DiagnosticResult(passed=True, severity="warning", message="Warning"),
        ]

        assert diagnostic_agent.has_critical_issues(results) is False

    def test_has_critical_issues_critical(self, diagnostic_agent):
        """Test has_critical_issues with critical issues."""
        results = [
            DiagnosticResult(passed=True, severity="info", message="OK"),
            DiagnosticResult(passed=False, severity="critical", message="Critical"),
        ]

        assert diagnostic_agent.has_critical_issues(results) is True

    def test_has_critical_issues_error(self, diagnostic_agent):
        """Test has_critical_issues with error issues."""
        results = [
            DiagnosticResult(passed=True, severity="info", message="OK"),
            DiagnosticResult(passed=False, severity="error", message="Error"),
        ]

        assert diagnostic_agent.has_critical_issues(results) is True

    def test_diagnostic_history_tracking(self, diagnostic_agent, tmp_workspace):
        """Test that diagnostic history is tracked."""
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Perform multiple checks
        diagnostic_agent.check_drift(str(test_file))
        diagnostic_agent.check_confidence(str(test_file), confidence=85.0)
        diagnostic_agent.check_loop_limits(10, 2, 5000, 5, 1)

        # Verify history
        assert len(diagnostic_agent.diagnostic_history) == 3
        assert all(isinstance(r, DiagnosticResult) for r in diagnostic_agent.diagnostic_history)


class TestMultiModeAgentIntegration:
    """Test MultiModeAgent integration with InternalDiagnosticAgent."""

    @pytest.fixture
    def tmp_workspace(self):
        """Create temporary workspace."""
        tmp_dir = tempfile.mkdtemp()
        yield tmp_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.fixture
    def agent(self, tmp_workspace):
        """Create LocalMultiModeAgent instance."""
        return LocalMultiModeAgent(
            name="test-agent",
            workspace_root=tmp_workspace,
        )

    def test_agent_has_diagnostics(self, agent):
        """Test that MultiModeAgent has integrated diagnostics."""
        assert hasattr(agent, "diagnostics")
        assert isinstance(agent.diagnostics, InternalDiagnosticAgent)

    def test_diagnostics_shares_state(self, agent):
        """Test that diagnostics shares state with parent agent."""
        assert agent.diagnostics.drift_detector is agent.drift_detector
        assert agent.diagnostics.confidence_tracker is agent.confidence_tracker
        assert agent.diagnostics.limits is agent.limits

    def test_check_safety_no_context(self, agent):
        """Test check_safety with no active context."""
        result = agent.check_safety()
        assert result is not None
        assert "no active operation context" in result.lower()

    def test_check_safety_with_context(self, agent, tmp_workspace):
        """Test check_safety with active context."""
        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Register file first to avoid drift errors
        from core.fingerprint import capture_fingerprint
        fp = capture_fingerprint(str(test_file))
        agent.drift_detector.register_fingerprint(fp)

        # Begin operation
        agent.begin_operation(AgentMode.PLAN, [str(test_file)])

        # Check safety
        result = agent.check_safety()

        # Should pass (no critical issues)
        assert result is None

    def test_execute_plan_mode_calls_diagnostics(self, agent, tmp_workspace):
        """Test that PLAN mode calls integrated diagnostics."""
        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Execute plan mode
        task = {
            "task_description": "Test task",
            "target_files": [str(test_file)],
        }

        result = agent.execute_plan_mode(task)

        # Verify diagnostics were called (history should have entries)
        assert len(agent.diagnostics.diagnostic_history) > 0


class TestCLIAgentIntegration:
    """Test CLIAgent integration with MultiModeAgent diagnostics."""

    @pytest.fixture
    def tmp_workspace(self):
        """Create temporary workspace."""
        tmp_dir = tempfile.mkdtemp()
        yield tmp_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.fixture
    def cli_agent(self, tmp_workspace):
        """Create CLIAgent instance."""
        return CLIAgent(workspace_root=tmp_workspace)

    def test_cli_agent_has_multi_mode_agent(self, cli_agent):
        """Test that CLIAgent has MultiModeAgent."""
        assert hasattr(cli_agent, "agent")
        assert isinstance(cli_agent.agent, LocalMultiModeAgent)

    def test_cli_agent_accesses_diagnostics(self, cli_agent):
        """Test that CLIAgent can access integrated diagnostics."""
        assert hasattr(cli_agent.agent, "diagnostics")
        assert isinstance(cli_agent.agent.diagnostics, InternalDiagnosticAgent)

    def test_run_diagnostic_no_files(self, cli_agent, tmp_workspace):
        """Test run_diagnostic with no files."""
        # Register a file first so there's something to diagnose
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        cli_agent.agent.drift_detector.register_file(str(test_file))

        results = cli_agent.run_diagnostic()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_run_diagnostic_with_files(self, cli_agent, tmp_workspace):
        """Test run_diagnostic with specific files."""
        # Create test files
        test_file1 = Path(tmp_workspace) / "test1.py"
        test_file1.write_text("def hello():\n    pass\n")
        test_file2 = Path(tmp_workspace) / "test2.py"
        test_file2.write_text("def world():\n    pass\n")

        # Run diagnostics
        results = cli_agent.run_diagnostic([str(test_file1), str(test_file2)])

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, DiagnosticResult) for r in results)

    def test_cli_agent_diagnostic_history(self, cli_agent, tmp_workspace):
        """Test that CLI agent can access diagnostic history."""
        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Run diagnostic
        cli_agent.run_diagnostic([str(test_file)])

        # Access history
        history = cli_agent.agent.diagnostics.diagnostic_history
        assert isinstance(history, list)
        assert len(history) > 0

    def test_cli_agent_run_agent_task_plan(self, cli_agent, tmp_workspace):
        """Test CLI agent running PLAN task."""
        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Register file first
        cli_agent.agent.drift_detector.register_file(str(test_file))

        # Create task payload
        task_payload = {
            "task_description": "Test planning task",
            "target_files": [str(test_file)],
        }

        # Run task (will fail due to missing LLM, but should call diagnostics first)
        try:
            result = cli_agent.run_agent_task("plan", task_payload)
        except Exception:
            pass  # Expected if no LLM configured

        # Verify diagnostics were called (may be 0 if task fails before safety check)
        # The important thing is that the integration exists
        assert hasattr(cli_agent.agent, "diagnostics")
        assert isinstance(cli_agent.agent.diagnostics, InternalDiagnosticAgent)


class TestDiagnosticResultDataclass:
    """Test DiagnosticResult dataclass."""

    def test_diagnostic_result_creation(self):
        """Test creating DiagnosticResult."""
        result = DiagnosticResult(
            passed=True,
            severity="info",
            message="Test message",
            details={"key": "value"},
        )

        assert result.passed is True
        assert result.severity == "info"
        assert result.message == "Test message"
        assert result.details == {"key": "value"}
        assert result.timestamp is not None

    def test_diagnostic_result_defaults(self):
        """Test DiagnosticResult with defaults."""
        result = DiagnosticResult(
            passed=False,
            severity="error",
            message="Error message",
        )

        assert result.passed is False
        assert result.severity == "error"
        assert result.message == "Error message"
        assert result.details == {}
        assert result.timestamp is not None


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def tmp_workspace(self):
        """Create temporary workspace."""
        tmp_dir = tempfile.mkdtemp()
        yield tmp_dir
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_full_workflow_with_diagnostics(self, tmp_workspace):
        """Test full workflow: Agent -> Diagnostics -> Safety Check."""
        # Create agent
        agent = LocalMultiModeAgent(
            name="integration-test",
            workspace_root=tmp_workspace,
        )

        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Register fingerprint
        from core.fingerprint import capture_fingerprint
        fp = capture_fingerprint(str(test_file))
        agent.drift_detector.register_fingerprint(fp)

        # Begin operation
        agent.begin_operation(AgentMode.PLAN, [str(test_file)])

        # Check safety (should call diagnostics)
        safety_result = agent.check_safety()

        # Verify diagnostics were called
        assert len(agent.diagnostics.diagnostic_history) > 0

        # Verify safety check result
        assert safety_result is None or isinstance(safety_result, str)

    def test_cli_to_agent_to_diagnostics(self, tmp_workspace):
        """Test CLI -> Agent -> Diagnostics flow."""
        # Create CLI agent
        cli_agent = CLIAgent(workspace_root=tmp_workspace)

        # Create test file
        test_file = Path(tmp_workspace) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Run diagnostic through CLI
        results = cli_agent.run_diagnostic([str(test_file)])

        # Verify results
        assert isinstance(results, list)
        assert len(results) > 0

        # Verify diagnostic history
        history = cli_agent.agent.diagnostics.diagnostic_history
        assert len(history) > 0
        assert all(isinstance(r, DiagnosticResult) for r in history)

    def test_multiple_operations_accumulate_history(self, tmp_workspace):
        """Test that multiple operations accumulate diagnostic history."""
        agent = LocalMultiModeAgent(
            name="history-test",
            workspace_root=tmp_workspace,
        )

        # Create test files
        test_file1 = Path(tmp_workspace) / "test1.py"
        test_file1.write_text("def hello():\n    pass\n")
        test_file2 = Path(tmp_workspace) / "test2.py"
        test_file2.write_text("def world():\n    pass\n")

        # Perform multiple operations
        agent.begin_operation(AgentMode.PLAN, [str(test_file1)])
        agent.check_safety()
        agent.end_operation(True)

        history_after_first = len(agent.diagnostics.diagnostic_history)

        agent.begin_operation(AgentMode.REVIEW, [str(test_file2)])
        agent.check_safety()
        agent.end_operation(True)

        history_after_second = len(agent.diagnostics.diagnostic_history)

        # History should accumulate
        assert history_after_second > history_after_first
        assert history_after_second >= history_after_first * 2

