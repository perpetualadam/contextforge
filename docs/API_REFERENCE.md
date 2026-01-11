# ContextForge API Reference

## Base URL
```
http://localhost:8080
```

## Authentication
Currently, ContextForge operates without authentication for local development. In production deployments, implement appropriate authentication mechanisms.

## Common Response Format

### Success Response
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2024-01-01T00:00:00Z",
    "latency_ms": 150,
    "version": "1.0.0"
  }
}
```

### Error Response
```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": { ... },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Core Endpoints

### Query System

#### POST /query
Main question answering endpoint using RAG pipeline.

**Request Body:**
```json
{
  "query": "How does authentication work in this codebase?",
  "max_tokens": 512,
  "top_k": 5,
  "enable_web_search": true
}
```

**Parameters:**
- `query` (string, required): The question to answer
- `max_tokens` (integer, optional): Maximum tokens for LLM response (default: 512, max: 4096)
- `top_k` (integer, optional): Number of context chunks to retrieve (default: 5, max: 20)
- `enable_web_search` (boolean, optional): Enable web search for additional context (default: true)

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
        "chunk_id": "auth_1",
        "start_line": 10,
        "end_line": 25
      },
      "rank": 1
    }
  ],
  "web_results": [
    {
      "title": "Authentication Best Practices",
      "snippet": "Learn about secure authentication...",
      "url": "https://example.com/auth",
      "source": "serpapi",
      "content": "Full page content...",
      "fetched_at": "2024-01-01T00:00:00Z"
    }
  ],
  "meta": {
    "llm_backend": "ollama",
    "total_contexts": 5,
    "total_web_results": 3,
    "latency_ms": 1250,
    "tokens_used": 487
  }
}
```

### Repository Ingestion

#### POST /ingest
Ingest a local repository into the vector index.

**Request Body:**
```json
{
  "path": "/path/to/repository",
  "recursive": true,
  "file_patterns": ["*.py", "*.js", "*.md"],
  "exclude_patterns": ["*.pyc", "node_modules/*"]
}
```

**Parameters:**
- `path` (string, required): Absolute path to repository
- `recursive` (boolean, optional): Scan subdirectories (default: true)
- `file_patterns` (array, optional): Include patterns (default: all supported)
- `exclude_patterns` (array, optional): Exclude patterns (default: common excludes)

**Response:**
```json
{
  "files_processed": 45,
  "chunks_created": 234,
  "chunks_indexed": 234,
  "total_size": 1048576,
  "processing_time_ms": 5432,
  "files": [
    {
      "path": "src/auth.py",
      "size": 2048,
      "chunks": 5,
      "language": "python"
    }
  ]
}
```

## Search Endpoints

### Vector Search

#### POST /search/vector
Direct vector similarity search.

**Request Body:**
```json
{
  "query": "authentication function",
  "top_k": 10
}
```

**Response:**
```json
[
  {
    "text": "def authenticate_user(username, password):",
    "score": 0.95,
    "meta": {
      "source": "auth.py",
      "chunk_type": "function",
      "start_line": 10
    },
    "rank": 1
  }
]
```

### Web Search

#### POST /search/web
Search the web for additional context.

**Request Body:**
```json
{
  "query": "Python authentication best practices",
  "max_results": 5
}
```

**Response:**
```json
[
  {
    "title": "Python Authentication Guide",
    "snippet": "Learn how to implement secure authentication...",
    "url": "https://example.com/python-auth",
    "source": "serpapi"
  }
]
```

## LLM Endpoints

### Generate Response

#### POST /llm/generate
Direct LLM text generation.

**Request Body:**
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
    "model": "llama2",
    "latency_ms": 850,
    "tokens": 245
  }
}
```

### List Adapters

#### GET /llm/adapters
List available LLM adapters and their priority.

**Response:**
```json
{
  "available": ["ollama", "openai", "mock"],
  "priority": ["ollama", "openai", "mock"],
  "active": "ollama"
}
```

## Index Management

### Index Statistics

#### GET /index/stats
Get vector index statistics.

**Response:**
```json
{
  "total_vectors": 1234,
  "dimension": 384,
  "backend": "faiss",
  "memory_usage_mb": 45.6,
  "last_updated": "2024-01-01T00:00:00Z"
}
```

### Clear Index

#### DELETE /index/clear
Clear all vectors from the index.

**Response:**
```json
{
  "status": "cleared",
  "vectors_removed": 1234,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Code Index Endpoints

The code index provides symbol-based search functionality for source code.

### Code Index Statistics

#### GET /code-index/stats
Get code index statistics (symbol-based indexing).

**Response:**
```json
{
  "total_files": 150,
  "total_symbols": 1200,
  "languages": {"python": 100, "javascript": 50},
  "index_time_ms": 523,
  "last_indexed": "2024-01-01T00:00:00Z",
  "is_incremental": true,
  "files_changed": 5,
  "files_unchanged": 145
}
```

### Code Index Search

#### POST /code-index/search
Search the code index for symbols and code fragments.

**Query Parameters:**
- `query` (string, required): Search query (symbol name, partial match)
- `top_k` (integer, optional): Maximum results to return (default: 10)

**Response:**
```json
{
  "query": "UserService",
  "results": [
    {
      "symbol": "UserService",
      "type": "class",
      "path": "src/services/user.py",
      "line_start": 15,
      "line_end": 45,
      "docstring": "Service for user management."
    }
  ],
  "count": 1
}
```

## System Endpoints

### Health Check

#### GET /health
System health and status information.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0",
  "services": {
    "vector_index": "healthy",
    "preprocessor": "healthy",
    "connector": "healthy",
    "web_fetcher": "healthy",
    "llm_client": "healthy"
  },
  "uptime_seconds": 3600
}
```

