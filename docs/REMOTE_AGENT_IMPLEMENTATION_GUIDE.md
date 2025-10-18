# Remote Agent Implementation Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Phase 1: Single Remote Agent](#phase-1-single-remote-agent)
3. [Phase 2: Multiple Agents](#phase-2-multiple-agents)
4. [Phase 3: Production Deployment](#phase-3-production-deployment)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- Redis (for registry and caching)
- RabbitMQ (for message queue)

### Installation

```bash
# Clone the repository
git clone https://github.com/perpetualadam/contextforge.git
cd contextforge

# Install dependencies
pip install -r requirements.txt
pip install redis pika consul

# Start infrastructure services
docker-compose up -d redis rabbitmq
```

---

## Phase 1: Single Remote Agent

### Step 1: Create Agent Service

Create `services/remote_agent/agent.py`:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import uuid
import logging

app = FastAPI(title="ContextForge Remote Agent")
logger = logging.getLogger(__name__)

class Task(BaseModel):
    task_id: str
    task_type: str
    payload: dict

class TaskResult(BaseModel):
    task_id: str
    status: str
    result: dict
    error: str = None

# In-memory task storage (use database in production)
tasks_db = {}

@app.post("/tasks/submit")
async def submit_task(task: Task):
    """Submit a task for processing"""
    logger.info(f"Received task: {task.task_id}")
    tasks_db[task.task_id] = {
        "status": "processing",
        "result": None,
        "error": None
    }
    
    # Process task asynchronously
    asyncio.create_task(process_task(task))
    
    return {"task_id": task.task_id, "status": "accepted"}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks_db[task_id]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent_id": "agent-1"}

async def process_task(task: Task):
    """Process the task"""
    try:
        # Simulate processing
        await asyncio.sleep(2)
        
        result = {
            "processed": True,
            "input": task.payload
        }
        
        tasks_db[task.task_id]["status"] = "completed"
        tasks_db[task.task_id]["result"] = result
        
        logger.info(f"Task {task.task_id} completed")
    except Exception as e:
        tasks_db[task.task_id]["status"] = "failed"
        tasks_db[task.task_id]["error"] = str(e)
        logger.error(f"Task {task.task_id} failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Step 2: Create Agent Registration

Create `services/remote_agent/registry.py`:

```python
import redis
import json
import time
from typing import Dict, List

class AgentRegistry:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.heartbeat_interval = 5
    
    def register_agent(self, agent_id: str, agent_info: Dict):
        """Register agent in registry"""
        agent_data = {
            "agent_id": agent_id,
            "status": "healthy",
            "timestamp": time.time(),
            **agent_info
        }
        
        self.redis_client.setex(
            f"agent:{agent_id}",
            300,  # 5 minute TTL
            json.dumps(agent_data)
        )
        print(f"Agent {agent_id} registered")
    
    def get_agents(self) -> List[Dict]:
        """Get all registered agents"""
        agents = []
        for key in self.redis_client.keys("agent:*"):
            agent_data = self.redis_client.get(key)
            if agent_data:
                agents.append(json.loads(agent_data))
        return agents
    
    def send_heartbeat(self, agent_id: str):
        """Send heartbeat to keep agent alive"""
        self.redis_client.expire(f"agent:{agent_id}", 300)
```

### Step 3: Update Coordinator

Update `services/api_gateway/app.py` to add agent endpoints:

```python
from fastapi import FastAPI
import httpx

app = FastAPI()

# Agent registry
agents = {}

@app.post("/agents/register")
async def register_agent(agent_id: str, endpoint: str):
    """Register a remote agent"""
    agents[agent_id] = {
        "endpoint": endpoint,
        "status": "healthy"
    }
    return {"status": "registered", "agent_id": agent_id}

@app.get("/agents")
async def list_agents():
    """List all registered agents"""
    return {"agents": agents}

@app.post("/tasks/submit")
async def submit_task(task_id: str, task_type: str, payload: dict):
    """Submit task to available agent"""
    if not agents:
        raise HTTPException(status_code=503, detail="No agents available")
    
    # Round-robin agent selection
    agent_id = list(agents.keys())[0]
    agent = agents[agent_id]
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{agent['endpoint']}/tasks/submit",
            json={"task_id": task_id, "task_type": task_type, "payload": payload}
        )
    
    return response.json()
```

---

## Phase 2: Multiple Agents

### Step 1: Implement Load Balancing

Create `services/api_gateway/load_balancer.py`:

```python
from enum import Enum
from typing import List, Dict

class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"

class LoadBalancer:
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self.current_index = 0
        self.agent_connections = {}
    
    def select_agent(self, agents: List[Dict]) -> str:
        """Select agent based on strategy"""
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin(agents)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections(agents)
        else:
            return agents[0]["agent_id"]
    
    def _round_robin(self, agents: List[Dict]) -> str:
        """Round-robin selection"""
        agent_id = agents[self.current_index % len(agents)]["agent_id"]
        self.current_index += 1
        return agent_id
    
    def _least_connections(self, agents: List[Dict]) -> str:
        """Select agent with least connections"""
        return min(
            agents,
            key=lambda a: self.agent_connections.get(a["agent_id"], 0)
        )["agent_id"]
```

### Step 2: Implement Health Checks

Create `services/api_gateway/health_checker.py`:

```python
import asyncio
import httpx
from typing import Dict, List

class HealthChecker:
    def __init__(self, check_interval: int = 5, timeout: int = 3):
        self.check_interval = check_interval
        self.timeout = timeout
        self.agent_health = {}
    
    async def check_agent_health(self, agent_id: str, endpoint: str) -> bool:
        """Check if agent is healthy"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{endpoint}/health")
                return response.status_code == 200
        except Exception as e:
            print(f"Health check failed for {agent_id}: {e}")
            return False
    
    async def monitor_agents(self, agents: Dict[str, Dict]):
        """Continuously monitor agent health"""
        while True:
            for agent_id, agent_info in agents.items():
                is_healthy = await self.check_agent_health(
                    agent_id,
                    agent_info["endpoint"]
                )
                self.agent_health[agent_id] = is_healthy
                print(f"Agent {agent_id}: {'healthy' if is_healthy else 'unhealthy'}")
            
            await asyncio.sleep(self.check_interval)
    
    def get_healthy_agents(self, agents: Dict[str, Dict]) -> List[Dict]:
        """Get only healthy agents"""
        return [
            {"agent_id": aid, **info}
            for aid, info in agents.items()
            if self.agent_health.get(aid, False)
        ]
```

---

## Phase 3: Production Deployment

### Docker Compose Setup

Create `docker-compose.remote-agents.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - contextforge

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    networks:
      - contextforge

  agent-1:
    build: ./services/remote_agent
    environment:
      - AGENT_ID=agent-1
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    networks:
      - contextforge

  agent-2:
    build: ./services/remote_agent
    environment:
      - AGENT_ID=agent-2
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    networks:
      - contextforge

  coordinator:
    build: ./services/api_gateway
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://rabbitmq:5672
    depends_on:
      - redis
      - rabbitmq
      - agent-1
      - agent-2
    networks:
      - contextforge

networks:
  contextforge:
    driver: bridge
```

### Kubernetes Deployment

Create `k8s/agent-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: contextforge-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: contextforge-agent
  template:
    metadata:
      labels:
        app: contextforge-agent
    spec:
      containers:
      - name: agent
        image: contextforge/agent:latest
        ports:
        - containerPort: 8001
        env:
        - name: REDIS_URL
          value: redis://redis-service:6379
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## Troubleshooting

### Agent Not Registering

```bash
# Check Redis connection
redis-cli ping

# Check agent logs
docker logs contextforge-agent-1

# Verify agent endpoint
curl http://localhost:8001/health
```

### Tasks Not Processing

```bash
# Check RabbitMQ queue
rabbitmqctl list_queues

# Check coordinator logs
docker logs contextforge-coordinator

# Verify task submission
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_id": "test-1", "task_type": "analyze", "payload": {}}'
```

### Performance Issues

```bash
# Monitor agent resources
docker stats contextforge-agent-1

# Check queue depth
redis-cli LLEN task:queue

# Review metrics
curl http://localhost:8080/metrics
```

---

## Next Steps

1. **Implement Message Queue**: Integrate RabbitMQ for async task processing
2. **Add Monitoring**: Set up Prometheus and Grafana
3. **Enable Caching**: Implement distributed caching with Redis
4. **Security**: Add TLS/SSL and authentication
5. **Auto-Scaling**: Implement Kubernetes HPA for dynamic scaling

