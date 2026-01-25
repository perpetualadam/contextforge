"""
Tests for Advanced Metrics Service.
"""

import pytest
from datetime import datetime
import sys
import os

# Add the services directory to path for importing
services_path = os.path.join(os.path.dirname(__file__), '..', 'services')
if services_path not in sys.path:
    sys.path.insert(0, services_path)

from metrics.retrieval_accuracy import (
    RetrievalAccuracyTracker, RetrievalResult, get_retrieval_tracker
)
from metrics.test_correlation import CorrelationTracker, ExecutionResult, CodeChange
from metrics.llm_efficiency import LLMEfficiencyTracker, LLMRequest


class TestRetrievalAccuracy:
    """Test retrieval accuracy metrics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = RetrievalAccuracyTracker()
        self.tracker._evaluations.clear()

    def test_evaluate_retrieval(self):
        """Test evaluating retrieval quality."""
        retrieved = [
            RetrievalResult(chunk_id="doc-1", content="content 1", score=0.9),
            RetrievalResult(chunk_id="doc-2", content="content 2", score=0.8),
            RetrievalResult(chunk_id="doc-3", content="content 3", score=0.7),
        ]

        evaluation = self.tracker.evaluate(
            query="test query",
            retrieved=retrieved,
            relevant_ids=["doc-1", "doc-3"]
        )

        assert evaluation.precision is not None
        assert evaluation.recall is not None
        assert evaluation.f1_score is not None

    def test_precision_calculation(self):
        """Test precision calculation."""
        retrieved = [
            RetrievalResult(chunk_id="doc-1", content="c1", score=0.9),
            RetrievalResult(chunk_id="doc-2", content="c2", score=0.8),
            RetrievalResult(chunk_id="doc-3", content="c3", score=0.7),
            RetrievalResult(chunk_id="doc-4", content="c4", score=0.6),
        ]

        evaluation = self.tracker.evaluate(
            query="test",
            retrieved=retrieved,
            relevant_ids=["doc-1", "doc-3"]  # 2 out of 4 are relevant
        )

        # Precision = 2/4 = 0.5
        assert evaluation.precision == pytest.approx(0.5, rel=0.01)

    def test_recall_calculation(self):
        """Test recall calculation."""
        retrieved = [
            RetrievalResult(chunk_id="doc-1", content="c1", score=0.9),
            RetrievalResult(chunk_id="doc-2", content="c2", score=0.8),
        ]

        evaluation = self.tracker.evaluate(
            query="test",
            retrieved=retrieved,
            relevant_ids=["doc-1", "doc-3", "doc-4"]  # 1 out of 3 relevant retrieved
        )

        # Recall = 1/3 ≈ 0.333
        assert evaluation.recall == pytest.approx(0.333, rel=0.01)

    def test_get_aggregate_metrics(self):
        """Test getting aggregate metrics."""
        retrieved = [
            RetrievalResult(chunk_id="doc-1", content="c1", score=0.9),
        ]

        self.tracker.evaluate(query="q1", retrieved=retrieved, relevant_ids=["doc-1"])
        self.tracker.evaluate(query="q2", retrieved=retrieved, relevant_ids=["doc-1"])

        metrics = self.tracker.get_aggregate_metrics()
        assert metrics["total_evaluations"] >= 2


class TestTestCorrelationTracker:
    """Test test correlation tracker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = CorrelationTracker()
        self.tracker._test_history.clear()
        self.tracker._correlations.clear()

    def test_record_test_result(self):
        """Test recording a test result."""
        result = ExecutionResult(
            test_name="test_auth_login",
            test_file="tests/test_auth.py",
            passed=True,
            duration_ms=150
        )

        self.tracker.record_test_result(result)

        # Check the history contains the result
        history = self.tracker._test_history.get("test_auth_login", [])
        assert len(history) >= 1
        assert history[-1].passed is True

    def test_correlate_change(self):
        """Test correlating a code change with test results."""
        change = CodeChange(
            file_path="src/auth.py",
            change_type="modified",
            lines_added=10,
            lines_removed=5
        )

        test_results = [
            ExecutionResult(test_name="test_auth_login", test_file="tests/test_auth.py", passed=True, duration_ms=100),
            ExecutionResult(test_name="test_auth_logout", test_file="tests/test_auth.py", passed=False, duration_ms=50),
        ]

        correlation = self.tracker.correlate_change(change, test_results)

        assert correlation.tests_passed == 1
        assert correlation.tests_failed == 1
        assert correlation.pass_rate == 0.5

    def test_flaky_test_detection(self):
        """Test flaky test detection."""
        # Record alternating pass/fail results
        for i in range(10):
            result = ExecutionResult(
                test_name="test_sometimes_fails",
                test_file="tests/test_flaky.py",
                passed=(i % 2 == 0),  # Alternating
                duration_ms=100
            )
            self.tracker.record_test_result(result)

        flaky_tests = self.tracker.get_flaky_tests(threshold=0.3)
        # Should detect the test as flaky (50% failure rate)
        assert len(flaky_tests) >= 1
        assert "test_sometimes_fails" in [t["test_name"] for t in flaky_tests]

    def test_get_correlations(self):
        """Test getting correlations."""
        change = CodeChange(file_path="src/auth.py", change_type="modified")
        test_results = [
            ExecutionResult(test_name="test_auth", test_file="tests/test_auth.py", passed=True, duration_ms=100),
        ]

        correlation = self.tracker.correlate_change(change, test_results)

        # Verify correlation was recorded
        assert len(self.tracker._correlations) >= 1


class TestLLMEfficiencyTracker:
    """Test LLM efficiency tracker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = LLMEfficiencyTracker()
        self.tracker._requests.clear()
        self.tracker._backend_stats.clear()

    def test_record_request(self):
        """Test recording an LLM request."""
        request = LLMRequest(
            backend="mock",
            model="mock-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200,
            success=True
        )

        self.tracker.record_request(request)

        metrics = self.tracker.get_metrics()
        assert metrics.total_requests >= 1

    def test_latency_tracking(self):
        """Test latency tracking."""
        # Record multiple requests with varying latencies
        latencies = [100, 150, 200, 250, 500, 150, 200, 180, 220, 300]
        for lat in latencies:
            request = LLMRequest(
                backend="mock",
                model="test",
                latency_ms=lat,
                success=True
            )
            self.tracker.record_request(request)

        metrics = self.tracker.get_metrics()
        assert metrics.avg_latency_ms is not None

    def test_token_usage_tracking(self):
        """Test token usage tracking."""
        request = LLMRequest(
            backend="mock",
            model="test",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200,
            success=True
        )

        self.tracker.record_request(request)

        metrics = self.tracker.get_metrics()
        assert metrics.total_prompt_tokens >= 100
        assert metrics.total_completion_tokens >= 50

    def test_backend_comparison(self):
        """Test backend comparison metrics."""
        req1 = LLMRequest(backend="ollama", model="llama", latency_ms=300, success=True)
        req2 = LLMRequest(backend="openai", model="gpt-4", latency_ms=500, success=True)

        self.tracker.record_request(req1)
        self.tracker.record_request(req2)

        comparison = self.tracker.get_backend_comparison()
        assert "ollama" in comparison
        assert "openai" in comparison

