"""
ContextForge Multi-Agent Orchestrator.

Provides async orchestration for parallel module indexing and retrieval.
Supports hierarchical context retrieval (module -> file -> function).

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum

from services.utils import utc_now, duration_ms

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of an agent task."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ModuleTask:
    """Task for processing a module."""
    module_path: str
    operation: str  # "index", "search", "update"
    parameters: Dict[str, Any] = field(default_factory=dict)


class ModuleAgent:
    """
    Agent for processing a single module.
    
    Handles indexing, searching, and updating embeddings for a specific module.
    """
    
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.module_name = module_path.replace("/", ".").replace("\\", ".")
        self._indexed = False
    
    async def index(self, force: bool = False) -> TaskResult:
        """Index the module files and generate embeddings."""
        start_time = utc_now()
        task_id = f"index:{self.module_name}"
        
        try:
            # Import here to avoid circular imports
            from services.vector_index.index import VectorIndex
            
            index = VectorIndex()
            files_indexed = 0
            chunks_created = 0
            
            import os
            for root, dirs, files in os.walk(self.module_path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            # Add to index with module metadata
                            result = index.add_document(content, {
                                "file_path": file_path,
                                "module_name": self.module_name,
                                "type": "code"
                            })
                            files_indexed += 1
                            chunks_created += len(result) if isinstance(result, list) else 1
                        except Exception as e:
                            logger.warning(f"Failed to index {file_path}: {e}")
            
            self._indexed = True

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result={"files_indexed": files_indexed, "chunks_created": chunks_created},
                duration_ms=duration_ms(start_time),
                started_at=start_time,
                completed_at=utc_now()
            )
        except Exception as e:
            logger.error(f"Module indexing failed for {self.module_name}: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms(start_time),
                started_at=start_time,
                completed_at=utc_now()
            )
    
    async def search(self, query: str, top_k: int = 10) -> TaskResult:
        """Search within the module context."""
        start_time = utc_now()
        task_id = f"search:{self.module_name}"

        try:
            from services.vector_index.index import VectorIndex

            index = VectorIndex()
            # Search with module filter
            results = index.search(query, top_k=top_k, filters={"module_name": self.module_name})

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=results,
                duration_ms=duration_ms(start_time),
                started_at=start_time,
                completed_at=utc_now()
            )
        except Exception as e:
            logger.error(f"Module search failed for {self.module_name}: {e}")
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                started_at=start_time,
                completed_at=utc_now()
            )


class Orchestrator:
    """
    Multi-agent orchestrator for parallel operations.

    Coordinates multiple module agents to perform:
    - Parallel module indexing
    - Parallel retrieval across modules
    - Result aggregation and ranking

    Usage:
        orchestrator = Orchestrator()
        await orchestrator.index_modules(["core", "utils", "api"])
        results = await orchestrator.parallel_search("find function X", top_k=10)
    """

    def __init__(self, max_concurrent: int = None):
        from services.config import get_config
        config = get_config()

        self.max_concurrent = max_concurrent or config.agent.max_concurrent
        self._agents: Dict[str, ModuleAgent] = {}
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._active_tasks: Set[str] = set()

    def register_module(self, module_path: str) -> ModuleAgent:
        """Register a module for processing."""
        if module_path not in self._agents:
            self._agents[module_path] = ModuleAgent(module_path)
        return self._agents[module_path]

    async def _run_with_semaphore(self, coro: Callable) -> Any:
        """Run coroutine with semaphore for concurrency control."""
        async with self._semaphore:
            return await coro

    async def index_modules(self, module_paths: List[str], force: bool = False) -> List[TaskResult]:
        """
        Index multiple modules in parallel.

        Args:
            module_paths: List of module paths to index
            force: Force re-indexing even if already indexed

        Returns:
            List of TaskResult for each module
        """
        logger.info(f"Indexing {len(module_paths)} modules in parallel (max_concurrent={self.max_concurrent})")

        # Create agents for each module
        agents = [self.register_module(path) for path in module_paths]

        # Run indexing in parallel with semaphore
        tasks = [self._run_with_semaphore(agent.index(force=force)) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to TaskResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(TaskResult(
                    task_id=f"index:{module_paths[i]}",
                    status=TaskStatus.FAILED,
                    error=str(result)
                ))
            else:
                final_results.append(result)

        succeeded = sum(1 for r in final_results if r.status == TaskStatus.COMPLETED)
        logger.info(f"Indexing complete: {succeeded}/{len(module_paths)} modules succeeded")

        return final_results

    async def parallel_search(self, query: str, top_k: int = 10,
                              module_paths: List[str] = None) -> Dict[str, Any]:
        """
        Search across multiple modules in parallel.

        Args:
            query: Search query
            top_k: Number of results per module
            module_paths: Optional list of modules to search (all if None)

        Returns:
            Aggregated and ranked results from all modules
        """
        if module_paths:
            agents = [self.register_module(path) for path in module_paths]
        else:
            agents = list(self._agents.values())

        if not agents:
            logger.warning("No modules registered for search")
            return {"results": [], "module_results": {}}

        logger.info(f"Searching {len(agents)} modules for: {query[:50]}...")

        # Search all modules in parallel
        tasks = [self._run_with_semaphore(agent.search(query, top_k=top_k)) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results from all modules
        all_results = []
        module_results = {}

        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                module_results[agent.module_name] = {"error": str(result)}
            elif result.status == TaskStatus.COMPLETED:
                module_results[agent.module_name] = result.result
                if isinstance(result.result, list):
                    all_results.extend(result.result)

        # Sort by score and deduplicate
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        seen_ids = set()
        unique_results = []
        for r in all_results:
            rid = r.get("id") or r.get("chunk_id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                unique_results.append(r)

        return {
            "results": unique_results[:top_k],
            "module_results": module_results,
            "total_results": len(unique_results)
        }

    async def detect_changes(self, commit_hash: str = None) -> List[str]:
        """
        Detect changed files since last index.

        Uses git to find modified files for incremental indexing.
        """
        import subprocess

        try:
            if commit_hash:
                cmd = ["git", "diff", "--name-only", commit_hash]
            else:
                cmd = ["git", "diff", "--name-only", "HEAD~1"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
                return files
        except Exception as e:
            logger.warning(f"Failed to detect changes: {e}")

        return []

    async def incremental_index(self) -> Dict[str, Any]:
        """
        Perform incremental indexing on changed files.

        Only re-indexes files that have changed since the last commit.
        """
        changed_files = await self.detect_changes()

        if not changed_files:
            logger.info("No changed files detected")
            return {"files_updated": 0, "status": "no_changes"}

        logger.info(f"Incremental indexing {len(changed_files)} changed files")

        # Group files by module
        module_files: Dict[str, List[str]] = {}
        for file_path in changed_files:
            # Extract module from path (first directory)
            parts = file_path.replace("\\", "/").split("/")
            module = parts[0] if len(parts) > 1 else "root"
            if module not in module_files:
                module_files[module] = []
            module_files[module].append(file_path)

        # Index changed files in each module
        results = await self.index_modules(list(module_files.keys()), force=True)

        return {
            "files_updated": len(changed_files),
            "modules_updated": len(module_files),
            "results": [r.result for r in results if r.status == TaskStatus.COMPLETED]
        }


# =============================================================================
# Specialized Agents for Code Review, Testing, and Documentation
# =============================================================================

class ReviewAgent:
    """
    Agent for code review and bug detection.

    Combines static analysis with LLM-powered review.
    """

    def __init__(self):
        self.name = "ReviewAgent"

    async def review_file(self, file_path: str, content: str = None,
                          include_static_analysis: bool = True) -> Dict[str, Any]:
        """
        Perform comprehensive code review on a file.

        Args:
            file_path: Path to the file
            content: Optional file content
            include_static_analysis: Run linters/type checkers

        Returns:
            Review results with issues and suggestions
        """
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )
        from services.code_analysis import get_code_analyzer, AnalyzerType

        result = {
            "file": file_path,
            "static_analysis": [],
            "llm_review": None,
            "issues": [],
            "suggestions": []
        }

        # Load content if not provided
        if content is None:
            try:
                from pathlib import Path
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                result["error"] = str(e)
                return result

        # Run static analysis
        if include_static_analysis:
            analyzer = get_code_analyzer()
            analysis_results = await analyzer.analyze_file(file_path)
            result["static_analysis"] = [
                {"analyzer": r.analyzer, "issues": len(r.issues), "summary": r.summary}
                for r in analysis_results
            ]

            # Extract issues for prompt
            for ar in analysis_results:
                for issue in ar.issues:
                    result["issues"].append({
                        "rule": issue.rule,
                        "message": issue.message,
                        "line": issue.line,
                        "severity": issue.severity.value,
                        "analyzer": issue.analyzer
                    })

        # Build context for LLM review
        aggregator = get_context_aggregator()
        context = await aggregator.gather_context(content[:500], file_path)
        context.lint_results = result["issues"]

        # Build enhanced prompt
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            TaskType.CODE_REVIEW,
            context,
            code=content,
            language=self._detect_language(file_path)
        )

        result["prompt"] = prompt  # For debugging/transparency

        return result

    async def detect_bugs(self, file_path: str, content: str = None) -> Dict[str, Any]:
        """
        Specialized bug detection.

        Args:
            file_path: Path to the file
            content: Optional file content

        Returns:
            Bug detection results
        """
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData
        )
        from services.code_analysis import get_code_analyzer, AnalyzerType

        if content is None:
            from pathlib import Path
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')

        # Run security-focused analysis
        analyzer = get_code_analyzer()
        results = await analyzer.analyze_file(
            file_path,
            analyzer_types=[AnalyzerType.SECURITY, AnalyzerType.LINTER]
        )

        context = ContextData()
        for r in results:
            for issue in r.issues:
                context.security_findings.append({
                    "rule": issue.rule,
                    "message": issue.message,
                    "severity": issue.severity.value,
                    "location": f"{file_path}:{issue.line}"
                })

        builder = PromptBuilder()
        prompt = builder.build_prompt(
            TaskType.BUG_DETECTION,
            context,
            code=content,
            language=self._detect_language(file_path)
        )

        return {
            "file": file_path,
            "security_findings": context.security_findings,
            "prompt": prompt
        }

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        from pathlib import Path
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust"
        }
        return ext_map.get(Path(file_path).suffix.lower(), "text")


class TestAgent:
    """
    Agent for test generation and verification.

    Generates tests and tracks test results.
    """

    def __init__(self):
        self.name = "TestAgent"

    async def generate_tests(self, file_path: str, content: str = None,
                             test_framework: str = "pytest") -> Dict[str, Any]:
        """
        Generate tests for a file.

        Args:
            file_path: Path to the source file
            content: Optional file content
            test_framework: Test framework to use

        Returns:
            Generated test code and metadata
        """
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )

        if content is None:
            from pathlib import Path
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')

        # Gather context
        aggregator = get_context_aggregator()
        context = await aggregator.gather_context(content[:500], file_path)

        # Build test generation prompt
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            TaskType.TEST_GENERATION,
            context,
            code=content,
            language=self._detect_language(file_path),
            test_framework=test_framework
        )

        return {
            "file": file_path,
            "test_framework": test_framework,
            "prompt": prompt
        }

    async def run_tests(self, test_path: str = "tests/",
                        pattern: str = None) -> Dict[str, Any]:
        """
        Run tests and collect results.

        Args:
            test_path: Path to test directory
            pattern: Optional test pattern

        Returns:
            Test results summary
        """
        import subprocess
        import time

        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
        if pattern:
            cmd.extend(["-k", pattern])

        start = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration_ms = int((time.time() - start) * 1000)

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "duration_ms": duration_ms,
                "summary": self._parse_pytest_output(result.stdout)
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Test execution timed out"}

    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """Parse pytest output for summary."""
        import re
        summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        # Look for summary line like "10 passed, 2 failed, 1 skipped"
        match = re.search(r'(\d+) passed', output)
        if match:
            summary["passed"] = int(match.group(1))

        match = re.search(r'(\d+) failed', output)
        if match:
            summary["failed"] = int(match.group(1))

        match = re.search(r'(\d+) skipped', output)
        if match:
            summary["skipped"] = int(match.group(1))

        return summary

    def _detect_language(self, file_path: str) -> str:
        from pathlib import Path
        ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript"}
        return ext_map.get(Path(file_path).suffix.lower(), "text")


class DocAgent:
    """
    Agent for documentation generation and updates.
    """

    def __init__(self):
        self.name = "DocAgent"

    async def generate_docs(self, file_path: str, content: str = None,
                            doc_style: str = "Google") -> Dict[str, Any]:
        """
        Generate documentation for a file.

        Args:
            file_path: Path to the source file
            content: Optional file content
            doc_style: Documentation style (Google, NumPy, Sphinx)

        Returns:
            Generated documentation
        """
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData
        )

        if content is None:
            from pathlib import Path
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')

        context = ContextData()
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            TaskType.DOCUMENTATION,
            context,
            code=content,
            language=self._detect_language(file_path),
            doc_style=doc_style
        )

        return {
            "file": file_path,
            "doc_style": doc_style,
            "prompt": prompt
        }

    def _detect_language(self, file_path: str) -> str:
        from pathlib import Path
        ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript"}
        return ext_map.get(Path(file_path).suffix.lower(), "text")


# Singleton instances
_orchestrator: Optional[Orchestrator] = None
_review_agent: Optional[ReviewAgent] = None
_test_agent: Optional[TestAgent] = None
_doc_agent: Optional[DocAgent] = None


def get_orchestrator() -> Orchestrator:
    """Get singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def get_review_agent() -> ReviewAgent:
    """Get singleton ReviewAgent instance."""
    global _review_agent
    if _review_agent is None:
        _review_agent = ReviewAgent()
    return _review_agent


def get_test_agent() -> TestAgent:
    """Get singleton TestAgent instance."""
    global _test_agent
    if _test_agent is None:
        _test_agent = TestAgent()
    return _test_agent


def get_doc_agent() -> DocAgent:
    """Get singleton DocAgent instance."""
    global _doc_agent
    if _doc_agent is None:
        _doc_agent = DocAgent()
    return _doc_agent

