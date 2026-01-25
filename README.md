# ContextForge

A complete local-first context engine and AI assistant pipeline for intelligent code analysis and retrieval. ContextForge provides semantic search, multi-LLM support, and VS Code integration for enhanced developer productivity.

## 🚀 Features

- **Local-First Architecture**: Privacy-focused design with optional remote LLM support
- **Multi-Language Support**: 15+ languages with tree-sitter AST-based and regex chunking
  - **Tree-sitter support**: Python, JavaScript, TypeScript, Java, Rust, Go, C/C++, C#, Ruby, PHP, Kotlin, Julia, HTML, CSS
  - **Hybrid chunking**: Automatic selection between tree-sitter (incremental) and regex (batch) modes
  - **Regex fallback**: Additional languages including Swift, R, Scala, Lua, Perl, Shell
- **Vector Search**: FAISS-powered semantic search with hybrid retrieval (dense + lexical)
  - **Dual embeddings**: all-mpnet-base-v2 (general) + CodeBERT (code-specific)
  - **HNSW indexing**: Optimized for large datasets (100k+ vectors)
  - **Recency boosting**: Prioritize recently modified code
- **Multi-LLM Backend**: 8 providers with intelligent fallback
  - **Local**: Ollama, LM Studio
  - **Cloud**: OpenAI, Anthropic, Mistral, DeepSeek, Grok (xAI), Groq
- **Web Search Integration**: SerpAPI, Bing, Google CSE with scraping fallback
- **VS Code Extension**: Native editor integration with workspace ingestion, query interface, and AI chat
- **AI Chat Interface**: Interactive chat panel with multi-turn conversations, markdown rendering, and code actions
- **Git/GitHub Integration**: Comprehensive Git operations with AI-powered commit messages and GitHub API integration
- **File/Media Attachments**: Upload and analyze files, images, PDFs, and documents in chat with AI-powered insights
- **Microservices Architecture**: Docker Compose orchestration with health monitoring
- **Remote Agent Support (Planned)**: Distributed agent architecture for scalable processing across multiple machines
- **Comprehensive Testing**: Unit tests, integration tests, and CI/CD pipeline

## 📋 Prerequisites

- **Docker & Docker Compose**: For running services
- **Python 3.9+**: For development and scripts
- **Node.js 18+**: For VS Code extension development
- **VS Code**: For extension usage

### Optional LLM Backends

- **Ollama**: Local LLM inference (recommended for privacy)
- **LM Studio**: Alternative local LLM platform
- **API Keys**: For remote LLM providers (OpenAI, Anthropic, Mistral)

## 🏃 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/your-org/contextforge.git
cd contextforge
cp .env.example .env
```

### 2. Configure LLM Provider

ContextForge requires at least one LLM provider. Choose one:

**Option A: Ollama (Recommended - Local & Private)**
```bash
# Install Ollama from https://ollama.ai
# Run: ollama serve
# Then configure in .env:
LLM_PRIORITY=ollama
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=mistral
```

**Option B: OpenAI (Remote)**
```bash
LLM_PRIORITY=openai
OPENAI_API_KEY=sk-your-key-here
```

**Option C: Anthropic Claude (Remote)**
```bash
LLM_PRIORITY=anthropic
ANTHROPIC_API_KEY=your-key-here
```

**Option D: LM Studio (Local Alternative)**
```bash
LLM_PRIORITY=lm_studio
LM_STUDIO_URL=http://localhost:8085/generate
```

### 3. Start Services

```bash
make dev
```

This starts all services:
- API Gateway: http://localhost:8080 (Docker) or http://localhost:8082 (local dev)
- Vector Index: http://localhost:8001
- Connector: http://localhost:8002
- Preprocessor: http://localhost:8003
- Web Fetcher: http://localhost:8004
- Terminal Executor: http://localhost:8006

> **Note**: Docker Compose uses port 8080 for the API Gateway. Local development uses port 8082 to avoid conflicts.

### 4. Ingest Example Repository

```bash
make ingest-example
```

### 5. Query the System

```bash
make query-example --q "How does authentication work?"
```

## 📦 Installation Options

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
make dev

# Or manually
docker-compose up --build
```

### Option 2: Local Development (Windows)

Run each service in a separate CMD window:

**Step 1: Install Ollama and start it**
```cmd
# Download from https://ollama.ai
ollama serve
# (If you see "bind: Only one usage of each socket address..." it's already running - that's OK!)
```

