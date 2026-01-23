"""
Agent Reliability Components - Phase 4

Provides output validation, circuit breakers, and confidence scoring
for agent reliability and error handling.

Components:
- OutputValidator: Schema-based validation for agent outputs
- CircuitBreaker: Prevents cascading failures
- ConfidenceScorer: Scores agent output reliability
"""

import time
import logging
import hashlib
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# Output Validation
# =============================================================================

class AgentOutputSchema(BaseModel):
    """Base schema for agent outputs."""
    type: str = Field(..., description="Type of output (analysis, review, etc.)")
    content: Any = Field(..., description="Main content of the output")
    provenance: str = Field(..., description="Agent that produced this output")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AnalysisOutputSchema(AgentOutputSchema):
    """Schema for analysis outputs from ReasoningAgent."""
    type: str = "analysis"
    content: str = Field(..., min_length=10, description="Analysis text")
    backend: Optional[str] = Field(None, description="LLM backend used")
    offline_mode: Optional[bool] = Field(None, description="Whether offline mode was used")


class ReviewOutputSchema(AgentOutputSchema):
    """Schema for review outputs from CritiqueAgent/ReviewAgent."""
    type: str = "review"
    content: Optional[str] = Field(None, description="Review summary (optional)")
    items_reviewed: int = Field(..., ge=0, description="Number of items reviewed")
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="Review findings")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed results")


class DocumentationOutputSchema(AgentOutputSchema):
    """Schema for documentation outputs from DocAgent."""
    type: str = "documentation"
    content: str = Field(..., min_length=10, description="Documentation text")
    doc_style: Optional[str] = Field(None, description="Documentation style (google, numpy, etc.)")


class RefactoringOutputSchema(AgentOutputSchema):
    """Schema for refactoring outputs from RefactorAgent."""
    type: str = "refactoring_plan"
    refactor_type: str = Field(..., description="Type of refactoring")
    target: str = Field(..., description="Refactoring target")
    files_analyzed: int = Field(..., ge=0, description="Number of files analyzed")
    result: Dict[str, Any] = Field(..., description="Refactoring result")


