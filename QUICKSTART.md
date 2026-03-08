# ContextForge Quick Start Guide

Get ContextForge running in 5 minutes. Choose your path: Docker (recommended) or local development.

---

## Path A: Docker Compose (Recommended)

### Step 1 -- Clone and Configure

```bash
git clone https://github.com/contextforge/contextforge.git
cd contextforge
cp .env.example .env
```

### Step 2 -- Choose Your LLM Provider

Edit `.env` and set at least one LLM backend.

**Option 1: Ollama (Local, Private, Free)**

Install Ollama from https://ollama.ai, then:

```bash
ollama serve
ollama pull mistral         # or llama3, codellama, deepseek-coder, etc.
```

In `.env`:

```
LLM_PRIORITY=ollama
OLLAMA_URL=http://host.docker.internal:11434/api/generate
OLLAMA_MODEL=mistral
```

> Use `host.docker.internal` (not `localhost`) so Docker containers can reach Ollama running on the host.

**Option 2: OpenAI (Cloud)**

```
LLM_PRIORITY=openai
OPENAI_API_KEY=sk-your-key-here
```

**Option 3: Anthropic Claude (Cloud)**

```
LLM_PRIORITY=anthropic
ANTHROPIC_API_KEY=your-key-here
```

**Option 4: LM Studio (Local)**

```
LLM_PRIORITY=lm_studio
LM_STUDIO_URL=http://host.docker.internal:1234/v1/chat/completions
```

### Step 3 -- Start All Services

```bash
docker-compose up --build -d
```

Wait for all containers to report healthy:

```bash
docker-compose ps
curl http://localhost:8080/health
```

Expected output: all services show `Up` and health endpoint returns `{"status": "healthy"}`.

### Step 4 -- Install the VS Code Extension

```bash
cd vscode-extension
npm install
npm run compile
npx vsce package
code --install-extension contextforge-1.0.0.vsix
```

### Step 5 -- Configure the Extension

Open VS Code Settings (`Ctrl+,`) and set:

```json
{
  "contextforge.apiUrl": "http://localhost:8080"
}
```

### Step 6 -- Index Your First Project

1. Open a project folder in VS Code.
2. Press `Ctrl+Shift+I` or run **ContextForge: Ingest Workspace** from the Command Palette.
3. Wait for the indexing notification to complete.

### Step 7 -- Start Using ContextForge

- Press `Ctrl+Shift+H` to open **AI Chat**.
- Press `Ctrl+Shift+C` to **ask a question** about your code.
- Select code and press `Ctrl+K` for **inline editing**.
- Press `Ctrl+Shift+E` for **multi-file agent mode**.
- Press `Ctrl+Shift+P` for **Composer** (long-running agent).

---

## Path B: Local Development (No Docker)

### Step 1 -- Install Prerequisites

- Python 3.9+ with pip
- Node.js 18+ with npm
- An LLM backend (Ollama recommended)

### Step 2 -- Set Up Python Environment

```bash
cd contextforge
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3 -- Start LLM Backend

```bash
ollama serve
ollama pull mistral
```

### Step 4 -- Start Services (Each in a Separate Terminal)

**Terminal 1 -- Vector Index (port 8001)**

```bash
# Windows
cd contextforge
.\venv\Scripts\activate
set PYTHONPATH=services\vector_index;.
python -m uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001

# Linux/Mac
cd contextforge
source venv/bin/activate
PYTHONPATH=services/vector_index:. uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001
```

**Terminal 2 -- Connector (port 8002)**

```bash
# Windows
.\venv\Scripts\activate
set PYTHONPATH=services\connector;.
python -m uvicorn services.connector.app:app --host 0.0.0.0 --port 8002

# Linux/Mac
PYTHONPATH=services/connector:. uvicorn services.connector.app:app --host 0.0.0.0 --port 8002
```

**Terminal 3 -- Preprocessor (port 8003)**

```bash
# Windows
.\venv\Scripts\activate
set PYTHONPATH=services\preprocessor;.
python -m uvicorn services.preprocessor.app:app --host 0.0.0.0 --port 8003

# Linux/Mac
PYTHONPATH=services/preprocessor:. uvicorn services.preprocessor.app:app --host 0.0.0.0 --port 8003
```

**Terminal 4 -- API Gateway (port 8082)**

```bash
# Windows
.\venv\Scripts\activate
set PYTHONPATH=services\api_gateway;.
set VECTOR_INDEX_URL=http://localhost:8001
set CONNECTOR_URL=http://localhost:8002
set PREPROCESSOR_URL=http://localhost:8003
python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8082

# Linux/Mac
PYTHONPATH=services/api_gateway:. \
VECTOR_INDEX_URL=http://localhost:8001 \
CONNECTOR_URL=http://localhost:8002 \
PREPROCESSOR_URL=http://localhost:8003 \
uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8082
```

### Step 5 -- Install VS Code Extension

```bash
cd vscode-extension
npm install
npm run compile
npx vsce package
code --install-extension contextforge-1.0.0.vsix
```

Set `contextforge.apiUrl` to `http://localhost:8082` in VS Code Settings.

---

## Verify Installation

Run these checks to confirm everything works:

```bash
# 1. Health check
curl http://localhost:8080/health        # Docker
curl http://localhost:8082/health        # Local dev

# 2. Ingest example repo
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/contextforge/examples/small-repo", "recursive": true}'

# 3. Query
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How does the API work?", "max_tokens": 256}'

# 4. Test chat
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 128}'
```

---

## Feature-Specific Setup

### Privacy Mode

Click the lock icon in the VS Code status bar to toggle between:
- **Private** (local LLMs only)
- **Cloud** (all configured LLMs)

### Project Rules

Create `.contextforge-rules` in your workspace root with coding conventions. The AI follows these for every request.

### Documentation Indexing

Run **ContextForge: Index Docs** from the Command Palette, enter a documentation URL (e.g., `https://docs.python.org/3/library/asyncio.html`), and assign a label. Reference indexed docs in chat with `@docs:label`.

### Inline Completion

Enabled by default. Disable in settings:

```json
{
  "contextforge.enableInlineCompletion": false
}
```

### Auto Linting

After AI edits, the extension checks for lint errors and offers auto-fix. Disable in settings:

```json
{
  "contextforge.enableAutoLint": false
}
```

---

## Troubleshooting

### Docker containers exit immediately

```bash
docker-compose logs api-gateway    # Check for errors
docker-compose logs vector-index
```

Common fix: ensure the `.env` file exists and has valid LLM configuration.

### Extension says "connection refused"

Check that:
1. Services are running (`docker-compose ps` or check terminal windows).
2. `contextforge.apiUrl` matches the running port (8080 for Docker, 8082 for local).
3. No firewall is blocking the port.

### Ollama not reachable from Docker

Use `host.docker.internal` instead of `localhost` in the `OLLAMA_URL`:

```
OLLAMA_URL=http://host.docker.internal:11434/api/generate
```

### Inline completion not appearing

1. Check `contextforge.enableInlineCompletion` is `true`.
2. Check that the API Gateway is running and reachable.
3. Check the Output panel (View -> Output -> ContextForge) for errors.

### Slow indexing

Large embedding models take longer. For development, use a smaller model:

```
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## Next Steps

- Read the full [README.md](README.md) for all 20 features
- See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for the complete API
- See [docs/RETRIEVAL_CONFIGURATION.md](docs/RETRIEVAL_CONFIGURATION.md) to tune search quality
- See [PUBLISHING.md](PUBLISHING.md) if you want to publish to the VS Code Marketplace
