# ContextForge API Reference

## Base URL

```
http://localhost:8080      # Docker
http://localhost:8082      # Local development
```

## Authentication

ContextForge operates without authentication for local development. In production, implement JWT-based authentication via the `Authorization: Bearer <token>` header.

---

## Core Endpoints

### POST /query

Main question-answering endpoint using the RAG pipeline.

**Request:**
```json
{
  "query": "How does authentication work in this codebase?",
  "max_tokens": 512,
  "top_k": 5,
  "task_scope": "explain",
  "enable_web_search": true,
  "project_rules": "Use TypeScript strict mode",
  "privacy_mode": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | The question to answer |
| `max_tokens` | int | 512 | Max LLM output tokens (up to `MAX_OUTPUT_TOKENS`) |
| `top_k` | int | 10 | Number of context chunks to retrieve |
| `task_scope` | string | null | `find_bugs`, `explain`, `refactor`, `test`, `general` |
| `enable_web_search` | bool | true | Include web search results |
| `project_rules` | string | null | Project-level instructions for the LLM |
| `privacy_mode` | bool | false | When true, only local LLMs are used |

**Response:**
```json
{
  "answer": "Authentication in this codebase works through...",
  "contexts": [
    {
      "text": "def authenticate_user(username, password):",
      "score": 0.95,
      "meta": {
        "source": "auth.py",
        "chunk_type": "function",
        "start_line": 10,
        "end_line": 25
      }
    }
  ],
  "web_results": [],
  "meta": {
    "llm_backend": "ollama",
    "total_contexts": 5,
    "latency_ms": 1250
  }
}
```

---

### POST /chat

Multi-turn AI chat with context, attachments, @ mentions, and project rules.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "How does the auth middleware work?"}
  ],
  "max_tokens": 1024,
  "enable_web_search": false,
  "enable_context": true,
  "attachments": [
    {
      "name": "screenshot.png",
      "type": "image/png",
      "data": "base64-encoded-data",
      "extracted_text": ""
    }
  ],
  "resolved_mentions": "@file:src/auth.py content here...",
  "project_rules": "Follow clean architecture patterns",
  "privacy_mode": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `messages` | array | required | Conversation history `[{role, content}]` |
| `max_tokens` | int | 1024 | Max response tokens |
| `enable_web_search` | bool | false | Include web results |
| `enable_context` | bool | true | Include RAG context |
| `attachments` | array | null | File attachments (base64) |
| `resolved_mentions` | string | null | Pre-resolved @ mention content |
| `project_rules` | string | null | Project-level AI instructions |
| `privacy_mode` | bool | false | Local LLMs only |

---

### POST /ingest

Ingest a local repository into the vector index.

**Request:**
```json
{
  "path": "/path/to/repository",
  "recursive": true,
  "file_patterns": ["*.py", "*.js", "*.md"],
  "exclude_patterns": ["*.pyc", "node_modules/*"]
}
```

**Response:**
```json
{
  "files_processed": 45,
  "chunks_created": 234,
  "chunks_indexed": 234,
  "total_size": 1048576,
  "processing_time_ms": 5432
}
```

---

## Feature Endpoints

### POST /completion

Inline code completion. Returns a completion string given prefix/suffix context.

**Request:**
```json
{
  "prefix": "def calculate_total(items):\n    total = 0\n    for item in items:\n        ",
  "suffix": "\n    return total",
  "language": "python",
  "file_path": "src/utils.py",
  "max_tokens": 128,
  "privacy_mode": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prefix` | string | required | Code before cursor (max 50k chars) |
| `suffix` | string | `""` | Code after cursor (max 20k chars) |
| `language` | string | `"plaintext"` | Programming language |
| `file_path` | string | null | Current file path |
| `max_tokens` | int | 128 | Max completion tokens (max 1024) |
| `privacy_mode` | bool | false | Local LLMs only |

**Response:**
```json
{
  "completion": "total += item.price * item.quantity",
  "model": "ollama",
  "latency_ms": 85
}
```

---

### POST /inline-edit

Edit a code selection based on a natural language instruction.

**Request:**
```json
{
  "code": "def add(a, b):\n    return a + b",
  "instruction": "Add type hints and a docstring",
  "language": "python",
  "file_path": "src/math.py",
  "context_before": "import math\n\n",
  "context_after": "\ndef subtract(a, b):\n    return a - b",
  "project_rules": "Use Google-style docstrings",
  "privacy_mode": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `code` | string | required | Selected code to edit (max 100k) |
| `instruction` | string | required | What to do (max 10k) |
| `language` | string | `"plaintext"` | Programming language |
| `context_before` | string | `""` | Code before selection (max 10k) |
| `context_after` | string | `""` | Code after selection (max 10k) |
| `project_rules` | string | null | Project rules |
| `privacy_mode` | bool | false | Local LLMs only |

**Response:**
```json
{
  "edited_code": "def add(a: float, b: float) -> float:\n    \"\"\"Add two numbers.\n\n    Args:\n        a: First number.\n        b: Second number.\n\n    Returns:\n        Sum of a and b.\n    \"\"\"\n    return a + b",
  "explanation": "",
  "model": "ollama"
}
```

---

### POST /agent/execute

Multi-file agent mode. Plans changes across multiple files and returns diffs.

**Request:**
```json
{
  "task": "Add input validation to all API endpoints",
  "repo_path": "/path/to/project",
  "mode": "auto",
  "project_rules": "Use Pydantic for validation",
  "privacy_mode": false,
  "dry_run": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | required | Task description (max 50k) |
| `repo_path` | string | required | Repository root path |
| `mode` | string | `"auto"` | Agent mode |
| `project_rules` | string | null | Project rules |
| `privacy_mode` | bool | false | Local LLMs only |
| `dry_run` | bool | true | Preview changes without applying |

**Response:**
```json
{
  "changes": [
    {
      "path": "src/api/routes.py",
      "diff": "--- a/src/api/routes.py\n+++ b/src/api/routes.py\n...",
      "newContent": "full file content...",
      "action": "modify"
    },
    {
      "path": "src/api/validators.py",
      "diff": "",
      "newContent": "new file content...",
      "action": "create"
    }
  ],
  "plan": "Add Pydantic models for request validation...",
  "status": "completed"
}
```

---

### POST /smart-apply

Determine where in a file to apply a code block and return the result.

**Request:**
```json
{
  "file_path": "src/utils.py",
  "file_content": "existing file content...",
  "code_block": "def new_helper():\n    return True",
  "language": "python"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_path` | string | required | Target file path |
| `file_content` | string | required | Current file content (max 500k) |
| `code_block` | string | required | Code to apply (max 100k) |
| `language` | string | `"plaintext"` | Programming language |

**Response:**
```json
{
  "start_line": 15,
  "end_line": 15,
  "replacement": "def new_helper():\n    return True",
  "new_content": "full file with code applied...",
  "confidence": 0.85
}
```

---

### POST /symbols/lookup

Look up symbol definitions or references using the code graph.

**Request:**
```json
{
  "symbol": "authenticate_user",
  "file_path": "src/auth.py",
  "line": 42,
  "kind": "definition"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | string | required | Symbol name (max 500) |
| `file_path` | string | null | File containing the symbol |
| `line` | int | null | Line number |
| `kind` | string | `"definition"` | `"definition"` or `"references"` |

**Response (definition):**
```json
{
  "location": {
    "file_path": "src/auth.py",
    "line": 10,
    "column": 0,
    "content": "def authenticate_user(username, password):..."
  },
  "references": [],
  "content": "def authenticate_user(username, password):\n    ..."
}
```

**Response (references):**
```json
{
  "location": null,
  "references": [
    {"file_path": "src/routes.py", "line": 25, "column": 4, "content": "authenticate_user(req.user, req.pass)"},
    {"file_path": "tests/test_auth.py", "line": 15, "column": 8, "content": "result = authenticate_user('admin', 'pass')"}
  ],
  "content": ""
}
```

---

### POST /multi-cursor-edit

Generate multiple simultaneous edits across a file.

**Request:**
```json
{
  "file_content": "full file content...",
  "instruction": "Rename all variables called 'tmp' to 'result'",
  "language": "python",
  "file_path": "src/processor.py"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_content` | string | required | File content (max 500k) |
| `instruction` | string | required | Edit instruction (max 10k) |
| `language` | string | `"plaintext"` | Programming language |
| `file_path` | string | null | File path |

**Response:**
```json
{
  "edits": [
    {"start_line": 5, "start_col": 4, "end_line": 5, "end_col": 7, "new_text": "result"},
    {"start_line": 8, "start_col": 12, "end_line": 8, "end_col": 15, "new_text": "result"},
    {"start_line": 12, "start_col": 8, "end_line": 12, "end_col": 11, "new_text": "result"}
  ]
}
```

Edits are sorted bottom-to-top so applying them in order preserves line numbers.

---

### POST /docs/index

Fetch and index external documentation from a URL.

**Request:**
```json
{
  "url": "https://docs.python.org/3/library/asyncio.html",
  "label": "python-asyncio",
  "recursive": true,
  "max_pages": 50
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | Documentation URL |
| `label` | string | URL | Label for later search filtering |
| `recursive` | bool | true | Follow links (future) |
| `max_pages` | int | 50 | Maximum pages to index (max 200) |

**Response:**
```json
{
  "status": "ok",
  "pages_indexed": 1,
  "chunks": 12,
  "label": "python-asyncio"
}
```

---

### POST /docs/search

Search previously indexed documentation.

**Request:**
```json
{
  "query": "how to use asyncio gather",
  "top_k": 5,
  "label": "python-asyncio"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query |
| `top_k` | int | 5 | Max results (max 20) |
| `label` | string | null | Filter by label |

**Response:**
```json
{
  "results": [
    {
      "text": "asyncio.gather(*aws, return_exceptions=False)...",
      "score": 0.89,
      "meta": {
        "source": "docs",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "label": "python-asyncio"
      }
    }
  ]
}
```

---

### POST /composer/start

Start a long-running Composer agent session.

**Request:**
```json
{
  "task": "Refactor the auth module to use OAuth2",
  "repo_path": "/path/to/project",
  "project_rules": "Use httpx for HTTP calls",
  "privacy_mode": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | required | Task description (max 50k) |
| `repo_path` | string | required | Repository root path |
| `project_rules` | string | null | Project rules |
| `privacy_mode` | bool | false | Local LLMs only |

**Response:**
```json
{
  "session_id": "a1b2c3d4",
  "state": "starting"
}
```

---

### GET /composer/status/{session_id}

Poll the status of a running Composer session.

**Response (running):**
```json
{
  "session_id": "a1b2c3d4",
  "state": "running",
  "progress": 0.45,
  "current_step": "Editing src/auth/oauth.py",
  "changes": [],
  "error": null,
  "log": [
    "Starting composer for: Refactor the auth module...",
    "Plan: Migrate from session-based auth to OAuth2...",
    "Steps: 4",
    "Step 1: Create OAuth2 client configuration"
  ]
}
```

**Response (completed):**
```json
{
  "session_id": "a1b2c3d4",
  "state": "completed",
  "progress": 1.0,
  "current_step": "Done",
  "changes": [
    {
      "path": "src/auth/oauth.py",
      "action": "create",
      "newContent": "...",
      "diff": ""
    }
  ],
  "error": null,
  "log": ["...", "Completed with 3 file change(s)"]
}
```

---

## Search Endpoints

### POST /search/vector

Direct vector similarity search with code graph expansion.

**Request:**
```json
{
  "query": "authentication function",
  "top_k": 10,
  "task_scope": "find_bugs",
  "expand_graph": true,
  "graph_depth": 1,
  "graph_edge_types": ["CALLS", "IMPORTS"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query |
| `top_k` | int | 10 | Number of results |
| `task_scope` | string | null | `find_bugs`, `explain`, `refactor`, `test` |
| `expand_graph` | bool | false | Include related code graph nodes |
| `graph_depth` | int | 1 | Traversal depth |
| `graph_edge_types` | list | `[]` | `IMPORTS`, `CALLS`, `INHERITS`, `CONTAINS` |

**Response:**
```json
{
  "query": "authentication function",
  "results": [
    {
      "text": "def authenticate_user(username, password):",
      "score": 0.95,
      "dense_score": 0.92,
      "lexical_score": 0.45,
      "chunk_id": "auth.py#3#a1b2c3d4",
      "meta": {
        "file_path": "auth.py",
        "chunk_type": "function",
        "symbol_name": "authenticate_user",
        "relationships": [
          {"type": "CALLS", "target": "hash_password"}
        ]
      }
    }
  ],
  "search_type": "hybrid",
  "graph_expanded": true,
  "total_results": 10
}
```

---

### POST /search/web

Web search for additional context.

**Request:**
```json
{
  "query": "Python authentication best practices",
  "max_results": 5
}
```

---

## LLM Endpoints

### POST /llm/generate

Direct LLM text generation.

**Request:**
```json
{
  "prompt": "Explain how JWT tokens work",
  "max_tokens": 256,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "text": "JWT (JSON Web Tokens) are a compact way to...",
  "meta": {
    "backend": "ollama",
    "model": "mistral",
    "latency_ms": 850
  }
}
```

### GET /llm/adapters

List available LLM backends and their priority.

---

## Index Management

### GET /index/stats

Vector index statistics (total vectors, dimension, memory usage).

### DELETE /index/clear

Clear all vectors from the index. Requires re-ingestion.

---

## System Endpoints

### GET /health

Health check for all services.

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "vector_index": "healthy",
    "preprocessor": "healthy",
    "connector": "healthy"
  }
}
```

### GET /config

Current system configuration.

---

## Terminal Endpoints

### POST /terminal/execute

Execute a terminal command.

```json
{
  "command": "npm install",
  "working_directory": "/path/to/project",
  "timeout": 60
}
```

### POST /terminal/suggest

Get AI-suggested commands for a task.

```json
{
  "task_description": "install project dependencies",
  "working_directory": "/path/to/project"
}
```

---

## Git Endpoints

### POST /git/commit-message

Generate an AI-powered commit message from a diff.

```json
{
  "diff": "diff --git a/src/feature.py ...",
  "staged_files": ["src/feature.py"],
  "branch": "feature/auth",
  "recent_commits": ["feat: add input validation"]
}
```

---

## File Upload

### POST /files/upload

Upload a file for AI analysis (images, PDFs, documents).

```bash
curl -X POST http://localhost:8080/files/upload \
  -F "file=@/path/to/screenshot.png"
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Invalid request parameters |
| 404 | Resource not found |
| 422 | Validation error (e.g., LLM could not parse response) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 502 | Upstream service unreachable |
| 504 | Upstream service timeout |

---

## Rate Limits

| Endpoint Group | Limit |
|---------------|-------|
| `/query`, `/chat` | 60 req/min |
| `/completion`, `/inline-edit` | 120 req/min |
| `/ingest` | 10 req/min |
| `/search/*` | 100 req/min |
| `/agent/*`, `/composer/*` | 20 req/min |
| System endpoints | 200 req/min |

---

## SDK Examples

### Python

```python
import requests

# Inline completion
resp = requests.post("http://localhost:8080/completion", json={
    "prefix": "def hello():\n    ",
    "language": "python",
    "max_tokens": 64
})
print(resp.json()["completion"])

# Multi-file agent
resp = requests.post("http://localhost:8080/agent/execute", json={
    "task": "Add error handling to all database calls",
    "repo_path": "/path/to/project",
    "dry_run": True
})
for change in resp.json()["changes"]:
    print(f"{change['action']} {change['path']}")
```

### JavaScript / TypeScript

```typescript
const response = await fetch('http://localhost:8080/completion', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prefix: 'function hello() {\n  ',
    language: 'javascript',
    max_tokens: 64
  })
});
const { completion } = await response.json();
```

### cURL

```bash
# Inline edit
curl -X POST http://localhost:8080/inline-edit \
  -H "Content-Type: application/json" \
  -d '{
    "code": "x = a + b",
    "instruction": "Add type hints",
    "language": "python"
  }'

# Start composer
curl -X POST http://localhost:8080/composer/start \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Refactor auth to use OAuth2",
    "repo_path": "/my/project"
  }'

# Poll composer status
curl http://localhost:8080/composer/status/a1b2c3d4
```