@dataclass
class ValidationResult:
    """Result of output validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_used: Optional[str] = None


class OutputValidator:
    """
    Validates agent outputs against expected schemas.
    
    Provides schema-based validation with retry logic for malformed outputs.
    """
    
    def __init__(self):
        self.schemas: Dict[str, type[BaseModel]] = {
            "analysis": AnalysisOutputSchema,
            "review": ReviewOutputSchema,
            "documentation": DocumentationOutputSchema,
            "refactoring_plan": RefactoringOutputSchema,
        }
        self.validation_stats: Dict[str, int] = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
        }
    
    def validate(self, output: Dict[str, Any], expected_type: Optional[str] = None) -> ValidationResult:
        """
        Validate agent output against schema.
        
        Args:
            output: Agent output dictionary
            expected_type: Expected output type (optional, will use output['type'] if not provided)
        
        Returns:
            ValidationResult with validation status and errors
        """
        self.validation_stats["total"] += 1
        
        # Determine output type
        output_type = expected_type or output.get("type")
        if not output_type:
            self.validation_stats["invalid"] += 1
            return ValidationResult(
                valid=False,
                errors=["Output missing 'type' field"],
                schema_used=None
            )
        
        # Get schema
        schema = self.schemas.get(output_type)
        if not schema:
            # No schema defined - use basic validation
            logger.warning(f"No schema defined for output type: {output_type}")
            return self._basic_validation(output, output_type)
        
        # Validate against schema
        try:
            schema(**output)
            self.validation_stats["valid"] += 1
            return ValidationResult(
                valid=True,
                schema_used=output_type
            )
        except ValidationError as e:
            self.validation_stats["invalid"] += 1
            errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            return ValidationResult(
                valid=False,
                errors=errors,
                schema_used=output_type
            )
    
    def _basic_validation(self, output: Dict[str, Any], output_type: str) -> ValidationResult:
        """Basic validation for outputs without schemas."""
        errors = []
        warnings = []
        
        # Check required fields
        if "provenance" not in output:
            errors.append("Missing 'provenance' field")
        
        if "content" not in output and "result" not in output:
            warnings.append("Output has neither 'content' nor 'result' field")
        
        valid = len(errors) == 0
        if valid:
            self.validation_stats["valid"] += 1
        else:
            self.validation_stats["invalid"] += 1
        
        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            schema_used=None
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = self.validation_stats["total"]
        if total == 0:
            return {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "success_rate": 0.0
            }

        return {
            **self.validation_stats,
            "success_rate": self.validation_stats["valid"] / total
        }


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 60.0  # Seconds before trying half-open
    window_size: int = 10  # Rolling window for failure tracking


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Usage:
        breaker = CircuitBreaker("reasoning_agent")

        if breaker.can_execute():
            try:
                result = await agent.invoke(bundle)
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.failure_history: List[float] = []

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.config.timeout:
                logger.info(f"Circuit breaker {self.name}: Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            return True

        return False

    def record_success(self):
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                logger.info(f"Circuit breaker {self.name}: Transitioning to CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.failure_history.clear()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.failure_history.append(self.last_failure_time)

        # Trim history to window size
        if len(self.failure_history) > self.config.window_size:
            self.failure_history.pop(0)

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker {self.name}: Failure in HALF_OPEN, transitioning to OPEN")
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                logger.warning(f"Circuit breaker {self.name}: Threshold reached, transitioning to OPEN")
                self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker {self.name}: Manual reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.failure_history.clear()

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute()
        }


# =============================================================================
# Confidence Scoring
# =============================================================================

@dataclass
class ConfidenceScore:
    """Confidence score for agent output."""
    score: float  # 0.0 to 1.0
    factors: Dict[str, float] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)


class ConfidenceScorer:
    """
    Scores agent outputs for reliability and confidence.

    Factors considered:
    - Output validation (schema compliance)
    - Output completeness (has required fields)
    - Backend quality (cloud vs local LLM)
    - Historical accuracy (if available)
    - Response time (faster may indicate cached/simple responses)

    Usage:
        scorer = ConfidenceScorer()
        score = scorer.score_output(output, validation_result, response_time=1.5)

        if score.score < 0.5:
            # Low confidence, may need retry or human review
            pass
    """

    def __init__(self):
        self.history: Dict[str, List[float]] = {}  # agent_name -> scores

    def score_output(
        self,
        output: Dict[str, Any],
        validation_result: ValidationResult,
        response_time: Optional[float] = None,
        backend: Optional[str] = None
    ) -> ConfidenceScore:
        """
        Score agent output for confidence.

        Args:
            output: Agent output dictionary
            validation_result: Result from OutputValidator
            response_time: Time taken to generate output (seconds)
            backend: LLM backend used (if applicable)

        Returns:
            ConfidenceScore with overall score and factor breakdown
        """
        factors = {}
        reasoning = []

        # Factor 1: Validation (40% weight)
        if validation_result.valid:
            factors["validation"] = 1.0
            reasoning.append("Output passed schema validation")
        else:
            factors["validation"] = 0.0
            reasoning.append(f"Output failed validation: {', '.join(validation_result.errors)}")

        # Factor 2: Completeness (20% weight)
        completeness = self._score_completeness(output)
        factors["completeness"] = completeness
        if completeness >= 0.8:
            reasoning.append("Output is complete with all expected fields")
        elif completeness >= 0.5:
            reasoning.append("Output is partially complete")
        else:
            reasoning.append("Output is missing important fields")

        # Factor 3: Backend Quality (20% weight)
        backend_score = self._score_backend(backend or output.get("backend"))
        factors["backend"] = backend_score
        if backend_score >= 0.8:
            reasoning.append("High-quality LLM backend used")
        elif backend_score >= 0.5:
            reasoning.append("Medium-quality LLM backend used")
        else:
            reasoning.append("Local/fallback LLM backend used")

        # Factor 4: Response Time (10% weight)
        if response_time is not None:
            time_score = self._score_response_time(response_time)
            factors["response_time"] = time_score
            if time_score >= 0.8:
                reasoning.append(f"Fast response time ({response_time:.2f}s)")
            elif time_score >= 0.5:
                reasoning.append(f"Normal response time ({response_time:.2f}s)")
            else:
                reasoning.append(f"Slow response time ({response_time:.2f}s)")
        else:
            factors["response_time"] = 0.5  # Neutral if not provided

        # Factor 5: Historical Performance (10% weight)
        agent_name = output.get("provenance", "unknown")
        historical_score = self._score_historical(agent_name)
        factors["historical"] = historical_score

        # Calculate weighted score
        weights = {
            "validation": 0.4,
            "completeness": 0.2,
            "backend": 0.2,
            "response_time": 0.1,
            "historical": 0.1
        }

        overall_score = sum(factors[k] * weights[k] for k in weights)

        # Record score for historical tracking
        if agent_name not in self.history:
            self.history[agent_name] = []
        self.history[agent_name].append(overall_score)

        # Keep only last 100 scores
        if len(self.history[agent_name]) > 100:
            self.history[agent_name].pop(0)

        return ConfidenceScore(
            score=overall_score,
            factors=factors,
            reasoning=reasoning
        )

    def _score_completeness(self, output: Dict[str, Any]) -> float:
        """Score output completeness."""
        required_fields = ["type", "provenance"]
        content_fields = ["content", "result", "findings"]

        score = 0.0

        # Check required fields (50%)
        for field in required_fields:
            if field in output and output[field]:
                score += 0.5 / len(required_fields)

        # Check content fields (50%)
        has_content = any(field in output and output[field] for field in content_fields)
        if has_content:
            score += 0.5

        return min(1.0, score)

    def _score_backend(self, backend: Optional[str]) -> float:
        """Score LLM backend quality."""
        if not backend:
            return 0.5  # Neutral if unknown

        backend_lower = backend.lower()

        # Cloud LLMs (high quality)
        if any(provider in backend_lower for provider in ["gpt-4", "claude", "gemini"]):
            return 1.0

        # Cloud LLMs (medium quality)
        if any(provider in backend_lower for provider in ["gpt-3.5", "openai"]):
            return 0.8

        # Local LLMs (variable quality)
        if any(provider in backend_lower for provider in ["ollama", "lm studio", "local"]):
            return 0.5

        return 0.5  # Default neutral

    def _score_response_time(self, response_time: float) -> float:
        """Score response time (faster is better, but not too fast)."""
        # Optimal range: 0.5s - 5s
        # Too fast (<0.5s) might be cached/trivial
        # Too slow (>10s) might indicate issues

        if response_time < 0.5:
            return 0.7  # Possibly cached/trivial
        elif response_time <= 5.0:
            return 1.0  # Optimal
        elif response_time <= 10.0:
            return 0.8  # Acceptable
        elif response_time <= 30.0:
            return 0.5  # Slow
        else:
            return 0.3  # Very slow

    def _score_historical(self, agent_name: str) -> float:
        """Score based on historical performance."""
        if agent_name not in self.history or not self.history[agent_name]:
            return 0.5  # Neutral for new agents

        # Average of recent scores
        recent_scores = self.history[agent_name][-10:]  # Last 10
        return sum(recent_scores) / len(recent_scores)

    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get statistics for a specific agent."""
        if agent_name not in self.history or not self.history[agent_name]:
            return {
                "agent_name": agent_name,
                "total_outputs": 0,
                "average_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0
            }

        scores = self.history[agent_name]
        return {
            "agent_name": agent_name,
            "total_outputs": len(scores),
            "average_confidence": sum(scores) / len(scores),
            "min_confidence": min(scores),
            "max_confidence": max(scores)
        }


