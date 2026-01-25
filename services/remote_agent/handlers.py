"""
Task handlers for Remote Agent capabilities.

Implements the specialized agent handlers per the blueprint:
- IndexAgent: Updates embeddings per module
- TestAgent: Runs unit/integration tests
- ReviewAgent: Static analysis + bug detection
- RefactorAgent: Multi-file reasoning & changes
- DocAgent: Architecture notes + docstrings

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class IndexHandler:
    """Handler for index agent tasks - updates embeddings per module."""
    
    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Index files and update embeddings.
        
        Payload:
            module_path: Path to module to index
            force: Force re-indexing even if unchanged
        """
        module_path = payload.get("module_path", "")
        force = payload.get("force", False)
        
        from services.orchestrator import ModuleAgent
        
        agent = ModuleAgent(module_path)
        result = await agent.index(force=force)
        
        return {
            "status": result.status.value,
            "result": result.result,
            "duration_ms": result.duration_ms,
            "error": result.error
        }


class TestHandler:
    """Handler for test agent tasks - runs unit/integration tests."""
    
    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate or run tests.
        
        Payload:
            action: "generate" or "run"
            file_path: Path to file (for generate)
            test_path: Path to tests (for run)
            test_framework: Framework to use (pytest, jest, etc.)
        """
        action = payload.get("action", "run")
        
        if action == "generate":
            return await self._generate_tests(payload)
        else:
            return await self._run_tests(payload)
    
    async def _generate_tests(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate tests for a file."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )
        
        file_path = payload.get("file_path", "")
        content = payload.get("content")
        test_framework = payload.get("test_framework", "pytest")
        
        if not content and file_path:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        
        aggregator = get_context_aggregator()
        context = await aggregator.gather_context(content[:500] if content else "", file_path)
        
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            TaskType.TEST_GENERATION,
            context,
            code=content or "",
            test_framework=test_framework
        )
        
        return {"file": file_path, "test_framework": test_framework, "prompt": prompt}
    
    async def _run_tests(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run tests and return results."""
        import subprocess
        import time
        import re
        
        test_path = payload.get("test_path", "tests/")
        pattern = payload.get("pattern")
        
        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
        if pattern:
            cmd.extend(["-k", pattern])
        
        start = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration_ms = int((time.time() - start) * 1000)
            
            # Parse summary
            summary = {"passed": 0, "failed": 0, "skipped": 0}
            for key in ["passed", "failed", "skipped"]:
                match = re.search(rf'(\d+) {key}', result.stdout)
                if match:
                    summary[key] = int(match.group(1))
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "duration_ms": duration_ms,
                "summary": summary
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Test execution timed out"}


