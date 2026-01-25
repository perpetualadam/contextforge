"""
Integration tests for Multi-Mode Agent Architecture.

Tests drift detection, fingerprinting, diff-based edits, confidence scoring,
and safety mechanisms.

Copyright (c) 2025 ContextForge
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import time
import sys

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from core.fingerprint import capture_fingerprint, FileFingerprint
from core.drift_detection import DriftDetector, DriftSeverity
from core.diff_engine import DiffEngine
from core.safety import ConfidenceTracker, LoopDetector, OperationMetrics, OperationLimits
from core.multi_mode_agent import AgentMode
from core.local_multi_mode_agent import LocalMultiModeAgent


class TestFingerprinting:
    """Test file fingerprinting functionality."""
    
    def test_capture_fingerprint(self, tmp_path):
        """Test capturing file fingerprint."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")
        
        # Capture fingerprint
        fp = capture_fingerprint(str(test_file))
        
        assert fp is not None
        assert fp.path == str(test_file)
        assert fp.content_hash != ""
        assert fp.size > 0
        assert "hello" in fp.symbols
    
    def test_fingerprint_matches_filesystem(self, tmp_path):
        """Test fingerprint matching."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        fp = capture_fingerprint(str(test_file))
        
        # Should match immediately
        assert fp.matches_filesystem()
        
        # Modify file
        time.sleep(0.2)  # Ensure mtime changes
        test_file.write_text("def hello():\n    print('modified')\n")
        
        # Should not match
        assert not fp.matches_filesystem()
    
    def test_symbol_extraction(self, tmp_path):
        """Test symbol extraction from code."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class MyClass:
    def method1(self):
        pass
    
    def method2(self):
        pass

def standalone_function():
    pass
""")
        
        fp = capture_fingerprint(str(test_file))
        
        assert "MyClass" in fp.symbols
        assert "method1" in fp.symbols
        assert "method2" in fp.symbols
        assert "standalone_function" in fp.symbols


class TestDriftDetection:
    """Test drift detection functionality."""
    
    def test_no_drift(self, tmp_path):
        """Test when no drift occurs."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        detector = DriftDetector()
        detector.register_file(str(test_file))
        
        result = detector.detect_drift()
        
        assert not result.has_drift
        assert len(result.stable_files) == 1
        assert result.max_severity == DriftSeverity.NONE
    
    def test_moderate_drift(self, tmp_path):
        """Test moderate drift (content changed, symbols intact)."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        detector = DriftDetector()
        detector.register_file(str(test_file))
        
        # Modify content but keep symbols
        time.sleep(0.2)
        test_file.write_text("def hello():\n    print('modified')\n")
        
        result = detector.detect_drift()
        
        assert result.has_drift
        assert len(result.drifted_files) == 1
        assert result.max_severity == DriftSeverity.MODERATE
    
    def test_major_drift(self, tmp_path):
        """Test major drift (symbols changed)."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        detector = DriftDetector()
        detector.register_file(str(test_file))
        
        # Change symbols
        time.sleep(0.2)
        test_file.write_text("def goodbye():\n    pass\n")
        
        result = detector.detect_drift()
        
        assert result.has_drift
        assert result.max_severity == DriftSeverity.MAJOR
        
        event = result.drifted_files[0]
        added, removed = event.get_changed_symbols()
        assert "goodbye" in added
        assert "hello" in removed
    
    def test_missing_file(self, tmp_path):
        """Test drift when file is deleted."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        detector = DriftDetector()
        detector.register_file(str(test_file))
        
        # Delete file
        test_file.unlink()
        
        result = detector.detect_drift()
        
        assert result.has_drift
        assert len(result.missing_files) == 1
        assert result.max_severity == DriftSeverity.MAJOR


class TestDiffEngine:
    """Test diff-based edit functionality."""
    
    def test_compute_diff(self, tmp_path):
        """Test diff computation."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")
        
        engine = DiffEngine()
        new_content = "line1\nmodified\nline3\n"
        
        diff = engine.compute_diff(str(test_file), new_content)
        
        assert diff is not None
        assert diff.file_path == str(test_file)
        assert len(diff.line_diffs) > 0
    
    def test_apply_diff(self, tmp_path):
        """Test diff application."""
        test_file = tmp_path / "test.py"
        original = "line1\nline2\nline3\n"
        test_file.write_text(original)
        
        engine = DiffEngine()
        new_content = "line1\nmodified\nline3\n"
        
        diff = engine.compute_diff(str(test_file), new_content)
        success = engine.apply_diff(diff, dry_run=False)
        
        assert success
        # Note: Actual diff application logic may need refinement
        # This is a placeholder test


class TestSafety:
    """Test safety mechanisms."""
    
    def test_confidence_levels(self):
        """Test confidence level categorization."""
        tracker = ConfidenceTracker()
        
        tracker.set_confidence("file1.py", 95.0)
        tracker.set_confidence("file2.py", 85.0)
        tracker.set_confidence("file3.py", 70.0)
        tracker.set_confidence("file4.py", 30.0)
        
        fc1 = tracker.get_confidence("file1.py")
        fc4 = tracker.get_confidence("file4.py")
        
        assert fc1.level.value == "high"
        assert fc4.level.value == "critical"
        assert fc4.should_stop()
        
        critical = tracker.get_critical_files()
        assert len(critical) == 1
    
    def test_loop_detection(self):
        """Test loop detection."""
        detector = LoopDetector(max_identical_states=3)
        
        state = {"mode": "plan", "files": ["a.py"]}
        
        # First occurrence
        assert not detector.record_state(state)
        # Second occurrence
        assert not detector.record_state(state)
        # Third occurrence - loop detected
        assert detector.record_state(state)
    
    def test_operation_limits(self):
        """Test operation limit checking."""
        limits = OperationLimits(
            max_tool_calls=10,
            max_tokens=1000,
        )
        
        metrics = OperationMetrics()
        metrics.tool_calls = 5
        metrics.tokens_used = 500
        
        # Within limits
        assert metrics.check_limits(limits) is None
        
        # Exceed tool calls
        metrics.tool_calls = 15
        error = metrics.check_limits(limits)
        assert error is not None
        assert "Tool call limit" in error


@pytest.fixture
def workspace(tmp_path):
    """Create temporary workspace."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    return workspace_dir


class TestMultiModeAgent:
    """Test multi-mode agent integration."""
    
    def test_agent_initialization(self, workspace):
        """Test agent initialization."""
        agent = LocalMultiModeAgent(
            name="test-agent",
            workspace_root=str(workspace)
        )
        
        assert agent.name == "test-agent"
        assert agent.current_mode == AgentMode.PLAN
        assert agent.drift_detector is not None
        assert agent.diff_engine is not None
    
    def test_mode_switching(self, workspace):
        """Test mode switching."""
        agent = LocalMultiModeAgent(workspace_root=str(workspace))
        
        assert agent.current_mode == AgentMode.PLAN
        
        agent.switch_mode(AgentMode.IMPLEMENT)
        assert agent.current_mode == AgentMode.IMPLEMENT
    
    def test_plan_mode_execution(self, workspace):
        """Test PLAN mode execution."""
        agent = LocalMultiModeAgent(workspace_root=str(workspace))
        
        # Create test file
        test_file = workspace / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        
        result = agent.execute(AgentMode.PLAN, {
            "task_description": "Test planning",
            "context_files": ["test.py"],
        })
        
        assert result.success
        assert result.mode == AgentMode.PLAN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

