"""
ContextForge Core Module.

Provides:
- LLMRouter: Intelligent LLM routing with auto-offline detection
- ProductionOrchestrator: Multi-agent orchestration for production workflows
- Offline/Online mode management
- Context schema and validation

Copyright (c) 2025 ContextForge
"""

import asyncio
import hashlib
import socket
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, field

from services.utils import utc_now

logger = logging.getLogger(__name__)


# =============================================================================
# Context Schema & Validation (Gap #1)
# =============================================================================

class ContextType(str, Enum):
    """
    Known context types in ContextForge.

    Agents can produce and consume these types.
    Unknown types are allowed but will log a warning.
    """
    CODE_FRAGMENT = "code_fragment"
    ANALYSIS = "analysis"
    REVIEW = "review"
    INDEX_SUMMARY = "index_summary"
    ERROR = "error"
    DIAGNOSTIC = "diagnostic"
    TEST_RESULT = "test_result"
    PLAN = "plan"
    RECOMMENDATION = "recommendation"
    FINDINGS = "findings"
    SUGGESTIONS = "suggestions"
    TASK_REQUEST = "task_request"
    ORCHESTRATION_RESULT = "orchestration_result"


class ContextScope(str, Enum):
    """
    Context visibility scope.

    Controls which agents can see a context.
    """
    GLOBAL = "global"      # Visible to all agents
    AGENT = "agent"        # Visible only to creating agent
    SESSION = "session"    # Visible within session


@dataclass(frozen=True)
class Context:
    """
    Immutable context object passed between agents.

    Attributes:
        type: Context type (should be from ContextType enum)
        provenance: Name of agent/source that created this context
        id: Unique identifier (auto-generated if not provided)
        scope: Visibility scope (default: global)
        created_at: ISO timestamp of creation
        content: Arbitrary content payload
        parent_id: Optional ID of parent context for lineage tracking
    """
    type: str
    provenance: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scope: str = field(default_factory=lambda: ContextScope.GLOBAL.value)
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    content: Any = None
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "provenance": self.provenance,
            "scope": self.scope,
            "created_at": self.created_at,
            "content": self.content,
            "parent_id": self.parent_id
        }


