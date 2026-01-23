"""
Tests for Phase 1 improvements:
- Configuration validation
- Simplified execution strategy
- Event bus
"""

import pytest
import asyncio
from pathlib import Path


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_config_validator_imports(self):
        """Test that config validator can be imported."""
        from services.config.validator import ConfigValidator, ValidationResult
        assert ConfigValidator is not None
        assert ValidationResult is not None
    
    def test_validation_result_structure(self):
        """Test ValidationResult dataclass."""
        from services.config.validator import ValidationResult
        
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=["Test warning"],
            info=["Test info"]
        )
        
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert len(result.info) == 1


class TestExecutionStrategy:
    """Test simplified execution strategy."""
    
    def test_execution_strategy_enum(self):
        """Test ExecutionStrategy enum."""
        from services.core.execution_strategy import ExecutionStrategy
        
        assert ExecutionStrategy.LOCAL_ONLY.value == "local"
        assert ExecutionStrategy.HYBRID_AUTO.value == "auto"
        assert ExecutionStrategy.CLOUD_PREFERRED.value == "cloud"
    
    def test_execution_resolver_local_only(self):
        """Test LOCAL_ONLY strategy."""
        from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver
        
        resolver = ExecutionResolver(ExecutionStrategy.LOCAL_ONLY)
        
        # Should never use cloud in LOCAL_ONLY mode
        assert resolver.should_use_cloud_llm() is False
        assert resolver.should_use_remote_agent("ReasoningAgent") is False
        assert resolver.should_use_remote_agent("IndexAgent") is False
    
    def test_execution_decision(self):
        """Test execution decision structure."""
        from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver
        
        resolver = ExecutionResolver(ExecutionStrategy.LOCAL_ONLY)
        decision = resolver.get_decision("ReasoningAgent", requires_filesystem=False)
        
        assert hasattr(decision, 'use_cloud_llm')
        assert hasattr(decision, 'use_remote_agent')
        assert hasattr(decision, 'reason')
        assert isinstance(decision.reason, str)
    
    def test_filesystem_requirement_override(self):
        """Test that filesystem requirement forces local execution."""
        from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver
        
        # Even with CLOUD_PREFERRED, filesystem requirement forces local
        resolver = ExecutionResolver(ExecutionStrategy.CLOUD_PREFERRED)
        decision = resolver.get_decision("SomeAgent", requires_filesystem=True)
        
        assert decision.use_cloud_llm is False
        assert decision.use_remote_agent is False
        assert "filesystem" in decision.reason.lower()
    
    def test_reasoning_agents_list(self):
        """Test that reasoning agents are correctly identified."""
        from services.core.execution_strategy import ExecutionResolver
        
        assert "ReasoningAgent" in ExecutionResolver.REASONING_AGENTS
        assert "DocAgent" in ExecutionResolver.REASONING_AGENTS
        assert "RefactorAgent" in ExecutionResolver.REASONING_AGENTS
        assert "CritiqueAgent" in ExecutionResolver.REASONING_AGENTS
    
    def test_get_status(self):
        """Test status reporting."""
        from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver
        
        resolver = ExecutionResolver(ExecutionStrategy.HYBRID_AUTO)
        status = resolver.get_status()
        
        assert "strategy" in status
        assert "online" in status
        assert "has_cloud_keys" in status
        assert "will_use_cloud_llm" in status
        assert "reasoning_agents" in status


class TestEventBus:
    """Test event bus functionality."""
    
    def test_event_bus_imports(self):
        """Test that event bus can be imported."""
        from services.core.event_bus import EventBus, Event, EventType, get_event_bus
        assert EventBus is not None
        assert Event is not None
        assert EventType is not None
        assert get_event_bus is not None
    
    def test_event_types(self):
        """Test event type enum."""
        from services.core.event_bus import EventType
        
        assert EventType.INDEX_STARTED.value == "index.started"
        assert EventType.INDEX_UPDATED.value == "index.updated"
        assert EventType.QUERY_COMPLETED.value == "query.completed"
        assert EventType.LLM_REQUEST.value == "llm.request"
        assert EventType.AGENT_STARTED.value == "agent.started"
    
    @pytest.mark.asyncio
    async def test_event_publish_subscribe(self):
        """Test basic publish/subscribe."""
        from services.core.event_bus import EventBus, Event, EventType
        
        bus = EventBus()
        received_events = []
        
        async def handler(event: Event):
            received_events.append(event)
        
        # Subscribe
        bus.subscribe(EventType.INDEX_UPDATED, handler)
        
        # Publish
        event = Event(
            type=EventType.INDEX_UPDATED,
            payload={"test": "data"},
            source="test"
        )
        await bus.publish(event)
        
        # Wait a bit for async execution
        await asyncio.sleep(0.1)
        
        # Verify
        assert len(received_events) == 1
        assert received_events[0].type == EventType.INDEX_UPDATED
        assert received_events[0].payload["test"] == "data"
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers to same event."""
        from services.core.event_bus import EventBus, Event, EventType
        
        bus = EventBus()
        handler1_called = []
        handler2_called = []
        
        async def handler1(event: Event):
            handler1_called.append(True)
        
        async def handler2(event: Event):
            handler2_called.append(True)
        
        # Subscribe both handlers
        bus.subscribe(EventType.QUERY_COMPLETED, handler1)
        bus.subscribe(EventType.QUERY_COMPLETED, handler2)
        
        # Publish
        event = Event(
            type=EventType.QUERY_COMPLETED,
            payload={},
            source="test"
        )
        await bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        # Both should be called
        assert len(handler1_called) == 1
        assert len(handler2_called) == 1
    
    def test_event_to_dict(self):
        """Test event serialization."""
        from services.core.event_bus import Event, EventType
        from datetime import datetime
        
        event = Event(
            type=EventType.LLM_RESPONSE,
            payload={"tokens": 100},
            source="llm_service",
            trace_id="trace-123"
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["type"] == "llm.response"
        assert event_dict["payload"]["tokens"] == 100
        assert event_dict["source"] == "llm_service"
        assert event_dict["trace_id"] == "trace-123"
        assert "timestamp" in event_dict
    
    def test_get_stats(self):
        """Test event bus statistics."""
        from services.core.event_bus import EventBus, EventType
        
        bus = EventBus()
        
        async def dummy_handler(event):
            pass
        
        bus.subscribe(EventType.INDEX_UPDATED, dummy_handler)
        bus.subscribe(EventType.QUERY_COMPLETED, dummy_handler)
        
        stats = bus.get_stats()
        
        assert "total_event_types" in stats
        assert "total_subscribers" in stats
        assert stats["total_subscribers"] >= 2

