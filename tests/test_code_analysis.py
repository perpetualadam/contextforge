"""
Tests for the ContextForge code analysis module.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestSeverity:
    """Test Severity enum."""
    
    def test_severity_levels(self):
        """Test severity levels exist."""
        from services.code_analysis import Severity
        
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"


class TestAnalyzerType:
    """Test AnalyzerType enum."""
    
    def test_analyzer_types(self):
        """Test analyzer types exist."""
        from services.code_analysis import AnalyzerType
        
        assert AnalyzerType.LINTER.value == "linter"
        assert AnalyzerType.TYPE_CHECKER.value == "type_checker"
        assert AnalyzerType.SECURITY.value == "security"
        assert AnalyzerType.COMPLEXITY.value == "complexity"


class TestAnalysisIssue:
    """Test AnalysisIssue dataclass."""
    
    def test_issue_creation(self):
        """Test creating an AnalysisIssue."""
        from services.code_analysis import AnalysisIssue, Severity
        
        issue = AnalysisIssue(
            rule="E501",
            message="line too long",
            file_path="test.py",
            line=10,
            column=80,
            severity=Severity.LOW
        )
        
        assert issue.rule == "E501"
        assert issue.message == "line too long"
        assert issue.line == 10
        assert issue.severity == Severity.LOW


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""
    
    def test_result_creation(self):
        """Test creating an AnalysisResult."""
        from services.code_analysis import AnalysisResult, AnalyzerType
        
        result = AnalysisResult(
            analyzer="pylint",
            analyzer_type=AnalyzerType.LINTER
        )
        
        assert result.analyzer == "pylint"
        assert result.issues == []
        assert result.error is None


class TestPylintAnalyzer:
    """Test PylintAnalyzer class."""
    
    def test_analyzer_properties(self):
        """Test analyzer properties."""
        from services.code_analysis import PylintAnalyzer, AnalyzerType
        
        analyzer = PylintAnalyzer()
        
        assert analyzer.name == "pylint"
        assert analyzer.analyzer_type == AnalyzerType.LINTER
        assert ".py" in analyzer.supported_extensions
    
    def test_map_severity(self):
        """Test severity mapping."""
        from services.code_analysis import PylintAnalyzer, Severity
        
        analyzer = PylintAnalyzer()
        
        assert analyzer._map_severity("error") == Severity.HIGH
        assert analyzer._map_severity("warning") == Severity.MEDIUM
        assert analyzer._map_severity("convention") == Severity.LOW
        assert analyzer._map_severity("fatal") == Severity.CRITICAL


class TestFlake8Analyzer:
    """Test Flake8Analyzer class."""
    
    def test_analyzer_properties(self):
        """Test analyzer properties."""
        from services.code_analysis import Flake8Analyzer, AnalyzerType
        
        analyzer = Flake8Analyzer()
        
        assert analyzer.name == "flake8"
        assert analyzer.analyzer_type == AnalyzerType.LINTER
    
    def test_map_severity(self):
        """Test severity mapping."""
        from services.code_analysis import Flake8Analyzer, Severity
        
        analyzer = Flake8Analyzer()
        
        assert analyzer._map_severity("E999") == Severity.HIGH
        assert analyzer._map_severity("F401") == Severity.HIGH
        assert analyzer._map_severity("E501") == Severity.MEDIUM
        assert analyzer._map_severity("W503") == Severity.LOW


class TestCodeAnalyzer:
    """Test CodeAnalyzer class."""
    
    def test_analyzer_creation(self):
        """Test creating a CodeAnalyzer."""
        from services.code_analysis import CodeAnalyzer
        
        analyzer = CodeAnalyzer()
        
        assert ".py" in analyzer.analyzers
        assert len(analyzer.analyzers[".py"]) > 0
    
    def test_get_analyzers_for_file(self):
        """Test getting analyzers for a file."""
        from services.code_analysis import CodeAnalyzer
        
        analyzer = CodeAnalyzer()
        
        py_analyzers = analyzer.get_analyzers_for_file("test.py")
        assert len(py_analyzers) > 0
        
        txt_analyzers = analyzer.get_analyzers_for_file("test.txt")
        assert len(txt_analyzers) == 0
    
    def test_format_for_prompt(self):
        """Test formatting results for prompt."""
        from services.code_analysis import (
            CodeAnalyzer, AnalysisResult, AnalysisIssue, 
            AnalyzerType, Severity
        )
        
        analyzer = CodeAnalyzer()
        
        results = [
            AnalysisResult(
                analyzer="pylint",
                analyzer_type=AnalyzerType.LINTER,
                issues=[
                    AnalysisIssue(
                        rule="E501",
                        message="line too long",
                        file_path="test.py",
                        line=10,
                        severity=Severity.MEDIUM
                    )
                ]
            )
        ]
        
        formatted = analyzer.format_for_prompt(results)
        
        assert "pylint" in formatted
        assert "E501" in formatted
    
    def test_singleton_accessor(self):
        """Test get_code_analyzer singleton."""
        from services.code_analysis import get_code_analyzer
        import services.code_analysis as ca_module
        
        ca_module._analyzer = None
        
        a1 = get_code_analyzer()
        a2 = get_code_analyzer()
        
        assert a1 is a2

