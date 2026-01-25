"""
Tests for the ContextForge orchestrator.

Copyright (c) 2025 ContextForge
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


class TestTaskResult:
    """Test TaskResult dataclass."""
    
    def test_task_result_creation(self):
        """Test creating a TaskResult."""
        from services.orchestrator import TaskResult, TaskStatus
        
        result = TaskResult(
            task_id="test-1",
            status=TaskStatus.COMPLETED,
            result={"count": 10}
        )
        
        assert result.task_id == "test-1"
        assert result.status == TaskStatus.COMPLETED
        assert result.result["count"] == 10
    
    def test_task_result_with_error(self):
        """Test TaskResult with error."""
        from services.orchestrator import TaskResult, TaskStatus
        
        result = TaskResult(
            task_id="test-1",
            status=TaskStatus.FAILED,
            error="Something went wrong"
        )
        
        assert result.status == TaskStatus.FAILED
        assert result.error == "Something went wrong"


class TestModuleAgent:
    """Test ModuleAgent class."""
    
    def test_module_agent_creation(self):
        """Test creating a ModuleAgent."""
        from services.orchestrator import ModuleAgent
        
        agent = ModuleAgent("services/api_gateway")
        
        assert agent.module_path == "services/api_gateway"
        assert agent.module_name == "services.api_gateway"
    
    @pytest.mark.asyncio
    async def test_module_agent_index(self):
        """Test module indexing."""
        from services.orchestrator import ModuleAgent, TaskStatus
        
        with patch('services.vector_index.index.VectorIndex') as mock_index:
            mock_index.return_value.add_document.return_value = [1, 2, 3]
            
            agent = ModuleAgent("tests")
            result = await agent.index()
            
            assert result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            assert result.task_id.startswith("index:")


class TestOrchestrator:
    """Test Orchestrator class."""
    
    def test_orchestrator_creation(self):
        """Test creating an Orchestrator."""
        from services.orchestrator import Orchestrator
        
        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4
            
            orchestrator = Orchestrator()
            
            assert orchestrator.max_concurrent == 4
    
    def test_register_module(self):
        """Test registering a module."""
        from services.orchestrator import Orchestrator, ModuleAgent
        
        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4
            
            orchestrator = Orchestrator()
            agent = orchestrator.register_module("services/test")
            
            assert isinstance(agent, ModuleAgent)
            assert "services/test" in orchestrator._agents
    
    @pytest.mark.asyncio
    async def test_index_modules(self):
        """Test indexing multiple modules."""
        from services.orchestrator import Orchestrator, TaskStatus
        
        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4
            
            orchestrator = Orchestrator()
            
            with patch.object(orchestrator, '_run_with_semaphore', new_callable=AsyncMock) as mock_run:
                from services.orchestrator import TaskResult
                mock_run.return_value = TaskResult(
                    task_id="test",
                    status=TaskStatus.COMPLETED,
                    result={"files_indexed": 5}
                )
                
                results = await orchestrator.index_modules(["module1", "module2"])
                
                assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_parallel_search(self):
        """Test parallel search across modules."""
        from services.orchestrator import Orchestrator, TaskStatus, TaskResult
        
        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4
            
            orchestrator = Orchestrator()
            orchestrator.register_module("module1")
            
            with patch.object(orchestrator, '_run_with_semaphore', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = TaskResult(
                    task_id="search:module1",
                    status=TaskStatus.COMPLETED,
                    result=[{"id": 1, "score": 0.9}]
                )
                
                results = await orchestrator.parallel_search("test query")
                
                assert "results" in results
                assert "module_results" in results
    
    @pytest.mark.asyncio
    async def test_detect_changes(self):
        """Test change detection."""
        from services.orchestrator import Orchestrator
        
        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4
            
            orchestrator = Orchestrator()
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="file1.py\nfile2.py\n"
                )
                
                files = await orchestrator.detect_changes()
                
                assert len(files) == 2
                assert "file1.py" in files


class TestOrchestratorSingleton:
    """Test orchestrator singleton pattern."""
    
    def test_get_orchestrator(self):
        """Test getting singleton orchestrator."""
        from services.orchestrator import get_orchestrator, Orchestrator
        import services.orchestrator as orch_module

        # Reset singleton
        orch_module._orchestrator = None

        with patch('services.config.get_config') as mock_config:
            mock_config.return_value.agent.max_concurrent = 4

            o1 = get_orchestrator()
            o2 = get_orchestrator()

            assert o1 is o2


class TestReviewAgent:
    """Test ReviewAgent class."""

    def test_review_agent_creation(self):
        """Test creating a ReviewAgent."""
        from services.orchestrator import ReviewAgent

        agent = ReviewAgent()
        assert agent.name == "ReviewAgent"

    def test_detect_language(self):
        """Test language detection from file path."""
        from services.orchestrator import ReviewAgent

        agent = ReviewAgent()

        assert agent._detect_language("test.py") == "python"
        assert agent._detect_language("test.js") == "javascript"
        assert agent._detect_language("test.ts") == "typescript"
        assert agent._detect_language("test.txt") == "text"

    @pytest.mark.asyncio
    async def test_review_file_with_content(self):
        """Test reviewing file with provided content."""
        from services.orchestrator import ReviewAgent

        agent = ReviewAgent()

        # Mock the dependencies
        with patch('services.prompt_enhancer.get_context_aggregator') as mock_agg, \
             patch('services.code_analysis.get_code_analyzer') as mock_analyzer:

            mock_agg.return_value.gather_context = AsyncMock(return_value=MagicMock())
            mock_analyzer.return_value.analyze_file = AsyncMock(return_value=[])

            result = await agent.review_file(
                "test.py",
                content="def hello(): pass",
                include_static_analysis=False
            )

            assert result["file"] == "test.py"
            assert "prompt" in result


class TestTestAgent:
    """Test TestAgent class."""

    def test_test_agent_creation(self):
        """Test creating a TestAgent."""
        from services.orchestrator import TestAgent

        agent = TestAgent()
        assert agent.name == "TestAgent"

    def test_parse_pytest_output(self):
        """Test parsing pytest output."""
        from services.orchestrator import TestAgent

        agent = TestAgent()

        output = "10 passed, 2 failed, 1 skipped in 5.23s"
        summary = agent._parse_pytest_output(output)

        assert summary["passed"] == 10
        assert summary["failed"] == 2
        assert summary["skipped"] == 1

    @pytest.mark.asyncio
    async def test_generate_tests(self):
        """Test test generation."""
        from services.orchestrator import TestAgent

        agent = TestAgent()

        with patch('services.prompt_enhancer.get_context_aggregator') as mock_agg:
            mock_agg.return_value.gather_context = AsyncMock(return_value=MagicMock())

            result = await agent.generate_tests(
                "test.py",
                content="def add(a, b): return a + b",
                test_framework="pytest"
            )

            assert result["file"] == "test.py"
            assert result["test_framework"] == "pytest"
            assert "prompt" in result


class TestDocAgent:
    """Test DocAgent class."""

    def test_doc_agent_creation(self):
        """Test creating a DocAgent."""
        from services.orchestrator import DocAgent

        agent = DocAgent()
        assert agent.name == "DocAgent"

    @pytest.mark.asyncio
    async def test_generate_docs(self):
        """Test documentation generation."""
        from services.orchestrator import DocAgent

        agent = DocAgent()

        result = await agent.generate_docs(
            "test.py",
            content="def hello(): pass",
            doc_style="Google"
        )

        assert result["file"] == "test.py"
        assert result["doc_style"] == "Google"
        assert "prompt" in result


class TestAgentSingletons:
    """Test agent singleton accessors."""

    def test_get_review_agent(self):
        """Test ReviewAgent singleton."""
        from services.orchestrator import get_review_agent
        import services.orchestrator as orch_module

        orch_module._review_agent = None

        a1 = get_review_agent()
        a2 = get_review_agent()

        assert a1 is a2

    def test_get_test_agent(self):
        """Test TestAgent singleton."""
        from services.orchestrator import get_test_agent
        import services.orchestrator as orch_module

        orch_module._test_agent = None

        a1 = get_test_agent()
        a2 = get_test_agent()

        assert a1 is a2

    def test_get_doc_agent(self):
        """Test DocAgent singleton."""
        from services.orchestrator import get_doc_agent
        import services.orchestrator as orch_module

        orch_module._doc_agent = None

        a1 = get_doc_agent()
        a2 = get_doc_agent()

        assert a1 is a2


class TestLLMRouter:
    """Test LLMRouter from core module."""

    def test_llm_router_creation_auto(self):
        """Test creating LLMRouter with auto mode."""
        from services.core import LLMRouter, OperationMode

        router = LLMRouter(mode="auto")

        assert router.user_mode == OperationMode.AUTO

    def test_llm_router_creation_offline(self):
        """Test creating LLMRouter with offline mode."""
        from services.core import LLMRouter

        router = LLMRouter(mode="offline")

        assert router.offline_mode is True

    def test_llm_router_creation_online(self):
        """Test creating LLMRouter with online mode."""
        from services.core import LLMRouter

        router = LLMRouter(mode="online")

        assert router.offline_mode is False

    def test_detect_mode_auto(self):
        """Test auto mode detection."""
        from services.core import LLMRouter

        with patch('services.core.check_internet', return_value=True):
            router = LLMRouter(mode="auto")
            assert router.offline_mode is False

        with patch('services.core.check_internet', return_value=False):
            router = LLMRouter(mode="auto")
            assert router.offline_mode is True


class TestCheckInternet:
    """Test internet connectivity check."""

    def test_check_internet_success(self):
        """Test successful internet check."""
        from services.core import check_internet

        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            result = check_internet()

            assert result is True
            mock_sock.connect.assert_called_once()
            mock_sock.close.assert_called_once()

    def test_check_internet_failure(self):
        """Test failed internet check."""
        from services.core import check_internet
        import socket

        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = socket.error("Connection failed")
            mock_socket.return_value = mock_sock

            result = check_internet()

            assert result is False


class TestOrchestrationResult:
    """Test OrchestrationResult dataclass."""

    def test_result_creation(self):
        """Test creating OrchestrationResult."""
        from services.core import OrchestrationResult

        result = OrchestrationResult(
            success=True,
            repo_path="/test/path",
            analysis={"test": "data"}
        )

        assert result.success is True
        assert result.repo_path == "/test/path"
        assert result.analysis == {"test": "data"}

    def test_result_to_json(self):
        """Test JSON serialization."""
        from services.core import OrchestrationResult

        result = OrchestrationResult(
            success=True,
            repo_path="/test/path",
            context_file="/test/.contextforge.md",
            analysis={"scan": {"files": 10}},
            agents_used=["architect", "reviewer"],
            duration_ms=1500,
            offline_mode=False,
            errors=[]
        )

        json_data = result.to_json()

        assert json_data["success"] is True
        assert json_data["repo_path"] == "/test/path"
        assert json_data["context_file"] == "/test/.contextforge.md"
        assert json_data["agents_used"] == ["architect", "reviewer"]
        assert json_data["duration_ms"] == 1500
        assert json_data["offline_mode"] is False


class TestProductionOrchestrator:
    """Test ProductionOrchestrator class."""

    def test_orchestrator_creation(self):
        """Test creating ProductionOrchestrator."""
        from services.core import ProductionOrchestrator

        with patch('services.core.check_internet', return_value=True):
            orchestrator = ProductionOrchestrator(mode="auto")

            assert orchestrator.router is not None
            assert orchestrator.router.offline_mode is False

    def test_orchestrator_offline_mode(self):
        """Test orchestrator with offline mode."""
        from services.core import ProductionOrchestrator

        orchestrator = ProductionOrchestrator(mode="offline")

        assert orchestrator.router.offline_mode is True

    def test_to_markdown(self):
        """Test markdown generation."""
        from services.core import ProductionOrchestrator

        orchestrator = ProductionOrchestrator(mode="offline")

        analysis = {
            "scan": {"files": 25, "languages": ["python", "javascript"]},
            "architecture": {"summary": "Microservices architecture"},
            "review": {"findings": "Code quality is good"}
        }

        markdown = orchestrator._to_markdown(analysis)

        assert "# ContextForge Analysis" in markdown
        assert "25" in markdown
        assert "python" in markdown
        assert "Microservices architecture" in markdown

    def test_to_xml(self):
        """Test XML generation."""
        from services.core import ProductionOrchestrator

        orchestrator = ProductionOrchestrator(mode="offline")

        analysis = {
            "scan": {"files": 10, "languages": ["python"]},
            "architecture": {"summary": "Monolith"}
        }

        xml = orchestrator._to_xml(analysis)

        assert '<?xml version="1.0"' in xml
        assert "<contextforge>" in xml
        assert "<files>10</files>" in xml


class TestProductionRun:
    """Test production_run convenience function."""

    def test_production_run_returns_dict(self):
        """Test that production_run returns a dict."""
        from services.core import production_run

        with patch('services.core.ProductionOrchestrator') as mock_orch:
            mock_result = MagicMock()
            mock_result.to_json.return_value = {"success": True, "repo_path": "/test"}
            mock_orch.return_value.run.return_value = mock_result

            result = production_run("/test/path", mode="offline")

            assert isinstance(result, dict)
            assert result["success"] is True


# =============================================================================
# Agent Interface Tests
# =============================================================================

class TestExecutionHint:
    """Test ExecutionHint enum."""

    def test_execution_hint_values(self):
        """Test all execution hint values exist."""
        from services.core import ExecutionHint

        assert ExecutionHint.LOCAL.value == "local"
        assert ExecutionHint.REMOTE.value == "remote"
        assert ExecutionHint.HYBRID.value == "hybrid"


class TestContextBundle:
    """Test ContextBundle dataclass."""

    def test_context_bundle_creation(self):
        """Test creating a context bundle."""
        from services.core import ContextBundle

        bundle = ContextBundle(
            contexts=[{"type": "test"}],
            metadata={"key": "value"},
            provenance="test_source"
        )

        assert len(bundle.contexts) == 1
        assert bundle.metadata["key"] == "value"
        assert bundle.provenance == "test_source"

    def test_context_bundle_add_context(self):
        """Test adding context returns new bundle (immutable)."""
        from services.core import ContextBundle

        bundle1 = ContextBundle(contexts=[{"type": "initial"}])
        bundle2 = bundle1.add_context({"type": "added"}, "test_agent")

        # Original unchanged
        assert len(bundle1.contexts) == 1
        # New bundle has both
        assert len(bundle2.contexts) == 2
        assert bundle2.contexts[1]["type"] == "added"
        # Mutation logged
        assert len(bundle2.mutation_log) == 1
        assert bundle2.mutation_log[0]["source"] == "test_agent"


class TestAgentCapabilities:
    """Test AgentCapabilities dataclass."""

    def test_capabilities_creation(self):
        """Test creating agent capabilities."""
        from services.core import AgentCapabilities

        caps = AgentCapabilities(
            consumes=["code_fragment"],
            produces=["analysis"],
            requires_filesystem=True,
            requires_network=False,
            mutation_rights=["index_storage"]
        )

        assert "code_fragment" in caps.consumes
        assert "analysis" in caps.produces
        assert caps.requires_filesystem is True
        assert caps.requires_network is False


class TestAgentInterface:
    """Test AgentInterface base class."""

    def test_agent_interface_creation(self):
        """Test creating an agent interface."""
        from services.core import AgentInterface, ExecutionHint

        agent = AgentInterface(
            name="test_agent",
            execution_hint=ExecutionHint.LOCAL
        )

        assert agent.name == "test_agent"
        assert agent.execution_hint == ExecutionHint.LOCAL
        assert agent.is_local is True

    def test_agent_interface_repr(self):
        """Test agent string representation."""
        from services.core import AgentInterface, ExecutionHint

        agent = AgentInterface(name="my_agent", execution_hint=ExecutionHint.REMOTE)

        assert "my_agent" in repr(agent)
        assert "remote" in repr(agent)

    def test_agent_default_capabilities(self):
        """Test default capabilities are empty."""
        from services.core import AgentInterface

        agent = AgentInterface(name="test")
        caps = agent.capabilities()

        assert caps.consumes == []
        assert caps.produces == []


class TestCoordinatorAgent:
    """Test CoordinatorAgent implementation."""

    def test_coordinator_creation(self):
        """Test creating coordinator agent."""
        from services.core import CoordinatorAgent, ExecutionHint

        coord = CoordinatorAgent()

        assert coord.name == "coordinator"
        assert coord.execution_hint == ExecutionHint.LOCAL

    def test_coordinator_register_agent(self):
        """Test registering agents with coordinator."""
        from services.core import CoordinatorAgent, AgentInterface, ExecutionHint

        coord = CoordinatorAgent()
        agent = AgentInterface(name="test", execution_hint=ExecutionHint.REMOTE)

        coord.register_agent(agent)

        assert "test" in coord._agents

    def test_coordinator_resolve_local_hint(self):
        """Test coordinator resolves LOCAL hint to local."""
        from services.core import CoordinatorAgent, AgentInterface, ExecutionHint

        coord = CoordinatorAgent()
        agent = AgentInterface(name="local_agent", execution_hint=ExecutionHint.LOCAL)

        is_local = coord.resolve_execution_location(agent)

        assert is_local is True

    def test_coordinator_resolve_filesystem_requirement(self):
        """Test coordinator forces local for filesystem access."""
        from services.core import CoordinatorAgent, IndexingAgent

        coord = CoordinatorAgent()
        agent = IndexingAgent()

        is_local = coord.resolve_execution_location(agent)

        assert is_local is True  # Indexing needs filesystem


class TestIndexingAgent:
    """Test IndexingAgent implementation."""

    def test_indexing_agent_creation(self):
        """Test creating indexing agent."""
        from services.core import IndexingAgent, ExecutionHint

        agent = IndexingAgent()

        assert agent.name == "indexing"
        assert agent.execution_hint == ExecutionHint.LOCAL

    def test_indexing_capabilities(self):
        """Test indexing agent capabilities."""
        from services.core import IndexingAgent

        agent = IndexingAgent()
        caps = agent.capabilities()

        assert caps.requires_filesystem is True
        assert "code_fragment" in caps.produces
        assert "index_storage" in caps.mutation_rights


class TestReasoningAgent:
    """Test ReasoningAgent implementation."""

    def test_reasoning_agent_creation(self):
        """Test creating reasoning agent."""
        from services.core import ReasoningAgent, ExecutionHint

        agent = ReasoningAgent(name="planner")

        assert agent.name == "planner"
        assert agent.execution_hint == ExecutionHint.REMOTE

    def test_reasoning_capabilities(self):
        """Test reasoning agent capabilities."""
        from services.core import ReasoningAgent

        agent = ReasoningAgent()
        caps = agent.capabilities()

        assert caps.requires_network is True
        assert "analysis" in caps.produces


class TestCritiqueAgent:
    """Test CritiqueAgent implementation."""

    def test_critique_agent_creation(self):
        """Test creating critique agent."""
        from services.core import CritiqueAgent, ExecutionHint

        agent = CritiqueAgent()

        assert agent.name == "critique"
        assert agent.execution_hint == ExecutionHint.HYBRID


class TestCoreReviewAgent:
    """Test ReviewAgent implementation from services.core."""

    def test_review_agent_creation(self):
        """Test creating review agent."""
        from services.core import ReviewAgent, ExecutionHint

        agent = ReviewAgent()

        assert agent.name == "review"
        assert agent.execution_hint == ExecutionHint.HYBRID

    def test_review_agent_capabilities(self):
        """Test review agent capabilities."""
        from services.core import ReviewAgent

        agent = ReviewAgent()
        caps = agent.capabilities()

        assert "code_fragment" in caps.consumes
        assert "file_path" in caps.consumes
        assert "review" in caps.produces
        assert caps.requires_filesystem is True
        assert caps.requires_network is False


class TestCoreDocAgent:
    """Test DocAgent implementation from services.core."""

    def test_doc_agent_creation(self):
        """Test creating doc agent."""
        from services.core import DocAgent, ExecutionHint

        agent = DocAgent()

        assert agent.name == "doc"
        assert agent.execution_hint == ExecutionHint.HYBRID

    def test_doc_agent_capabilities(self):
        """Test doc agent capabilities."""
        from services.core import DocAgent

        agent = DocAgent()
        caps = agent.capabilities()

        assert "code_fragment" in caps.consumes
        assert "file_path" in caps.consumes
        assert "documentation" in caps.produces
        assert "docstring" in caps.produces
        assert caps.requires_filesystem is True
        assert caps.requires_network is False


class TestCoreRefactorAgent:
    """Test RefactorAgent implementation from services.core."""

    def test_refactor_agent_creation(self):
        """Test creating refactor agent."""
        from services.core import RefactorAgent, ExecutionHint

        agent = RefactorAgent()

        assert agent.name == "refactor"
        assert agent.execution_hint == ExecutionHint.HYBRID

    def test_refactor_agent_capabilities(self):
        """Test refactor agent capabilities."""
        from services.core import RefactorAgent

        agent = RefactorAgent()
        caps = agent.capabilities()

        assert "code_fragment" in caps.consumes
        assert "file_path" in caps.consumes
        assert "file_tree" in caps.consumes
        assert "refactoring_plan" in caps.produces
        assert "code_changes" in caps.produces
        assert caps.requires_filesystem is True
        assert caps.requires_network is False
        assert "source_files" in caps.mutation_rights


class TestCoreTestingAgent:
    """Test TestingAgent implementation from services.core."""

    def test_testing_agent_creation(self):
        """Test creating testing agent."""
        from services.core import TestingAgent, ExecutionHint

        agent = TestingAgent()

        assert agent.name == "testing"
        assert agent.execution_hint == ExecutionHint.LOCAL

    def test_testing_agent_capabilities(self):
        """Test testing agent capabilities."""
        from services.core import TestingAgent

        agent = TestingAgent()
        caps = agent.capabilities()

        assert "code_fragment" in caps.consumes
        assert "file_path" in caps.consumes
        assert "test_result" in caps.produces
        assert caps.requires_filesystem is True
        assert caps.requires_network is False


class TestAgentRegistry:
    """Test global agent registry."""

    def test_register_and_get_agent(self):
        """Test registering and retrieving agents."""
        from services.core import (
            AgentInterface, ExecutionHint,
            register_agent, get_agent, _agent_registry
        )

        # Clear registry
        _agent_registry.clear()

        agent = AgentInterface(name="registered_agent", execution_hint=ExecutionHint.LOCAL)
        register_agent(agent)

        retrieved = get_agent("registered_agent")
        assert retrieved is agent

    def test_list_agents(self):
        """Test listing all registered agents."""
        from services.core import (
            CoordinatorAgent, IndexingAgent,
            register_agent, list_agents, _agent_registry
        )

        _agent_registry.clear()

        register_agent(CoordinatorAgent())
        register_agent(IndexingAgent())

        agents = list_agents()

        assert "coordinator" in agents
        assert "indexing" in agents
        assert agents["coordinator"]["execution_hint"] == "local"
        assert agents["indexing"]["capabilities"]["requires_filesystem"] is True


# =============================================================================
# Gap #1: Context Schema & Validation Tests
# =============================================================================

class TestContextSchema:
    """Test Context dataclass and validation."""

    def test_context_creation_with_required_fields(self):
        """Test creating a Context with required fields."""
        from services.core import Context

        ctx = Context(type="analysis", provenance="test_agent")

        assert ctx.type == "analysis"
        assert ctx.provenance == "test_agent"
        assert ctx.id is not None  # Auto-generated
        assert ctx.scope == "global"  # Default
        assert ctx.created_at is not None

    def test_context_to_dict(self):
        """Test Context serialization."""
        from services.core import Context

        ctx = Context(
            type="code_fragment",
            provenance="indexing",
            content={"code": "def foo(): pass"}
        )

        d = ctx.to_dict()

        assert d["type"] == "code_fragment"
        assert d["provenance"] == "indexing"
        assert d["content"]["code"] == "def foo(): pass"
        assert "id" in d
        assert "created_at" in d

    def test_context_is_frozen(self):
        """Test that Context is immutable."""
        from services.core import Context
        from dataclasses import FrozenInstanceError

        ctx = Context(type="analysis", provenance="test")

        with pytest.raises(FrozenInstanceError):
            ctx.type = "modified"

    def test_validate_context_success(self):
        """Test successful context validation."""
        from services.core import validate_context, Context

        result = validate_context({
            "type": "analysis",
            "provenance": "reasoning"
        })

        assert isinstance(result, Context)
        assert result.type == "analysis"
        assert result.provenance == "reasoning"

    def test_validate_context_missing_type(self):
        """Test validation fails without type."""
        from services.core import validate_context

        with pytest.raises(ValueError) as exc_info:
            validate_context({"provenance": "test"})

        assert "type" in str(exc_info.value)

    def test_validate_context_missing_provenance(self):
        """Test validation fails without provenance."""
        from services.core import validate_context

        with pytest.raises(ValueError) as exc_info:
            validate_context({"type": "analysis"})

        assert "provenance" in str(exc_info.value)

    def test_validate_context_accepts_context_object(self):
        """Test validation accepts existing Context objects."""
        from services.core import validate_context, Context

        original = Context(type="analysis", provenance="test")
        result = validate_context(original)

        assert result is original

    def test_context_type_enum_values(self):
        """Test ContextType enum has expected values."""
        from services.core import ContextType

        assert ContextType.CODE_FRAGMENT.value == "code_fragment"
        assert ContextType.ANALYSIS.value == "analysis"
        assert ContextType.DIAGNOSTIC.value == "diagnostic"
        assert ContextType.ERROR.value == "error"

    def test_context_scope_enum_values(self):
        """Test ContextScope enum has expected values."""
        from services.core import ContextScope

        assert ContextScope.GLOBAL.value == "global"
        assert ContextScope.AGENT.value == "agent"
        assert ContextScope.SESSION.value == "session"


# =============================================================================
# Gap #2: Context Mutation Controls Tests
# =============================================================================

class TestContextMutationControls:
    """Test immutability and mutation controls."""

    def test_bundle_contexts_returns_copy(self):
        """Test that bundle.contexts returns a copy."""
        from services.core import ContextBundle

        bundle = ContextBundle(contexts=[{"type": "test", "data": "original"}])

        contexts = bundle.contexts
        contexts.append({"type": "new"})

        # Original bundle unchanged
        assert len(bundle.contexts) == 1

    def test_bundle_contexts_dict_copy(self):
        """Test that individual contexts are copied."""
        from services.core import ContextBundle

        bundle = ContextBundle(contexts=[{"type": "test", "data": "original"}])

        contexts = bundle.contexts
        contexts[0]["data"] = "modified"

        # Original bundle unchanged (shallow copy)
        assert bundle.contexts[0]["data"] == "original"

    def test_add_context_creates_new_bundle(self):
        """Test add_context returns new bundle, original unchanged."""
        from services.core import ContextBundle

        bundle1 = ContextBundle(contexts=[{"type": "initial"}])
        bundle2 = bundle1.add_context({"type": "added"}, "test")

        assert len(bundle1.contexts) == 1
        assert len(bundle2.contexts) == 2
        assert bundle1 is not bundle2

    def test_add_context_with_validation(self):
        """Test add_context with validation enabled."""
        from services.core import ContextBundle, Context

        bundle = ContextBundle()
        new_bundle = bundle.add_context(
            {"type": "analysis", "provenance": "test"},
            source="test",
            validate=True
        )

        # Should have converted to proper structure
        assert len(new_bundle.contexts) == 1
        assert new_bundle.contexts[0]["type"] == "analysis"

    def test_add_context_validation_fails(self):
        """Test add_context validation rejects invalid context."""
        from services.core import ContextBundle

        bundle = ContextBundle()

        with pytest.raises(ValueError):
            bundle.add_context({"invalid": "no_type"}, source="test", validate=True)

    def test_mutation_log_tracks_additions(self):
        """Test mutation log records add_context calls."""
        from services.core import ContextBundle

        bundle = ContextBundle()
        bundle = bundle.add_context({"type": "test"}, "agent1")
        bundle = bundle.add_context({"type": "test2"}, "agent2")

        assert len(bundle.mutation_log) == 2
        assert bundle.mutation_log[0]["source"] == "agent1"
        assert bundle.mutation_log[1]["source"] == "agent2"
        assert bundle.mutation_log[0]["action"] == "add_context"

    def test_add_context_generates_id(self):
        """Test add_context generates ID if missing."""
        from services.core import ContextBundle

        bundle = ContextBundle()
        bundle = bundle.add_context({"type": "test"}, "agent")

        assert "id" in bundle.contexts[0]
        assert bundle.contexts[0]["id"] is not None

    def test_bundle_accepts_context_objects(self):
        """Test bundle can store Context objects."""
        from services.core import ContextBundle, Context

        ctx = Context(type="analysis", provenance="test")
        bundle = ContextBundle()
        bundle = bundle.add_context(ctx, "test")

        # contexts property returns dicts
        assert bundle.contexts[0]["type"] == "analysis"


# =============================================================================
# Gap #3: Debugging Agent Tests
# =============================================================================

class TestDebuggingAgent:
    """Test DebuggingAgent implementation."""

    def test_debugging_agent_creation(self):
        """Test creating a DebuggingAgent."""
        from services.core import DebuggingAgent, ExecutionHint

        agent = DebuggingAgent()

        assert agent.name == "debugging"
        assert agent.execution_hint == ExecutionHint.LOCAL

    def test_debugging_agent_capabilities(self):
        """Test debugging agent capabilities."""
        from services.core import DebuggingAgent

        agent = DebuggingAgent()
        caps = agent.capabilities()

        assert "*" in caps.consumes  # Consumes all
        assert "diagnostic" in caps.produces
        assert caps.requires_network is False
        assert caps.mutation_rights == []  # Read-only

    @pytest.mark.asyncio
    async def test_debugging_agent_invoke(self):
        """Test debugging agent produces diagnostic context."""
        from services.core import DebuggingAgent, ContextBundle

        agent = DebuggingAgent()
        bundle = ContextBundle(contexts=[
            {"type": "analysis", "provenance": "reasoning"},
            {"type": "code_fragment", "provenance": "indexing"}
        ])

        result = await agent.invoke(bundle)

        # Should have original + diagnostic
        assert len(result.contexts) == 3

        # Find diagnostic context
        diagnostic = [c for c in result.contexts if c.get("type") == "diagnostic"][0]

        assert diagnostic["content"]["context_count"] == 2
        assert "analysis" in diagnostic["content"]["contexts_by_type"]
        assert "reasoning" in diagnostic["content"]["contexts_by_agent"]

    @pytest.mark.asyncio
    async def test_debugging_agent_health_assessment(self):
        """Test debugging agent health assessment."""
        from services.core import DebuggingAgent, ContextBundle

        agent = DebuggingAgent()
        bundle = ContextBundle(contexts=[{"type": "test", "provenance": "test"}])

        result = await agent.invoke(bundle)
        diagnostic = [c for c in result.contexts if c.get("type") == "diagnostic"][0]

        assert diagnostic["content"]["health"] == "healthy"

    def test_debugging_agent_format_report(self):
        """Test debugging agent report formatting."""
        from services.core import DebuggingAgent, ContextBundle

        agent = DebuggingAgent()
        bundle = ContextBundle(contexts=[
            {"type": "analysis", "provenance": "reasoning"},
            {"type": "analysis", "provenance": "critique"}
        ])

        report = agent.format_report(bundle)

        assert "DIAGNOSTIC REPORT" in report
        assert "Total Contexts: 2" in report
        assert "analysis" in report


# =============================================================================
# Gap #4: Coordinator Safeguards Tests
# =============================================================================

class TestCoordinatorSafeguards:
    """Test coordinator safety features."""

    def test_coordinator_config_defaults(self):
        """Test default coordinator config values."""
        from services.core import CoordinatorConfig

        config = CoordinatorConfig()

        assert config.max_depth == 10
        assert config.max_contexts == 1000
        assert config.agent_timeout_seconds == 60.0
        assert config.enable_scope_filtering is True
        assert config.enable_loop_detection is True

    def test_coordinator_with_custom_config(self):
        """Test coordinator accepts custom config."""
        from services.core import CoordinatorAgent, CoordinatorConfig

        config = CoordinatorConfig(max_depth=5, max_contexts=100)
        coord = CoordinatorAgent(config=config)

        assert coord._config.max_depth == 5
        assert coord._config.max_contexts == 100

    def test_coordinator_errors_exist(self):
        """Test coordinator exception classes exist."""
        from services.core import (
            CoordinatorError,
            RecursionLimitError,
            ContextLimitError,
            AgentTimeoutError,
            LoopDetectedError
        )

        assert issubclass(RecursionLimitError, CoordinatorError)
        assert issubclass(ContextLimitError, CoordinatorError)
        assert issubclass(AgentTimeoutError, CoordinatorError)
        assert issubclass(LoopDetectedError, CoordinatorError)

    @pytest.mark.asyncio
    async def test_context_limit_error(self):
        """Test context limit triggers error."""
        from services.core import (
            CoordinatorAgent, CoordinatorConfig,
            ContextBundle, ContextLimitError, AgentInterface, ExecutionHint
        )

        config = CoordinatorConfig(max_contexts=5)
        coord = CoordinatorAgent(config=config)

        # Register a simple agent
        class SimpleAgent(AgentInterface):
            def __init__(self):
                super().__init__(name="simple", execution_hint=ExecutionHint.LOCAL)
            async def invoke(self, bundle):
                return bundle

        coord.register_agent(SimpleAgent())

        # Bundle with too many contexts
        contexts = [{"type": f"test{i}", "provenance": "test"} for i in range(6)]
        bundle = ContextBundle(contexts=contexts)

        with pytest.raises(ContextLimitError):
            await coord.invoke_agent("simple", bundle)

    def test_coordinator_invocation_history(self):
        """Test invocation history tracking."""
        from services.core import CoordinatorAgent

        coord = CoordinatorAgent()

        # Initially empty
        assert coord.get_invocation_history() == []

        # History should be a copy
        history = coord.get_invocation_history()
        history.append({"fake": "entry"})
        assert coord.get_invocation_history() == []

    def test_reset_invocation_state(self):
        """Test reset clears invocation tracking."""
        from services.core import CoordinatorAgent

        coord = CoordinatorAgent()
        coord._invocation_depth = 5
        coord._invocation_hashes.add("test_hash")

        coord.reset_invocation_state()

        assert coord._invocation_depth == 0
        assert len(coord._invocation_hashes) == 0