"""
ContextForge Prompt Enhancement System.

Provides context-aware prompt injection, task-specialized templates,
and multi-step prompt chaining for improved LLM accuracy.

Features:
- Context-aware prompt injection (module summaries, embeddings, test results, git history)
- Task-specialized templates (code review, test generation, refactoring, docs)
- Multi-step prompt chaining with langchain-style execution
- Token budget management

Copyright (c) 2025 ContextForge
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Specialized task types for prompt templates."""
    CODE_REVIEW = "code_review"
    BUG_DETECTION = "bug_detection"
    TEST_GENERATION = "test_generation"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    EXPLAIN = "explain"
    SECURITY_AUDIT = "security_audit"
    PERFORMANCE = "performance"
    GENERAL = "general"


@dataclass
class ContextData:
    """Aggregated context data for prompt injection."""
    module_summary: str = ""
    file_embeddings: List[Dict[str, Any]] = field(default_factory=list)
    function_embeddings: List[Dict[str, Any]] = field(default_factory=list)
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    git_history: List[Dict[str, Any]] = field(default_factory=list)
    lint_results: List[Dict[str, Any]] = field(default_factory=list)
    security_findings: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    custom_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainStep:
    """Single step in a prompt chain."""
    name: str
    prompt_template: str
    output_key: str
    depends_on: List[str] = field(default_factory=list)
    post_process: Optional[Callable[[str], str]] = None


@dataclass
class ChainResult:
    """Result from executing a prompt chain."""
    steps_completed: int
    outputs: Dict[str, str]
    final_output: str
    errors: List[str] = field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0


# Task-specific prompt templates
TASK_TEMPLATES: Dict[TaskType, str] = {
    TaskType.CODE_REVIEW: """You are an expert code reviewer. Analyze the following code for:
- Code quality and readability
- Potential bugs and edge cases
- Performance issues
- Security vulnerabilities
- Best practices violations

{context_section}

CODE TO REVIEW:
```{language}
{code}
```

Provide:
1. Summary of issues found (HIGH/MEDIUM/LOW severity)
2. Specific line-by-line suggestions
3. Refactoring recommendations
4. Overall assessment (APPROVE/REQUEST_CHANGES/NEEDS_DISCUSSION)""",

    TaskType.BUG_DETECTION: """You are an expert bug detector. Analyze the code for:
- Logic errors
- Off-by-one errors
- Null/undefined handling
- Race conditions
- Resource leaks
- Error handling issues

{context_section}

CODE TO ANALYZE:
```{language}
{code}
```

{lint_results}

{security_findings}

For each bug found, provide:
1. Location (file:line if available)
2. Bug type and severity
3. Root cause analysis
4. Suggested fix with code example""",

    TaskType.TEST_GENERATION: """You are an expert test engineer. Generate comprehensive tests for:

{context_section}

CODE TO TEST:
```{language}
{code}
```

{existing_tests}

Generate tests that include:
1. Happy path tests
2. Edge case tests (empty inputs, max values, etc.)
3. Error handling tests
4. Integration tests (if applicable)

Use framework: {test_framework}
Output complete, runnable test code.""",

    TaskType.REFACTOR: """You are an expert software architect. Refactor the following code for:
- Improved readability
- Better modularity
- Enhanced testability
- Performance optimization
- Design pattern application

{context_section}

CODE TO REFACTOR:
```{language}
{code}
```

{dependency_info}

Provide:
1. Refactoring plan with rationale
2. Impact analysis (affected files/functions)
3. Complete refactored code
4. Migration steps if breaking changes""",

    TaskType.DOCUMENTATION: """You are a technical writer. Generate documentation for:

{context_section}

CODE TO DOCUMENT:
```{language}
{code}
```

Generate:
1. Module/class overview
2. Function/method docstrings (with params, returns, examples)
3. Usage examples
4. Architecture notes (if applicable)

Style: {doc_style}""",

    TaskType.SECURITY_AUDIT: """You are a security expert. Audit the code for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication/authorization issues
- Data exposure risks
- Cryptographic weaknesses
- Dependency vulnerabilities

{context_section}

CODE TO AUDIT:
```{language}
{code}
```

{security_findings}

For each vulnerability:
1. CWE/OWASP classification
2. Severity (CRITICAL/HIGH/MEDIUM/LOW)
3. Attack vector
4. Remediation with code fix""",

    TaskType.GENERAL: """You are ContextForge Assistant, an expert code assistant.

{context_section}

USER QUERY: {query}

Provide:
- Concise, accurate answer
- Code examples if applicable
- Cite sources using [SOURCE n] format"""
}