**Step 2: Create virtual environment (one time setup)**
```cmd
cd C:\path\to\ContextForge
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**Step 3: Start all services (each in separate CMD window)**

**CMD Window 1 - Vector Index (port 8001)**
```cmd
cd /d C:\path\to\ContextForge
.\venv\Scripts\activate
set PYTHONPATH=services\vector_index;.
python -m uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001
```

**CMD Window 2 - Connector (port 8002)**
```cmd
cd /d C:\path\to\ContextForge
.\venv\Scripts\activate
set PYTHONPATH=services\connector;.
python -m uvicorn services.connector.app:app --host 0.0.0.0 --port 8002
```

**CMD Window 3 - Preprocessor (port 8003)**
```cmd
cd /d C:\path\to\ContextForge
.\venv\Scripts\activate
set PYTHONPATH=services\preprocessor;.
python -m uvicorn services.preprocessor.app:app --host 0.0.0.0 --port 8003
```

**CMD Window 4 - API Gateway (port 8082)**
```cmd
cd /d C:\path\to\ContextForge
.\venv\Scripts\activate
set PYTHONPATH=services\api_gateway;.
set VECTOR_INDEX_URL=http://localhost:8001
set CONNECTOR_URL=http://localhost:8002
set PREPROCESSOR_URL=http://localhost:8003
python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8082
```

**Step 4: Install VS Code Extension**
```cmd
cd vscode-extension
npm install
npm run compile
npx vsce package
code --install-extension contextforge-1.0.0.vsix
```

**Step 5: Configure Extension**
- Open VS Code Settings (`Ctrl+,`)
- Set `contextforge.apiUrl` to `http://localhost:8082`

### Service Ports Summary

| Service | Port | Purpose |
|---------|------|---------|
| Vector Index | 8001 | FAISS vector search and embeddings |
| Connector | 8002 | File system reading |
| Preprocessor | 8003 | Code chunking |
| API Gateway | 8082 | Main API (orchestrates all services) |
| Ollama | 11434 | LLM inference |

### Option 3: Local Development (Linux/Mac)

```bash
# Create virtual environment
make venv

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Start individual services (each in separate terminal)
export PYTHONPATH=services/vector_index:.
uvicorn services.vector_index.app:app --host 0.0.0.0 --port 8001

export PYTHONPATH=services/connector:.
uvicorn services.connector.app:app --host 0.0.0.0 --port 8002

export PYTHONPATH=services/preprocessor:.
uvicorn services.preprocessor.app:app --host 0.0.0.0 --port 8003

export PYTHONPATH=services/api_gateway:.
export VECTOR_INDEX_URL=http://localhost:8001
export CONNECTOR_URL=http://localhost:8002
export PREPROCESSOR_URL=http://localhost:8003
uvicorn services.api_gateway.app:app --host 0.0.0.0 --port 8082
```

## 🔧 Usage

### Command Line Interface

#### Ingest a Repository

```bash
python scripts/ingest_example.py --path /path/to/your/repo
```

#### Query the System

```bash
python scripts/query_example.py --query "How is user authentication implemented?"
```

#### Test LLM Adapters

```bash
python scripts/test_llm.py
```

### VS Code Extension

1. **Install Extension**:
   ```bash
   cd vscode-extension
   npm install
   npm run package
   code --install-extension contextforge-1.0.0.vsix
   ```

2. **Configure API URL**: Set `contextforge.apiUrl` in VS Code settings

3. **Ingest Workspace**: `Ctrl+Shift+I` or "ContextForge: Ingest Workspace"

4. **Ask Questions**: `Ctrl+Shift+C` or "ContextForge: Ask"

5. **Execute Terminal Commands**: `Ctrl+Shift+T` or "ContextForge: Execute Terminal Command"

6. **Get Command Suggestions**: `Ctrl+Shift+S` or "ContextForge: Suggest Terminal Command"

7. **View Active Processes**: "ContextForge: Show Terminal Processes"

8. **Toggle Auto Terminal Mode**: `Ctrl+Shift+A` or "ContextForge: Toggle Auto Terminal Mode"
   - ⚠️ **SECURITY WARNING**: Auto mode executes AI-suggested commands automatically
   - Only executes commands from your configured whitelist
   - Shows warning dialog before enabling
   - Status bar indicator shows current mode