def validate_context(ctx: Union[Dict[str, Any], Context]) -> Context:
    """
    Validate and convert dict to Context.

    Args:
        ctx: Dictionary or Context to validate

    Returns:
        Valid Context object

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Already a Context object
    if isinstance(ctx, Context):
        return ctx

    if not isinstance(ctx, dict):
        raise ValueError(f"Context must be a dict or Context, got {type(ctx)}")

    if "type" not in ctx:
        raise ValueError("Context missing required field: 'type'")

    if "provenance" not in ctx:
        raise ValueError("Context missing required field: 'provenance'")

    # Validate type is known (warning only, don't block)
    known_types = [t.value for t in ContextType]
    if ctx["type"] not in known_types:
        logger.warning(f"Unknown context type: {ctx['type']}")

    return Context(
        id=ctx.get("id", str(uuid.uuid4())),
        type=ctx["type"],
        provenance=ctx["provenance"],
        scope=ctx.get("scope", ContextScope.GLOBAL.value),
        created_at=ctx.get("created_at", utc_now().isoformat()),
        content=ctx.get("content"),
        parent_id=ctx.get("parent_id")
    )


class OperationMode(str, Enum):
    """LLM operation mode."""
    AUTO = "auto"      # Auto-detect based on connectivity
    ONLINE = "online"  # Force cloud LLM
    OFFLINE = "offline"  # Force local LLM


class ExecutionHint(str, Enum):
    """
    Agent execution location hint.

    Agents are logical roles that may execute locally or remotely.
    This hint guides the Coordinator's scheduling decisions.
    """
    LOCAL = "local"      # Prefer local execution (filesystem access, low latency)
    REMOTE = "remote"    # Prefer remote execution (cloud LLM, scale)
    HYBRID = "hybrid"    # Can run either locally or remotely


class ContextBundle:
    """
    Immutable context passed between agents.

    Agents communicate only via ContextBundles - they never have
    direct access to each other or shared state.

    The bundle uses tuples internally for true immutability.
    The contexts property returns copies to prevent external mutation.

    Attributes:
        _contexts: Internal tuple of context objects (immutable)
        metadata: Additional metadata about the bundle
        provenance: Where this context came from
        mutation_log: Record of modifications (append-only, immutable)
    """
    __slots__ = ('_contexts', 'metadata', 'provenance', 'mutation_log')

    def __init__(
        self,
        contexts: Union[List[Any], tuple, None] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "",
        mutation_log: Union[List[Any], tuple, None] = None,
        *,
        _contexts: Optional[tuple] = None
    ):
        """
        Initialize ContextBundle.

        Args:
            contexts: List or tuple of context objects (backwards compatible)
            metadata: Additional metadata about the bundle
            provenance: Where this context came from
            mutation_log: Record of modifications
            _contexts: Internal parameter, prefer using contexts
        """
        # Support both 'contexts' (legacy) and '_contexts' (internal)
        if _contexts is not None:
            raw_contexts = _contexts
        elif contexts is not None:
            raw_contexts = contexts
        else:
            raw_contexts = ()

        # Convert to tuple for immutability
        if isinstance(raw_contexts, list):
            self._contexts = tuple(raw_contexts)
        else:
            self._contexts = raw_contexts

        self.metadata = metadata if metadata is not None else {}
        self.provenance = provenance

        # Convert mutation_log to tuple
        if mutation_log is None:
            self.mutation_log = ()
        elif isinstance(mutation_log, list):
            self.mutation_log = tuple(mutation_log)
        else:
            self.mutation_log = mutation_log

    @property
    def contexts(self) -> List[Dict[str, Any]]:
        """
        Return contexts as list of dicts (copy for safety).

        Returns a copy so external code cannot modify the bundle.
        """
        result = []
        for c in self._contexts:
            if isinstance(c, Context):
                result.append(c.to_dict())
            elif isinstance(c, dict):
                result.append(dict(c))  # Shallow copy
            else:
                result.append(c)
        return result

    def add_context(
        self,
        context: Union[Dict[str, Any], Context],
        source: str = "",
        validate: bool = False
    ) -> "ContextBundle":
        """
        Add a context object and return NEW bundle. Original is unchanged.

        Args:
            context: Context to add (dict or Context object)
            source: Name of agent/source adding this context
            validate: If True, validate context schema

        Returns:
            New ContextBundle with context added
        """
        if validate:
            context = validate_context(context)
        elif isinstance(context, dict):
            # Ensure minimum fields even without full validation
            if "provenance" not in context:
                context = {**context, "provenance": source}

        # Get context ID for logging
        if isinstance(context, Context):
            context_id = context.id
        else:
            context_id = context.get("id", str(uuid.uuid4()))
            if "id" not in context:
                context = {**context, "id": context_id}

        new_contexts = self._contexts + (context,)
        new_log = self.mutation_log + ({
            "action": "add_context",
            "source": source,
            "context_id": context_id,
            "timestamp": utc_now().isoformat()
        },)

        return ContextBundle(
            _contexts=new_contexts,
            metadata=self.metadata.copy(),
            provenance=self.provenance,
            mutation_log=new_log
        )


@dataclass
class AgentCapabilities:
    """
    Declares what an agent can do.

    Used by Coordinator to decide:
    - What contexts to provide
    - What permissions to grant
    - Where to execute
    """
    consumes: list = field(default_factory=list)   # Context types it needs
    produces: list = field(default_factory=list)   # Context types it outputs
    requires_filesystem: bool = False               # Needs local file access
    requires_network: bool = False                  # Needs network access
    mutation_rights: list = field(default_factory=list)  # What it can modify


class AgentInterface:
    """
    Base interface for all ContextForge agents.

    Agents are logical roles, not processes. They may execute:
    - Locally (in-process, same host)
    - Remotely (via API/RPC)
    - Hybrid (Coordinator decides based on context)

    Key principles:
    - Agents communicate only via ContextBundles
    - Location is an implementation detail
    - Agents declare capabilities, not implementation

    Usage:
        class ArchitectAgent(AgentInterface):
            def __init__(self):
                super().__init__(
                    name="architect",
                    execution_hint=ExecutionHint.REMOTE
                )

            def capabilities(self) -> AgentCapabilities:
                return AgentCapabilities(
                    consumes=["code_fragment", "file_tree"],
                    produces=["architecture_analysis"],
                    requires_network=True
                )

            async def invoke(self, bundle: ContextBundle) -> ContextBundle:
                # Analyze architecture...
                return bundle.add_context(analysis, "architect")
    """

    def __init__(
        self,
        name: str,
        execution_hint: ExecutionHint = ExecutionHint.HYBRID,
        version: str = "1.0.0"
    ):
        self.name = name
        self.execution_hint = execution_hint
        self.version = version
        self._is_local = True  # Resolved by Coordinator

    def capabilities(self) -> AgentCapabilities:
        """
        Declare what this agent can do.

        Override in subclasses to specify:
        - What context types it consumes
        - What context types it produces
        - What permissions it needs
        """
        return AgentCapabilities()

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """
        Execute the agent's task.

        Args:
            bundle: Input context bundle

        Returns:
            Output context bundle with results added
        """
        raise NotImplementedError("Subclasses must implement invoke()")

    @property
    def is_local(self) -> bool:
        """Whether this agent is currently executing locally."""
        return self._is_local

    @property
    def is_remote(self) -> bool:
        """Whether this agent is currently executing remotely."""
        return not self._is_local

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, hint={self.execution_hint.value})>"


# =============================================================================
# Coordinator Exceptions (Gap #4)
# =============================================================================

class CoordinatorError(Exception):
    """Base exception for coordinator errors."""
    pass


class RecursionLimitError(CoordinatorError):
    """Raised when max invocation depth exceeded."""
    pass


class ContextLimitError(CoordinatorError):
    """Raised when max context count exceeded."""
    pass


class AgentTimeoutError(CoordinatorError):
    """Raised when agent exceeds timeout."""
    pass


class LoopDetectedError(CoordinatorError):
    """Raised when agent loop detected."""
    pass


@dataclass
class CoordinatorConfig:
    """
    Configuration for CoordinatorAgent safeguards.

    Attributes:
        max_depth: Maximum invocation depth before raising RecursionLimitError
        max_contexts: Maximum number of contexts in a bundle
        agent_timeout_seconds: Timeout for individual agent invocations
        enable_scope_filtering: Whether to filter contexts by agent capabilities
        enable_loop_detection: Whether to detect and prevent infinite loops
    """
    max_depth: int = 10
    max_contexts: int = 1000
    agent_timeout_seconds: float = 60.0
    enable_scope_filtering: bool = True
    enable_loop_detection: bool = True


# =============================================================================
# Built-in Agent Implementations
# =============================================================================

class CoordinatorAgent(AgentInterface):
    """
    Coordinator agent - orchestrates other agents with safety limits.

    Always runs locally for:
    - Low latency control
    - Security boundary enforcement
    - Local state management

    Safety features (Gap #4):
    - Loop detection: prevents infinite agent cycles
    - Recursion limits: caps invocation depth
    - Context limits: prevents memory exhaustion
    - Timeout enforcement: prevents hung agents
    - Scope filtering: agents only see relevant contexts
    """

    def __init__(self, config: Optional[CoordinatorConfig] = None):
        super().__init__(
            name="coordinator",
            execution_hint=ExecutionHint.LOCAL
        )
        self._agents: Dict[str, AgentInterface] = {}
        self._config = config or CoordinatorConfig()
        self._invocation_depth: int = 0
        self._invocation_hashes: Set[str] = set()
        self._invocation_history: List[Dict[str, Any]] = []

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["task_request"],
            produces=["orchestration_result"],
            requires_filesystem=True,
            mutation_rights=["agent_registry"]
        )

    def register_agent(self, agent: AgentInterface) -> None:
        """Register an agent for coordination."""
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} (hint={agent.execution_hint.value})")

    def _compute_bundle_hash(self, bundle: ContextBundle) -> str:
        """Compute hash of bundle for loop detection."""
        content = str(sorted([str(c) for c in bundle.contexts]))
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _check_limits(self, bundle: ContextBundle, agent_name: str) -> None:
        """
        Check all safety limits before invocation.

        Raises:
            RecursionLimitError: If max depth exceeded
            ContextLimitError: If max contexts exceeded
            LoopDetectedError: If same agent/input combination detected
        """
        # Check depth
        if self._invocation_depth >= self._config.max_depth:
            raise RecursionLimitError(
                f"Max invocation depth ({self._config.max_depth}) exceeded"
            )

        # Check context count
        if len(bundle.contexts) >= self._config.max_contexts:
            raise ContextLimitError(
                f"Max context count ({self._config.max_contexts}) exceeded"
            )

        # Check for loops
        if self._config.enable_loop_detection:
            bundle_hash = f"{agent_name}:{self._compute_bundle_hash(bundle)}"
            if bundle_hash in self._invocation_hashes:
                raise LoopDetectedError(
                    f"Loop detected: {agent_name} invoked with same input"
                )
            self._invocation_hashes.add(bundle_hash)

    def _filter_by_scope(
        self,
        bundle: ContextBundle,
        agent: AgentInterface
    ) -> ContextBundle:
        """
        Filter bundle to only include contexts the agent can consume.

        Args:
            bundle: Full context bundle
            agent: Agent to filter for

        Returns:
            Filtered bundle with only relevant contexts
        """
        if not self._config.enable_scope_filtering:
            return bundle

        caps = agent.capabilities()
        if self._agent_consumes_all(caps):
            return bundle

        filtered_contexts = [
            ctx for ctx in bundle._contexts
            if self._context_matches_scope(ctx, caps.consumes)
        ]

        return ContextBundle(
            _contexts=tuple(filtered_contexts),
            metadata=bundle.metadata.copy(),
            provenance=bundle.provenance,
            mutation_log=bundle.mutation_log
        )

    def _agent_consumes_all(self, caps: AgentCapabilities) -> bool:
        """
        Check if agent capabilities indicate it consumes all context types.

        Args:
            caps: Agent capabilities

        Returns:
            True if agent consumes all types
        """
        return "*" in caps.consumes

    def _context_matches_scope(
        self,
        context: Union[Dict[str, Any], Context],
        allowed_types: set
    ) -> bool:
        """
        Check if a context matches the allowed types.

        Args:
            context: Context dict or Context object
            allowed_types: Set of allowed context types

        Returns:
            True if context type is in allowed types
        """
        if isinstance(context, dict):
            return context.get("type") in allowed_types
        if isinstance(context, Context):
            return context.type in allowed_types
        return False

    def resolve_execution_location(self, agent: AgentInterface) -> bool:
        """
        Decide where to execute an agent based on:
        - Execution hint
        - Current connectivity
        - Required permissions
        - Context size

        Returns:
            True if agent should run locally, False for remote
        """
        caps = agent.capabilities()

        # Must run locally if needs filesystem
        if caps.requires_filesystem:
            return True

        # Prefer local for LOCAL hint
        if agent.execution_hint == ExecutionHint.LOCAL:
            return True

        # Prefer remote for REMOTE hint (if network available)
        if agent.execution_hint == ExecutionHint.REMOTE:
            if caps.requires_network and check_internet():
                return False
            # Fallback to local if offline
            return True

        # HYBRID: Decide based on current state
        # Default: prefer local for simplicity
        return True

    async def invoke_agent(
        self,
        agent_name: str,
        bundle: ContextBundle
    ) -> ContextBundle:
        """
        Invoke a specific agent with safety checks.

        Args:
            agent_name: Name of registered agent
            bundle: Input context bundle

        Returns:
            Output context bundle

        Raises:
            RecursionLimitError: If max depth exceeded
            ContextLimitError: If max contexts exceeded
            LoopDetectedError: If same input detected
            AgentTimeoutError: If agent times out
            KeyError: If agent not registered
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent not registered: {agent_name}")

        agent = self._agents[agent_name]

        # Check safety limits
        self._check_limits(bundle, agent_name)

        # Resolve execution location
        is_local = self.resolve_execution_location(agent)
        agent._is_local = is_local

        # Filter by scope
        filtered_bundle = self._filter_by_scope(bundle, agent)

        # Track invocation
        self._invocation_depth += 1
        start_time = utc_now()

        try:
            # Invoke with timeout
            result = await asyncio.wait_for(
                agent.invoke(filtered_bundle),
                timeout=self._config.agent_timeout_seconds
            )

            # Record history
            self._invocation_history.append({
                "agent": agent_name,
                "input_contexts": len(filtered_bundle.contexts),
                "output_contexts": len(result.contexts),
                "duration_ms": int((utc_now() - start_time).total_seconds() * 1000),
                "timestamp": start_time.isoformat()
            })

            return result

        except asyncio.TimeoutError:
            raise AgentTimeoutError(
                f"Agent {agent_name} timed out after {self._config.agent_timeout_seconds}s"
            )
        finally:
            self._invocation_depth -= 1

    def reset_invocation_state(self) -> None:
        """Reset invocation tracking (call between independent operations)."""
        self._invocation_depth = 0
        self._invocation_hashes.clear()

    def get_invocation_history(self) -> List[Dict[str, Any]]:
        """Get history of agent invocations."""
        return list(self._invocation_history)

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """
        Coordinate agent execution based on task request.

        This method invokes all registered agents in order,
        applying safety checks at each step.
        """
        self.reset_invocation_state()  # Fresh state for new invocation

        result_bundle = bundle
        for agent_name, agent in self._agents.items():
            try:
                result_bundle = await self.invoke_agent(agent_name, result_bundle)
            except CoordinatorError as e:
                logger.error(f"Coordinator error invoking {agent_name}: {e}")
                # Add error context and continue or break based on error type
                error_context = Context(
                    type=ContextType.ERROR.value,
                    provenance=self.name,
                    content={
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "agent": agent_name
                    }
                )
                result_bundle = result_bundle.add_context(error_context, self.name)
                break  # Stop on coordinator errors

        return result_bundle


class IndexingAgent(AgentInterface):
    """
    Indexing agent - builds code indexes.

    Always runs locally because it needs:
    - Filesystem access
    - Fast I/O for scanning
    - Write access to index storage
    """

    def __init__(self):
        super().__init__(
            name="indexing",
            execution_hint=ExecutionHint.LOCAL
        )

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["file_path", "repo_path"],
            produces=["code_fragment", "symbol_index", "dependency_graph"],
            requires_filesystem=True,
            mutation_rights=["index_storage"]
        )

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """Index code and produce context objects."""
        repo_path = bundle.metadata.get("repo_path", "")

        # Delegate to existing scanner
        from services.scanner import scan_repo
        scan_result = scan_repo(repo_path)

        # Create context objects from scan
        contexts = []
        for file_info in scan_result.get("files", [])[:100]:  # Limit for safety
            contexts.append({
                "type": "code_fragment",
                "path": file_info.get("path", ""),
                "language": file_info.get("language", "unknown"),
                "hash": file_info.get("hash", ""),
                "provenance": "filesystem"
            })

        # Add index summary
        index_context = {
            "type": "index_summary",
            "total_files": len(scan_result.get("files", [])),
            "languages": scan_result.get("languages", []),
            "provenance": "indexing_agent"
        }

        return bundle.add_context(index_context, self.name)