class ReasoningHandler:
    """Handler for reasoning agent tasks - LLM-based analysis and planning."""

    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform reasoning/analysis task.

        Payload:
            query: The question or task to reason about
            context: Additional context for reasoning
            reasoning_type: Type of reasoning (analysis, planning, recommendation)
            max_tokens: Maximum tokens for response
        """
        query = payload.get("query", "")
        context = payload.get("context", "")
        reasoning_type = payload.get("reasoning_type", "analysis")

        return await self._perform_reasoning(query, context, reasoning_type, payload)

    async def _perform_reasoning(
        self,
        query: str,
        context: str,
        reasoning_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform LLM-based reasoning."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, get_context_aggregator
        )

        result = {
            "query": query,
            "reasoning_type": reasoning_type,
            "generated": False
        }

        if not query:
            result["error"] = "No query provided"
            return result

        # Map reasoning type to task type
        task_type_map = {
            "analysis": TaskType.CODE_ANALYSIS,
            "planning": TaskType.ARCHITECTURE,
            "recommendation": TaskType.CODE_ANALYSIS,
            "explanation": TaskType.EXPLANATION,
        }
        task_type = task_type_map.get(reasoning_type, TaskType.CODE_ANALYSIS)

        try:
            aggregator = get_context_aggregator()
            ctx = await aggregator.gather_context(query, payload.get("file_path", ""))

            builder = PromptBuilder()
            result["prompt"] = builder.build_prompt(
                task_type,
                ctx,
                query=query,
                additional_context=context
            )
            result["generated"] = True
        except Exception as e:
            logger.warning(f"Reasoning prompt build failed: {e}")
            result["error"] = str(e)

        return result


class CritiqueHandler:
    """Handler for critique agent tasks - code and analysis review."""

    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform critique/review task.

        Payload:
            content: Content to critique (code, analysis, etc.)
            content_type: Type of content (code, analysis, plan)
            critique_focus: Focus areas (correctness, style, performance, security)
            file_path: Optional file path for context
        """
        content = payload.get("content", "")
        content_type = payload.get("content_type", "code")
        critique_focus = payload.get("critique_focus", ["correctness", "style"])

        return await self._perform_critique(content, content_type, critique_focus, payload)

    async def _perform_critique(
        self,
        content: str,
        content_type: str,
        critique_focus: List[str],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform critique on content."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, get_context_aggregator
        )

        result = {
            "content_type": content_type,
            "critique_focus": critique_focus,
            "generated": False
        }

        if not content:
            result["error"] = "No content to critique"
            return result

        # Use code review for code content, otherwise general analysis
        task_type = TaskType.CODE_REVIEW if content_type == "code" else TaskType.CODE_ANALYSIS

        try:
            aggregator = get_context_aggregator()
            file_path = payload.get("file_path", "")
            ctx = await aggregator.gather_context(content[:500], file_path)

            builder = PromptBuilder()
            result["prompt"] = builder.build_prompt(
                task_type,
                ctx,
                code=content if content_type == "code" else "",
                additional_context=f"Focus areas: {', '.join(critique_focus)}"
            )
            result["generated"] = True
        except Exception as e:
            logger.warning(f"Critique prompt build failed: {e}")
            result["error"] = str(e)

        return result


class ReviewHandler:
    """Handler for review agent tasks - static analysis + bug detection."""
    
    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform code review.
        
        Payload:
            file_path: Path to file to review
            content: Optional code content
            include_static_analysis: Run linters
            focus: Review focus (general, security, performance)
        """
        file_path = payload.get("file_path", "")
        content = payload.get("content")
        include_static = payload.get("include_static_analysis", True)
        
        return await self._review_file(file_path, content, include_static)
    
    async def _review_file(self, file_path: str, content: str = None,
                           include_static: bool = True) -> Dict[str, Any]:
        """Perform comprehensive code review."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )
        from services.code_analysis import get_code_analyzer
        
        result = {
            "file": file_path,
            "static_analysis": [],
            "issues": []
        }
        
        if content is None and file_path:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                result["error"] = str(e)
                return result
        
        # Run static analysis
        if include_static:
            analyzer = get_code_analyzer()
            analysis_results = await analyzer.analyze_file(file_path)
            result["static_analysis"] = [
                {"analyzer": r.analyzer, "issues": len(r.issues), "summary": r.summary}
                for r in analysis_results
            ]
            
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
        context = await aggregator.gather_context(content[:500] if content else "", file_path)
        context.lint_results = result["issues"]
        
        builder = PromptBuilder()
        result["prompt"] = builder.build_prompt(
            TaskType.CODE_REVIEW,
            context,
            code=content or "",
            language=self._detect_language(file_path)
        )
        
        return result
    
    def _detect_language(self, file_path: str) -> str:
        ext_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                   ".java": "java", ".go": "go", ".rs": "rust"}
        return ext_map.get(Path(file_path).suffix.lower(), "text")


class RefactorHandler:
    """Handler for refactor agent tasks - multi-file reasoning & changes."""

    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform refactoring analysis.

        Payload:
            files: List of file paths to analyze
            refactor_type: Type of refactoring (extract_method, rename, move, etc.)
            target: Target symbol or code block
            new_name: New name (for rename operations)
        """
        files = payload.get("files", [])
        refactor_type = payload.get("refactor_type", "general")
        target = payload.get("target", "")

        return await self._analyze_refactoring(files, refactor_type, target, payload)

    async def _analyze_refactoring(self, files: List[str], refactor_type: str,
                                   target: str, payload: Dict) -> Dict[str, Any]:
        """Analyze files for refactoring opportunities."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )

        result = {
            "refactor_type": refactor_type,
            "files_analyzed": len(files),
            "target": target,
            "suggestions": []
        }

        # Gather context from all files
        aggregator = get_context_aggregator()
        all_content = []

        for file_path in files[:10]:  # Limit to 10 files
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                all_content.append(f"# File: {file_path}\n{content[:2000]}")
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")

        combined = "\n\n".join(all_content)
        context = await aggregator.gather_context(target or combined[:500], files[0] if files else "")

        builder = PromptBuilder()
        result["prompt"] = builder.build_prompt(
            TaskType.REFACTORING,
            context,
            code=combined,
            refactor_type=refactor_type,
            target=target,
            new_name=payload.get("new_name", "")
        )

        return result