### Configuration

#### GET /config
Get current system configuration.

**Response:**
```json
{
  "privacy_mode": "local",
  "enable_web_search": true,
  "llm_priority": ["ollama", "mock"],
  "max_file_size_mb": 10,
  "supported_languages": ["python", "javascript", "typescript", "markdown"]
}
```

## Error Codes

### Client Errors (4xx)

- **400 Bad Request**: Invalid request parameters
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **429 Too Many Requests**: Rate limit exceeded

### Server Errors (5xx)

- **500 Internal Server Error**: General server error
- **502 Bad Gateway**: Upstream service error
- **503 Service Unavailable**: Service temporarily unavailable
- **504 Gateway Timeout**: Upstream service timeout

## Rate Limits

- **Query Endpoint**: 60 requests per minute
- **Ingestion Endpoint**: 10 requests per minute
- **Search Endpoints**: 100 requests per minute
- **System Endpoints**: 200 requests per minute

## Usage Examples

### Basic Query
```bash
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How is user authentication implemented?",
    "max_tokens": 512
  }'
```

### Repository Ingestion
```bash
curl -X POST "http://localhost:8080/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/home/user/my-project",
    "recursive": true,
    "file_patterns": ["*.py", "*.js"]
  }'
```

### Vector Search
```bash
curl -X POST "http://localhost:8080/search/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection",
    "top_k": 5
  }'
```

### Health Check
```bash
curl "http://localhost:8080/health"
```

## SDK Examples

### Python
```python
import requests

# Query the system
response = requests.post(
    "http://localhost:8080/query",
    json={
        "query": "How does authentication work?",
        "max_tokens": 512
    }
)
result = response.json()
print(result["answer"])
```

### JavaScript
```javascript
// Query the system
const response = await fetch('http://localhost:8080/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'How does authentication work?',
    max_tokens: 512
  })
});
const result = await response.json();
console.log(result.answer);
```

### cURL Scripts
```bash
#!/bin/bash
# ingest.sh - Ingest a repository
curl -X POST "http://localhost:8080/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"$1\", \"recursive\": true}"

# query.sh - Ask a question
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$1\", \"max_tokens\": 512}"
```

## WebSocket Support (Future)

ContextForge will support WebSocket connections for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Real-time update:', data);
};
```

## Pagination

For endpoints returning large datasets, use pagination:

```json
{
  "query": "search term",
  "page": 1,
  "page_size": 20
}
```

Response includes pagination metadata:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "total_items": 100
  }
}
```

---

## Code Index Module

The `services.index` module provides incremental, metadata-first code indexing.

### Classes

#### CodeFragment
Represents a single indexed code unit (function, class, module).

```python
from services.index import CodeFragment

fragment = CodeFragment(
    type="function",           # function, class, module
    path="src/utils.py",       # File path relative to repo
    symbol="calculate_sum",    # Symbol name
    language="python",         # Programming language
    hash="abc123",             # Content hash for change detection
    start_line=10,             # Starting line number
    end_line=25,               # Ending line number
    docstring="Add two nums.", # Extracted docstring
    dependencies=["math"],     # Imported modules
    provenance="ast"           # How it was extracted
)

# Serialize to dict
data = fragment.to_dict()
```

#### IndexStats
Statistics about an indexing operation.

```python
from services.index import IndexStats

stats = IndexStats(
    total_files=50,
    total_symbols=200,
    languages={"python": 40, "javascript": 10},
    index_time_ms=1500,
    last_indexed="2026-01-11T12:00:00Z",
    is_incremental=True,
    files_changed=5,
    files_unchanged=45
)
```

#### CodeIndex
Main indexing class with search capabilities.

```python
from services.index import CodeIndex

# Create index (optionally with persistence)
index = CodeIndex(storage_path="/path/to/storage")

# Index a repository
stats = index.index_repository(
    repo_path="/path/to/repo",
    extensions=['.py', '.js', '.ts'],  # File types to index
    incremental=True,                   # Only re-index changes
    annotate=False                      # Enable LLM annotation
)

# Search for symbols
results = index.search("UserService", top_k=10)

# Get file dependencies
deps = index.get_dependencies("src/api.py")

# Get dependents of a module
dependents = index.get_dependents("utils")

# Get statistics
stats = index.get_stats()
```

### Global Singleton

```python
from services.index import get_code_index

# Get or create global index instance
index = get_code_index(storage_path="/path/to/storage")
```

### Supported Languages

| Extension | Language | Extraction Method |
|-----------|----------|-------------------|
| `.py` | Python | AST parsing |
| `.js` | JavaScript | Regex patterns |
| `.ts` | TypeScript | Regex patterns |
| `.java` | Java | Fallback (module) |
| `.go` | Go | Fallback (module) |
| `.rs` | Rust | Fallback (module) |
| `.cpp`, `.c`, `.h` | C/C++ | Fallback (module) |
| `.rb` | Ruby | Fallback (module) |
| `.php` | PHP | Fallback (module) |
| `.swift` | Swift | Fallback (module) |
| `.kt` | Kotlin | Fallback (module) |

### Backwards Compatibility

For backwards compatibility, all classes are also exported from `services.core`:

```python
# These imports are equivalent
from services.index import CodeIndex, CodeFragment, IndexStats
from services.core import CodeIndex, CodeFragment, IndexStats
```

New code should use `services.index` directly.
