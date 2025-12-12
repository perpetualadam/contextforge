"""
Agent Registry - Manages agent registration, discovery, and health tracking.

Copyright (c) 2025 ContextForge
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from threading import Lock

from .models import AgentInfo, AgentStatus, AgentRegistration, HeartbeatRequest

logger = logging.getLogger(__name__)

# Singleton instance
_registry_instance = None
_registry_lock = Lock()


class AgentRegistry:
    """
    In-memory agent registry for managing remote agents.
    
    Provides:
    - Agent registration and deregistration
    - Agent discovery by capabilities
    - Health tracking via heartbeats
    - Load balancing support
    """
    
    def __init__(self, heartbeat_timeout_seconds: int = 30):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = Lock()
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self._health_check_task: Optional[asyncio.Task] = None
        logger.info("Agent registry initialized")
    
    def register(self, registration: AgentRegistration) -> AgentInfo:
        """Register a new agent."""
        with self._lock:
            agent = AgentInfo(
                name=registration.name,
                endpoint=registration.endpoint,
                capabilities=registration.capabilities,
                max_concurrent_tasks=registration.max_concurrent_tasks,
                metadata=registration.metadata,
            )
            self._agents[agent.agent_id] = agent
            logger.info(f"Agent registered: {agent.agent_id} ({agent.name})")
            return agent
    
    def deregister(self, agent_id: str) -> bool:
        """Deregister an agent."""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                logger.info(f"Agent deregistered: {agent_id}")
                return True
            return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID."""
        with self._lock:
            return self._agents.get(agent_id)
    
    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentInfo]:
        """List all agents, optionally filtered by status."""
        with self._lock:
            agents = list(self._agents.values())
            if status:
                agents = [a for a in agents if a.status == status]
            return agents
    
    def find_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        """Find agents with a specific capability."""
        with self._lock:
            return [
                a for a in self._agents.values()
                if capability in a.capabilities and a.status == AgentStatus.ONLINE
            ]
    
    def find_available_agent(self, required_capabilities: List[str] = None) -> Optional[AgentInfo]:
        """Find an available agent, optionally with required capabilities."""
        with self._lock:
            candidates = [
                a for a in self._agents.values()
                if a.status == AgentStatus.ONLINE
                and a.current_tasks < a.max_concurrent_tasks
            ]
            
            if required_capabilities:
                candidates = [
                    a for a in candidates
                    if all(cap in a.capabilities for cap in required_capabilities)
                ]
            
            if not candidates:
                return None
            
            # Return agent with least current tasks (load balancing)
            return min(candidates, key=lambda a: a.current_tasks)
    
    def heartbeat(self, request: HeartbeatRequest) -> bool:
        """Process agent heartbeat."""
        with self._lock:
            agent = self._agents.get(request.agent_id)
            if not agent:
                return False
            
            agent.last_heartbeat = datetime.utcnow()
            agent.status = request.status
            agent.current_tasks = request.current_tasks
            agent.metadata.update(request.metadata)
            return True
    
    def update_agent_tasks(self, agent_id: str, delta: int) -> bool:
        """Update agent's current task count."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                agent.current_tasks = max(0, agent.current_tasks + delta)
                return True
            return False
    
    def check_health(self) -> List[str]:
        """Check agent health and mark unhealthy agents."""
        now = datetime.utcnow()
        unhealthy = []
        
        with self._lock:
            for agent in self._agents.values():
                if agent.status == AgentStatus.ONLINE:
                    if now - agent.last_heartbeat > self._heartbeat_timeout:
                        agent.status = AgentStatus.UNHEALTHY
                        unhealthy.append(agent.agent_id)
                        logger.warning(f"Agent marked unhealthy: {agent.agent_id}")
        
        return unhealthy
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        with self._lock:
            total = len(self._agents)
            online = sum(1 for a in self._agents.values() if a.status == AgentStatus.ONLINE)
            busy = sum(1 for a in self._agents.values() if a.status == AgentStatus.BUSY)
            unhealthy = sum(1 for a in self._agents.values() if a.status == AgentStatus.UNHEALTHY)
            total_tasks = sum(a.current_tasks for a in self._agents.values())
            
            return {
                "total_agents": total,
                "online": online,
                "busy": busy,
                "unhealthy": unhealthy,
                "offline": total - online - busy - unhealthy,
                "total_active_tasks": total_tasks,
            }


def get_registry() -> AgentRegistry:
    """Get the singleton registry instance."""
    global _registry_instance
    with _registry_lock:
        if _registry_instance is None:
            _registry_instance = AgentRegistry()
        return _registry_instance