class PromptBuilder:
    """
    Context-aware prompt builder with token budget management.

    Automatically injects relevant context while respecting token limits.
    """

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens
        self._approx_chars_per_token = 4

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // self._approx_chars_per_token

    def _truncate_to_budget(self, text: str, budget_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        max_chars = budget_tokens * self._approx_chars_per_token
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 20] + "\n... [truncated]"

    def build_context_section(self, context: ContextData,
                              budget_tokens: int = 2000) -> str:
        """Build formatted context section from ContextData."""
        sections = []
        remaining_budget = budget_tokens

        # Module summary (high priority)
        if context.module_summary:
            section = f"## Repository Context\n{context.module_summary}"
            tokens = self._estimate_tokens(section)
            if tokens <= remaining_budget:
                sections.append(section)
                remaining_budget -= tokens

        # Test results (high priority for bug detection)
        if context.test_results:
            test_summary = self._format_test_results(context.test_results)
            section = f"## Recent Test Results\n{test_summary}"
            tokens = self._estimate_tokens(section)
            if tokens <= remaining_budget:
                sections.append(section)
                remaining_budget -= tokens

        # Git history (medium priority)
        if context.git_history:
            git_summary = self._format_git_history(context.git_history[:5])
            section = f"## Recent Git History\n{git_summary}"
            tokens = self._estimate_tokens(section)
            if tokens <= remaining_budget:
                sections.append(section)
                remaining_budget -= tokens

        # Lint results
        if context.lint_results:
            lint_summary = self._format_lint_results(context.lint_results)
            section = f"## Static Analysis Results\n{lint_summary}"
            tokens = self._estimate_tokens(section)
            if tokens <= remaining_budget:
                sections.append(section)
                remaining_budget -= tokens

        # File embeddings (semantic context)
        if context.file_embeddings:
            file_summary = self._format_embeddings(context.file_embeddings[:3])
            section = f"## Related Files\n{file_summary}"
            tokens = self._estimate_tokens(section)
            if tokens <= remaining_budget:
                sections.append(section)
                remaining_budget -= tokens

        return "\n\n".join(sections) if sections else "No additional context available."

    def _format_test_results(self, results: List[Dict[str, Any]]) -> str:
        """Format test results for prompt inclusion."""
        lines = []
        passed = sum(1 for r in results if r.get("passed", False))
        failed = len(results) - passed
        lines.append(f"Summary: {passed} passed, {failed} failed")

        for r in results[:10]:  # Limit to 10 results
            status = "✅" if r.get("passed") else "❌"
            name = r.get("test_name", r.get("name", "unknown"))
            lines.append(f"{status} {name}")
            if not r.get("passed") and r.get("error_message"):
                lines.append(f"   Error: {r['error_message'][:100]}")

        return "\n".join(lines)

    def _format_git_history(self, commits: List[Dict[str, Any]]) -> str:
        """Format git history for prompt inclusion."""
        lines = []
        for c in commits:
            hash_short = c.get("hash", "")[:7]
            msg = c.get("message", "")[:60]
            author = c.get("author", "")
            lines.append(f"- [{hash_short}] {msg} ({author})")
        return "\n".join(lines)

    def _format_lint_results(self, results: List[Dict[str, Any]]) -> str:
        """Format lint/analysis results for prompt inclusion."""
        lines = []
        for r in results[:15]:  # Limit
            severity = r.get("severity", "info").upper()
            msg = r.get("message", "")
            loc = r.get("location", "")
            lines.append(f"[{severity}] {loc}: {msg}")
        return "\n".join(lines)

    def _format_embeddings(self, embeddings: List[Dict[str, Any]]) -> str:
        """Format related file embeddings."""
        lines = []
        for e in embeddings:
            path = e.get("file_path", e.get("path", "unknown"))
            score = e.get("score", 0)
            snippet = e.get("text", "")[:150]
            lines.append(f"- {path} (relevance: {score:.2f})")
            if snippet:
                lines.append(f"  ```\n  {snippet}\n  ```")
        return "\n".join(lines)

    def build_prompt(self, task_type: TaskType, context: ContextData,
                     code: str = "", query: str = "", language: str = "python",
                     **kwargs) -> str:
        """
        Build a complete prompt with context injection.

        Args:
            task_type: Type of task for template selection
            context: Context data to inject
            code: Code to analyze/review
            query: User query (for general tasks)
            language: Programming language
            **kwargs: Additional template variables

        Returns:
            Formatted prompt string
        """
        template = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES[TaskType.GENERAL])

        # Calculate token budget for context
        code_tokens = self._estimate_tokens(code)
        template_base_tokens = 500  # Approximate template overhead
        context_budget = self.max_tokens - code_tokens - template_base_tokens
        context_budget = max(context_budget, 500)  # Minimum context

        context_section = self.build_context_section(context, context_budget)

        # Build template variables
        vars_dict = {
            "context_section": context_section,
            "code": code,
            "query": query,
            "language": language,
            "lint_results": self._format_lint_results(context.lint_results) if context.lint_results else "",
            "security_findings": self._format_security_findings(context.security_findings) if context.security_findings else "",
            "dependency_info": self._format_dependencies(context.dependencies) if context.dependencies else "",
            "existing_tests": "",
            "test_framework": kwargs.get("test_framework", "pytest"),
            "doc_style": kwargs.get("doc_style", "Google"),
            **kwargs
        }

        try:
            return template.format(**vars_dict)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            # Fallback: replace missing vars with empty string
            import re
            result = template
            for key in re.findall(r'\{(\w+)\}', template):
                if key not in vars_dict:
                    result = result.replace(f'{{{key}}}', '')
            return result.format(**vars_dict)

    def _format_security_findings(self, findings: List[Dict[str, Any]]) -> str:
        """Format security findings."""
        if not findings:
            return ""
        lines = ["## Security Scan Results"]
        for f in findings[:10]:
            severity = f.get("severity", "unknown").upper()
            rule = f.get("rule", f.get("check_id", ""))
            msg = f.get("message", "")
            loc = f.get("location", "")
            lines.append(f"[{severity}] {rule}: {msg}")
            if loc:
                lines.append(f"   Location: {loc}")
        return "\n".join(lines)

    def _format_dependencies(self, deps: Dict[str, List[str]]) -> str:
        """Format dependency information."""
        if not deps:
            return ""
        lines = ["## Dependencies"]
        for file_path, imports in list(deps.items())[:5]:
            lines.append(f"- {file_path}:")
            for imp in imports[:5]:
                lines.append(f"  - {imp}")
        return "\n".join(lines)


