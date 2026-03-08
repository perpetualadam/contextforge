# ContextForge

A full-featured, local-first AI coding assistant and context engine that rivals commercial tools like Cursor. ContextForge provides inline code completion, intelligent editing, multi-file agent mode, semantic search, and deep VS Code integration -- all with privacy-first design and multi-LLM support.

## Feature Matrix

| # | Feature | Status | Shortcut |
|---|---------|--------|----------|
| 1 | **Inline code completion (Tab)** | Integrated | _Auto-trigger_ |
| 2 | **Inline editing (Ctrl+K)** | Integrated | `Ctrl+K` |
| 3 | **Multi-file agent mode** | Integrated | `Ctrl+Shift+E` |
| 4 | **Diff preview before applying** | Integrated | _Automatic_ |
| 5 | **@ mentions in chat** | Integrated | `@file:` `@symbol:` `@git` |
| 6 | **Auto-context detection** | Integrated | _Automatic_ |
| 7 | **Project rules (.contextforge-rules)** | Integrated | _Auto-loaded_ |
| 8 | **Documentation indexing (@docs)** | Integrated | Command palette |
| 9 | **Image input in chat** | Integrated | Drag & drop |
| 10 | **Smart apply** | Integrated | Command palette |
| 11 | **Auto linting after AI edits** | Integrated | _Automatic_ |
| 12 | **Undo/redo AI changes** | Integrated | `Ctrl+Shift+Z` |
| 13 | **Background indexing on save** | Integrated | _Automatic_ |
| 14 | **Symbol-level navigation** | Integrated | Go-to-definition |
| 15 | **Multi-cursor AI editing** | Integrated | Command palette |
| 16 | **Web search in chat (@web)** | Integrated | _Automatic_ |
| 17 | **Git diff context in chat** | Integrated | _Automatic_ |
| 18 | **Conversation branching** | Integrated | Fork button |
| 19 | **Privacy mode toggle** | Integrated | Status bar |
| 20 | **Composer (long-running agent)** | Integrated | `Ctrl+Shift+P` |

## Quick Links

- **[QUICKSTART.md](QUICKSTART.md)** -- Get running in 5 minutes
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** -- Full API documentation
- **[docs/RETRIEVAL_CONFIGURATION.md](docs/RETRIEVAL_CONFIGURATION.md)** -- Embedding models, code graph, task scopes
- **[PUBLISHING.md](PUBLISHING.md)** -- VS Code Marketplace publishing and monetisation guide
- **[DATA_PRIVACY.md](DATA_PRIVACY.md)** -- Privacy and security details

---

## Core Capabilities

### AI-Powered Editor Features

- **Inline Code Completion (Tab)** -- Ghost-text autocomplete as you type, powered by your configured LLM. Suggests single lines or multi-line blocks. Toggle with `contextforge.enableInlineCompletion`.
- **Inline Editing (Ctrl+K)** -- Select code, type a natural language instruction, get an inline diff preview. Accept or reject with one click.
- **Multi-File Agent Mode** -- Describe a task, the AI reads your codebase, plans changes across multiple files, and shows you a diff for each file before applying.
- **Composer (Long-Running Agent)** -- A persistent background agent for complex multi-step tasks. Plans, executes, and delivers file changes with status polling.
- **Smart Apply** -- Paste a code block and the AI figures out where in the file to place it, even if line numbers have shifted. Shows diff preview before applying.
- **Multi-Cursor AI Editing** -- Describe a pattern-based edit and the AI applies changes at every matching location simultaneously.

### Context Engine

- **Auto-Context Detection** -- Automatically detects which files and symbols are relevant based on your editor state (current file, selection, open tabs, cursor position).
- **@ Mentions in Chat** -- Type `@file:path`, `@symbol:name`, `@folder:dir`, `@web:query`, `@docs:label`, or `@git:diff` to attach specific context.
- **Project Rules** -- Create a `.contextforge-rules` file in your workspace root to set coding standards, conventions, and instructions that the AI follows for every request.
- **Documentation Indexing** -- Index external library docs (API references, framework guides) and search them with `@docs:label`.
- **Git Diff Context** -- The current `git diff` is automatically included as context in all queries and chat messages.
- **Background Indexing** -- Files are incrementally re-indexed on save (2-second debounce) so the index stays fresh.

### Search & Retrieval

