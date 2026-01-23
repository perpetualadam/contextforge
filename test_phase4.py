"""
Phase 4 Test Suite: Agent Reliability

Tests for output validation, circuit breakers, and confidence scoring.
"""

import sys
import time
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent))

from services.core.agent_reliability import (
    OutputValidator,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    ConfidenceScorer,
    ReliabilityManager,
    ValidationResult,
    ConfidenceScore
)


def test_output_validator():
    """Test OutputValidator with various agent outputs."""
    print("\n=== Testing OutputValidator ===")
    
    validator = OutputValidator()
    
    # Test 1: Valid analysis output
    analysis_output = {
        "type": "analysis",
        "content": "This is a detailed analysis of the code structure.",
        "provenance": "reasoning",
        "backend": "gpt-4",
        "offline_mode": False
    }
    
    result = validator.validate(analysis_output)
    assert result.valid, f"Analysis output should be valid, got errors: {result.errors}"
    assert result.schema_used == "analysis"
    print("✓ Valid analysis output passed validation")
    
    # Test 2: Valid review output
    review_output = {
        "type": "review",
        "items_reviewed": 5,
        "findings": [{"issue": "Missing docstring", "severity": "low"}],
        "provenance": "critique"
    }
    
    result = validator.validate(review_output)
    assert result.valid, f"Review output should be valid, got errors: {result.errors}"
    assert result.schema_used == "review"
    print("✓ Valid review output passed validation")
    
    # Test 3: Invalid output (missing required field)
    invalid_output = {
        "type": "analysis",
        # Missing 'content' field
        "provenance": "reasoning"
    }
    
    result = validator.validate(invalid_output)
    assert not result.valid, "Invalid output should fail validation"
    assert len(result.errors) > 0
    print(f"✓ Invalid output correctly rejected: {result.errors[0]}")
    
    # Test 4: Output without schema (basic validation)
    custom_output = {
        "type": "custom_type",
        "content": "Some custom content",
        "provenance": "custom_agent"
    }
    
    result = validator.validate(custom_output)
    assert result.valid, "Custom output with basic fields should pass basic validation"
    print("✓ Custom output passed basic validation")
    
    # Test 5: Validation stats
    stats = validator.get_stats()
    assert stats["total"] == 4
    assert stats["valid"] == 3
    assert stats["invalid"] == 1
    assert stats["success_rate"] == 0.75
    print(f"✓ Validation stats: {stats['valid']}/{stats['total']} valid (success rate: {stats['success_rate']:.0%})")
    
    print("✅ OutputValidator tests passed!")
    return True


def test_circuit_breaker():
    """Test CircuitBreaker state transitions."""
    print("\n=== Testing CircuitBreaker ===")
    
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=1.0  # 1 second for testing
    )
    
    breaker = CircuitBreaker("test_agent", config)
    
    # Test 1: Initial state is CLOSED
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute()
    print("✓ Initial state: CLOSED, can execute")
    
    # Test 2: Record failures until threshold
    for i in range(3):
        breaker.record_failure()
    
    assert breaker.state == CircuitState.OPEN
    assert not breaker.can_execute()
    print("✓ After 3 failures: OPEN, cannot execute")
    
    # Test 3: Wait for timeout and transition to HALF_OPEN
    time.sleep(1.1)  # Wait for timeout
    assert breaker.can_execute()  # This should transition to HALF_OPEN
    assert breaker.state == CircuitState.HALF_OPEN
    print("✓ After timeout: HALF_OPEN, can execute (testing)")
    
    # Test 4: Failure in HALF_OPEN returns to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert not breaker.can_execute()
    print("✓ Failure in HALF_OPEN: back to OPEN")
    
    # Test 5: Success in HALF_OPEN closes circuit
    time.sleep(1.1)  # Wait for timeout again
    breaker.can_execute()  # Transition to HALF_OPEN
    breaker.record_success()
    breaker.record_success()  # Need 2 successes
    assert breaker.state == CircuitState.CLOSED
    print("✓ 2 successes in HALF_OPEN: CLOSED")
    
    # Test 6: Manual reset
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    print("✓ Manual reset: CLOSED, failure count reset")
    
    print("✅ CircuitBreaker tests passed!")
    return True


