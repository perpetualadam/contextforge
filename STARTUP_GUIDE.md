# ContextForge Startup Guide

Complete guide to running ContextForge locally, with Docker, and with VS Code extension.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start (Local Development)](#quick-start-local-development)
3. [Docker Deployment](#docker-deployment)
4. [VS Code Extension Setup](#vs-code-extension-setup)
5. [Redis Setup (Optional)](#redis-setup-optional)
6. [Troubleshooting](#troubleshooting)
7. [Command Reference](#command-reference)

---

## Prerequisites

### Required Software

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.10+ | https://www.python.org/downloads/ |
| Ollama | Latest | https://ollama.ai/download |
| Git | Latest | https://git-scm.com/downloads |

### Optional Software

| Software | Purpose | Download |
|----------|---------|----------|
| Docker Desktop | Container deployment | https://www.docker.com/products/docker-desktop |
| LM Studio | Alternative local LLM | https://lmstudio.ai/ |
| Redis/Memurai | Persistent storage | See Redis section |

---

## Quick Start (Local Development)

### Step 1: Install Ollama and Download a Model

```powershell
# Install Ollama (Windows - run as admin or use installer from website)
winget install Ollama.Ollama

# Start Ollama (it runs as a background service)
ollama serve

# In a new terminal, download a model (mistral is recommended, ~4GB)
ollama pull mistral

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

**Expected output:**
```json
{"models":[{"name":"mistral:latest",...}]}
```

### Step 2: Create Virtual Environment and Install Dependencies

```powershell
# Navigate to project directory
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge

# Create virtual environment
python -m venv venv

# Activate virtual environment (PowerShell)
.\venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Start the Services

**Terminal 1 - Vector Index Service:**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
.\venv\Scripts\activate
$env:PYTHONPATH = "services\vector_index;."
python -m uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001
```

**Terminal 2 - API Gateway:**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
.\venv\Scripts\activate
$env:PYTHONPATH = "services\api_gateway;."
python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8080
```

### Step 4: Verify Everything is Working

```powershell
# Check health endpoint
curl http://localhost:8080/health

# Test a query (PowerShell-friendly)
.\venv\Scripts\activate
python -c "import requests; r = requests.post('http://localhost:8080/query', json={'query': 'What is 2+2?'}); print(r.json())"
```

**Expected health response:**
```json
{
  "status": "healthy",
  "components": {
    "vector_index": {"status": "healthy", "url": "http://localhost:8001"},
    "llm_adapters": {"status": "healthy", "available": ["ollama"]},
    "search_providers": {"status": "disabled", "available": []}
  }
}
```

---

## Docker Deployment

### Step 1: Start Docker Desktop

1. Open Docker Desktop application
2. Wait for it to fully start (whale icon stops animating)
3. Verify Docker is running:

```powershell
docker --version
docker ps
```

### Step 2: Make Sure Ollama is Accessible to Docker

Ollama needs to be running on your host machine and accessible to Docker containers:

```powershell
# Verify Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

### Step 3: Start All Services with Docker Compose

```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge

# Build and start all services
docker-compose up --build

# Or run in background (detached mode)
docker-compose up -d --build

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api_gateway
```

### Step 4: Verify Docker Services

```powershell
# List running containers
docker-compose ps

# Check health
curl http://localhost:8080/health
```

### Stop Docker Services

```powershell
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

---

## VS Code Extension Setup

### Step 1: Install the Extension

```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
code --install-extension vscode-extension\contextforge-1.0.0.vsix
```

### Step 2: Configure the Extension

1. Open VS Code
2. Press `Ctrl+,` to open Settings
3. Search for "contextforge"
4. Set `Contextforge: Api Url` to:
   - Local development: `http://localhost:8080`
   - If using port 8082: `http://localhost:8082`
   - Docker: `http://localhost:8080`

### Step 3: Using the Extension

**Commands (Ctrl+Shift+P):**
- `ContextForge: Open Chat Panel` - Open AI chat interface
- `ContextForge: Ingest Workspace` - Index your current workspace
- `ContextForge: Query` - Ask a question about your code
- `ContextForge: Open Prompt Generator` - AI prompt enhancement tool

**Keyboard Shortcuts:**
- `Ctrl+Shift+C` - Open Chat Panel
- `Ctrl+Shift+Q` - Quick Query

### Step 4: Ingest Your Workspace

1. Open your project folder in VS Code
2. Run command: `ContextForge: Ingest Workspace`
3. Wait for indexing to complete
4. Now you can ask questions about your codebase!

---

## Redis Setup (Optional)

Redis provides persistent storage for the remote agent system. Without Redis, the system uses in-memory storage (data lost on restart).

### Option A: Docker Redis (Recommended)

```powershell
# Start Redis container
docker run -d --name contextforge-redis -p 6379:6379 redis:alpine

# Verify Redis is running
docker ps | findstr redis

# Test Redis connection
docker exec -it contextforge-redis redis-cli ping
# Expected: PONG

# Stop Redis
docker stop contextforge-redis

# Start Redis again
docker start contextforge-redis

# Remove Redis container completely
docker rm -f contextforge-redis
```

### Option B: Memurai (Windows Native Redis)

```powershell
# Install Memurai Developer Edition
winget install Memurai.MemuraiDeveloper

# Start Memurai service (it may auto-start)
net start memurai

# Test connection
redis-cli ping
```

### Enable Redis in ContextForge

Add to your `.env` file:
```ini
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0
```

---

## Troubleshooting

### Problem: Port Already in Use

**Symptoms:**
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8080)
```

**Solution:**
```powershell
# Find what's using the port
netstat -aon | findstr ":8080"

# Kill the process (replace PID with actual number)
taskkill /F /PID <PID>

# Or use a different port
python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8082
```

### Problem: Ollama Not Responding

**Symptoms:**
```json
{"llm_adapters": {"status": "unhealthy"}}
```

**Solution:**
```powershell
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start Ollama
ollama serve

# Make sure you have a model
ollama list

# If no models, download one
ollama pull mistral
```

### Problem: Vector Index Connection Failed

**Symptoms:**
```
Failed to resolve 'vector-index'
```

**Solution:** You're running locally but using Docker hostnames. Check your `.env`:
```ini
# For local development, use localhost:
VECTOR_INDEX_URL=http://localhost:8001

# For Docker, use service names:
VECTOR_INDEX_URL=http://vector-index:8001
```

### Problem: Module Not Found Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'rag'
```

**Solution:**
```powershell
# Make sure PYTHONPATH is set correctly
$env:PYTHONPATH = "services\api_gateway;."

# Or run from the correct directory
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
```

### Problem: Import Errors (Relative Imports)

**Symptoms:**
```
ImportError: attempted relative import with no known parent package
```

**Solution:**
```powershell
# Run as a module from project root with PYTHONPATH set
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
$env:PYTHONPATH = "."
python -m uvicorn services.vector_index.app:app --port 8001
```

### Problem: VS Code Extension Not Connecting

**Symptoms:** Chat panel shows "Error connecting to server"

**Solutions:**
1. Verify the API is running: `curl http://localhost:8080/health`
2. Check VS Code settings: `Contextforge: Api Url` matches your port
3. Restart VS Code after changing settings

### Problem: Docker Desktop Not Running

**Symptoms:**
```
error during connect: ... open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```

**Solution:**
1. Open Docker Desktop application
2. Wait for it to fully start
3. Run `docker ps` to verify

### Problem: Slow LLM Responses

**Symptoms:** First query takes 30+ seconds

**Explanation:** This is normal! The first query loads the model into GPU/RAM. Subsequent queries are faster.

**Optimizations:**
```powershell
# Use a smaller/faster model
ollama pull phi3

# Update .env
OLLAMA_MODEL=phi3
```

### Problem: Python Package Conflicts

**Symptoms:**
```
ERROR: ResolutionImpossible: conflicting dependencies
```

**Solution:**
```powershell
# Create fresh virtual environment
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Problem: Rust/Cargo Required for Some Packages

**Symptoms:**
```
error: Rust is required to build this package
```

**Solution:**
```powershell
# Install Rust
winget install Rustlang.Rustup

# Restart terminal and retry
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

## Command Reference

### Startup Commands (Copy-Paste Ready)

**One-Time Setup:**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Start Vector Index (Terminal 1):**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
.\venv\Scripts\activate
$env:PYTHONPATH = "services\vector_index;."
python -m uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001
```

**Start API Gateway (Terminal 2):**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
.\venv\Scripts\activate
$env:PYTHONPATH = "services\api_gateway;."
python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8080
```

**Health Check:**
```powershell
curl http://localhost:8080/health
```

**Test Query:**
```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
.\venv\Scripts\activate
python -c "import requests; r = requests.post('http://localhost:8080/query', json={'query': 'Hello!'}); print(r.json())"
```

### Docker Commands

```powershell
# Start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild specific service
docker-compose up -d --build api_gateway

# View running containers
docker-compose ps
```

### Ollama Commands

```powershell
# Start Ollama
ollama serve

# List models
ollama list

# Download model
ollama pull mistral
ollama pull llama3
ollama pull phi3
ollama pull codellama

# Remove model
ollama rm <model-name>

# Test Ollama
curl http://localhost:11434/api/tags
```

### VS Code Extension Commands

```powershell
# Install extension
code --install-extension vscode-extension\contextforge-1.0.0.vsix

# List installed extensions
code --list-extensions | findstr contextforge

# Uninstall extension
code --uninstall-extension contextforge.contextforge
```

---

## Service Ports Reference

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| API Gateway | 8080 | http://localhost:8080/health |
| Vector Index | 8001 | http://localhost:8001/health |
| Preprocessor | 8003 | http://localhost:8003/health |
| Connector | 8002 | http://localhost:8002/health |
| Web Fetcher | 8004 | http://localhost:8004/health |
| Terminal Executor | 8006 | http://localhost:8006/health |
| MCP Server | 8010 | http://localhost:8010/health |
| Remote Agent | 8011 | http://localhost:8011/health |
| Ollama | 11434 | http://localhost:11434/api/tags |
| LM Studio | 1234 | http://localhost:1234/v1/models |
| Redis | 6379 | redis-cli ping |

---

## Quick Troubleshooting Flowchart

```
API not responding?
├── Is Ollama running? → ollama serve
├── Is Vector Index running? → Check Terminal 1
├── Is API Gateway running? → Check Terminal 2
├── Port conflict? → netstat -aon | findstr ":8080"
└── Wrong URL in .env? → Check VECTOR_INDEX_URL

VS Code extension not working?
├── Is API running? → curl http://localhost:8080/health
├── Correct port in settings? → Check Contextforge: Api Url
└── Extension installed? → code --list-extensions | findstr context
```

---

## Need More Help?

1. Check the logs for error messages
2. Verify all prerequisites are installed
3. Make sure Ollama has at least one model downloaded
4. Check that ports aren't blocked by firewall
5. Try restarting all services