class ReasoningAgent(AgentInterface):
    """
    Reasoning/Planning agent - uses LLM for complex reasoning.

    Prefers remote execution for:
    - Access to powerful cloud LLMs
    - Scalability
    - Latest model versions

    Falls back to local Ollama/LM Studio when offline.
    """

    def __init__(self, name: str = "reasoning"):
        super().__init__(
            name=name,
            execution_hint=ExecutionHint.REMOTE
        )
        self._router: Optional["LLMRouter"] = None

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["code_fragment", "query", "architecture_context"],
            produces=["analysis", "plan", "recommendation"],
            requires_network=True  # Prefers network for cloud LLM
        )

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """Perform LLM-based reasoning on the context."""
        if not self._router:
            self._router = LLMRouter(mode="auto")

        query = bundle.metadata.get("query", "Analyze this context")

        # Build prompt from contexts
        context_text = "\n".join([
            str(ctx) for ctx in bundle.contexts[-5:]  # Last 5 contexts
        ])

        prompt = f"""Based on the following context:

{context_text}

{query}"""

        response = self._router.query(prompt)

        analysis_context = {
            "type": "analysis",
            "content": response.text,
            "backend": response.backend,
            "offline_mode": response.offline_mode,
            "provenance": self.name
        }

        return bundle.add_context(analysis_context, self.name)


class CritiqueAgent(AgentInterface):
    """
    Critique/Review agent - reviews code and analysis.

    Can run locally or remotely depending on:
    - Context size
    - Required model capability
    """

    def __init__(self):
        super().__init__(
            name="critique",
            execution_hint=ExecutionHint.HYBRID
        )

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["code_fragment", "analysis"],
            produces=["review", "findings", "suggestions"],
            requires_network=False  # Can work offline
        )

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """Review and critique the context."""
        # Find analysis contexts to review
        analyses = [c for c in bundle.contexts if c.get("type") == "analysis"]

        if not analyses:
            return bundle

        # Simple critique logic (would use LLM in production)
        review = {
            "type": "review",
            "items_reviewed": len(analyses),
            "findings": [],
            "provenance": self.name
        }

        return bundle.add_context(review, self.name)


# =============================================================================
# Debugging Agent (Gap #3)
# =============================================================================

@dataclass
class DiagnosticConfig:
    """
    Configuration for DebuggingAgent.

    Attributes:
        stale_threshold_seconds: Contexts older than this are flagged as stale
        detect_contradictions: Whether to detect potentially conflicting contexts
        verbosity: Output verbosity level (minimal, normal, verbose)
    """
    stale_threshold_seconds: int = 3600  # 1 hour
    detect_contradictions: bool = True
    verbosity: str = "normal"  # minimal, normal, verbose


