# Remote Agent Usage Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Basic Operations](#basic-operations)
3. [Advanced Usage](#advanced-usage)
4. [API Reference](#api-reference)
5. [Examples](#examples)

---

## Getting Started

### Starting the System

```bash
# Start all services with Docker Compose
docker-compose -f docker-compose.remote-agents.yml up -d

# Verify services are running
docker-compose -f docker-compose.remote-agents.yml ps

# Check coordinator is ready
curl http://localhost:8080/health
```

### Registering Agents

```bash
# Register agent 1
curl -X POST http://localhost:8080/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-1",
    "endpoint": "http://agent-1:8001",
    "capabilities": ["code-analysis", "documentation"]
  }'

# Register agent 2
curl -X POST http://localhost:8080/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-2",
    "endpoint": "http://agent-2:8001",
    "capabilities": ["code-review", "testing"]
  }'

# List all agents
curl http://localhost:8080/agents
```

---

## Basic Operations

### Submitting Tasks

```bash
# Submit a simple task
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-001",
    "task_type": "analyze",
    "payload": {
      "file_path": "src/main.py",
      "analysis_type": "complexity"
    }
  }'

# Response:
# {
#   "task_id": "task-001",
#   "status": "accepted",
#   "agent_id": "agent-1"
# }
```

### Checking Task Status

```bash
# Get task status
curl http://localhost:8080/tasks/task-001

# Response:
# {
#   "task_id": "task-001",
#   "status": "processing",
#   "progress": 45,
#   "result": null
# }

# Poll for completion
while true; do
  status=$(curl -s http://localhost:8080/tasks/task-001 | jq -r '.status')
  if [ "$status" = "completed" ]; then
    curl http://localhost:8080/tasks/task-001/result
    break
  fi
  sleep 1
done
```

### Canceling Tasks

```bash
# Cancel a task
curl -X DELETE http://localhost:8080/tasks/task-001

# Response:
# {
#   "task_id": "task-001",
#   "status": "cancelled"
# }
```

---

## Advanced Usage

### Batch Task Submission

```bash
# Submit multiple tasks
for i in {1..10}; do
  curl -X POST http://localhost:8080/tasks/submit \
    -H "Content-Type: application/json" \
    -d "{
      \"task_id\": \"batch-task-$i\",
      \"task_type\": \"analyze\",
      \"payload\": {
        \"file_id\": $i,
        \"priority\": \"normal\"
      }
    }"
done

# Monitor batch progress
curl http://localhost:8080/tasks/batch/batch-task-1/progress
```

### Priority-Based Task Submission

```bash
# Submit high-priority task
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "urgent-task-001",
    "task_type": "code-review",
    "priority": "high",
    "payload": {
      "pr_id": "123",
      "files": ["main.py", "utils.py"]
    }
  }'

# Submit low-priority task
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "background-task-001",
    "task_type": "index",
    "priority": "low",
    "payload": {
      "repo_path": "/repos/myrepo"
    }
  }'
```

### WebSocket Real-Time Updates

```bash
# Connect to task stream
wscat -c ws://localhost:8080/tasks/stream/task-001

# Receive updates:
# {"event": "started", "timestamp": "2025-10-18T10:00:00Z"}
# {"event": "progress", "progress": 25, "timestamp": "2025-10-18T10:00:05Z"}
# {"event": "progress", "progress": 50, "timestamp": "2025-10-18T10:00:10Z"}
# {"event": "completed", "result": {...}, "timestamp": "2025-10-18T10:00:15Z"}
```

### Agent Metrics

```bash
# Get agent metrics
curl http://localhost:8080/metrics/agents

# Response:
# {
#   "agents": [
#     {
#       "agent_id": "agent-1",
#       "status": "healthy",
#       "cpu_usage": 45.2,
#       "memory_usage": 62.1,
#       "active_tasks": 3,
#       "completed_tasks": 127,
#       "failed_tasks": 2
#     },
#     {
#       "agent_id": "agent-2",
#       "status": "healthy",
#       "cpu_usage": 38.5,
#       "memory_usage": 55.3,
#       "active_tasks": 2,
#       "completed_tasks": 145,
#       "failed_tasks": 1
#     }
#   ]
# }
```

---

## API Reference

### Agent Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/register` | POST | Register new agent |
| `/agents` | GET | List all agents |
| `/agents/{agent_id}` | GET | Get agent details |
| `/agents/{agent_id}` | DELETE | Deregister agent |
| `/agents/health` | GET | Check all agents health |

### Task Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks/submit` | POST | Submit new task |
| `/tasks/{task_id}` | GET | Get task status |
| `/tasks/{task_id}/result` | GET | Get task result |
| `/tasks/{task_id}` | DELETE | Cancel task |
| `/tasks` | GET | List all tasks |

### Metrics & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics/agents` | GET | Agent metrics |
| `/metrics/tasks` | GET | Task metrics |
| `/metrics/performance` | GET | Performance metrics |
| `/health` | GET | System health |

---

## Examples

### Example 1: Code Analysis Pipeline

```python
import requests
import time

coordinator_url = "http://localhost:8080"

# Submit code analysis task
response = requests.post(
    f"{coordinator_url}/tasks/submit",
    json={
        "task_id": "analysis-001",
        "task_type": "code-analysis",
        "payload": {
            "repo_path": "/repos/myproject",
            "analysis_types": ["complexity", "security", "performance"]
        }
    }
)

task_id = response.json()["task_id"]
print(f"Task submitted: {task_id}")

# Poll for completion
while True:
    status_response = requests.get(f"{coordinator_url}/tasks/{task_id}")
    status = status_response.json()
    
    if status["status"] == "completed":
        result = requests.get(f"{coordinator_url}/tasks/{task_id}/result").json()
        print("Analysis complete:")
        print(f"  Complexity: {result['complexity_score']}")
        print(f"  Security Issues: {result['security_issues']}")
        print(f"  Performance: {result['performance_score']}")
        break
    elif status["status"] == "failed":
        print(f"Task failed: {status['error']}")
        break
    
    print(f"Progress: {status.get('progress', 0)}%")
    time.sleep(2)
```

### Example 2: Distributed Repository Analysis

```python
import requests
import concurrent.futures

coordinator_url = "http://localhost:8080"
files = ["main.py", "utils.py", "config.py", "tests.py"]

def analyze_file(file_path):
    response = requests.post(
        f"{coordinator_url}/tasks/submit",
        json={
            "task_id": f"file-{file_path}",
            "task_type": "analyze",
            "payload": {"file": file_path}
        }
    )
    return response.json()

# Submit all files in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(analyze_file, f) for f in files]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

print(f"Submitted {len(results)} analysis tasks")
for result in results:
    print(f"  {result['task_id']}: {result['status']}")
```

### Example 3: Monitoring Agent Health

```python
import requests
import time

coordinator_url = "http://localhost:8080"

while True:
    # Get agent metrics
    response = requests.get(f"{coordinator_url}/metrics/agents")
    agents = response.json()["agents"]
    
    print("\n=== Agent Status ===")
    for agent in agents:
        status = "✓" if agent["status"] == "healthy" else "✗"
        print(f"{status} {agent['agent_id']}")
        print(f"  CPU: {agent['cpu_usage']:.1f}%")
        print(f"  Memory: {agent['memory_usage']:.1f}%")
        print(f"  Active Tasks: {agent['active_tasks']}")
        print(f"  Completed: {agent['completed_tasks']}")
    
    time.sleep(5)
```

### Example 4: Error Handling & Retry

```python
import requests
import time
from typing import Optional

def submit_task_with_retry(
    task_id: str,
    task_type: str,
    payload: dict,
    max_retries: int = 3
) -> Optional[str]:
    """Submit task with automatic retry on failure"""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8080/tasks/submit",
                json={
                    "task_id": task_id,
                    "task_type": task_type,
                    "payload": payload
                },
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()["task_id"]
            
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    
    return None

# Usage
task_id = submit_task_with_retry(
    "retry-task-001",
    "analyze",
    {"file": "main.py"}
)

if task_id:
    print(f"Task submitted successfully: {task_id}")
else:
    print("Failed to submit task after retries")
```

---

## Best Practices

1. **Always use task IDs**: Generate unique task IDs for tracking
2. **Implement timeouts**: Set reasonable timeouts for task completion
3. **Monitor metrics**: Regularly check agent and task metrics
4. **Handle failures gracefully**: Implement retry logic with exponential backoff
5. **Use priorities**: Mark urgent tasks as high priority
6. **Batch operations**: Submit multiple tasks efficiently
7. **Clean up**: Cancel tasks that are no longer needed