9. **Open AI Chat**: `Ctrl+Shift+H` or "ContextForge: Open Chat"
   - Interactive chat panel in the Explorer sidebar
   - Multi-turn conversations with context awareness
   - Markdown rendering with syntax highlighting
   - Copy and insert code snippets directly into editor
   - Chat history persistence across sessions
   - Session management with multiple chat threads

10. **Git Operations**: Comprehensive Git integration with AI assistance
    - **Git Status**: `Ctrl+Shift+G S` - View repository status and changes
    - **Git Commit**: `Ctrl+Shift+G C` - Commit with AI-generated messages
    - **Git Push**: `Ctrl+Shift+G P` - Push changes to remote repository
    - **Git Pull**: Pull latest changes from remote repository
    - **Branch Management**: Create, switch, and delete branches
    - **Repository Health**: Automated repository health checks

11. **GitHub Integration**: Seamless GitHub workflow integration
    - **Create Pull Requests**: `Ctrl+Shift+G R` - Create PRs with AI assistance
    - **View Issues**: Browse and manage GitHub issues
    - **Repository Operations**: Clone, fork, and manage repositories
    - **Automatic PR descriptions**: AI-generated PR titles and descriptions

12. **File/Media Attachments**: Upload and analyze files in chat
    - **Drag-and-drop support**: Simply drag files into the chat panel
    - **Image analysis**: AI-powered image recognition and description
    - **Document extraction**: Automatic text extraction from PDFs and Word documents
    - **File previews**: Inline previews of images and document content
    - **Multiple file types**: Support for images, PDFs, Word docs, text files, and more

13. **AI Prompt Generator/Enhancer**: Intelligent prompt optimization and templates
    - **Prompt Enhancement**: AI-powered suggestions to improve prompt clarity and effectiveness
    - **Prompt Templates**: Pre-built templates for common tasks (code review, debugging, documentation, etc.)
    - **Context Enhancement**: Automatically add relevant workspace context to prompts
    - **Prompt History**: Save and retrieve previously used prompts
    - **Prompt Favorites**: Mark and organize your best prompts for quick access

### REST API

#### Ingest Repository

```bash
curl -X POST "http://localhost:8080/ingest" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/repo", "recursive": true}'
```

#### Query System

```bash
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication implementation", "max_tokens": 512}'
```

#### Query with Auto-Terminal Execution

```bash
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I run tests for this project?",
    "auto_terminal_mode": true,
    "auto_terminal_timeout": 30,
    "auto_terminal_whitelist": ["npm test", "python -m pytest", "git status"]
  }'
```

#### AI Chat Conversation

```bash
curl -X POST "http://localhost:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello! Can you help me understand this codebase?"},
      {"role": "assistant", "content": "I'd be happy to help! What specific part would you like to explore?"},
      {"role": "user", "content": "How does the authentication system work?"}
    ],
    "max_tokens": 1024,
    "enable_web_search": false,
    "enable_context": true
  }'
```

#### Git Commit Message Generation

```bash
curl -X POST "http://localhost:8080/git/commit-message" \
  -H "Content-Type: application/json" \
  -d '{
    "diff": "diff --git a/src/feature.py b/src/feature.py\n...",
    "staged_files": ["src/feature.py", "tests/test_feature.py"],
    "branch": "feature/improve-validation",
    "recent_commits": [
      "feat: add input validation",
      "fix: handle edge cases",
      "docs: update API documentation"
    ]
  }'
```

#### File Upload and Analysis

```bash
# Upload a file for analysis
curl -X POST "http://localhost:8080/files/upload" \
  -F "file=@/path/to/file.pdf"

# Response includes:
# - File ID for reference
# - Extracted text (for PDFs, documents)
# - Image analysis (for images)
# - Base64 encoded file data
```

### Vision Model Strategy

ContextForge uses a **cost-effective, tiered vision model approach** for image analysis:

#### Model Priority (Fastest to Most Detailed)

1. **CLIP (Primary)** - OpenAI's Contrastive Language-Image Pre-training
   - ✅ **Cost**: Free (open-source)
   - ✅ **Speed**: Fast (~100-200ms per image)
   - ✅ **Accuracy**: Good general understanding
   - ✅ **Memory**: ~350MB
   - **Use case**: Quick image classification and understanding