class DebuggingAgent(AgentInterface):
    """
    Debugging agent - traces context flow and detects issues.

    Always runs locally for:
    - Low latency diagnostics
    - Access to full context history
    - No network dependency

    Produces diagnostic contexts containing:
    - Context counts by type and agent
    - Lineage tracking from mutation log
    - Stale context detection
    - Contradiction detection
    - Overall health assessment
    """

    def __init__(self, config: Optional[DiagnosticConfig] = None):
        super().__init__(
            name="debugging",
            execution_hint=ExecutionHint.LOCAL
        )
        self._config = config or DiagnosticConfig()

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["*"],  # Reads all context types
            produces=["diagnostic"],
            requires_filesystem=False,
            requires_network=False,
            mutation_rights=[]  # Read-only
        )

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """Generate diagnostic context from bundle analysis."""
        diagnostic_content = {
            "context_count": len(bundle.contexts),
            "mutation_count": len(bundle.mutation_log),
            "contexts_by_type": self._count_by_type(bundle),
            "contexts_by_agent": self._count_by_agent(bundle),
            "lineage": self._trace_lineage(bundle),
            "stale_contexts": self._find_stale(bundle),
            "contradictions": self._find_contradictions(bundle),
            "health": self._assess_health(bundle)
        }

        diagnostic = Context(
            type=ContextType.DIAGNOSTIC.value,
            provenance=self.name,
            content=diagnostic_content
        )

        return bundle.add_context(diagnostic, self.name)

    def _count_by_type(self, bundle: ContextBundle) -> Dict[str, int]:
        """Count contexts by type."""
        counts: Dict[str, int] = {}
        for ctx in bundle.contexts:
            ctx_type = ctx.get("type", "unknown")
            counts[ctx_type] = counts.get(ctx_type, 0) + 1
        return counts

    def _count_by_agent(self, bundle: ContextBundle) -> Dict[str, int]:
        """Count contexts by producing agent."""
        counts: Dict[str, int] = {}
        for ctx in bundle.contexts:
            agent = ctx.get("provenance", "unknown")
            counts[agent] = counts.get(agent, 0) + 1
        return counts

    def _trace_lineage(self, bundle: ContextBundle) -> List[Dict[str, Any]]:
        """Trace context creation order from mutation log."""
        lineage = []
        for entry in bundle.mutation_log:
            if isinstance(entry, dict) and entry.get("action") == "add_context":
                lineage.append({
                    "context_id": entry.get("context_id"),
                    "source": entry.get("source"),
                    "timestamp": entry.get("timestamp")
                })
        return lineage

    def _find_stale(self, bundle: ContextBundle) -> List[str]:
        """Find contexts older than threshold."""
        stale = []
        threshold = utc_now() - timedelta(seconds=self._config.stale_threshold_seconds)

        for ctx in bundle.contexts:
            created = ctx.get("created_at")
            if created:
                try:
                    # Handle both Z suffix and +00:00 suffix
                    created_str = created.replace("Z", "+00:00")
                    created_dt = datetime.fromisoformat(created_str)
                    if created_dt < threshold:
                        stale.append(ctx.get("id", "unknown"))
                except (ValueError, TypeError):
                    pass
        return stale

    def _find_contradictions(self, bundle: ContextBundle) -> List[Dict[str, Any]]:
        """Find potentially contradicting contexts."""
        if not self._config.detect_contradictions:
            return []

        contradictions = []
        analyses = [c for c in bundle.contexts if c.get("type") == "analysis"]

        # Simple heuristic: multiple analyses from same source
        by_source: Dict[str, int] = {}
        for a in analyses:
            source = a.get("provenance", "unknown")
            by_source[source] = by_source.get(source, 0) + 1

        for source, count in by_source.items():
            if count > 1:
                contradictions.append({
                    "type": "multiple_analyses",
                    "source": source,
                    "count": count
                })

        return contradictions

    def _assess_health(self, bundle: ContextBundle) -> str:
        """Overall health assessment."""
        issues = []

        if len(bundle.contexts) > 500:
            issues.append("high_context_count")

        stale_count = len(self._find_stale(bundle))
        if stale_count > 10:
            issues.append("many_stale_contexts")

        if self._find_contradictions(bundle):
            issues.append("contradictions_detected")

        if not issues:
            return "healthy"
        elif len(issues) == 1:
            return f"warning: {issues[0]}"
        else:
            return f"degraded: {', '.join(issues)}"

    def format_report(self, bundle: ContextBundle) -> str:
        """
        Generate human-readable diagnostic report.

        Args:
            bundle: Context bundle to analyze

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 60,
            "CONTEXTFORGE DIAGNOSTIC REPORT",
            "=" * 60,
            "",
            f"Total Contexts: {len(bundle.contexts)}",
            f"Total Mutations: {len(bundle.mutation_log)}",
            "",
            "Contexts by Type:",
        ]

        for ctx_type, count in self._count_by_type(bundle).items():
            lines.append(f"  - {ctx_type}: {count}")

        lines.append("")
        lines.append("Contexts by Agent:")
        for agent, count in self._count_by_agent(bundle).items():
            lines.append(f"  - {agent}: {count}")

        stale = self._find_stale(bundle)
        if stale:
            lines.append("")
            lines.append(f"Stale Contexts ({len(stale)}):")
            for ctx_id in stale[:5]:  # Show first 5
                lines.append(f"  - {ctx_id}")
            if len(stale) > 5:
                lines.append(f"  ... and {len(stale) - 5} more")

        contradictions = self._find_contradictions(bundle)
        if contradictions:
            lines.append("")
            lines.append("Potential Contradictions:")
            for c in contradictions:
                lines.append(f"  - {c['source']}: {c['count']} analyses")

        lines.append("")
        lines.append(f"Health: {self._assess_health(bundle).upper()}")
        lines.append("=" * 60)

        return "\n".join(lines)


# =============================================================================
# Agent Registry
# =============================================================================

_agent_registry: Dict[str, AgentInterface] = {}

def register_agent(agent: AgentInterface) -> None:
    """Register an agent globally."""
    _agent_registry[agent.name] = agent
    logger.info(f"Global agent registered: {agent.name}")

def get_agent(name: str) -> Optional[AgentInterface]:
    """Get a registered agent by name."""
    return _agent_registry.get(name)

def list_agents() -> Dict[str, Dict[str, Any]]:
    """List all registered agents with their status."""
    return {
        name: {
            "execution_hint": agent.execution_hint.value,
            "is_local": agent.is_local,
            "capabilities": {
                "consumes": agent.capabilities().consumes,
                "produces": agent.capabilities().produces,
                "requires_filesystem": agent.capabilities().requires_filesystem,
                "requires_network": agent.capabilities().requires_network
            }
        }
        for name, agent in _agent_registry.items()
    }


def check_internet(host: str = "8.8.8.8", port: int = 53, timeout: float = 3.0) -> bool:
    """
    Check internet connectivity by attempting to connect to DNS server.
    
    Args:
        host: Host to check (default: Google DNS)
        port: Port to connect to (default: 53 for DNS)
        timeout: Connection timeout in seconds
        
    Returns:
        True if internet is available, False otherwise
    """
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.close()
        logger.debug("Internet connectivity check: ONLINE")
        return True
    except socket.error as e:
        logger.debug(f"Internet connectivity check: OFFLINE ({e})")
        return False


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    text: str
    backend: str
    model: str = ""
    latency_ms: int = 0
    offline_mode: bool = False
    tokens: int = 0
    error: Optional[str] = None


class LLMRouter:
    """
    Intelligent LLM router with automatic offline detection and fallback.
    
    Supports three modes:
    - auto: Detect internet connectivity and switch automatically
    - online: Force cloud LLM (fail if unavailable)
    - offline: Force local LLM (Ollama/LM Studio)
    
    Usage:
        router = LLMRouter(mode="auto")
        response = router.query("Explain this code...")
    """
    
    def __init__(self, mode: str = "auto"):
        """
        Initialize LLM Router.
        
        Args:
            mode: Operation mode - "auto", "online", or "offline"
        """
        self.user_mode = OperationMode(mode.lower())
        self._offline_mode = False
        self._last_check = None
        self._check_interval = 60  # Re-check connectivity every 60 seconds
        self._llm_client = None
        
        # Detect initial mode
        self.detect_mode()
        
        logger.info(f"LLMRouter initialized: mode={self.user_mode.value}, offline={self._offline_mode}")
    
    @property
    def offline_mode(self) -> bool:
        """Current offline status."""
        return self._offline_mode
    
    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            from services.api_gateway.llm_client import LLMClient
            self._llm_client = LLMClient()
        return self._llm_client
    
    def detect_mode(self) -> bool:
        """
        Detect and set the current operation mode.
        
        Returns:
            True if offline, False if online
        """
        if self.user_mode == OperationMode.OFFLINE:
            self._offline_mode = True
        elif self.user_mode == OperationMode.ONLINE:
            self._offline_mode = False
        else:
            # Auto-detect based on internet connectivity
            self._offline_mode = not check_internet()
        
        self._last_check = utc_now()
        return self._offline_mode
    
    def _should_recheck(self) -> bool:
        """Check if we should re-verify connectivity."""
        if self._last_check is None:
            return True
        elapsed = (utc_now() - self._last_check).total_seconds()
        return elapsed > self._check_interval
    
    def query(self, prompt: str, model: Optional[str] = None, 
              max_tokens: int = 1024, **kwargs) -> LLMResponse:
        """
        Query LLM with automatic fallback.
        
        Args:
            prompt: The prompt to send
            model: Optional model override
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for LLM
            
        Returns:
            LLMResponse with generated text and metadata
        """
        # Re-check connectivity if in auto mode and interval elapsed
        if self.user_mode == OperationMode.AUTO and self._should_recheck():
            self.detect_mode()
        
        try:
            if self._offline_mode:
                return self._query_local(prompt, model, max_tokens, **kwargs)
            else:
                return self._query_cloud(prompt, model, max_tokens, **kwargs)
        except Exception as e:
            # If cloud fails, fallback to local
            if not self._offline_mode:
                logger.warning(f"Cloud LLM failed, falling back to local: {e}")
                self._offline_mode = True
                return self._query_local(prompt, model, max_tokens, **kwargs)
            raise

    def _query_cloud(self, prompt: str, model: Optional[str],
                     max_tokens: int, **kwargs) -> LLMResponse:
        """Query cloud LLM (OpenAI, Anthropic, etc.)."""
        import time
        start = time.time()

        try:
            result = self.llm_client.generate(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                **kwargs
            )
            latency = int((time.time() - start) * 1000)

            return LLMResponse(
                text=result.get("text", ""),
                backend="cloud",
                model=result.get("model", model or "unknown"),
                latency_ms=latency,
                offline_mode=False,
                tokens=result.get("tokens", 0)
            )
        except Exception as e:
            logger.error(f"Cloud LLM error: {e}")
            raise

    # Local LLM backend configurations
    LOCAL_BACKENDS = [
        {
            'name': 'ollama',
            'url': 'http://localhost:11434/api/generate',
            'build_payload': lambda model, prompt, max_tokens: {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {'num_predict': max_tokens}
            },
            'extract_text': lambda data: data.get('response', ''),
            'extract_tokens': lambda data: data.get('eval_count', 0)
        },
        {
            'name': 'lm_studio',
            'url': 'http://localhost:1234/v1/completions',
            'build_payload': lambda model, prompt, max_tokens: {
                'model': model,
                'prompt': prompt,
                'max_tokens': max_tokens
            },
            'extract_text': lambda data: data['choices'][0]['text'],
            'extract_tokens': lambda data: data.get('usage', {}).get('completion_tokens', 0)
        }
    ]

    def _query_local(self, prompt: str, model: Optional[str],
                     max_tokens: int, **kwargs) -> LLMResponse:
        """
        Query local LLM (Ollama, LM Studio).

        Tries each configured local backend in order until one succeeds.

        Args:
            prompt: The prompt to send
            model: Model name (defaults to llama3.2)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse from the first successful backend
        """
        import time

        start_time = time.time()
        local_model = model or "llama3.2"
        last_error = None

        for backend in self.LOCAL_BACKENDS:
            result = self._try_local_backend(
                backend, local_model, prompt, max_tokens, start_time
            )
            if result is not None:
                return result
            last_error = f"{backend['name']} not available"

        # All backends failed
        return LLMResponse(
            text="",
            backend="local",
            model=local_model,
            offline_mode=True,
            error=last_error or "No local LLM available"
        )

    def _try_local_backend(
        self,
        backend: Dict[str, Any],
        model: str,
        prompt: str,
        max_tokens: int,
        start_time: float
    ) -> Optional[LLMResponse]:
        """
        Try to query a single local LLM backend.

        Args:
            backend: Backend configuration dict
            model: Model name to use
            prompt: The prompt to send
            max_tokens: Maximum tokens to generate
            start_time: Request start time for latency calculation

        Returns:
            LLMResponse if successful, None if backend unavailable
        """
        import time
        import requests

        try:
            payload = backend['build_payload'](model, prompt, max_tokens)
            response = requests.post(
                backend['url'],
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            latency = int((time.time() - start_time) * 1000)

            return LLMResponse(
                text=backend['extract_text'](data),
                backend=backend['name'],
                model=model,
                latency_ms=latency,
                offline_mode=True,
                tokens=backend['extract_tokens'](data)
            )
        except requests.exceptions.ConnectionError:
            logger.warning(f"{backend['name']} not available")
            return None
        except Exception as e:
            logger.warning(f"{backend['name']} error: {e}")
            return None


@dataclass
class OrchestrationResult:
    """Result from production orchestration."""
    success: bool
    repo_path: str
    context_file: Optional[str] = None
    analysis: Dict[str, Any] = field(default_factory=dict)
    agents_used: list = field(default_factory=list)
    duration_ms: int = 0
    offline_mode: bool = False
    errors: list = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for VS Code."""
        return {
            "success": self.success,
            "repo_path": self.repo_path,
            "context_file": self.context_file,
            "analysis": self.analysis,
            "agents_used": self.agents_used,
            "duration_ms": self.duration_ms,
            "offline_mode": self.offline_mode,
            "errors": self.errors
        }


