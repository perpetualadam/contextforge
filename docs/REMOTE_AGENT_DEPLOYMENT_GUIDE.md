# Remote Agent Deployment Guide

## Table of Contents
1. [Local Development](#local-development)
2. [Docker Compose Deployment](#docker-compose-deployment)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Cloud Deployment](#cloud-deployment)
5. [Monitoring & Logging](#monitoring--logging)

---

## Local Development

### Prerequisites

```bash
# Install Python dependencies
pip install fastapi uvicorn redis pika httpx

# Install Docker
# Download from https://www.docker.com/products/docker-desktop

# Install Docker Compose
# Usually included with Docker Desktop
```

### Quick Start

```bash
# 1. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 2. Start RabbitMQ
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management-alpine

# 3. Start coordinator
cd services/api_gateway
python -m uvicorn app:app --host 0.0.0.0 --port 8080

# 4. Start agents (in separate terminals)
cd services/remote_agent
AGENT_ID=agent-1 python -m uvicorn agent:app --host 0.0.0.0 --port 8001
AGENT_ID=agent-2 python -m uvicorn agent:app --host 0.0.0.0 --port 8002
```

### Testing Locally

```bash
# Register agents
curl -X POST http://localhost:8080/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-1", "endpoint": "http://localhost:8001"}'

# Submit task
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"task_id": "test-1", "task_type": "analyze", "payload": {}}'

# Check status
curl http://localhost:8080/tasks/test-1
```

---

## Docker Compose Deployment

### Production Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - contextforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - contextforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  coordinator:
    build:
      context: ./services/api_gateway
      dockerfile: Dockerfile.prod
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@rabbitmq:5672
      - LOG_LEVEL=INFO
      - WORKERS=4
    depends_on:
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - contextforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  agent-1:
    build:
      context: ./services/remote_agent
      dockerfile: Dockerfile.prod
    environment:
      - AGENT_ID=agent-1
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - contextforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  agent-2:
    build:
      context: ./services/remote_agent
      dockerfile: Dockerfile.prod
    environment:
      - AGENT_ID=agent-2
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    networks:
      - contextforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  redis_data:
  rabbitmq_data:

networks:
  contextforge:
    driver: bridge
```

### Environment File

Create `.env.prod`:

```bash
# Redis
REDIS_PASSWORD=your-secure-redis-password

# RabbitMQ
RABBITMQ_USER=contextforge
RABBITMQ_PASSWORD=your-secure-rabbitmq-password

# Coordinator
COORDINATOR_WORKERS=4
LOG_LEVEL=INFO

# Agents
AGENT_WORKERS=2
AGENT_TIMEOUT=300
```

### Deployment

```bash
# Load environment
export $(cat .env.prod | xargs)

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Verify
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f coordinator
```

---

## Kubernetes Deployment

### Namespace & ConfigMap

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: contextforge

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
  namespace: contextforge
data:
  agent-config.yaml: |
    agent:
      timeout: 300
      max_retries: 3
      heartbeat_interval: 5
    logging:
      level: INFO
      format: json
```

### Redis Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: contextforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: contextforge
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  clusterIP: None
```

### Agent Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: contextforge-agent
  namespace: contextforge
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
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
        imagePullPolicy: Always
        ports:
        - containerPort: 8001
        env:
        - name: AGENT_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 15
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2

---
apiVersion: v1
kind: Service
metadata:
  name: agent-service
  namespace: contextforge
spec:
  selector:
    app: contextforge-agent
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-hpa
  namespace: contextforge
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: contextforge-agent
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deployment Commands

```bash
# Create namespace
kubectl create namespace contextforge

# Deploy Redis
kubectl apply -f k8s/redis-deployment.yaml

# Deploy agents
kubectl apply -f k8s/agent-deployment.yaml

# Check status
kubectl get pods -n contextforge
kubectl get svc -n contextforge

# View logs
kubectl logs -n contextforge -l app=contextforge-agent -f

# Scale agents
kubectl scale deployment contextforge-agent -n contextforge --replicas=5
```

---

## Cloud Deployment

### AWS ECS

```json
{
  "family": "contextforge-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "agent",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/contextforge-agent:latest",
      "portMappings": [
        {
          "containerPort": 8001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "REDIS_URL",
          "value": "redis://redis-endpoint:6379"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/contextforge-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/contextforge-agent

# Deploy
gcloud run deploy contextforge-agent \
  --image gcr.io/PROJECT_ID/contextforge-agent \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars REDIS_URL=redis://redis-endpoint:6379
```

---

## Monitoring & Logging

### Prometheus Metrics

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'contextforge-agents'
    static_configs:
      - targets: ['localhost:8001', 'localhost:8002']
```

### ELK Stack Logging

```yaml
filebeat.inputs:
- type: container
  enabled: true
  paths:
    - '/var/lib/docker/containers/*/*.log'

output.elasticsearch:
  hosts: ["elasticsearch:9200"]

processors:
  - add_docker_metadata: ~
  - add_kubernetes_metadata: ~
```

### Health Checks

```bash
# Check coordinator health
curl http://coordinator:8080/health

# Check agent health
curl http://agent-1:8001/health

# Get metrics
curl http://coordinator:8080/metrics/agents
```

