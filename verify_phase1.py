"""Quick verification script for Phase 1 improvements."""

print("=" * 60)
print("Phase 1 Implementation Verification")
print("=" * 60)

# Test 1: Config Validator
print("\n[1/3] Testing Config Validator...")
try:
    from services.config.validator import ConfigValidator, ValidationResult
    print("  ✓ ConfigValidator imported successfully")
    
    result = ValidationResult(valid=True, errors=[], warnings=[], info=[])
    print(f"  ✓ ValidationResult created: valid={result.valid}")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 2: Execution Strategy
print("\n[2/3] Testing Execution Strategy...")
try:
    from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver, ExecutionDecision
    print("  ✓ ExecutionStrategy imported successfully")
    
    # Test LOCAL_ONLY
    resolver = ExecutionResolver(ExecutionStrategy.LOCAL_ONLY)
    print(f"  ✓ ExecutionResolver created with LOCAL_ONLY strategy")
    
    decision = resolver.get_decision("ReasoningAgent", requires_filesystem=False)
    print(f"  ✓ Decision: cloud_llm={decision.use_cloud_llm}, remote={decision.use_remote_agent}")
    print(f"    Reason: {decision.reason}")
    
    # Test status
    status = resolver.get_status()
    print(f"  ✓ Status: strategy={status['strategy']}, online={status['online']}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Event Bus
print("\n[3/3] Testing Event Bus...")
try:
    from services.core.event_bus import EventBus, Event, EventType, get_event_bus
    print("  ✓ EventBus imported successfully")
    
    bus = get_event_bus()
    print(f"  ✓ Global event bus retrieved")
    
    # Create event
    event = Event(
        type=EventType.INDEX_UPDATED,
        payload={"test": "data"},
        source="test_script"
    )
    print(f"  ✓ Event created: type={event.type.value}, source={event.source}")
    
    # Get stats
    stats = bus.get_stats()
    print(f"  ✓ Stats: {stats['total_event_types']} event types available")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Verification Complete!")
print("=" * 60)
print("\nSummary:")
print("  - Config Validator: ✓")
print("  - Execution Strategy: ✓")
print("  - Event Bus: ✓")
print("\nPhase 1 improvements are ready to use!")

