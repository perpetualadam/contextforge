"""
Simplified execution strategy for ContextForge.

Reduces complexity from 9 combinations (3 modes × 3 hints) to 3 clear strategies.
"""

import logging
from enum import Enum
from typing import Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """
    Simplified execution strategy.
    
    Replaces the complex 3×3 matrix of (OperationMode × ExecutionHint)
    with 3 clear strategies.
    """
    LOCAL_ONLY = "local"      # All local, no network (offline mode)
    HYBRID_AUTO = "auto"       # Smart routing based on connectivity (default)
    CLOUD_PREFERRED = "cloud"  # Prefer cloud, fallback to local


@dataclass
class ExecutionDecision:
    """Result of execution strategy decision."""
    use_cloud_llm: bool
    use_remote_agent: bool
    reason: str


class ExecutionResolver:
    """
    Resolves execution decisions based on simplified strategy.
    
    This replaces the complex ProductionOrchestrator.resolve_execution_location()
    logic with a simpler, more predictable approach.
    """
    
    # Agents that benefit from cloud LLM (reasoning-heavy)
    REASONING_AGENTS: Set[str] = {
        "ReasoningAgent",
        "DocAgent", 
        "RefactorAgent",
        "CritiqueAgent"
    }
    
    def __init__(self, strategy: ExecutionStrategy):
        """
        Initialize resolver with execution strategy.
        
        Args:
            strategy: ExecutionStrategy to use
        """
        self.strategy = strategy
        self._is_online = self._check_connectivity()
        self._has_cloud_keys = self._check_cloud_keys()
    
    def _check_connectivity(self) -> bool:
        """Check if internet is available."""
        try:
            from services.core import check_internet
            return check_internet()
        except Exception as e:
            logger.warning(f"Connectivity check failed: {e}")
            return False
    
    def _check_cloud_keys(self) -> bool:
        """Check if any cloud API keys are configured."""
        try:
            from services.config import get_config
            config = get_config()
            return bool(
                config.llm.openai_api_key or
                config.llm.anthropic_api_key or
                config.llm.gemini_api_key or
                config.llm.deepseek_api_key
            )
        except Exception as e:
            logger.warning(f"Cloud key check failed: {e}")
            return False
    
    def should_use_cloud_llm(self) -> bool:
        """
        Decide if cloud LLM should be used.
        
        Returns:
            True if cloud LLM should be used, False for local
        """
        if self.strategy == ExecutionStrategy.LOCAL_ONLY:
            return False
        
        if self.strategy == ExecutionStrategy.CLOUD_PREFERRED:
            return self._is_online and self._has_cloud_keys
        
        # HYBRID_AUTO: Use cloud if available, otherwise local
        return self._is_online and self._has_cloud_keys
    
    def should_use_remote_agent(self, agent_name: str) -> bool:
        """
        Decide if agent should run remotely.
        
        Only reasoning-heavy agents benefit from remote execution.
        Filesystem-dependent agents always run locally.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            True if agent should run remotely, False for local
        """
        if self.strategy == ExecutionStrategy.LOCAL_ONLY:
            return False
        
        # Only reasoning agents benefit from remote execution
        if agent_name not in self.REASONING_AGENTS:
            return False
        
        # Use remote if cloud LLM is available
        return self.should_use_cloud_llm()
    
    def get_decision(self, agent_name: str, requires_filesystem: bool = False) -> ExecutionDecision:
        """
        Get execution decision for an agent.
        
        Args:
            agent_name: Name of the agent
            requires_filesystem: Whether agent needs filesystem access
            
        Returns:
            ExecutionDecision with reasoning
        """
        # Filesystem requirement overrides everything
        if requires_filesystem:
            return ExecutionDecision(
                use_cloud_llm=False,
                use_remote_agent=False,
                reason="Agent requires filesystem access (must run locally)"
            )
        
        use_cloud = self.should_use_cloud_llm()
        use_remote = self.should_use_remote_agent(agent_name)
        
        # Build reason
        if self.strategy == ExecutionStrategy.LOCAL_ONLY:
            reason = "LOCAL_ONLY strategy (offline mode)"
        elif self.strategy == ExecutionStrategy.CLOUD_PREFERRED:
            if use_cloud:
                reason = "CLOUD_PREFERRED strategy with connectivity"
            else:
                reason = "CLOUD_PREFERRED strategy but offline/no keys (fallback to local)"
        else:  # HYBRID_AUTO
            if use_cloud:
                reason = "HYBRID_AUTO with cloud available"
            else:
                reason = "HYBRID_AUTO but offline/no keys (using local)"
        
        if use_remote and agent_name in self.REASONING_AGENTS:
            reason += f" + {agent_name} is reasoning-heavy (remote execution)"
        
        return ExecutionDecision(
            use_cloud_llm=use_cloud,
            use_remote_agent=use_remote,
            reason=reason
        )
    
    def get_status(self) -> dict:
        """Get current execution strategy status."""
        return {
            "strategy": self.strategy.value,
            "online": self._is_online,
            "has_cloud_keys": self._has_cloud_keys,
            "will_use_cloud_llm": self.should_use_cloud_llm(),
            "reasoning_agents": list(self.REASONING_AGENTS)
        }