def test_confidence_scorer():
    """Test ConfidenceScorer with various outputs."""
    print("\n=== Testing ConfidenceScorer ===")
    
    scorer = ConfidenceScorer()
    
    # Test 1: High-quality output (valid, complete, cloud LLM, fast)
    output1 = {
        "type": "analysis",
        "content": "Detailed analysis...",
        "provenance": "reasoning",
        "backend": "gpt-4"
    }
    
    validation1 = ValidationResult(valid=True, schema_used="analysis")
    score1 = scorer.score_output(output1, validation1, response_time=2.0, backend="gpt-4")
    
    assert score1.score >= 0.8, f"High-quality output should have high confidence, got {score1.score}"
    assert score1.factors["validation"] == 1.0
    assert score1.factors["backend"] >= 0.8
    print(f"✓ High-quality output: confidence={score1.score:.2f}")
    print(f"  Factors: {score1.factors}")
    
    # Test 2: Low-quality output (invalid, incomplete, local LLM, slow)
    output2 = {
        "type": "analysis",
        # Missing content
        "provenance": "reasoning",
        "backend": "ollama"
    }
    
    validation2 = ValidationResult(valid=False, errors=["Missing content"])
    score2 = scorer.score_output(output2, validation2, response_time=15.0, backend="ollama")
    
    assert score2.score <= 0.5, f"Low-quality output should have low confidence, got {score2.score}"
    assert score2.factors["validation"] == 0.0
    print(f"✓ Low-quality output: confidence={score2.score:.2f}")
    print(f"  Factors: {score2.factors}")
    
    # Test 3: Historical performance tracking
    stats = scorer.get_agent_stats("reasoning")
    assert stats["total_outputs"] == 2
    assert stats["average_confidence"] > 0
    print(f"✓ Agent stats: {stats['total_outputs']} outputs, avg confidence={stats['average_confidence']:.2f}")
    
    print("✅ ConfidenceScorer tests passed!")
    return True


def test_reliability_manager():
    """Test ReliabilityManager integration."""
    print("\n=== Testing ReliabilityManager ===")

    manager = ReliabilityManager()

    # Test 1: Check circuit breaker before invocation
    assert manager.can_invoke("test_agent"), "Should be able to invoke initially"
    print("✓ Can invoke agent initially")

    # Test 2: Process valid output
    valid_output = {
        "type": "analysis",
        "content": "Analysis result",
        "provenance": "test_agent",
        "backend": "gpt-4"
    }

    result = manager.process_output(
        agent_name="test_agent",
        output=valid_output,
        response_time=1.5
    )

    assert result["valid"], "Valid output should pass validation"
    assert result["confidence"].score > 0.5, "Valid output should have decent confidence"
    assert result["circuit_breaker_state"] == "closed"
    print(f"✓ Valid output processed: confidence={result['confidence'].score:.2f}")

    # Test 3: Process invalid outputs to trigger circuit breaker
    invalid_output = {
        "type": "analysis",
        # Missing content
        "provenance": "failing_agent"
    }

    for i in range(5):  # Trigger circuit breaker
        result = manager.process_output(
            agent_name="failing_agent",
            output=invalid_output,
            response_time=10.0
        )

    assert not manager.can_invoke("failing_agent"), "Circuit breaker should be open"
    print("✓ Circuit breaker opened after repeated failures")

    # Test 4: Recommendations
    assert len(result["recommendations"]) > 0, "Should have recommendations"
    print(f"✓ Recommendations: {result['recommendations']}")

    # Test 5: Get overall stats
    stats = manager.get_stats()
    assert "validation" in stats
    assert "circuit_breakers" in stats
    assert "agent_confidence" in stats
    assert "test_agent" in stats["circuit_breakers"]
    assert "failing_agent" in stats["circuit_breakers"]
    print(f"✓ Stats collected for {len(stats['circuit_breakers'])} agents")

    print("✅ ReliabilityManager tests passed!")
    return True