class ProductionOrchestrator:
    """
    Production-ready orchestration for multi-agent context generation.

    Coordinates:
    - LLM routing (cloud/local)
    - Agent execution (Architect, Coder, Reviewer)
    - Context file generation
    - VS Code integration

    Usage:
        orchestrator = ProductionOrchestrator(mode="auto")
        result = orchestrator.run("/path/to/repo", task="Analyze architecture")
    """

    def __init__(self, mode: str = "auto"):
        """
        Initialize orchestrator.

        Args:
            mode: LLM mode - "auto", "online", or "offline"
        """
        self.router = LLMRouter(mode=mode)
        self._agents = {}

        logger.info(f"ProductionOrchestrator initialized: mode={mode}")

    def run(self, repo_path: str, task: str = "full_analysis",
            output_format: str = "markdown", **kwargs) -> OrchestrationResult:
        """
        Run production orchestration on a repository.

        Args:
            repo_path: Path to the repository
            task: Task type - "full_analysis", "architecture", "code_review", etc.
            output_format: Output format - "markdown", "json", "xml"
            **kwargs: Additional options

        Returns:
            OrchestrationResult with analysis and context file
        """
        import time
        from pathlib import Path

        start = time.time()
        errors = []
        agents_used = []
        analysis = {}

        try:
            # Step 1: Scan repository
            logger.info(f"Scanning repository: {repo_path}")
            from services.scanner import scan_repo
            scan_result = scan_repo(repo_path)
            analysis["scan"] = {
                "files": len(scan_result.get("files", [])),
                "languages": scan_result.get("languages", []),
                "size_bytes": scan_result.get("size_bytes", 0)
            }

            # Step 2: Run agents based on task
            if task in ("full_analysis", "architecture"):
                agents_used.append("architect")
                arch_result = self._run_architect_agent(repo_path, scan_result)
                analysis["architecture"] = arch_result

            if task in ("full_analysis", "code_review"):
                agents_used.append("reviewer")
                review_result = self._run_reviewer_agent(repo_path, scan_result)
                analysis["review"] = review_result

            # Step 3: Generate context file
            context_file = self._generate_context_file(
                repo_path, analysis, output_format
            )

            duration = int((time.time() - start) * 1000)

            return OrchestrationResult(
                success=True,
                repo_path=repo_path,
                context_file=context_file,
                analysis=analysis,
                agents_used=agents_used,
                duration_ms=duration,
                offline_mode=self.router.offline_mode,
                errors=errors
            )

        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            errors.append(str(e))
            duration = int((time.time() - start) * 1000)

            return OrchestrationResult(
                success=False,
                repo_path=repo_path,
                analysis=analysis,
                agents_used=agents_used,
                duration_ms=duration,
                offline_mode=self.router.offline_mode,
                errors=errors
            )

    def _run_architect_agent(self, repo_path: str,
                              scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run architect agent for high-level analysis."""
        prompt = f"""Analyze the architecture of this codebase:

Repository: {repo_path}
Files: {scan_result.get('files', [])[:20]}
Languages: {scan_result.get('languages', [])}

Provide:
1. Overall architecture pattern (monolith, microservices, etc.)
2. Key components and their responsibilities
3. Dependencies and data flow
4. Potential improvements

Be concise and structured."""

        response = self.router.query(prompt, max_tokens=2048)

        return {
            "summary": response.text[:500] if response.text else "Analysis unavailable",
            "backend": response.backend,
            "latency_ms": response.latency_ms
        }

    def _run_reviewer_agent(self, repo_path: str,
                             scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run code reviewer agent."""
        prompt = f"""Review this codebase for quality and best practices:

Repository: {repo_path}
Languages: {scan_result.get('languages', [])}

Identify:
1. Code quality issues
2. Security concerns
3. Performance bottlenecks
4. Testing coverage gaps

Be specific and actionable."""

        response = self.router.query(prompt, max_tokens=2048)

        return {
            "findings": response.text[:500] if response.text else "Review unavailable",
            "backend": response.backend,
            "latency_ms": response.latency_ms
        }

    def _generate_context_file(self, repo_path: str,
                                analysis: Dict[str, Any],
                                output_format: str) -> Optional[str]:
        """Generate context file from analysis."""
        from pathlib import Path

        repo = Path(repo_path)

        if output_format == "json":
            import json
            content = json.dumps(analysis, indent=2)
            filename = ".contextforge.json"
        elif output_format == "xml":
            content = self._to_xml(analysis)
            filename = ".contextforge.xml"
        else:
            content = self._to_markdown(analysis)
            filename = ".contextforge.md"

        output_path = repo / filename
        try:
            output_path.write_text(content, encoding="utf-8")
            logger.info(f"Context file written: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"Failed to write context file: {e}")
            return None

    def _to_markdown(self, analysis: Dict[str, Any]) -> str:
        """Convert analysis to Markdown."""
        lines = ["# ContextForge Analysis\n"]

        if "scan" in analysis:
            scan = analysis["scan"]
            lines.append("## Repository Scan\n")
            lines.append(f"- **Files**: {scan.get('files', 0)}")
            lines.append(f"- **Languages**: {', '.join(scan.get('languages', []))}")
            lines.append("")

        if "architecture" in analysis:
            arch = analysis["architecture"]
            lines.append("## Architecture Analysis\n")
            lines.append(arch.get("summary", ""))
            lines.append("")

        if "review" in analysis:
            review = analysis["review"]
            lines.append("## Code Review\n")
            lines.append(review.get("findings", ""))
            lines.append("")

        return "\n".join(lines)

    def _to_xml(self, analysis: Dict[str, Any]) -> str:
        """Convert analysis to XML."""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append("<contextforge>")

        if "scan" in analysis:
            scan = analysis["scan"]
            lines.append("  <scan>")
            lines.append(f"    <files>{scan.get('files', 0)}</files>")
            lines.append(f"    <languages>{','.join(scan.get('languages', []))}</languages>")
            lines.append("  </scan>")

        if "architecture" in analysis:
            lines.append("  <architecture>")
            lines.append(f"    <summary>{analysis['architecture'].get('summary', '')}</summary>")
            lines.append("  </architecture>")

        if "review" in analysis:
            lines.append("  <review>")
            lines.append(f"    <findings>{analysis['review'].get('findings', '')}</findings>")
            lines.append("  </review>")

        lines.append("</contextforge>")
        return "\n".join(lines)


# Convenience function for CLI/API usage
def production_run(repo_path: str, mode: str = "auto",
                   task: str = "full_analysis", **kwargs) -> Dict[str, Any]:
    """
    Run production orchestration and return JSON-serializable result.

    This is the main entry point for VS Code extension and CLI.

    Args:
        repo_path: Path to repository
        mode: LLM mode - "auto", "online", "offline"
        task: Task type
        **kwargs: Additional options

    Returns:
        JSON-serializable dict with results
    """
    orchestrator = ProductionOrchestrator(mode=mode)
    result = orchestrator.run(repo_path, task=task, **kwargs)
    return result.to_json()


# =============================================================================
# Code Indexing System - Imported from services.index (Gap #6: Module Separation)
# =============================================================================
#
# For backwards compatibility, we re-export CodeFragment, IndexStats, CodeIndex,
# and get_code_index from services.index. New code should import directly from
# services.index.
#
# Example:
#     from services.index import CodeIndex, CodeFragment, IndexStats
#
# =============================================================================

try:
    from services.index import CodeFragment, IndexStats, CodeIndex, get_code_index
except ImportError:
    # Fallback if services.index not available - define locally
    @dataclass
    class CodeFragment:
        """A single indexed code fragment (fallback definition)."""
        type: str
        path: str
        symbol: str = ""
        language: str = "unknown"
        hash: str = ""
        start_line: int = 0
        end_line: int = 0
        docstring: str = ""
        dependencies: list = field(default_factory=list)
        semantic_summary: str = ""
        embedding_ref: str = ""
        last_modified: str = ""
        provenance: str = "filesystem"

        def to_dict(self) -> Dict[str, Any]:
            return {
                "type": self.type, "path": self.path, "symbol": self.symbol,
                "language": self.language, "hash": self.hash,
                "start_line": self.start_line, "end_line": self.end_line,
                "docstring": self.docstring, "dependencies": self.dependencies,
                "semantic_summary": self.semantic_summary, "embedding_ref": self.embedding_ref,
                "last_modified": self.last_modified, "provenance": self.provenance
            }

    @dataclass
    class IndexStats:
        """Statistics about the code index (fallback definition)."""
        total_files: int = 0
        total_symbols: int = 0
        languages: Dict[str, int] = field(default_factory=dict)
        index_time_ms: int = 0
        last_indexed: str = ""
        is_incremental: bool = False
        files_changed: int = 0
        files_unchanged: int = 0

    # Fallback CodeIndex - minimal implementation
    class CodeIndex:
        """Minimal fallback CodeIndex when services.index not available."""
        def __init__(self, storage_path: str = None):
            self.storage_path = storage_path
            self._fragments = {}
            self._stats = IndexStats()
        def index_repository(self, *args, **kwargs): return self._stats
        def search(self, query: str, top_k: int = 10): return []
        def get_stats(self): return {}

    _code_index = None
    def get_code_index(storage_path: str = None):
        global _code_index
        if _code_index is None:
            _code_index = CodeIndex(storage_path)
        return _code_index


# =============================================================================
# Note: CodeIndex, CodeFragment, IndexStats are now in services.index (Gap #6)
# They are re-exported here for backwards compatibility.
# New code should import directly from services.index.
# =============================================================================


# =============================================================================
# Remote Agent Transport Layer
# =============================================================================

@dataclass
class TransportConfig:
    """Configuration for remote agent transport."""
    base_url: str = "http://localhost:8001"
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0


class AgentTransport:
    """
    Transport layer for remote agent execution.

    Enables agents to execute remotely via HTTP/RPC while maintaining
    the same AgentInterface abstraction.

    Usage:
        transport = AgentTransport(config)
        result = await transport.invoke_remote(agent_name, bundle)
    """

    def __init__(self, config: TransportConfig = None):
        self.config = config or TransportConfig()
        self._session = None

    async def invoke_remote(
        self,
        agent_name: str,
        bundle: ContextBundle,
        timeout: float = None
    ) -> ContextBundle:
        """
        Invoke an agent remotely via HTTP.

        Args:
            agent_name: Name of the remote agent
            bundle: Input context bundle
            timeout: Request timeout (optional)

        Returns:
            Output context bundle from remote agent
        """
        import aiohttp
        import json

        url = f"{self.config.base_url}/agents/{agent_name}/invoke"
        timeout = timeout or self.config.timeout

        payload = {
            "contexts": bundle.contexts,
            "metadata": bundle.metadata,
            "provenance": bundle.provenance
        }

        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.retry_count):
                try:
                    async with session.post(
                        url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return ContextBundle(
                                contexts=data.get("contexts", []),
                                metadata=data.get("metadata", {}),
                                provenance=data.get("provenance", "remote"),
                                mutation_log=bundle.mutation_log + [{
                                    "action": "remote_invoke",
                                    "agent": agent_name,
                                    "timestamp": utc_now().isoformat()
                                }]
                            )
                        else:
                            error_text = await response.text()
                            logger.warning(f"Remote agent error: {response.status} - {error_text}")

                except Exception as e:
                    logger.warning(f"Transport error (attempt {attempt + 1}): {e}")
                    if attempt < self.config.retry_count - 1:
                        import asyncio
                        await asyncio.sleep(self.config.retry_delay)

        # Return original bundle with error on failure
        return bundle.add_context({
            "type": "error",
            "message": f"Remote agent {agent_name} invocation failed",
            "provenance": "transport"
        }, "transport")

    async def check_agent_status(self, agent_name: str) -> Dict[str, Any]:
        """Check if a remote agent is available."""
        import aiohttp

        url = f"{self.config.base_url}/agents/{agent_name}/status"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"status": "unavailable", "error": f"HTTP {response.status}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def list_remote_agents(self) -> list:
        """List all available remote agents."""
        import aiohttp

        url = f"{self.config.base_url}/agents"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.json()
                    return []
        except Exception:
            return []


class RemoteAgentProxy(AgentInterface):
    """
    Proxy that wraps a remote agent as a local AgentInterface.

    This allows remote agents to be used transparently with the
    same interface as local agents.

    Usage:
        proxy = RemoteAgentProxy("reasoning", transport)
        result = await proxy.invoke(bundle)  # Executes remotely
    """

    def __init__(
        self,
        name: str,
        transport: AgentTransport,
        remote_capabilities: AgentCapabilities = None
    ):
        super().__init__(
            name=name,
            execution_hint=ExecutionHint.REMOTE
        )
        self.transport = transport
        self._remote_capabilities = remote_capabilities or AgentCapabilities(
            requires_network=True
        )
        self._is_local = False

    def capabilities(self) -> AgentCapabilities:
        return self._remote_capabilities

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """Invoke the remote agent via transport."""
        return await self.transport.invoke_remote(self.name, bundle)


# =============================================================================
# Enhanced ProductionOrchestrator with Agent Integration
# =============================================================================

class EnhancedOrchestrator:
    """
    Enhanced orchestrator with full agent pipeline integration.

    Combines:
    - CodeIndex for incremental indexing
    - CoordinatorAgent for agent management
    - Local/Remote agent execution
    - LLM routing

    Usage:
        orch = EnhancedOrchestrator(mode="auto")
        result = await orch.run_pipeline("/path/to/repo")
    """

    def __init__(self, mode: str = "auto", remote_url: str = None):
        """
        Initialize enhanced orchestrator.

        Args:
            mode: LLM mode - "auto", "online", "offline"
            remote_url: URL for remote agent service (optional)
        """
        self.router = LLMRouter(mode=mode)
        self.coordinator = CoordinatorAgent()
        self.code_index = get_code_index()
        self.transport = AgentTransport(
            TransportConfig(base_url=remote_url or "http://localhost:8001")
        ) if remote_url else None

        # Register built-in agents
        self._setup_agents()

        logger.info(f"EnhancedOrchestrator initialized: mode={mode}")

    def _setup_agents(self):
        """Set up the agent pipeline."""
        # Local agents
        self.coordinator.register_agent(IndexingAgent())
        self.coordinator.register_agent(CritiqueAgent())

        # Reasoning agent (can be local or remote)
        reasoning = ReasoningAgent()
        reasoning._router = self.router
        self.coordinator.register_agent(reasoning)

    async def run_pipeline(
        self,
        repo_path: str,
        task: str = "full_analysis",
        incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Run the full agent pipeline.

        Pipeline:
        1. Index repository (IndexingAgent - LOCAL)
        2. Analyze architecture (ReasoningAgent - AUTO)
        3. Review code (CritiqueAgent - HYBRID)
        4. Generate context file

        Args:
            repo_path: Path to repository
            task: Analysis task type
            incremental: Use incremental indexing

        Returns:
            Pipeline result with analysis and stats
        """
        import time

        start = time.time()
        result = {
            "success": False,
            "repo_path": repo_path,
            "task": task,
            "agents_executed": [],
            "analysis": {},
            "errors": []
        }

        try:
            # Step 1: Index repository
            logger.info(f"Step 1: Indexing {repo_path}")
            index_stats = self.code_index.index_repository(
                repo_path,
                incremental=incremental
            )
            result["analysis"]["index"] = self.code_index.get_stats()
            result["agents_executed"].append({
                "name": "indexing",
                "location": "local",
                "duration_ms": index_stats.index_time_ms
            })

            # Create initial context bundle
            bundle = ContextBundle(
                contexts=[{
                    "type": "index_summary",
                    "total_files": index_stats.total_files,
                    "total_symbols": index_stats.total_symbols,
                    "languages": index_stats.languages
                }],
                metadata={
                    "repo_path": repo_path,
                    "task": task,
                    "query": f"Analyze the {task} of this repository"
                },
                provenance="orchestrator"
            )

            # Step 2: Run coordinator with all agents
            logger.info("Step 2: Running agent pipeline")
            result_bundle = await self.coordinator.invoke(bundle)

            # Extract analysis from result bundle
            for ctx in result_bundle.contexts:
                ctx_type = ctx.get("type", "unknown")
                if ctx_type not in result["analysis"]:
                    result["analysis"][ctx_type] = ctx

            # Record agent execution info
            for agent_name, agent in self.coordinator._agents.items():
                if agent_name not in [a["name"] for a in result["agents_executed"]]:
                    result["agents_executed"].append({
                        "name": agent_name,
                        "location": "local" if agent.is_local else "remote",
                        "hint": agent.execution_hint.value
                    })

            result["success"] = True

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            result["errors"].append(str(e))

        result["duration_ms"] = int((time.time() - start) * 1000)
        result["offline_mode"] = self.router.offline_mode

        return result

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all registered agents."""
        agents = {}
        for name, agent in self.coordinator._agents.items():
            is_local = self.coordinator.resolve_execution_location(agent)
            agents[name] = {
                "execution_hint": agent.execution_hint.value,
                "resolved_location": "local" if is_local else "remote",
                "capabilities": {
                    "consumes": agent.capabilities().consumes,
                    "produces": agent.capabilities().produces,
                    "requires_filesystem": agent.capabilities().requires_filesystem,
                    "requires_network": agent.capabilities().requires_network
                }
            }

        return {
            "agents": agents,
            "total_agents": len(agents),
            "local_agents": sum(1 for a in agents.values() if a["resolved_location"] == "local"),
            "remote_agents": sum(1 for a in agents.values() if a["resolved_location"] == "remote"),
            "llm_mode": "offline" if self.router.offline_mode else "online"
        }


# Global enhanced orchestrator
_enhanced_orchestrator: Optional[EnhancedOrchestrator] = None

def get_enhanced_orchestrator(mode: str = "auto") -> EnhancedOrchestrator:
    """Get or create the global enhanced orchestrator."""
    global _enhanced_orchestrator
    if _enhanced_orchestrator is None:
        _enhanced_orchestrator = EnhancedOrchestrator(mode=mode)
    return _enhanced_orchestrator


async def run_agent_pipeline(
    repo_path: str,
    mode: str = "auto",
    task: str = "full_analysis"
) -> Dict[str, Any]:
    """
    Convenience function to run the agent pipeline.

    This is the main async entry point for the enhanced orchestration.
    """
    orchestrator = get_enhanced_orchestrator(mode)
    return await orchestrator.run_pipeline(repo_path, task)


# =============================================================================
# Gap #5: Testing Agent Improvements - Structured Test Results
# =============================================================================

@dataclass(frozen=True)
class TestResult:
    """
    Structured test result context.

    Represents the result of a test execution with detailed metrics.
    """
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_ms: int = 0
    test_path: str = ""
    pattern: str = ""
    success: bool = True
    framework: str = "pytest"
    output: str = ""
    error_details: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
            "duration_ms": self.duration_ms,
            "test_path": self.test_path,
            "pattern": self.pattern,
            "success": self.success,
            "framework": self.framework,
            "output": self.output,
            "error_details": list(self.error_details),
            "timestamp": self.timestamp
        }

    def to_context(self) -> Context:
        """Convert to a Context object for the context bundle."""
        return Context(
            type=ContextType.TEST_RESULT.value,
            provenance="test_agent",
            content=self.to_dict(),
            scope=ContextScope.SESSION.value
        )

    # Maximum output length to store (prevent memory issues with large outputs)
    MAX_OUTPUT_LENGTH = 5000

    @classmethod
    def from_pytest_output(
        cls,
        output: str,
        test_path: str = "",
        pattern: str = "",
        duration_ms: int = 0
    ) -> "TestResult":
        """
        Create a TestResult from pytest output.

        Args:
            output: Raw pytest output string
            test_path: Path to the test directory/file
            pattern: Test pattern used (-k flag)
            duration_ms: Execution time in milliseconds

        Returns:
            TestResult with parsed values
        """
        # Parse test counts from output
        test_counts = cls._parse_test_counts(output)

        # Extract detailed error information
        error_details = cls._extract_error_details(output)

        total = sum(test_counts.values())
        has_failures = test_counts['failed'] > 0 or test_counts['errors'] > 0

        return cls(
            passed=test_counts['passed'],
            failed=test_counts['failed'],
            skipped=test_counts['skipped'],
            errors=test_counts['errors'],
            total=total,
            duration_ms=duration_ms,
            test_path=test_path,
            pattern=pattern,
            success=not has_failures,
            framework="pytest",
            output=cls._truncate_output(output),
            error_details=error_details
        )

    @classmethod
    def _parse_test_counts(cls, output: str) -> Dict[str, int]:
        """
        Parse test result counts from pytest output.

        Args:
            output: Raw pytest output string

        Returns:
            Dict with passed, failed, skipped, errors counts
        """
        import re

        counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}

        # Patterns for each test result type
        count_patterns = {
            'passed': r'(\d+) passed',
            'failed': r'(\d+) failed',
            'skipped': r'(\d+) skipped',
            'errors': r'(\d+) error'
        }

        for result_type, regex_pattern in count_patterns.items():
            match = re.search(regex_pattern, output)
            if match:
                counts[result_type] = int(match.group(1))

        return counts

    @classmethod
    def _extract_error_details(cls, output: str) -> list:
        """
        Extract failure and error details from pytest output.

        Args:
            output: Raw pytest output string

        Returns:
            List of error detail dictionaries
        """
        import re

        error_details = []

        # Patterns for failures and errors with their type labels
        detail_patterns = [
            (r'FAILED\s+([\w\./]+::\w+)', 'failure'),
            (r'ERROR\s+([\w\./]+::\w+)', 'error')
        ]

        for regex_pattern, error_type in detail_patterns:
            for match in re.finditer(regex_pattern, output):
                error_details.append({
                    "test": match.group(1),
                    "type": error_type
                })

        return error_details

    @classmethod
    def _truncate_output(cls, output: str) -> str:
        """
        Truncate output to maximum length if needed.

        Args:
            output: Output string to truncate

        Returns:
            Truncated output string
        """
        if len(output) > cls.MAX_OUTPUT_LENGTH:
            return output[:cls.MAX_OUTPUT_LENGTH]
        return output


class TestingAgent(AgentInterface):
    """
    Enhanced Testing Agent with structured result output.

    Produces test_result context type with detailed pass/fail/skip counts.
    """

    def __init__(self):
        super().__init__(
            name="testing",
            execution_hint=ExecutionHint.LOCAL
        )

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            consumes=["code_fragment", "file_path"],
            produces=["test_result", "analysis"],
            requires_filesystem=True,
            requires_network=False,
            mutation_rights=[]
        )

    async def invoke(self, bundle: ContextBundle) -> ContextBundle:
        """
        Run tests and produce structured test_result context.

        Looks for test configuration in bundle metadata.
        """
        test_path = bundle.metadata.get("test_path", "tests/")
        pattern = bundle.metadata.get("test_pattern", "")

        result = await self.run_tests(test_path, pattern)

        # Add test result as context
        return bundle.add_context(
            result.to_context().to_dict(),
            source=self.name,
            validate=False
        )

    async def run_tests(
        self,
        test_path: str = "tests/",
        pattern: str = None,
        timeout: int = 300
    ) -> TestResult:
        """
        Run tests and return structured result.

        Args:
            test_path: Path to test directory or file
            pattern: Optional test pattern (-k flag)
            timeout: Test timeout in seconds

        Returns:
            TestResult with parsed results
        """
        import subprocess
        import time

        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
        if pattern:
            cmd.extend(["-k", pattern])

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration_ms = int((time.time() - start) * 1000)

            return TestResult.from_pytest_output(
                output=result.stdout + result.stderr,
                test_path=test_path,
                pattern=pattern or "",
                duration_ms=duration_ms
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                total=1,
                duration_ms=timeout * 1000,
                test_path=test_path,
                pattern=pattern or "",
                success=False,
                framework="pytest",
                output="Test execution timed out",
                error_details=[{"type": "timeout", "message": f"Tests timed out after {timeout}s"}]
            )
        except Exception as e:
            return TestResult(
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                total=1,
                duration_ms=0,
                test_path=test_path,
                pattern=pattern or "",
                success=False,
                framework="pytest",
                output=str(e),
                error_details=[{"type": "exception", "message": str(e)}]
            )

    def generate_test_prompt(
        self,
        file_path: str,
        content: str,
        test_framework: str = "pytest"
    ) -> str:
        """
        Generate a prompt for test creation.

        Args:
            file_path: Source file path
            content: Source file content
            test_framework: Test framework to target

        Returns:
            Prompt string for LLM-based test generation
        """
        language = self._detect_language(file_path)

        return f"""Generate comprehensive {test_framework} tests for the following {language} code.

File: {file_path}

```{language}
{content[:3000]}
```

Requirements:
1. Test all public functions and methods
2. Include edge cases and error handling
3. Use appropriate assertions
4. Add docstrings to test functions
5. Follow {test_framework} conventions

Output only the test code, no explanations."""

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


