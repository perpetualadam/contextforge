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


class TestLanguageTools:
    """Test language tools configuration."""

    def test_language_id_enum(self):
        """Test LanguageId enum contains expected languages."""
        from services.code_analysis.language_tools import LanguageId

        # Test original languages
        assert LanguageId.PYTHON.value == "python"
        assert LanguageId.JAVASCRIPT.value == "javascript"
        assert LanguageId.TYPESCRIPT.value == "typescript"
        assert LanguageId.RUBY.value == "ruby"
        assert LanguageId.GO.value == "go"
        assert LanguageId.RUST.value == "rust"
        assert LanguageId.JAVA.value == "java"
        assert LanguageId.CSHARP.value == "csharp"
        assert LanguageId.CPP.value == "cpp"
        assert LanguageId.C.value == "c"
        assert LanguageId.PHP.value == "php"
        assert LanguageId.SHELL.value == "shell"

        # Test newly added languages
        assert LanguageId.HTML.value == "html"
        assert LanguageId.CSS.value == "css"
        assert LanguageId.JULIA.value == "julia"
        assert LanguageId.SWIFT.value == "swift"

    def test_test_framework_dataclass(self):
        """Test TestFramework dataclass structure."""
        from services.code_analysis.language_tools import TestFramework

        framework = TestFramework(
            name="pytest",
            command="pytest",
            install_command="pip install pytest",
            file_pattern="test_*.py",
            description="Python testing framework"
        )

        assert framework.name == "pytest"
        assert framework.command == "pytest"
        assert framework.open_source is True
        assert framework.free is True

    def test_debug_tool_dataclass(self):
        """Test DebugTool dataclass structure."""
        from services.code_analysis.language_tools import DebugTool

        tool = DebugTool(
            name="pdb",
            command="python -m pdb",
            install_command="",
            description="Python debugger"
        )

        assert tool.name == "pdb"
        assert tool.open_source is True
        assert tool.free is True

    def test_linter_dataclass(self):
        """Test Linter dataclass structure."""
        from services.code_analysis.language_tools import Linter

        linter = Linter(
            name="pylint",
            command="pylint",
            install_command="pip install pylint",
            description="Python linter"
        )

        assert linter.name == "pylint"
        assert linter.open_source is True
        assert linter.free is True

    def test_language_tools_registry(self):
        """Test LANGUAGE_TOOLS_REGISTRY contains all expected languages."""
        from services.code_analysis.language_tools import (
            LANGUAGE_TOOLS_REGISTRY, LanguageId
        )

        # Original languages
        assert LanguageId.PYTHON in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.JAVASCRIPT in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.TYPESCRIPT in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.RUBY in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.GO in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.RUST in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.JAVA in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.CSHARP in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.CPP in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.C in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.PHP in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.SHELL in LANGUAGE_TOOLS_REGISTRY

        # Newly added languages
        assert LanguageId.HTML in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.CSS in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.JULIA in LANGUAGE_TOOLS_REGISTRY
        assert LanguageId.SWIFT in LANGUAGE_TOOLS_REGISTRY

    def test_python_tools(self):
        """Test Python tools configuration."""
        from services.code_analysis.language_tools import (
            get_tools_by_language, LanguageId
        )

        tools = get_tools_by_language(LanguageId.PYTHON)

        assert tools is not None
        assert tools.language == LanguageId.PYTHON
        assert ".py" in tools.file_extensions

        # Check test frameworks
        framework_names = [f.name for f in tools.test_frameworks]
        assert "pytest" in framework_names

        # Check debug tools
        debug_names = [d.name for d in tools.debug_tools]
        assert "pdb" in debug_names

        # Check linters
        linter_names = [l.name for l in tools.linters]
        assert "pylint" in linter_names

    def test_html_tools(self):
        """Test HTML tools configuration."""
        from services.code_analysis.language_tools import (
            get_tools_by_language, LanguageId
        )

        tools = get_tools_by_language(LanguageId.HTML)

        assert tools is not None
        assert tools.language == LanguageId.HTML
        assert ".html" in tools.file_extensions

        # Check linters
        linter_names = [l.name for l in tools.linters]
        assert "HTMLHint" in linter_names

    def test_css_tools(self):
        """Test CSS tools configuration."""
        from services.code_analysis.language_tools import (
            get_tools_by_language, LanguageId
        )

        tools = get_tools_by_language(LanguageId.CSS)

        assert tools is not None
        assert tools.language == LanguageId.CSS
        assert ".css" in tools.file_extensions

        # Check linters
        linter_names = [l.name for l in tools.linters]
        assert "Stylelint" in linter_names

    def test_julia_tools(self):
        """Test Julia tools configuration."""
        from services.code_analysis.language_tools import (
            get_tools_by_language, LanguageId
        )

        tools = get_tools_by_language(LanguageId.JULIA)

        assert tools is not None
        assert tools.language == LanguageId.JULIA
        assert ".jl" in tools.file_extensions

        # Check test frameworks
        framework_names = [f.name for f in tools.test_frameworks]
        assert "Test.jl" in framework_names

        # Check debug tools
        debug_names = [d.name for d in tools.debug_tools]
        assert "Debugger.jl" in debug_names

    def test_swift_tools(self):
        """Test Swift tools configuration."""
        from services.code_analysis.language_tools import (
            get_tools_by_language, LanguageId
        )

        tools = get_tools_by_language(LanguageId.SWIFT)

        assert tools is not None
        assert tools.language == LanguageId.SWIFT
        assert ".swift" in tools.file_extensions

        # Check test frameworks
        framework_names = [f.name for f in tools.test_frameworks]
        assert "XCTest" in framework_names

        # Check linters
        linter_names = [l.name for l in tools.linters]
        assert "SwiftLint" in linter_names

    def test_get_tools_by_extension(self):
        """Test getting tools by file extension."""
        from services.code_analysis.language_tools import (
            get_tools_by_extension, LanguageId
        )

        # Python
        py_tools = get_tools_by_extension(".py")
        assert py_tools is not None
        assert py_tools.language == LanguageId.PYTHON

        # JavaScript
        js_tools = get_tools_by_extension(".js")
        assert js_tools is not None
        assert js_tools.language == LanguageId.JAVASCRIPT

        # HTML
        html_tools = get_tools_by_extension(".html")
        assert html_tools is not None
        assert html_tools.language == LanguageId.HTML

        # CSS
        css_tools = get_tools_by_extension(".css")
        assert css_tools is not None
        assert css_tools.language == LanguageId.CSS

        # Julia
        jl_tools = get_tools_by_extension(".jl")
        assert jl_tools is not None
        assert jl_tools.language == LanguageId.JULIA

        # Swift
        swift_tools = get_tools_by_extension(".swift")
        assert swift_tools is not None
        assert swift_tools.language == LanguageId.SWIFT

        # Unknown extension
        unknown_tools = get_tools_by_extension(".xyz")
        assert unknown_tools is None

    def test_get_all_test_frameworks(self):
        """Test getting all test frameworks."""
        from services.code_analysis.language_tools import get_all_test_frameworks

        frameworks = get_all_test_frameworks()

        assert len(frameworks) >= 16  # 16 languages in registry

        # Check some specific frameworks
        from services.code_analysis.language_tools import LanguageId
        assert LanguageId.PYTHON in frameworks
        assert len(frameworks[LanguageId.PYTHON]) > 0

    def test_get_all_debug_tools(self):
        """Test getting all debug tools."""
        from services.code_analysis.language_tools import get_all_debug_tools

        tools = get_all_debug_tools()

        assert len(tools) >= 16  # 16 languages in registry

        from services.code_analysis.language_tools import LanguageId
        assert LanguageId.PYTHON in tools
        assert len(tools[LanguageId.PYTHON]) > 0

    def test_get_all_linters(self):
        """Test getting all linters."""
        from services.code_analysis.language_tools import get_all_linters

        linters = get_all_linters()

        assert len(linters) >= 16  # 16 languages in registry

        from services.code_analysis.language_tools import LanguageId
        assert LanguageId.PYTHON in linters
        assert len(linters[LanguageId.PYTHON]) > 0

    def test_all_tools_are_open_source(self):
        """Test all tools are marked as open source and free."""
        from services.code_analysis.language_tools import LANGUAGE_TOOLS_REGISTRY

        for lang_id, tools in LANGUAGE_TOOLS_REGISTRY.items():
            for framework in tools.test_frameworks:
                assert framework.open_source is True, f"{framework.name} should be open source"
                assert framework.free is True, f"{framework.name} should be free"

            for debug_tool in tools.debug_tools:
                assert debug_tool.open_source is True, f"{debug_tool.name} should be open source"
                assert debug_tool.free is True, f"{debug_tool.name} should be free"

            for linter in tools.linters:
                assert linter.open_source is True, f"{linter.name} should be open source"
                assert linter.free is True, f"{linter.name} should be free"