def test_integration_with_coordinator():
    """Test Phase 4 integration with CoordinatorAgent."""
    print("\n=== Testing Integration with CoordinatorAgent ===")

    import asyncio
    from services.core import CoordinatorAgent, ContextBundle, AgentInterface, AgentCapabilities
    from services.core.agent_reliability import ReliabilityManager

    # Create a simple test agent
    class TestAgent(AgentInterface):
        def __init__(self, name="test", should_fail=False):
            super().__init__(name=name)
            self.should_fail = should_fail
            self.invocation_count = 0

        def capabilities(self) -> AgentCapabilities:
            return AgentCapabilities(
                consumes=["query"],
                produces=["analysis"]
            )

        async def invoke(self, bundle: ContextBundle) -> ContextBundle:
            self.invocation_count += 1

            if self.should_fail:
                # Return invalid output
                output = {
                    "type": "analysis",
                    # Missing required 'content' field
                    "provenance": self.name
                }
            else:
                # Return valid output
                output = {
                    "type": "analysis",
                    "content": f"Analysis from {self.name}",
                    "provenance": self.name,
                    "backend": "test"
                }

            return bundle.add_context(output, self.name)

    # Test 1: Successful agent invocation with reliability tracking
    async def test_successful_invocation():
        reliability_manager = ReliabilityManager()
        coordinator = CoordinatorAgent(reliability_manager=reliability_manager)

        test_agent = TestAgent("success_agent", should_fail=False)
        coordinator.register_agent(test_agent)

        bundle = ContextBundle()
        bundle = bundle.add_context({"type": "query", "text": "test query"}, "user")

        result = await coordinator.invoke_agent("success_agent", bundle)

        assert len(result.contexts) > 0, "Should have output contexts"
        assert "reliability" in result.metadata, "Should have reliability metadata"
        assert result.metadata["reliability"]["valid"], "Output should be valid"
        assert result.metadata["reliability"]["confidence_score"] > 0.5, "Should have decent confidence"

        print("✓ Successful invocation tracked reliability")
        return True

    # Test 2: Failed agent invocation with circuit breaker
    async def test_failed_invocation():
        reliability_manager = ReliabilityManager()
        coordinator = CoordinatorAgent(reliability_manager=reliability_manager)

        failing_agent = TestAgent("failing_agent", should_fail=True)
        coordinator.register_agent(failing_agent)

        # Invoke multiple times to trigger circuit breaker
        # Use different inputs to avoid loop detection
        for i in range(5):
            bundle = ContextBundle()
            bundle = bundle.add_context({"type": "query", "text": f"test query {i}"}, "user")
            result = await coordinator.invoke_agent("failing_agent", bundle)
            assert not result.metadata["reliability"]["valid"], "Output should be invalid"

        # Circuit breaker should now be open
        try:
            bundle = ContextBundle()
            bundle = bundle.add_context({"type": "query", "text": "final query"}, "user")
            await coordinator.invoke_agent("failing_agent", bundle)
            assert False, "Should have raised exception due to circuit breaker"
        except Exception as e:
            assert "Circuit breaker open" in str(e)
            print("✓ Circuit breaker prevented invocation after failures")

        return True

    # Run async tests
    asyncio.run(test_successful_invocation())
    asyncio.run(test_failed_invocation())

    print("✅ Integration tests passed!")
    return True


def main():
    """Run all Phase 4 tests."""
    print("=" * 60)
    print("Phase 4 Test Suite: Agent Reliability")
    print("Testing output validation, circuit breakers, confidence scoring")
    print("=" * 60)

    tests = [
        ("OutputValidator", test_output_validator),
        ("CircuitBreaker", test_circuit_breaker),
        ("ConfidenceScorer", test_confidence_scorer),
        ("ReliabilityManager", test_reliability_manager),
        ("Integration with CoordinatorAgent", test_integration_with_coordinator)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 All Phase 4 tests passed! Ready to commit.")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed. Please fix before committing.")
        return 1


if __name__ == "__main__":
    exit(main())