- **AST-Aware Chunking** -- Tree-sitter support for 14 languages. Code is chunked into semantic units (functions, classes, imports), not arbitrary character splits.
- **Hybrid Search** -- Dense vector search (FAISS) combined with BM25 lexical search using Reciprocal Rank Fusion.
- **Code Graph** -- Tracks imports, function calls, class inheritance, and containment as graph edges for relationship-aware retrieval.
- **Task-Scoped Retrieval** -- Different search strategies per task: `find_bugs`, `explain`, `refactor`, `test`.
- **Cross-Encoder Re-Ranking** -- Optional re-ranking with a cross-encoder model for higher relevance.
- **Hierarchical Retrieval** -- Multi-stage module-to-file-to-function retrieval for large codebases.
- **Token Budgeting** -- Context is trimmed to fit within the LLM's context window (configurable via `RAG_CONTEXT_BUDGET`).

### Editor Integration

- **Diff Preview** -- All AI edits show as a side-by-side diff that you accept or reject before changes are applied.
- **Undo/Redo AI Changes** -- Every AI edit creates a checkpoint. Restore any previous state via `Ctrl+Shift+Z`.
- **Auto Linting** -- After AI edits, the extension checks for lint errors and offers to have the AI fix them automatically.
- **Symbol Navigation** -- AI-powered go-to-definition and find-references using the code graph.
- **Conversation Branching** -- Fork a chat conversation to explore alternative approaches without losing the original thread.
- **Privacy Mode** -- One-click toggle in the status bar. When enabled, code is only sent to local LLMs.

### LLM & Search Providers

- **8 LLM Providers** -- Ollama, LM Studio, OpenAI, Anthropic, Mistral, DeepSeek, Grok (xAI), Groq
- **Web Search** -- SerpAPI, Bing, Google CSE with content scraping
- **Model-Agnostic Embeddings** -- Any sentence-transformers model via env vars
- **Image Analysis** -- CLIP, BLIP, ViT for local image understanding (zero API cost)

---

## Prerequisites

- **Docker & Docker Compose** -- For running services
- **Python 3.9+** -- For development and scripts
- **Node.js 18+** -- For VS Code extension development
- **VS Code** -- For extension usage

### Optional

- **Ollama** -- Local LLM inference (recommended for privacy)
- **LM Studio** -- Alternative local LLM platform
- **API Keys** -- For cloud LLM providers (OpenAI, Anthropic, etc.)

---

## Quick Start

See **[QUICKSTART.md](QUICKSTART.md)** for a detailed step-by-step guide.

```bash
# 1. Clone and configure
git clone https://github.com/contextforge/contextforge.git
cd contextforge
cp .env.example .env
# Edit .env to set your LLM provider

# 2. Start all services
docker-compose up --build -d

# 3. Install the VS Code extension
cd vscode-extension
npm install && npm run compile && npx vsce package
code --install-extension contextforge-1.0.0.vsix

# 4. Set contextforge.apiUrl to http://localhost:8080 in VS Code settings

# 5. Ingest your workspace (Ctrl+Shift+I) and start asking questions (Ctrl+Shift+C)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  VS Code     │  Web         │  CLI         │  REST API      │
│  Extension   │  Frontend    │  Scripts     │  Clients       │
│  (20 features│  (React)     │  (Python)    │  (curl, etc.)  │
│  integrated) │              │              │                │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │                │
       └──────────────┴──────────────┴────────────────┘
                              │
               ┌──────────────▼──────────────┐
               │       API Gateway           │
               │   (Port 8080 / 8082)        │
               │                             │
               │  Core Routes:               │
               │  /query, /chat, /ingest     │
               │                             │
               │  Feature Routes:            │
               │  /completion, /inline-edit  │
               │  /agent/execute, /composer  │
               │  /smart-apply, /symbols     │
               │  /docs/index, /docs/search  │
               │  /multi-cursor-edit         │
               └──────────────┬──────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
┌──────▼───────┐    ┌─────────▼────────┐    ┌────────▼────────┐
│ Vector Index │    │   Preprocessor   │    │    Connector    │
│ (Port 8001)  │    │   (Port 8003)    │    │   (Port 8002)   │
│              │    │                  │    │                 │
│ - FAISS/HNSW │    │ - Tree-sitter    │    │ - File scanner  │
│ - BM25       │    │   AST chunking   │    │ - Encoding      │
│ - Code Graph │    │ - 14 languages   │    │ - Filtering     │
│ - Reranker   │    │ - Relationships  │    │                 │
│ - Embeddings │    │ - Regex fallback │    │                 │
└──────────────┘    └──────────────────┘    └─────────────────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
┌──────▼───────┐    ┌─────────▼────────┐    ┌────────▼────────┐
│ Web Fetcher  │    │Terminal Executor │    │  LLM Providers  │
│ (Port 8004)  │    │  (Port 8006)     │    │  (8 backends)   │
│              │    │                  │    │                 │
│ - URL fetch  │    │ - Safe execution │    │ - Ollama        │
│ - Caching    │    │ - Whitelisting   │    │ - LM Studio     │
│ - Rate limit │    │ - Process mgmt   │    │ - OpenAI        │
│              │    │                  │    │ - Anthropic     │
└──────────────┘    └──────────────────┘    │ - Mistral       │
                                            │ - DeepSeek      │
                                            │ - Grok (xAI)    │
                                            │ - Groq          │
                                            └─────────────────┘
```

