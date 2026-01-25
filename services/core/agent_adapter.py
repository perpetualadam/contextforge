"""
Adapter to integrate MultiModeAgent with existing AgentInterface.

Provides backward compatibility while enabling new drift-safe architecture.

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Any, Dict, Optional

from .local_multi_mode_agent import LocalMultiModeAgent, AgentMode

logger = logging.getLogger(__name__)


class MultiModeAgentAdapter:
    """
    Adapter that wraps MultiModeAgent to work with existing agent infrastructure.
    
    Provides compatibility layer between old AgentInterface and new MultiModeAgent.
    """
    
    def __init__(
        self,
        name: str,
        workspace_root: Optional[str] = None,
    ):
        self.name = name
        self.multi_mode_agent = LocalMultiModeAgent(
            name=name,
            workspace_root=workspace_root,
        )
        
        # Map old agent names to modes
        self.mode_mapping = {
            "indexing": AgentMode.INDEX,
            "testing": AgentMode.TEST,
            "debugging": AgentMode.REVIEW,  # Debugging is a form of review
            "critique": AgentMode.REVIEW,
            "review": AgentMode.REVIEW,
            "reasoning": AgentMode.PLAN,
            "doc": AgentMode.IMPLEMENT,  # Doc generation is implementation
            "refactor": AgentMode.IMPLEMENT,
        }
    
    def get_mode_for_agent(self, agent_name: str) -> AgentMode:
        """Get appropriate mode for legacy agent name."""
        return self.mode_mapping.get(agent_name.lower(), AgentMode.PLAN)
    
    def execute(self, task: Dict[str, Any], agent_name: Optional[str] = None) -> Any:
        """
        Execute a task using appropriate mode.
        
        Args:
            task: Task payload
            agent_name: Optional legacy agent name to determine mode
        
        Returns:
            Operation result
        """
        # Determine mode
        if agent_name:
            mode = self.get_mode_for_agent(agent_name)
        else:
            mode = AgentMode.PLAN
        
        # Execute with multi-mode agent
        result = self.multi_mode_agent.execute(mode, task)
        
        return result
    
    def set_vector_service(self, vector_service: Any) -> None:
        """Set vector service reference."""
        self.multi_mode_agent.vector_service = vector_service
    
    def set_llm_client(self, llm_client: Any) -> None:
        """Set LLM client reference."""
        self.multi_mode_agent.llm_client = llm_client
    
    def set_preprocessor(self, preprocessor: Any) -> None:
        """Set preprocessor reference."""
        self.multi_mode_agent.preprocessor = preprocessor


# Factory functions for creating adapted agents

def create_indexing_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for IndexingAgent."""
    return MultiModeAgentAdapter("indexing", workspace_root)


def create_testing_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for TestingAgent."""
    return MultiModeAgentAdapter("testing", workspace_root)


def create_debugging_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for DebuggingAgent."""
    return MultiModeAgentAdapter("debugging", workspace_root)


def create_critique_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for CritiqueAgent."""
    return MultiModeAgentAdapter("critique", workspace_root)


def create_review_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for ReviewAgent."""
    return MultiModeAgentAdapter("review", workspace_root)


def create_reasoning_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for ReasoningAgent."""
    return MultiModeAgentAdapter("reasoning", workspace_root)


def create_doc_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for DocAgent."""
    return MultiModeAgentAdapter("doc", workspace_root)


def create_refactor_agent_adapter(workspace_root: Optional[str] = None) -> MultiModeAgentAdapter:
    """Create adapter for RefactorAgent."""
    return MultiModeAgentAdapter("refactor", workspace_root)


# Unified factory
def create_multi_mode_agent_for_role(
    role: str,
    workspace_root: Optional[str] = None,
) -> MultiModeAgentAdapter:
    """
    Create a multi-mode agent adapter for a specific role.
    
    Args:
        role: Agent role (indexing, testing, debugging, etc.)
        workspace_root: Workspace root directory
    
    Returns:
        MultiModeAgentAdapter configured for the role
    """
    factories = {
        "indexing": create_indexing_agent_adapter,
        "testing": create_testing_agent_adapter,
        "debugging": create_debugging_agent_adapter,
        "critique": create_critique_agent_adapter,
        "review": create_review_agent_adapter,
        "reasoning": create_reasoning_agent_adapter,
        "doc": create_doc_agent_adapter,
        "refactor": create_refactor_agent_adapter,
    }
    
    factory = factories.get(role.lower())
    if not factory:
        logger.warning(f"Unknown role '{role}', using default adapter")
        return MultiModeAgentAdapter(role, workspace_root)
    
    return factory(workspace_root)

