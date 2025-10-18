# Remote Agent Quick Reference

## Quick Commands

### Start Services

```bash
# All services
docker-compose -f docker-compose.remote-agents.yml up -d

# Individual services
docker-compose -f docker-compose.remote-agents.yml up -d redis
docker-compose -f docker-compose.remote-agents.yml up -d rabbitmq
docker-compose -f docker-compose.remote-agents.yml up -d coordinator
docker-compose -f docker-compose.remote-agents.yml up -d agent-1 agent-2
```

### Stop Services

```bash
# All services
docker-compose -f docker-compose.remote-agents.yml down

# Keep volumes
docker-compose -f docker-compose.remote-agents.yml down -v
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.remote-agents.yml logs -f

# Specific service
docker-compose -f docker-compose.remote-agents.yml logs -f coordinator
docker-compose -f docker-compose.remote-agents.yml logs -f agent-1
```

---

## API Quick Reference

### Register Agent

```bash
curl -X POST http://localhost:8080/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-1",
    "endpoint": "http://agent-1:8001",
    "capabilities": ["analysis", "review"]
  }'
```

### Submit Task

```bash
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-001",
    "task_type": "analyze",
    "priority": "normal",
    "payload": {
      "file": "main.py",
      "analysis": "complexity"
    }
  }'
```

### Get Task Status

```bash
curl http://localhost:8080/tasks/task-001
```

### Get Task Result

```bash
curl http://localhost:8080/tasks/task-001/result
```

### Cancel Task

```bash
curl -X DELETE http://localhost:8080/tasks/task-001
```

### List Agents

```bash
curl http://localhost:8080/agents
```

### Get Agent Details

```bash
curl http://localhost:8080/agents/agent-1
```

### Check Health

```bash
curl http://localhost:8080/health
curl http://localhost:8001/health  # Agent health
```

### Get Metrics

```bash
curl http://localhost:8080/metrics/agents
curl http://localhost:8080/metrics/tasks
curl http://localhost:8080/metrics/performance
```

---

## Python Client Examples

### Basic Task Submission

```python
import requests

# Submit task
response = requests.post(
    "http://localhost:8080/tasks/submit",
    json={
        "task_id": "task-001",
        "task_type": "analyze",
        "payload": {"file": "main.py"}
    }
)
print(response.json())
```

### Poll Task Status

```python
import requests
import time

task_id = "task-001"
while True:
    response = requests.get(f"http://localhost:8080/tasks/{task_id}")
    status = response.json()
    
    if status["status"] == "completed":
        result = requests.get(f"http://localhost:8080/tasks/{task_id}/result")
        print(result.json())
        break
    
    print(f"Status: {status['status']}")
    time.sleep(1)
```

### Batch Submission

```python
import requests
import concurrent.futures

def submit_task(task_id, payload):
    return requests.post(
        "http://localhost:8080/tasks/submit",
        json={
            "task_id": task_id,
            "task_type": "analyze",
            "payload": payload
        }
    ).json()

# Submit 10 tasks in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(submit_task, f"task-{i}", {"file": f"file-{i}.py"})
        for i in range(10)
    ]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

print(f"Submitted {len(results)} tasks")
```

---

## Troubleshooting

### Agent Not Responding

```bash
# Check if agent is running
docker-compose -f docker-compose.remote-agents.yml ps agent-1

# Check agent logs
docker-compose -f docker-compose.remote-agents.yml logs agent-1

# Test agent endpoint
curl http://localhost:8001/health

# Restart agent
docker-compose -f docker-compose.remote-agents.yml restart agent-1
```

### Tasks Not Processing

```bash
# Check coordinator logs
docker-compose -f docker-compose.remote-agents.yml logs coordinator

# Check Redis connection
docker-compose -f docker-compose.remote-agents.yml exec redis redis-cli ping

# Check RabbitMQ
docker-compose -f docker-compose.remote-agents.yml exec rabbitmq rabbitmqctl status

# List agents
curl http://localhost:8080/agents
```

### High Memory Usage

```bash
# Check container stats
docker stats contextforge-agent-1

# Check agent metrics
curl http://localhost:8080/metrics/agents

# Reduce replicas
docker-compose -f docker-compose.remote-agents.yml up -d --scale agent=2
```

### Connection Refused

```bash
# Check if services are running
docker-compose -f docker-compose.remote-agents.yml ps

# Check network
docker network ls
docker network inspect contextforge

# Restart all services
docker-compose -f docker-compose.remote-agents.yml restart
```

---

## Performance Tuning

### Increase Agent Replicas

```bash
docker-compose -f docker-compose.remote-agents.yml up -d --scale agent=5
```

### Adjust Worker Threads

```bash
# In docker-compose.yml
environment:
  - WORKERS=8  # Increase from default 4
```

### Optimize Redis

```bash
# In docker-compose.yml
command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### Monitor Performance

```bash
# Real-time metrics
watch -n 1 'curl -s http://localhost:8080/metrics/agents | jq'

# Task throughput
curl http://localhost:8080/metrics/tasks | jq '.throughput'

# Agent utilization
curl http://localhost:8080/metrics/agents | jq '.[] | {agent_id, cpu_usage, memory_usage}'
```

---

## Common Patterns

### Retry with Exponential Backoff

```python
import time

def submit_with_retry(task_id, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            return requests.post(
                "http://localhost:8080/tasks/submit",
                json={"task_id": task_id, "task_type": "analyze", "payload": payload},
                timeout=5
            ).json()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
```

### Parallel Task Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_files(files):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(submit_task, f"task-{i}", {"file": f}): f
            for i, f in enumerate(files)
        }
        
        for future in as_completed(futures):
            result = future.result()
            print(f"Submitted: {result['task_id']}")
```

### Stream Results

```python
import websocket

def on_message(ws, message):
    print(f"Update: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

ws = websocket.WebSocketApp(
    "ws://localhost:8080/tasks/stream/task-001",
    on_message=on_message,
    on_error=on_error
)
ws.run_forever()
```

---

## Environment Variables

```bash
# Coordinator
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://localhost:5672
LOG_LEVEL=INFO
WORKERS=4

# Agent
AGENT_ID=agent-1
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://localhost:5672
LOG_LEVEL=INFO
AGENT_TIMEOUT=300
```

---

## Useful Links

- [Architecture Documentation](./REMOTE_AGENT_ARCHITECTURE.md)
- [Implementation Guide](./REMOTE_AGENT_IMPLEMENTATION_GUIDE.md)
- [Usage Guide](./REMOTE_AGENT_USAGE_GUIDE.md)
- [Deployment Guide](./REMOTE_AGENT_DEPLOYMENT_GUIDE.md)
- [API Reference](./API_REFERENCE.md)