2. **BLIP (Secondary)** - Salesforce's Bootstrapping Language-Image Pre-training
   - ✅ **Cost**: Free (open-source)
   - ✅ **Speed**: Medium (~300-500ms per image)
   - ✅ **Accuracy**: Excellent captions and descriptions
   - ✅ **Memory**: ~500MB
   - **Use case**: Detailed image descriptions and captions

3. **Google ViT (Tertiary)** - Vision Transformer
   - ✅ **Cost**: Free (open-source)
   - ✅ **Speed**: Medium (~200-400ms per image)
   - ✅ **Accuracy**: Good classification
   - ✅ **Memory**: ~300MB
   - **Use case**: Fallback classification

4. **Basic Analysis (Fallback)** - Always available
   - ✅ **Cost**: Free
   - ✅ **Speed**: Instant
   - ✅ **Accuracy**: Image properties only
   - **Use case**: When all models fail

#### Cost Comparison

| Model | Cost | Speed | Quality | Memory |
|-------|------|-------|---------|--------|
| CLIP | Free | ⚡⚡⚡ | ⭐⭐⭐⭐ | 350MB |
| BLIP | Free | ⚡⚡ | ⭐⭐⭐⭐⭐ | 500MB |
| ViT | Free | ⚡⚡ | ⭐⭐⭐⭐ | 300MB |
| Basic | Free | ⚡⚡⚡⚡⚡ | ⭐⭐ | 0MB |

#### Why This Approach?

- **Zero API Costs**: All models run locally, no cloud API charges
- **Privacy**: Images never leave your machine
- **Reliability**: Multiple fallbacks ensure analysis always works
- **Performance**: Fastest models tried first
- **Flexibility**: Easy to swap models or add new ones

## Prompt Generator/Enhancer

The AI Prompt Generator/Enhancer helps you write better prompts for AI models. Access it via the **ContextForge Prompt Generator** panel in the Explorer sidebar.

### Features

#### 1. Prompt Enhancement
- **AI-Powered Suggestions**: Get intelligent suggestions to improve your prompts
- **Clarity Improvements**: Make prompts more specific and effective
- **Style Options**: Choose professional, technical, or casual tone
- **Context Awareness**: Add workspace context for better suggestions

#### 2. Prompt Templates
Pre-built templates for common development tasks:
- Code Review, Debug Issue, Generate Documentation
- Refactor Code, Generate Tests, Explain Code
- API Design Review, Performance Optimization

#### 3. Prompt History
- **Auto-Save**: Prompts are automatically saved
- **Quick Access**: View all previously used prompts
- **Favorites**: Mark important prompts as favorites
- **Delete**: Remove prompts you no longer need

#### 4. Context Enhancement
Automatically add relevant context from your workspace

#### Execute Terminal Command

```bash
curl -X POST "http://localhost:8080/terminal/execute" \
  -H "Content-Type: application/json" \
  -d '{"command": "npm install", "working_directory": "/path/to/project", "timeout": 60}'
```

#### Get Command Suggestions

```bash
curl -X POST "http://localhost:8080/terminal/suggest" \
  -H "Content-Type: application/json" \
  -d '{"task_description": "install project dependencies", "working_directory": "/path/to/project"}'
```

#### Stream Command Execution

```bash
curl -X POST "http://localhost:8080/terminal/execute-stream" \
  -H "Content-Type: application/json" \
  -d '{"command": "npm run build", "stream": true}' \
  --no-buffer
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   VS Code       │    │   Web Interface │    │   CLI Scripts   │
│   Extension     │    │   (Future)      │    │   & Tools       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      API Gateway          │
                    │  (Port 8080/8082)         │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐    ┌───────────▼──────────┐    ┌────────▼────────┐
│ Vector Index   │    │    Preprocessor      │    │   Connector     │
│ (Port 8001)    │    │    (Port 8003)       │    │   (Port 8002)   │
│ - FAISS        │    │ - Python AST         │    │ - File Scanner  │
│ - Embeddings   │    │ - JS/TS Regex        │    │ - Encoding      │
│ - Search       │    │ - Markdown           │    │ - Filtering     │
└────────────────┘    └──────────────────────┘    └─────────────────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐    ┌───────────▼──────────┐    ┌────────▼────────┐
│  Web Fetcher   │    │ Terminal Executor    │    │  LLM Providers  │
│  (Port 8004)   │    │    (Port 8006)       │    │ (External APIs) │
│ - URL Fetch    │    │ - Safe Execution     │    │ - Ollama        │
│ - Caching      │    │ - Command Validation │    │ - OpenAI        │
│ - Rate Limit   │    │ - Process Management │    │ - Anthropic     │
└────────────────┘    └──────────────────────┘    └─────────────────┘
                                  │
                      ┌───────────▼──────────┐
                      │     LLM Adapters     │
                      │  - Ollama           │
                      │  - LM Studio        │
                      │  - OpenAI           │
                      │  - Anthropic        │
                      └─────────────────────┘
```