class DocHandler:
    """Handler for doc agent tasks - architecture notes + docstrings."""

    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate documentation.

        Payload:
            file_path: Path to file
            content: Optional code content
            doc_style: Style (google, numpy, sphinx)
            doc_type: Type (docstring, readme, architecture)
        """
        file_path = payload.get("file_path", "")
        content = payload.get("content")
        doc_style = payload.get("doc_style", "google")
        doc_type = payload.get("doc_type", "docstring")

        return await self._generate_docs(file_path, content, doc_style, doc_type)

    async def _generate_docs(self, file_path: str, content: str = None,
                             doc_style: str = "google", doc_type: str = "docstring") -> Dict[str, Any]:
        """Generate documentation for code."""
        from services.prompt_enhancer import (
            PromptBuilder, TaskType, ContextData, get_context_aggregator
        )

        result = {
            "file": file_path,
            "doc_style": doc_style,
            "doc_type": doc_type
        }

        if content is None and file_path:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                result["error"] = str(e)
                return result

        aggregator = get_context_aggregator()
        context = await aggregator.gather_context(content[:500] if content else "", file_path)

        builder = PromptBuilder()
        result["prompt"] = builder.build_prompt(
            TaskType.DOCUMENTATION,
            context,
            code=content or "",
            doc_style=doc_style,
            doc_type=doc_type
        )

        return result


class DebuggingHandler:
    """Handler for debugging agent tasks - diagnostics and context tracing."""

    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run diagnostics on context bundle.

        Payload:
            contexts: List of context dicts to analyze
            mutation_log: Optional mutation log for lineage tracing
            config: Optional diagnostic config overrides
        """
        contexts = payload.get("contexts", [])
        mutation_log = payload.get("mutation_log", [])
        config = payload.get("config", {})

        if not contexts:
            return {"error": "No contexts provided for diagnostics"}

        return await self._run_diagnostics(contexts, mutation_log, config)

    async def _run_diagnostics(
        self,
        contexts: List[Dict[str, Any]],
        mutation_log: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run diagnostic analysis on contexts."""
        from services.core import DebuggingAgent, ContextBundle, DiagnosticConfig

        # Build config from payload
        diag_config = DiagnosticConfig(
            stale_threshold_seconds=config.get("stale_threshold_seconds", 3600),
            detect_contradictions=config.get("detect_contradictions", True),
            verbosity=config.get("verbosity", "normal")
        )

        agent = DebuggingAgent(config=diag_config)

        # Create bundle from contexts
        bundle = ContextBundle(contexts=contexts, mutation_log=mutation_log)

        # Run diagnostics
        result_bundle = await agent.invoke(bundle)

        # Extract diagnostic context from result
        diagnostic_ctx = None
        for ctx in result_bundle.contexts:
            if ctx.get("type") == "diagnostic":
                diagnostic_ctx = ctx
                break

        if diagnostic_ctx:
            return {
                "status": "success",
                "diagnostic": diagnostic_ctx.get("content", {}),
                "report": agent.format_report(bundle)
            }
        else:
            return {
                "status": "error",
                "error": "Failed to generate diagnostic context"
            }


# Handler registry for easy lookup
AGENT_HANDLERS = {
    "index_agent": IndexHandler(),
    "test_agent": TestHandler(),
    "reasoning_agent": ReasoningHandler(),
    "critique_agent": CritiqueHandler(),
    "review_agent": ReviewHandler(),
    "refactor_agent": RefactorHandler(),
    "doc_agent": DocHandler(),
    "debugging_agent": DebuggingHandler(),
}


def get_handler(capability: str):
    """Get handler for a capability."""
    return AGENT_HANDLERS.get(capability)