# =============================================================================
# Gap #7: Schema/Type Safety with Pydantic
# =============================================================================

try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from typing import Literal
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # Fallback


if PYDANTIC_AVAILABLE:
    class ContextModel(BaseModel):
        """
        Pydantic model for runtime validation of Context objects.

        Use this at API boundaries to validate incoming context data.
        """
        type: str = Field(..., description="Context type (e.g., 'analysis', 'code_fragment')")
        provenance: str = Field(..., description="Origin of the context (agent name)")
        id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique context ID")
        scope: str = Field(default="global", description="Context scope")
        content: Optional[Dict[str, Any]] = Field(default=None, description="Context payload")
        parent_id: Optional[str] = Field(default=None, description="Parent context ID")
        created_at: str = Field(default_factory=lambda: utc_now().isoformat(), description="Creation timestamp")

        @field_validator('type')
        @classmethod
        def validate_type(cls, v: str) -> str:
            """Validate type is not empty."""
            if not v or not v.strip():
                raise ValueError("type cannot be empty")
            return v.strip()

        @field_validator('provenance')
        @classmethod
        def validate_provenance(cls, v: str) -> str:
            """Validate provenance is not empty."""
            if not v or not v.strip():
                raise ValueError("provenance cannot be empty")
            return v.strip()

        def to_context(self) -> Context:
            """Convert to internal Context dataclass."""
            return Context(
                type=self.type,
                provenance=self.provenance,
                id=self.id,
                scope=self.scope,
                content=self.content,
                parent_id=self.parent_id,
                created_at=self.created_at
            )

        @classmethod
        def from_context(cls, ctx: Context) -> "ContextModel":
            """Create from internal Context dataclass."""
            return cls(
                type=ctx.type,
                provenance=ctx.provenance,
                id=ctx.id,
                scope=ctx.scope,
                content=ctx.content,
                parent_id=ctx.parent_id,
                created_at=ctx.created_at
            )

        model_config = {"extra": "forbid"}


    class ContextBundleModel(BaseModel):
        """
        Pydantic model for validating ContextBundle at API boundaries.
        """
        contexts: list[ContextModel] = Field(default_factory=list)
        metadata: Dict[str, Any] = Field(default_factory=dict)
        provenance: str = Field(default="api")
        mutation_log: list[Dict[str, Any]] = Field(default_factory=list)

        def to_bundle(self) -> ContextBundle:
            """Convert to internal ContextBundle."""
            return ContextBundle(
                contexts=[ctx.model_dump() for ctx in self.contexts],
                metadata=self.metadata,
                provenance=self.provenance,
                mutation_log=self.mutation_log
            )

        @classmethod
        def from_bundle(cls, bundle: ContextBundle) -> "ContextBundleModel":
            """Create from internal ContextBundle."""
            return cls(
                contexts=[ContextModel(**ctx) for ctx in bundle.contexts],
                metadata=bundle.metadata,
                provenance=bundle.provenance,
                mutation_log=bundle.mutation_log
            )

        model_config = {"extra": "forbid"}


    class TestResultModel(BaseModel):
        """
        Pydantic model for validating TestResult at API boundaries.
        """
        passed: int = Field(default=0, ge=0)
        failed: int = Field(default=0, ge=0)
        skipped: int = Field(default=0, ge=0)
        errors: int = Field(default=0, ge=0)
        total: int = Field(default=0, ge=0)
        duration_ms: int = Field(default=0, ge=0)
        test_path: str = Field(default="")
        pattern: str = Field(default="")
        success: bool = Field(default=True)
        framework: str = Field(default="pytest")
        output: str = Field(default="")
        error_details: list[Dict[str, Any]] = Field(default_factory=list)
        timestamp: str = Field(default_factory=lambda: utc_now().isoformat())

        @model_validator(mode='after')
        def validate_total(self) -> "TestResultModel":
            """Validate total matches sum of counts."""
            expected = self.passed + self.failed + self.skipped + self.errors
            if self.total == 0:
                self.total = expected
            return self

        def to_test_result(self) -> TestResult:
            """Convert to internal TestResult dataclass."""
            return TestResult(
                passed=self.passed,
                failed=self.failed,
                skipped=self.skipped,
                errors=self.errors,
                total=self.total,
                duration_ms=self.duration_ms,
                test_path=self.test_path,
                pattern=self.pattern,
                success=self.success,
                framework=self.framework,
                output=self.output,
                error_details=self.error_details,
                timestamp=self.timestamp
            )

        model_config = {"extra": "forbid"}


    class CodeFragmentModel(BaseModel):
        """
        Pydantic model for validating CodeFragment at API boundaries.
        """
        type: str = Field(..., description="Fragment type (function, class, module)")
        path: str = Field(..., description="File path")
        symbol: str = Field(default="")
        language: str = Field(default="unknown")
        hash: str = Field(default="")
        start_line: int = Field(default=0, ge=0)
        end_line: int = Field(default=0, ge=0)
        docstring: str = Field(default="")
        dependencies: list[str] = Field(default_factory=list)
        semantic_summary: str = Field(default="")
        embedding_ref: str = Field(default="")
        last_modified: str = Field(default="")
        provenance: str = Field(default="filesystem")

        def to_code_fragment(self) -> "CodeFragment":
            """Convert to internal CodeFragment dataclass."""
            return CodeFragment(
                type=self.type,
                path=self.path,
                symbol=self.symbol,
                language=self.language,
                hash=self.hash,
                start_line=self.start_line,
                end_line=self.end_line,
                docstring=self.docstring,
                dependencies=self.dependencies,
                semantic_summary=self.semantic_summary,
                embedding_ref=self.embedding_ref,
                last_modified=self.last_modified,
                provenance=self.provenance
            )

        model_config = {"extra": "forbid"}


def validate_context_pydantic(data: Dict[str, Any]) -> Context:
    """
    Validate context data using Pydantic model.

    Args:
        data: Dictionary with context fields

    Returns:
        Validated Context object

    Raises:
        ValueError: If validation fails (with detailed error message)
    """
    if not PYDANTIC_AVAILABLE:
        return validate_context(data)

    try:
        model = ContextModel(**data)
        return model.to_context()
    except Exception as e:
        raise ValueError(f"Context validation failed: {e}")


def validate_bundle_pydantic(data: Dict[str, Any]) -> ContextBundle:
    """
    Validate context bundle data using Pydantic model.

    Args:
        data: Dictionary with bundle fields

    Returns:
        Validated ContextBundle object

    Raises:
        ValueError: If validation fails
    """
    if not PYDANTIC_AVAILABLE:
        return ContextBundle(**data)

    try:
        model = ContextBundleModel(**data)
        return model.to_bundle()
    except Exception as e:
        raise ValueError(f"ContextBundle validation failed: {e}")