### Data Flow

1. **Ingestion**: Connector → Preprocessor → Vector Index
2. **Query**: API Gateway → Vector Index + Web Fetcher → LLM → Response
3. **Terminal Execution**: API Gateway → Terminal Executor → Command Execution → Response
4. **Command Suggestions**: API Gateway → LLM → Terminal Command Suggestions
5. **VS Code**: Extension → API Gateway → Services → Response → Webview

## 🔒 Privacy & Security

### Privacy Modes

- **Local**: All processing happens locally, no external API calls
- **Hybrid**: Local processing with remote LLM fallback
- **Remote**: Uses remote LLMs for generation

### Security Features

- Environment variable configuration (no secrets in code)
- JWT-based authentication (example API)
- Input validation and sanitization
- Rate limiting and request size limits
- CORS configuration
- Docker container isolation

### Data Handling

- **Code Analysis**: Processed locally, only relevant snippets sent to LLMs
- **Vector Storage**: Stored in local Docker volumes
- **Web Cache**: Cached locally with configurable TTL
- **Logs**: Structured logging with sensitive data filtering

## 🧪 Testing

### Run All Tests

```bash
make test
```

### Individual Test Suites

```bash
# Python unit tests
pytest tests/ -v

# Service integration tests
docker-compose up -d
python scripts/test_llm.py

# VS Code extension tests
cd vscode-extension && npm test

# Linting and formatting
make lint
make format
```

### Acceptance Tests

```bash
# Test complete workflow
make dev                                    # ✅ Services start
make ingest-example                        # ✅ Ingestion works
make query-example --q "API_TOKEN"        # ✅ Query returns results
python scripts/test_llm.py               # ✅ LLM adapters work
```

## 🎯 Acceptance Criteria Validation

The following acceptance tests validate that ContextForge meets all requirements:

### ✅ Core Functionality Tests

```bash
# 1. Services start successfully
make dev
curl -f http://localhost:8080/health

# 2. Example ingestion works
make ingest-example
# Should output: "✅ Ingested X chunks from examples/small-repo"

# 3. Query returns local file results
make query-example --q "API_TOKEN"
# Should return results with file paths from examples/small-repo

# 4. LLM provider is configured and working
# Verify your LLM provider (Ollama, OpenAI, etc.) is running
make query-example --q "test"
# Should return results with LLM-generated insights

# 5. VS Code extension installs and works
cd vscode-extension && npm run package
code --install-extension contextforge-1.0.0.vsix
# Use Ctrl+Shift+I to ingest, Ctrl+Shift+C to query
```

### ✅ Technical Requirements

- **Monorepo Structure**: ✅ Complete with services, scripts, examples
- **Docker Compose**: ✅ All services containerized and orchestrated
- **Makefile**: ✅ Common commands for dev, test, build, clean
- **Unit Tests**: ✅ Comprehensive test suite with pytest
- **CI/CD**: ✅ GitHub Actions workflow with multi-stage testing
- **VS Code Extension**: ✅ Functional extension with webview and commands
- **Documentation**: ✅ README with step-by-step instructions
- **Example Data**: ✅ Complete small-repo example with multiple languages
- **CLI Helpers**: ✅ Scripts for ingestion, querying, and LLM testing

## 📚 Documentation

### Core Documentation
- **[Architecture Guide](docs/ARCHITECTURE.md)**: System design and components
- **[API Reference](docs/API_REFERENCE.md)**: Complete API documentation
- **[VS Code Extension](vscode-extension/README.md)**: Extension usage guide
- **[Data Privacy](DATA_PRIVACY.md)**: Privacy and security details