### Data Flow

1. **Ingestion**: Connector (scan) -> Preprocessor (AST chunking + relationships) -> Vector Index (FAISS + Code Graph + BM25)
2. **Query/Chat**: API Gateway -> Vector Index (hybrid search + graph + reranking) + Web Search -> RAG Pipeline -> LLM -> Response
3. **Inline Completion**: Extension -> `/completion` -> LLM (fast model) -> Ghost text
4. **Inline Edit**: Extension -> `/inline-edit` -> LLM -> Diff preview -> Apply
5. **Agent Mode**: Extension -> `/agent/execute` -> Plan + per-file diffs -> Review -> Apply
6. **Composer**: Extension -> `/composer/start` -> Background thread -> Poll status -> Review changes

---

## VS Code Extension Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| Ask ContextForge | `Ctrl+Shift+C` | Query your codebase |
| Ingest Workspace | `Ctrl+Shift+I` | Index the current workspace |
| Open Chat | `Ctrl+Shift+H` | Open the AI chat panel |
| Inline Edit | `Ctrl+K` | Edit selected code with AI (requires selection) |
| Agent Mode | `Ctrl+Shift+E` | Multi-file AI editing |
| Composer | `Ctrl+Shift+P` | Long-running agent for complex tasks |
| Undo AI Change | `Ctrl+Shift+Z` | Restore a checkpoint from before an AI edit |
| Toggle Privacy | Status bar | Switch between local-only and cloud LLMs |
| Smart Apply | Command palette | Apply clipboard code at the right location |
| Multi-Cursor Edit | Command palette | AI-powered multi-position editing |
| Index Docs | Command palette | Index external documentation from a URL |
| Toggle Auto Terminal | `Ctrl+Shift+A` | Enable/disable auto command execution |
| Execute Terminal | `Ctrl+Shift+T` | Run a terminal command |
| Suggest Terminal | `Ctrl+Shift+S` | Get AI command suggestions |
| Git Status | `Ctrl+Shift+G S` | View repository status |
| Git Commit | `Ctrl+Shift+G C` | Commit with AI-generated message |
| Git Push | `Ctrl+Shift+G P` | Push to remote |
| Create PR | `Ctrl+Shift+G R` | Create a GitHub pull request |

### Chat @ Mentions

Use these in the chat input to attach specific context:

| Mention | Example | What it does |
|---------|---------|-------------|
| `@file:path` | `@file:src/auth.py` | Attaches file content |
| `@symbol:name` | `@symbol:authenticate` | Looks up symbol definition |
| `@folder:path` | `@folder:src/utils` | Lists folder contents |
| `@git` | `@git:diff` or `@git:log` | Attaches git diff or log |
| `@docs:query` | `@docs:react hooks` | Searches indexed documentation |
| `@web:query` | `@web:python async` | Triggers web search |

---

## Project Rules

Create a `.contextforge-rules` file (or `.contextforge/rules.md`) in your workspace root:

```markdown
# Project Rules for ContextForge

## Code Style
- Use TypeScript strict mode
- Prefer functional components with hooks
- Use camelCase for variables, PascalCase for components

## Architecture
- Follow clean architecture with use cases in /src/domain
- Keep API routes thin, business logic in services
- All database access through repository pattern

## Testing
- Write unit tests for all business logic
- Use React Testing Library for component tests
- Aim for 80%+ coverage
```

The rules are automatically loaded on startup and sent with every AI request (inline edit, chat, agent mode, composer).

---

## Configuration

### VS Code Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `contextforge.apiUrl` | `http://localhost:8082` | API Gateway URL |
| `contextforge.enableInlineCompletion` | `true` | Enable Tab completion |
| `contextforge.enableAutoLint` | `true` | Auto-check for lint errors after AI edits |
| `contextforge.privacyMode` | `false` | Only use local LLMs |
| `contextforge.enableWebSearch` | `true` | Include web results in context |
| `contextforge.incrementalIndexing` | `true` | Re-index files on save |
| `contextforge.autoTerminalMode` | `false` | Auto-execute AI-suggested commands |
| `contextforge.gitEnabled` | `true` | Enable Git integration |

### Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PRIORITY` | `local,cloud` | LLM backend priority |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Primary embedding model |
| `CODE_EMBEDDING_MODEL` | `nomic-ai/CodeRankEmbed` | Code-specific embeddings |
| `HYBRID_SEARCH_ENABLED` | `true` | Dense + lexical search |
| `RERANK_ENABLED` | `false` | Cross-encoder re-ranking |
| `RAG_CONTEXT_BUDGET` | `16384` | Max context tokens for RAG |
| `MAX_OUTPUT_TOKENS` | `131072` | Max LLM output tokens |
| `PRIVACY_MODE` | `true` | Default privacy setting |

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8080 (Docker) / 8082 (local) | Main orchestration API |
| Vector Index | 8001 | FAISS search, embeddings, code graph |
| Connector | 8002 | File system scanning |
| Preprocessor | 8003 | AST chunking (tree-sitter) |
| Web Fetcher | 8004 | Web search and caching |
| Terminal Executor | 8006 | Safe command execution |
| Ollama | 11434 | Local LLM inference |

---

## Privacy & Security

- **Privacy Mode** -- Toggle in the VS Code status bar. When enabled, no code leaves your machine.
- **Local-First** -- All indexing, search, and embedding happens locally.
- **JWT Auth** -- API supports JWT-based authentication.
- **Rate Limiting** -- Configurable per-endpoint rate limits.
- **CORS** -- Hardened CORS configuration.
- **Input Validation** -- All inputs validated with Pydantic models.
- **Docker Isolation** -- Each service runs in its own container.

---

## Testing

```bash
# All Python tests
pytest tests/ -v

# VS Code extension tests
cd vscode-extension && npm test

# Service integration tests
docker-compose up -d
python scripts/test_llm.py

# Linting
make lint
```

---

## Development

### Project Structure

```
contextforge/
├── services/
│   ├── api_gateway/        # Main API (core routes + feature_routes.py)
│   ├── vector_index/       # FAISS, BM25, code graph, reranker
│   ├── preprocessor/       # Tree-sitter chunking, language support
│   ├── connector/          # File system scanning
│   ├── web_fetcher/        # Web search and caching
│   ├── terminal_executor/  # Safe command execution
│   ├── core/               # Diff engine, multi-mode agent, safety
│   ├── retrieval/          # Hierarchical retriever
│   ├── config/             # Unified configuration
│   └── tools/              # File editor, task manager, diagnostics
├── vscode-extension/       # VS Code integration (20 features)
├── web-frontend/           # React web UI
├── scripts/                # CLI utilities
├── examples/               # Example repos
├── tests/                  # Test suites
├── docs/                   # Documentation
└── docker-compose.yml      # Service orchestration
```

### Adding New Features

1. **New LLM Provider** -- Add adapter to `services/api_gateway/llm_client.py`
2. **New Language** -- Add tree-sitter grammar to `services/preprocessor/lang_chunkers.py`
3. **New Embedding Model** -- Set `EMBEDDING_MODEL` env var (any sentence-transformers model)
4. **New Task Scope** -- Add to `services/vector_index/task_scopes.py`
5. **New API Endpoint** -- Add to `services/api_gateway/feature_routes.py`
6. **New VS Code Command** -- Add to `vscode-extension/src/extension.ts` and `package.json`

---

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Get running in 5 minutes |
| [PUBLISHING.md](PUBLISHING.md) | VS Code Marketplace + monetisation |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Full API endpoint documentation |
| [docs/RETRIEVAL_CONFIGURATION.md](docs/RETRIEVAL_CONFIGURATION.md) | Embeddings, code graph, task scopes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design overview |
| [DATA_PRIVACY.md](DATA_PRIVACY.md) | Privacy and security details |
| [docs/REMOTE_AGENT_ARCHITECTURE.md](docs/REMOTE_AGENT_ARCHITECTURE.md) | Distributed agent system |

---

## License

MIT License -- see [LICENSE](LICENSE) for details.

## Acknowledgments

- **FAISS** -- Facebook AI Similarity Search
- **Tree-sitter** -- Incremental parsing for 14+ languages
- **sentence-transformers** -- Embedding models
- **FastAPI** -- Modern Python web framework
- **Ollama** -- Local LLM inference

---

**ContextForge** -- A complete AI coding assistant you own and control.
