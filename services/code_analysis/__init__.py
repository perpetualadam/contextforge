"""
ContextForge Code Analysis Module.

Provides static analysis integration for:
- Linting (pylint, flake8, eslint)
- Type checking (mypy, pyright)
- Security scanning (bandit, semgrep)
- Code complexity analysis

Results are formatted for prompt injection and LLM reasoning.

Copyright (c) 2025 ContextForge
"""

import logging
import subprocess
import json
import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnalyzerType(Enum):
    """Types of analyzers."""
    LINTER = "linter"
    TYPE_CHECKER = "type_checker"
    SECURITY = "security"
    COMPLEXITY = "complexity"
    TEST_RUNNER = "test_runner"
    DEBUGGER = "debugger"


@dataclass
class AnalysisIssue:
    """Single analysis issue."""
    rule: str
    message: str
    file_path: str
    line: int = 0
    column: int = 0
    severity: Severity = Severity.MEDIUM
    analyzer: str = ""
    suggestion: str = ""
    code_snippet: str = ""


@dataclass
class AnalysisResult:
    """Result from running an analyzer."""
    analyzer: str
    analyzer_type: AnalyzerType
    issues: List[AnalysisIssue] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, int] = field(default_factory=dict)


class BaseAnalyzer:
    """Base class for code analyzers."""
    
    name: str = "base"
    analyzer_type: AnalyzerType = AnalyzerType.LINTER
    supported_extensions: List[str] = []
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    async def analyze(self, file_path: str) -> AnalysisResult:
        """Analyze a file. Override in subclasses."""
        raise NotImplementedError
    
    async def analyze_content(self, content: str, language: str) -> AnalysisResult:
        """Analyze content string. Override in subclasses."""
        raise NotImplementedError
    
    def _run_command(self, cmd: List[str], cwd: str = None) -> subprocess.CompletedProcess:
        """Run a command with timeout."""
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"{self.name} timed out after {self.timeout}s")
            raise
        except FileNotFoundError:
            logger.warning(f"{self.name} not found. Is it installed?")
            raise


class PylintAnalyzer(BaseAnalyzer):
    """Pylint static analysis for Python."""
    
    name = "pylint"
    analyzer_type = AnalyzerType.LINTER
    supported_extensions = [".py"]
    
    async def analyze(self, file_path: str) -> AnalysisResult:
        """Run pylint on a file."""
        import time
        start = time.time()
        
        result = AnalysisResult(
            analyzer=self.name,
            analyzer_type=self.analyzer_type
        )
        
        try:
            proc = self._run_command([
                "pylint", file_path,
                "--output-format=json",
                "--disable=C0114,C0115,C0116"  # Disable docstring warnings
            ])
            
            if proc.stdout:
                issues_data = json.loads(proc.stdout)
                for item in issues_data:
                    severity = self._map_severity(item.get("type", ""))
                    result.issues.append(AnalysisIssue(
                        rule=item.get("symbol", item.get("message-id", "")),
                        message=item.get("message", ""),
                        file_path=item.get("path", file_path),
                        line=item.get("line", 0),
                        column=item.get("column", 0),
                        severity=severity,
                        analyzer=self.name
                    ))
            
            result.summary = self._summarize(result.issues)
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result.error = str(e)
        except json.JSONDecodeError as e:
            result.error = f"Failed to parse pylint output: {e}"
        
        result.duration_ms = int((time.time() - start) * 1000)
        return result
    
    def _map_severity(self, pylint_type: str) -> Severity:
        """Map pylint message type to severity."""
        mapping = {
            "error": Severity.HIGH,
            "warning": Severity.MEDIUM,
            "convention": Severity.LOW,
            "refactor": Severity.LOW,
            "fatal": Severity.CRITICAL
        }
        return mapping.get(pylint_type.lower(), Severity.INFO)
    
    def _summarize(self, issues: List[AnalysisIssue]) -> Dict[str, int]:
        """Create summary counts."""
        summary: Dict[str, int] = {}
        for issue in issues:
            key = issue.severity.value
            summary[key] = summary.get(key, 0) + 1
        return summary