### Remote Agent Architecture (Planned Feature)
- **[Architecture Overview](docs/REMOTE_AGENT_ARCHITECTURE.md)**: Distributed agent system design with diagrams and patterns
- **[Implementation Guide](docs/REMOTE_AGENT_IMPLEMENTATION_GUIDE.md)**: Step-by-step implementation from Phase 1 to Phase 3
- **[Usage Guide](docs/REMOTE_AGENT_USAGE_GUIDE.md)**: Practical examples and API usage patterns
- **[Deployment Guide](docs/REMOTE_AGENT_DEPLOYMENT_GUIDE.md)**: Docker Compose, Kubernetes, and cloud deployment
- **[Quick Reference](docs/REMOTE_AGENT_QUICK_REFERENCE.md)**: Quick commands and troubleshooting

## 🛠️ Development

### Project Structure

```
contextforge/
├── services/                 # Microservices
│   ├── api_gateway/         # Main API and orchestration
│   ├── vector_index/        # FAISS vector search
│   ├── preprocessor/        # Language-aware chunking
│   ├── connector/           # File system integration
│   ├── web_fetcher/         # Web search and caching
│   └── terminal_executor/   # Safe command execution
├── vscode-extension/        # VS Code integration
├── scripts/                 # CLI utilities
├── examples/               # Example data and repos
├── tests/                  # Test suites
├── docs/                   # Documentation
└── .github/workflows/      # CI/CD pipeline
```

### Adding New Features

1. **New Language Support**: Extend `lang_chunkers.py`
2. **New LLM Provider**: Add adapter to `llm_client.py`
3. **New Search Provider**: Extend `search_adapter.py`
4. **New Endpoints**: Add to `api_gateway/app.py`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 🚀 Deployment

### Production Considerations

- Use PostgreSQL instead of SQLite for scalability
- Configure Redis for caching and session storage
- Set up proper logging and monitoring
- Use secrets management for API keys
- Configure reverse proxy (nginx) for SSL termination
- Set up backup and disaster recovery

### Environment Variables

See `.env.example` for complete configuration options:

- **LLM Configuration**: `LLM_PRIORITY`, API keys
- **Search Configuration**: `ENABLE_WEB_SEARCH`, search API keys
- **Privacy Settings**: `PRIVACY_MODE`
- **Service URLs**: Individual service endpoints
- **Logging**: `LOG_LEVEL`, `LOG_FORMAT`
- **Auto-Terminal**: Configure automatic command execution settings

### Auto-Terminal Configuration

Configure auto-terminal execution in VS Code settings:

```json
{
  "contextforge.autoTerminalMode": false,
  "contextforge.autoTerminalTimeout": 30,
  "contextforge.autoTerminalWhitelist": [
    "git status",
    "git log --oneline -10",
    "npm test",
    "npm run test",
    "python -m pytest",
    "pytest",
    "ls",
    "pwd",
    "cat package.json",
    "python --version",
    "node --version",
    "npm --version"
  ]
}
```

**Security Considerations:**
- Only enable auto-terminal mode if you trust the AI responses
- Carefully review your whitelist - only include safe, read-only commands
- Commands not in the whitelist will be blocked
- All executions are logged and displayed in the webview
- Use timeouts to prevent long-running commands

## 📚 Documentation

### Core Documentation

- **[Architecture Guide](docs/ARCHITECTURE.md)**: System design and component overview
- **[API Reference](docs/API_REFERENCE.md)**: Complete API endpoint documentation
- **[Remote Agent Architecture](docs/REMOTE_AGENT_ARCHITECTURE.md)**: Distributed agent system design (planned feature)

### Remote Agent Support (Planned)

ContextForge is designed to support distributed processing through a Remote Agent Architecture. This planned feature will enable:

- **Horizontal Scaling**: Distribute workloads across multiple machines
- **Load Balancing**: Intelligent task distribution across agents
- **Fault Tolerance**: Automatic failover and recovery
- **Specialization**: Deploy specialized agents for specific tasks

For detailed information about the planned remote agent architecture, including system design, communication patterns, deployment strategies, and implementation roadmap, see [Remote Agent Architecture Documentation](docs/REMOTE_AGENT_ARCHITECTURE.md).

## 🤝 Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join community discussions
- **Documentation**: Comprehensive guides in `/docs`
- **Examples**: Working examples in `/examples`

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FAISS**: Facebook AI Similarity Search
- **sentence-transformers**: Sentence embedding models
- **FastAPI**: Modern Python web framework
- **Ollama**: Local LLM inference platform
- **VS Code**: Extensible code editor

---

**ContextForge** - Intelligent code context at your fingertips 🔍✨