# =============================================================================
# Reliability Manager
# =============================================================================

class ReliabilityManager:
    """
    Unified manager for agent reliability components.

    Combines validation, circuit breaking, and confidence scoring
    into a single interface for easy integration.

    Usage:
        manager = ReliabilityManager()

        # Before agent invocation
        if not manager.can_invoke("reasoning"):
            # Circuit breaker is open
            raise Exception("Agent unavailable")

        # After agent invocation
        result = manager.process_output(
            agent_name="reasoning",
            output=output,
            response_time=1.5
        )

        if not result.valid:
            # Handle validation failure
            pass

        if result.confidence.score < 0.5:
            # Low confidence, may need retry
            pass
    """

    def __init__(self):
        self.validator = OutputValidator()
        self.scorer = ConfidenceScorer()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, agent_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for agent."""
        if agent_name not in self.circuit_breakers:
            self.circuit_breakers[agent_name] = CircuitBreaker(agent_name)
        return self.circuit_breakers[agent_name]

    def can_invoke(self, agent_name: str) -> bool:
        """Check if agent can be invoked (circuit breaker check)."""
        breaker = self.get_circuit_breaker(agent_name)
        return breaker.can_execute()

    def process_output(
        self,
        agent_name: str,
        output: Dict[str, Any],
        response_time: Optional[float] = None,
        expected_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process agent output through validation and scoring.

        Returns:
            Dictionary with validation result, confidence score, and recommendations
        """
        breaker = self.get_circuit_breaker(agent_name)

        # Validate output
        validation = self.validator.validate(output, expected_type)

        # Score confidence
        confidence = self.scorer.score_output(
            output,
            validation,
            response_time,
            output.get("backend")
        )

        # Update circuit breaker
        if validation.valid and confidence.score >= 0.5:
            breaker.record_success()
        else:
            breaker.record_failure()

        return {
            "valid": validation.valid,
            "validation": validation,
            "confidence": confidence,
            "circuit_breaker_state": breaker.state.value,
            "should_retry": not validation.valid and breaker.can_execute(),
            "recommendations": self._generate_recommendations(validation, confidence, breaker)
        }

    def _generate_recommendations(
        self,
        validation: ValidationResult,
        confidence: ConfidenceScore,
        breaker: CircuitBreaker
    ) -> List[str]:
        """Generate recommendations based on validation and confidence."""
        recommendations = []

        if not validation.valid:
            recommendations.append("Output failed validation - consider retry with corrected prompt")

        if confidence.score < 0.3:
            recommendations.append("Very low confidence - manual review recommended")
        elif confidence.score < 0.5:
            recommendations.append("Low confidence - consider retry or fallback")

        if breaker.state == CircuitState.OPEN:
            recommendations.append("Circuit breaker open - agent may be experiencing issues")
        elif breaker.state == CircuitState.HALF_OPEN:
            recommendations.append("Circuit breaker testing recovery - monitor closely")

        if confidence.factors.get("backend", 1.0) < 0.6:
            recommendations.append("Consider using cloud LLM for better quality")

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """Get overall reliability statistics."""
        return {
            "validation": self.validator.get_stats(),
            "circuit_breakers": {
                name: breaker.get_status()
                for name, breaker in self.circuit_breakers.items()
            },
            "agent_confidence": {
                agent: self.scorer.get_agent_stats(agent)
                for agent in self.scorer.history.keys()
            }
        }