class PromptChain:
    """
    Multi-step prompt chaining for complex reasoning tasks.

    Supports:
    - Sequential step execution
    - Parallel step execution (for independent steps)
    - Step dependencies
    - Output aggregation

    Example usage:
        chain = PromptChain([
            ChainStep("identify", "Identify files: {query}", "files"),
            ChainStep("analyze", "Analyze: {files}", "analysis", depends_on=["files"]),
            ChainStep("recommend", "Recommend: {analysis}", "recommendations", depends_on=["analysis"])
        ])
        result = await chain.execute(llm_func, {"query": "find auth bugs"})
    """

    def __init__(self, steps: List[ChainStep]):
        self.steps = steps
        self._validate_steps()

    def _validate_steps(self):
        """Validate step dependencies exist."""
        step_names = {s.name for s in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_names:
                    raise ValueError(f"Step '{step.name}' depends on unknown step '{dep}'")

    async def execute(self, llm_func: Callable[[str], Awaitable[str]],
                      initial_vars: Dict[str, Any]) -> ChainResult:
        """
        Execute the prompt chain.

        Args:
            llm_func: Async function that takes prompt and returns LLM response
            initial_vars: Initial variables available to all steps

        Returns:
            ChainResult with all outputs
        """
        start_time = datetime.now()
        outputs: Dict[str, str] = {}
        errors: List[str] = []
        completed = 0

        # Build dependency graph
        pending = set(s.name for s in self.steps)
        completed_steps: set = set()

        while pending:
            # Find steps that can run (all deps satisfied)
            runnable = []
            for step in self.steps:
                if step.name in pending:
                    deps_satisfied = all(d in completed_steps for d in step.depends_on)
                    if deps_satisfied:
                        runnable.append(step)

            if not runnable:
                errors.append(f"Deadlock: no runnable steps. Pending: {pending}")
                break

            # Execute runnable steps (could parallelize here)
            for step in runnable:
                try:
                    # Build variables for this step
                    step_vars = {**initial_vars, **outputs}

                    # Format prompt
                    try:
                        prompt = step.prompt_template.format(**step_vars)
                    except KeyError as e:
                        errors.append(f"Step '{step.name}' missing variable: {e}")
                        pending.discard(step.name)
                        continue

                    # Execute LLM
                    response = await llm_func(prompt)

                    # Post-process if defined
                    if step.post_process:
                        response = step.post_process(response)

                    outputs[step.output_key] = response
                    completed += 1
                    completed_steps.add(step.name)
                    pending.discard(step.name)

                except Exception as e:
                    errors.append(f"Step '{step.name}' failed: {str(e)}")
                    pending.discard(step.name)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # Final output is the last step's output
        final_output = outputs.get(self.steps[-1].output_key, "") if self.steps else ""

        return ChainResult(
            steps_completed=completed,
            outputs=outputs,
            final_output=final_output,
            errors=errors,
            duration_ms=duration_ms
        )


# Pre-built chains for common workflows
def create_code_review_chain() -> PromptChain:
    """Create a multi-step code review chain."""
    return PromptChain([
        ChainStep(
            name="identify_issues",
            prompt_template="""Analyze this code and list all potential issues:
{code}

Output a numbered list of issues with severity (HIGH/MEDIUM/LOW).""",
            output_key="issues"
        ),
        ChainStep(
            name="suggest_fixes",
            prompt_template="""For these issues:
{issues}

Original code:
{code}

Provide specific code fixes for each issue.""",
            output_key="fixes",
            depends_on=["identify_issues"]
        ),
        ChainStep(
            name="summarize",
            prompt_template="""Summarize this code review:
Issues found: {issues}
Suggested fixes: {fixes}

Provide:
1. Executive summary (2-3 sentences)
2. Priority actions
3. Overall verdict (APPROVE/REQUEST_CHANGES)""",
            output_key="summary",
            depends_on=["suggest_fixes"]
        )
    ])


def create_bug_detection_chain() -> PromptChain:
    """Create a multi-step bug detection chain."""
    return PromptChain([
        ChainStep(
            name="static_analysis",
            prompt_template="""Perform static analysis on this code:
{code}

Look for: null checks, error handling, resource leaks, type issues.
Output findings as JSON array.""",
            output_key="static_findings"
        ),
        ChainStep(
            name="logic_analysis",
            prompt_template="""Analyze logic and control flow:
{code}

Static findings: {static_findings}

Look for: logic errors, race conditions, edge cases.
Output findings as JSON array.""",
            output_key="logic_findings",
            depends_on=["static_analysis"]
        ),
        ChainStep(
            name="synthesize",
            prompt_template="""Synthesize bug report:
Static Analysis: {static_findings}
Logic Analysis: {logic_findings}

Create prioritized bug report with severity and fix suggestions.""",
            output_key="bug_report",
            depends_on=["logic_analysis"]
        )
    ])


class ContextAggregator:
    """
    Aggregates context from multiple sources for prompt injection.

    Sources:
    - Vector index (semantic search)
    - Git history
    - Test results
    - Static analysis
    - Dependency graph
    """

    def __init__(self, vector_index_url: str = None, cache_enabled: bool = True):
        try:
            from services.config import get_config
            config = get_config()
            self.vector_index_url = vector_index_url or config.services.vector_index
        except ImportError:
            self.vector_index_url = vector_index_url or "http://localhost:8001"

        self.cache_enabled = cache_enabled
        self._cache: Dict[str, Any] = {}

    async def gather_context(self, query: str, file_path: str = None,
                             include_git: bool = True,
                             include_tests: bool = True,
                             include_deps: bool = True) -> ContextData:
        """
        Gather all relevant context for a query.

        Args:
            query: The user's query or code to analyze
            file_path: Optional file path for targeted context
            include_git: Include git history
            include_tests: Include recent test results
            include_deps: Include dependency analysis

        Returns:
            ContextData with all gathered information
        """
        context = ContextData()

        # Helper for empty async result
        async def empty_list():
            return []

        # Gather in parallel
        tasks = []

        tasks.append(self._fetch_embeddings(query))

        if include_git and file_path:
            tasks.append(self._fetch_git_history(file_path))
        else:
            tasks.append(empty_list())

        if include_tests:
            tasks.append(self._fetch_test_results())
        else:
            tasks.append(empty_list())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        if not isinstance(results[0], Exception):
            context.file_embeddings = results[0]

        if not isinstance(results[1], Exception):
            context.git_history = results[1]

        if not isinstance(results[2], Exception):
            context.test_results = results[2]

        return context

    async def _fetch_embeddings(self, query: str) -> List[Dict[str, Any]]:
        """Fetch semantic embeddings from vector index."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.vector_index_url}/search",
                    json={"query": query, "top_k": 5},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("results", [])
        except Exception as e:
            logger.warning(f"Failed to fetch embeddings: {e}")
        return []

    async def _fetch_git_history(self, file_path: str) -> List[Dict[str, Any]]:
        """Fetch git history for a file."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10", "--", file_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(" ", 1)
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1] if len(parts) > 1 else ""
                        })
                return commits
        except Exception as e:
            logger.warning(f"Failed to fetch git history: {e}")
        return []

    async def _fetch_test_results(self) -> List[Dict[str, Any]]:
        """Fetch recent test results from metrics service."""
        try:
            from services.metrics.test_correlation import get_tracker
            tracker = get_tracker()
            return [r.model_dump() for r in tracker.get_recent_results(limit=10)]
        except Exception as e:
            logger.debug(f"Could not fetch test results: {e}")
        return []


# Singleton accessor
_prompt_builder: Optional[PromptBuilder] = None
_context_aggregator: Optional[ContextAggregator] = None


def get_prompt_builder(max_tokens: int = 4096) -> PromptBuilder:
    """Get singleton PromptBuilder instance."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder(max_tokens=max_tokens)
    return _prompt_builder


def get_context_aggregator() -> ContextAggregator:
    """Get singleton ContextAggregator instance."""
    global _context_aggregator
    if _context_aggregator is None:
        _context_aggregator = ContextAggregator()
    return _context_aggregator

