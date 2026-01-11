"""
Tests for the ContextForge prompt enhancer module.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestTaskType:
    """Test TaskType enum."""
    
    def test_task_types_exist(self):
        """Test that all task types are defined."""
        from services.prompt_enhancer import TaskType
        
        assert TaskType.CODE_REVIEW.value == "code_review"
        assert TaskType.BUG_DETECTION.value == "bug_detection"
        assert TaskType.TEST_GENERATION.value == "test_generation"
        assert TaskType.REFACTOR.value == "refactor"
        assert TaskType.DOCUMENTATION.value == "documentation"
        assert TaskType.SECURITY_AUDIT.value == "security_audit"
        assert TaskType.GENERAL.value == "general"


class TestContextData:
    """Test ContextData dataclass."""
    
    def test_context_data_creation(self):
        """Test creating ContextData with defaults."""
        from services.prompt_enhancer import ContextData
        
        context = ContextData()
        
        assert context.module_summary == ""
        assert context.file_embeddings == []
        assert context.test_results == []
        assert context.git_history == []
        assert context.lint_results == []
        assert context.security_findings == []
    
    def test_context_data_with_values(self):
        """Test ContextData with provided values."""
        from services.prompt_enhancer import ContextData
        
        context = ContextData(
            module_summary="Test module",
            file_embeddings=[{"file": "test.py", "embedding": [0.1, 0.2]}],
            test_results=[{"test": "test_foo", "passed": True}]
        )
        
        assert context.module_summary == "Test module"
        assert len(context.file_embeddings) == 1
        assert len(context.test_results) == 1


class TestPromptBuilder:
    """Test PromptBuilder class."""
    
    def test_prompt_builder_creation(self):
        """Test creating a PromptBuilder."""
        from services.prompt_enhancer import PromptBuilder

        builder = PromptBuilder()
        assert builder.max_tokens == 4096  # Default is 4096

        builder2 = PromptBuilder(max_tokens=8192)
        assert builder2.max_tokens == 8192

    def test_build_prompt_code_review(self):
        """Test building a code review prompt."""
        from services.prompt_enhancer import PromptBuilder, TaskType, ContextData

        builder = PromptBuilder()
        context = ContextData(module_summary="A utility module")

        prompt = builder.build_prompt(
            TaskType.CODE_REVIEW,
            context,
            code="def hello(): pass",
            language="python"
        )

        # Check for key elements in the prompt
        assert "code reviewer" in prompt.lower()
        assert "def hello(): pass" in prompt
        assert "A utility module" in prompt

    def test_build_prompt_bug_detection(self):
        """Test building a bug detection prompt."""
        from services.prompt_enhancer import PromptBuilder, TaskType, ContextData

        builder = PromptBuilder()
        context = ContextData(
            security_findings=[{"rule": "B101", "message": "assert used"}]
        )

        prompt = builder.build_prompt(
            TaskType.BUG_DETECTION,
            context,
            code="assert x > 0"
        )

        # Check for key elements
        assert "bug" in prompt.lower()
        assert "B101" in prompt

    def test_build_prompt_test_generation(self):
        """Test building a test generation prompt."""
        from services.prompt_enhancer import PromptBuilder, TaskType, ContextData

        builder = PromptBuilder()
        context = ContextData()

        prompt = builder.build_prompt(
            TaskType.TEST_GENERATION,
            context,
            code="def add(a, b): return a + b",
            test_framework="pytest"
        )

        # Check for key elements
        assert "test" in prompt.lower()
        assert "pytest" in prompt

    def test_build_prompt_with_lint_results(self):
        """Test prompt includes lint results."""
        from services.prompt_enhancer import PromptBuilder, TaskType, ContextData

        builder = PromptBuilder()
        context = ContextData(
            lint_results=[
                {"rule": "E501", "message": "line too long", "line": 10}
            ]
        )

        prompt = builder.build_prompt(
            TaskType.CODE_REVIEW,
            context,
            code="x = 1"
        )

        # Check for static analysis section
        assert "Static Analysis" in prompt or "line too long" in prompt
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        from services.prompt_enhancer import PromptBuilder
        
        builder = PromptBuilder()
        
        # Roughly 4 chars per token
        text = "a" * 400
        estimate = builder._estimate_tokens(text)
        
        assert 90 <= estimate <= 110  # Should be around 100


class TestContextAggregator:
    """Test ContextAggregator class."""
    
    def test_aggregator_creation(self):
        """Test creating a ContextAggregator."""
        from services.prompt_enhancer import ContextAggregator
        
        aggregator = ContextAggregator()
        assert aggregator is not None
    
    @pytest.mark.asyncio
    async def test_gather_context_basic(self):
        """Test basic context gathering."""
        from services.prompt_enhancer import ContextAggregator
        
        aggregator = ContextAggregator()
        
        context = await aggregator.gather_context(
            query="test query",
            include_git=False,
            include_tests=False
        )
        
        assert context is not None
    
    def test_singleton_accessor(self):
        """Test get_context_aggregator singleton."""
        from services.prompt_enhancer import get_context_aggregator
        import services.prompt_enhancer as pe_module
        
        pe_module._aggregator = None
        
        a1 = get_context_aggregator()
        a2 = get_context_aggregator()
        
        assert a1 is a2

