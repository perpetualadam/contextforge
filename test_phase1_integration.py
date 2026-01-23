"""
Quick test script to verify Phase 1 integration.
"""

def test_execution_resolver_integration():
    """Test that ExecutionResolver is integrated into orchestrators."""
    print("\n[1/3] Testing ExecutionResolver integration...")
    
    try:
        from services.core import ProductionOrchestrator, EnhancedOrchestrator
        from services.core.execution_strategy import ExecutionResolver
        
        # Test ProductionOrchestrator
        orch = ProductionOrchestrator(mode="auto")
        assert hasattr(orch, 'execution_resolver'), "ProductionOrchestrator missing execution_resolver"
        assert isinstance(orch.execution_resolver, ExecutionResolver), "execution_resolver is not ExecutionResolver instance"
        print("  ✓ ProductionOrchestrator has ExecutionResolver")
        
        # Test EnhancedOrchestrator
        enh_orch = EnhancedOrchestrator(mode="auto")
        assert hasattr(enh_orch, 'execution_resolver'), "EnhancedOrchestrator missing execution_resolver"
        assert isinstance(enh_orch.execution_resolver, ExecutionResolver), "execution_resolver is not ExecutionResolver instance"
        assert hasattr(enh_orch.coordinator, '_execution_resolver'), "CoordinatorAgent missing _execution_resolver"
        print("  ✓ EnhancedOrchestrator has ExecutionResolver")
        print("  ✓ CoordinatorAgent receives ExecutionResolver")
        
        return True
    except Exception as e:
        print(f"  ✗ ExecutionResolver integration failed: {e}")
        return False


def test_event_bus_integration():
    """Test that Event Bus is available."""
    print("\n[2/3] Testing Event Bus integration...")
    
    try:
        from services.core.event_bus import get_event_bus, Event, EventType
        
        event_bus = get_event_bus()
        assert event_bus is not None, "Event bus is None"
        print("  ✓ Event bus initialized")
        
        # Test event types
        assert hasattr(EventType, 'INDEX_STARTED'), "Missing INDEX_STARTED event type"
        assert hasattr(EventType, 'QUERY_COMPLETED'), "Missing QUERY_COMPLETED event type"
        assert hasattr(EventType, 'AGENT_STARTED'), "Missing AGENT_STARTED event type"
        print("  ✓ Event types available")
        
        return True
    except Exception as e:
        print(f"  ✗ Event Bus integration failed: {e}")
        return False


def test_api_gateway_integration():
    """Test that API Gateway has event bus."""
    print("\n[3/3] Testing API Gateway integration...")
    
    try:
        # Just check if the file imports correctly
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent / "services" / "api_gateway"))
        
        # We can't fully import app.py because it starts FastAPI
        # Just check the file exists and has the right imports
        app_path = Path(__file__).parent / "services" / "api_gateway" / "app.py"
        assert app_path.exists(), "API Gateway app.py not found"
        
        content = app_path.read_text()
        assert "from services.core.event_bus import get_event_bus" in content, "Missing event bus import"
        assert "event_bus = get_event_bus()" in content, "Missing event bus initialization"
        assert "EventType.SERVICE_STARTED" in content, "Missing SERVICE_STARTED event"
        assert "EventType.INDEX_STARTED" in content, "Missing INDEX_STARTED event"
        assert "EventType.QUERY_RECEIVED" in content, "Missing QUERY_RECEIVED event"
        print("  ✓ API Gateway has event bus imports")
        print("  ✓ API Gateway publishes events")
        
        return True
    except Exception as e:
        print(f"  ✗ API Gateway integration failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Phase 1 Integration Tests")
    print("=" * 60)
    
    results = []
    results.append(test_execution_resolver_integration())
    results.append(test_event_bus_integration())
    results.append(test_api_gateway_integration())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All integration tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some integration tests failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit(main())