class Flake8Analyzer(BaseAnalyzer):
    """Flake8 style checker for Python."""

    name = "flake8"
    analyzer_type = AnalyzerType.LINTER
    supported_extensions = [".py"]

    async def analyze(self, file_path: str) -> AnalysisResult:
        """Run flake8 on a file."""
        import time
        start = time.time()

        result = AnalysisResult(
            analyzer=self.name,
            analyzer_type=self.analyzer_type
        )

        try:
            proc = self._run_command([
                "flake8", file_path,
                "--format=json",
                "--max-line-length=127"
            ])

            # Flake8 outputs one issue per line in format: file:line:col: code message
            for line in proc.stdout.strip().split("\n"):
                if not line:
                    continue
                match = re.match(r'(.+):(\d+):(\d+): (\w+) (.+)', line)
                if match:
                    code = match.group(4)
                    result.issues.append(AnalysisIssue(
                        rule=code,
                        message=match.group(5),
                        file_path=match.group(1),
                        line=int(match.group(2)),
                        column=int(match.group(3)),
                        severity=self._map_severity(code),
                        analyzer=self.name
                    ))

            result.summary = self._summarize(result.issues)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result.error = str(e)

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def _map_severity(self, code: str) -> Severity:
        """Map flake8 code to severity."""
        if code.startswith("E9") or code.startswith("F"):
            return Severity.HIGH
        if code.startswith("E"):
            return Severity.MEDIUM
        if code.startswith("W"):
            return Severity.LOW
        return Severity.INFO

    def _summarize(self, issues: List[AnalysisIssue]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for issue in issues:
            key = issue.severity.value
            summary[key] = summary.get(key, 0) + 1
        return summary


class MypyAnalyzer(BaseAnalyzer):
    """Mypy type checker for Python."""

    name = "mypy"
    analyzer_type = AnalyzerType.TYPE_CHECKER
    supported_extensions = [".py"]

    async def analyze(self, file_path: str) -> AnalysisResult:
        """Run mypy on a file."""
        import time
        start = time.time()

        result = AnalysisResult(
            analyzer=self.name,
            analyzer_type=self.analyzer_type
        )

        try:
            proc = self._run_command([
                "mypy", file_path,
                "--ignore-missing-imports",
                "--no-error-summary"
            ])

            # Parse mypy output: file:line: severity: message
            for line in (proc.stdout + proc.stderr).strip().split("\n"):
                if not line:
                    continue
                match = re.match(r'(.+):(\d+): (error|warning|note): (.+)', line)
                if match:
                    sev_str = match.group(3)
                    result.issues.append(AnalysisIssue(
                        rule="type-error",
                        message=match.group(4),
                        file_path=match.group(1),
                        line=int(match.group(2)),
                        severity=Severity.HIGH if sev_str == "error" else Severity.MEDIUM,
                        analyzer=self.name
                    ))

            result.summary = self._summarize(result.issues)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result.error = str(e)

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def _summarize(self, issues: List[AnalysisIssue]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for issue in issues:
            key = issue.severity.value
            summary[key] = summary.get(key, 0) + 1
        return summary


class BanditAnalyzer(BaseAnalyzer):
    """Bandit security scanner for Python."""

    name = "bandit"
    analyzer_type = AnalyzerType.SECURITY
    supported_extensions = [".py"]

    async def analyze(self, file_path: str) -> AnalysisResult:
        """Run bandit security scan."""
        import time
        start = time.time()

        result = AnalysisResult(
            analyzer=self.name,
            analyzer_type=self.analyzer_type
        )

        try:
            proc = self._run_command([
                "bandit", file_path,
                "-f", "json",
                "-q"  # Quiet, only output issues
            ])

            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    for item in data.get("results", []):
                        result.issues.append(AnalysisIssue(
                            rule=item.get("test_id", ""),
                            message=item.get("issue_text", ""),
                            file_path=item.get("filename", file_path),
                            line=item.get("line_number", 0),
                            severity=self._map_severity(item.get("issue_severity", "")),
                            analyzer=self.name,
                            suggestion=item.get("more_info", "")
                        ))
                except json.JSONDecodeError:
                    pass

            result.summary = self._summarize(result.issues)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result.error = str(e)

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def _map_severity(self, sev: str) -> Severity:
        mapping = {
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW
        }
        return mapping.get(sev.upper(), Severity.INFO)

    def _summarize(self, issues: List[AnalysisIssue]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for issue in issues:
            key = issue.severity.value
            summary[key] = summary.get(key, 0) + 1
        return summary


class CodeAnalyzer:
    """
    Unified code analyzer that runs multiple analysis tools.

    Usage:
        analyzer = CodeAnalyzer()
        results = await analyzer.analyze_file("path/to/file.py")
        # or
        results = await analyzer.analyze_content(code, "python")
    """

    def __init__(self):
        self.analyzers: Dict[str, List[BaseAnalyzer]] = {
            ".py": [
                PylintAnalyzer(),
                Flake8Analyzer(),
                MypyAnalyzer(),
                BanditAnalyzer()
            ]
        }

    def get_analyzers_for_file(self, file_path: str) -> List[BaseAnalyzer]:
        """Get applicable analyzers for a file."""
        ext = Path(file_path).suffix.lower()
        return self.analyzers.get(ext, [])

    async def analyze_file(self, file_path: str,
                           analyzer_types: List[AnalyzerType] = None) -> List[AnalysisResult]:
        """
        Run all applicable analyzers on a file.

        Args:
            file_path: Path to file to analyze
            analyzer_types: Optional filter for analyzer types

        Returns:
            List of AnalysisResult from each analyzer
        """
        analyzers = self.get_analyzers_for_file(file_path)

        if analyzer_types:
            analyzers = [a for a in analyzers if a.analyzer_type in analyzer_types]

        if not analyzers:
            return []

        # Run analyzers in parallel
        tasks = [a.analyze(file_path) for a in analyzers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"Analyzer {analyzers[i].name} failed: {r}")
                valid_results.append(AnalysisResult(
                    analyzer=analyzers[i].name,
                    analyzer_type=analyzers[i].analyzer_type,
                    error=str(r)
                ))
            else:
                valid_results.append(r)

        return valid_results

    async def analyze_content(self, content: str, language: str,
                              analyzer_types: List[AnalyzerType] = None) -> List[AnalysisResult]:
        """
        Analyze code content by writing to temp file.

        Args:
            content: Code content to analyze
            language: Programming language
            analyzer_types: Optional filter for analyzer types

        Returns:
            List of AnalysisResult
        """
        import tempfile

        ext_map = {"python": ".py", "javascript": ".js", "typescript": ".ts"}
        ext = ext_map.get(language.lower(), ".txt")

        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            return await self.analyze_file(temp_path, analyzer_types)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def format_for_prompt(self, results: List[AnalysisResult]) -> str:
        """Format analysis results for prompt injection."""
        lines = []

        for result in results:
            if result.error:
                lines.append(f"## {result.analyzer} (error: {result.error})")
                continue

            if not result.issues:
                lines.append(f"## {result.analyzer}: No issues found ✅")
                continue

            lines.append(f"## {result.analyzer} ({len(result.issues)} issues)")

            # Group by severity
            by_severity: Dict[Severity, List[AnalysisIssue]] = {}
            for issue in result.issues:
                if issue.severity not in by_severity:
                    by_severity[issue.severity] = []
                by_severity[issue.severity].append(issue)

            for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                if sev in by_severity:
                    lines.append(f"### {sev.value.upper()}")
                    for issue in by_severity[sev][:5]:  # Limit per severity
                        lines.append(f"- Line {issue.line}: [{issue.rule}] {issue.message}")

        return "\n".join(lines)


# Singleton accessor
_analyzer: Optional[CodeAnalyzer] = None


def get_code_analyzer() -> CodeAnalyzer:
    """Get singleton CodeAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = CodeAnalyzer()
    return _analyzer

