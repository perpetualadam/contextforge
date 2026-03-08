# Retrieval Configuration Guide

This document describes ContextForge's retrieval pipeline — from AST-aware chunking through embedding, code-graph indexing, hybrid search, task-scoped retrieval, and graph expansion.

## Architecture Overview

```
Ingestion Pipeline:
  Connector (scan files)
    → Preprocessor (tree-sitter AST chunking + relationship extraction)
      → Vector Index (embed with configurable model + store in FAISS)
        → Code Graph (import/call/inheritance edges)
        → BM25 Lexical Index

Search Pipeline:
  Query + TaskScope
    → Embed query (with QUERY_PREFIX)
    → Dense search (FAISS)  ─┐
    → Lexical search (BM25)  ├─ Hybrid fusion (RRF)
                              ↓
    → Task-scope boost (chunk-type + content-type scoring)
    → Graph expansion (follow code relationships)
    → Final ranked results
```

## 1. AST-Aware Chunking

The preprocessor now uses **tree-sitter** by default to chunk code into semantic units — functions, classes, methods, and import blocks — rather than splitting at arbitrary character boundaries.

### How It Works

When a file is processed via `/process` or `/chunk`:
1. `ChunkerFactory` checks if tree-sitter supports the file's language.
2. If yes, `TreeSitterChunker` parses the AST and extracts semantic nodes.
3. Each chunk includes rich metadata: `chunk_type`, `symbol_name`, `start_line`/`end_line`, AST positions, and **relationships** (imports, calls, inheritance, containment).
4. If tree-sitter doesn't support the language, it falls back to the regex-based chunker.

### Supported Languages (14)

Python, JavaScript, TypeScript, Java, Rust, Go, C/C++, C#, Ruby, PHP, Kotlin, Julia, HTML, CSS.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_CHUNK_SIZE` | `512` | Minimum chunk size in characters |
| `MAX_CHUNK_SIZE` | `4096` | Maximum chunk size in characters |
| `DEFAULT_CHUNK_SIZE` | `2048` | Default target chunk size |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |

The `use_tree_sitter` flag (default `true`) can be set per request:

```bash
curl -X POST http://localhost:8003/process \
  -H "Content-Type: application/json" \
  -d '{
    "files": [...],
    "use_tree_sitter": true
  }'
```

Set `use_tree_sitter: false` to force regex-based chunking.

### Chunk Metadata

Each chunk produced by tree-sitter includes:

```json
{
  "text": "def authenticate(user, password): ...",
  "meta": {
    "file_path": "src/auth.py",
    "chunk_type": "function",
    "symbol_name": "authenticate",
    "parent_name": "AuthService",
    "start_line": 42,
    "end_line": 67,
    "language": "python",
    "start_byte": 1024,
    "end_byte": 2048,
    "relationships": [
      {"type": "CALLS", "target": "hash_password"},
      {"type": "CALLS", "target": "db.query"},
      {"type": "IMPORTS", "target": "hashlib"}
    ]
  }
}
```

---

## 2. Embedding Models

ContextForge uses a **model-agnostic embedding layer** — any sentence-transformers-compatible model works as a drop-in replacement via environment variables.

### Default Models

| Model | Role | Dimension | Use Case |
|-------|------|-----------|----------|
| `all-mpnet-base-v2` | Primary (general text) | 768 | Documentation, comments, prose |
| `nomic-ai/CodeRankEmbed` | Code-specific | 768 | Source code, functions, classes |

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Primary model for general text |
| `CODE_EMBEDDING_MODEL` | `nomic-ai/CodeRankEmbed` | Code-specific embedding model |
| `USE_CODE_EMBEDDINGS` | `true` | Route code content to the code model |
| `QUERY_PREFIX` | `""` (empty) | Prefix prepended to search queries |
| `DOCUMENT_PREFIX` | `""` (empty) | Prefix prepended to documents during indexing |

### Using Asymmetric Models

Many modern embedding models require different prefixes for queries vs. documents. Check the model card on Hugging Face and set the prefixes accordingly:

```bash
# Example for CodeRankEmbed / Nomic models
QUERY_PREFIX="search_query: "
DOCUMENT_PREFIX="search_document: "

# Example for Jina Embeddings
QUERY_PREFIX="Represent the search query: "
DOCUMENT_PREFIX="Represent the code snippet: "
```

### Swapping Models

To use a different model, just change the env var:

```bash
# Use a larger model for better accuracy
CODE_EMBEDDING_MODEL=Salesforce/SFR-Embedding-Code-2B_R

# Use a smaller model for faster indexing
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Models are auto-downloaded from Hugging Face Hub on first startup. For offline use, pre-download with `huggingface-cli download <model-name>` and set the env var to the local path.

**Important**: Changing the embedding model requires re-indexing. The system auto-detects the embedding dimension and will warn if a loaded index has a different dimension than the current model.

### Recommended Code Embedding Models

| Model | Params | Dim | License | Notes |
|-------|--------|-----|---------|-------|
| `nomic-ai/CodeRankEmbed` | 137M | 768 | Apache 2.0 | Default, good quality/size ratio |
| `jinaai/jina-embeddings-v3` | 570M | 1024 | CC-BY-NC 4.0 | Multilingual |
| `Salesforce/SFR-Embedding-Code-2B_R` | 2B | 3072 | Apache 2.0 | Best accuracy, requires GPU |
| `BAAI/bge-large-en-v1.5` | 335M | 1024 | MIT | Strong general-purpose alternative |

---

## 3. Hybrid Search

Hybrid retrieval combines dense vector search with BM25 lexical search using Reciprocal Rank Fusion (RRF).

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HYBRID_SEARCH_ENABLED` | `true` | Enable hybrid (dense + lexical) search |
| `DENSE_WEIGHT` | `0.7` | Weight for dense vector search |
| `LEXICAL_WEIGHT` | `0.3` | Weight for BM25 lexical search |
| `RECENCY_BOOST_ENABLED` | `true` | Prioritize recently indexed content |
| `RECENCY_BOOST_FACTOR` | `0.1` | Maximum boost factor |

### Tuning

```bash
# Better recall (balanced)
DENSE_WEIGHT=0.5
LEXICAL_WEIGHT=0.5

# Exact identifier matches (API names, variables)
DENSE_WEIGHT=0.3
LEXICAL_WEIGHT=0.7

# Semantic understanding (conceptual queries)
DENSE_WEIGHT=0.9
LEXICAL_WEIGHT=0.1
```

---

## 4. Code Graph

The **Code Graph** tracks structural relationships between indexed chunks — function calls, imports, class inheritance, and containment — as a lightweight directed graph stored alongside the FAISS index.

### What It Tracks

| Edge Type | Example | Extracted From |
|-----------|---------|----------------|
| `IMPORTS` | `auth.py` imports `hashlib` | Import statements in AST |
| `CALLS` | `login()` calls `hash_password()` | Function call nodes in AST |
| `INHERITS` | `AdminUser` inherits `BaseUser` | Class definition base classes |
| `CONTAINS` | `UserService` contains `authenticate()` | Methods inside class bodies |

### How It Works

1. **During indexing**: The preprocessor extracts `relationships` from each AST chunk. The vector index stores these as graph edges in `data/code_graph.json`.
2. **During search**: When `expand_graph: true` is set, search results are enriched with related chunks (callers, callees, parent classes) at a reduced score (0.6x).

### Storage

The graph is persisted as `data/code_graph.json` and loaded/saved alongside the FAISS index.

---

## 5. Task-Scoped Retrieval

Different tasks need different retrieval strategies. The `task_scope` parameter adjusts chunk scoring and graph expansion based on what you're doing.

### Available Scopes

| Scope | Preferred Chunks | Content Boost | Graph Expand | Edge Types | Depth |
|-------|------------------|---------------|--------------|------------|-------|
| `find_bugs` | function, method | code | Yes | CALLS, IMPORTS | 1 |
| `explain` | class, function, module | documentation, code | Yes | CONTAINS, INHERITS | 2 |
| `refactor` | function, class, method | code, test | Yes | CALLS, INHERITS, IMPORTS | 2 |
| `test` | function, class | test, code | Yes | CALLS, IMPORTS | 1 |
| `general` | (none) | (none) | No | — | 0 |

### How It Works

1. **Chunk-type boost**: Chunks whose `chunk_type` matches the scope's `preferred_chunk_types` get a **1.2x** score multiplier.
2. **Content-type boost**: Chunks whose `content_type` matches get a **1.1x** multiplier.
3. **Graph expansion**: If the scope enables it, related chunks are appended via the code graph using the specified edge types and depth.

### API Usage

```bash
# Query API — pass task_scope
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "potential security vulnerabilities in auth",
    "task_scope": "find_bugs"
  }'

# Direct vector search — full control
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user authentication",
    "top_k": 10,
    "task_scope": "explain",
    "expand_graph": true,
    "graph_depth": 2,
    "graph_edge_types": ["CONTAINS", "INHERITS"]
  }'
```

### Adding Custom Scopes

Edit `services/vector_index/task_scopes.py`:

```python
TASK_SCOPES["my_scope"] = {
    "preferred_chunk_types": ["function"],
    "boost_content_types": ["code"],
    "graph_expand": True,
    "graph_edge_types": ["CALLS"],
    "graph_depth": 1,
    "query_prefix_override": None,
}
```

---

## 6. Scalability Limits

All validation limits and timeouts are configurable via environment variables for large-model support.

### API Request Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_QUERY_LENGTH` | `100000` | Max query/task description length (chars) |
| `MAX_PROMPT_LENGTH` | `2000000` | Max LLM prompt length (~500k tokens) |
| `MAX_CONTEXT_LENGTH` | `500000` | Max context field length (chars) |
| `MAX_OUTPUT_TOKENS` | `131072` | Max output tokens (128k) |
| `DEFAULT_OUTPUT_TOKENS` | `512` | Default output tokens per request |

### Timeout Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_TIMEOUT` | `300` | LLM HTTP request timeout (seconds) |
| `LLM_REQUEST_TIMEOUT` | `300` | API gateway LLM timeout |
| `INGEST_PREPROCESS_TIMEOUT` | `300` | Preprocessing step timeout |
| `INGEST_INDEX_TIMEOUT` | `600` | Vector indexing step timeout |
| `SERVICE_REQUEST_TIMEOUT` | `60` | General inter-service timeout |
| `VECTOR_SEARCH_TIMEOUT` | `60` | RAG pipeline search timeout |

### Safety Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `SAFETY_MAX_TOKENS` | `2000000` | Max tokens per agent operation |
| `SAFETY_MAX_FILES` | `50` | Max files per operation |
| `SAFETY_MAX_LOOPS` | `10` | Max loop iterations |
| `SAFETY_TIMEOUT` | `600` | Agent operation timeout (seconds) |
| `PROMPT_BUILDER_MAX_TOKENS` | `32768` | Prompt builder token budget |
| `MAX_CONTEXT_TOKENS` | `32768` | Hierarchical retrieval token limit |

### Using Large Models (e.g., 600B+)

ContextForge supports arbitrarily large models. If you have the infrastructure:

```bash
# Point to your model via any supported provider
OLLAMA_MODEL=llama-3-600b
LLM_TIMEOUT=600

# Or use a cloud provider with a large model
OPENAI_API_KEY=sk-...
# Set model via the /llm/generate endpoint's "model" field

# Raise limits for large context windows
MAX_OUTPUT_TOKENS=1000000
MAX_PROMPT_LENGTH=10000000
SAFETY_MAX_TOKENS=10000000
PROMPT_BUILDER_MAX_TOKENS=500000
```

---

## 7. Search API Reference

### POST /search (Vector Index — port 8001)

```json
{
  "query": "user authentication",
  "top_k": 10,
  "expand_graph": false,
  "graph_depth": 1,
  "graph_edge_types": ["CALLS", "IMPORTS"],
  "task_scope": "general"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query |
| `top_k` | int | 10 | Number of results |
| `expand_graph` | bool | false | Expand results via code graph |
| `graph_depth` | int | 1 | Graph traversal depth |
| `graph_edge_types` | list[str] | [] | Edge types to follow (IMPORTS, CALLS, INHERITS, CONTAINS) |
| `task_scope` | string | "general" | Task scope key |

### Response

```json
{
  "query": "user authentication",
  "results": [
    {
      "text": "def authenticate_user(...)...",
      "score": 0.85,
      "dense_score": 0.82,
      "lexical_score": 0.45,
      "recency_boost": 0.08,
      "chunk_id": "src/auth.py#3#a1b2c3d4",
      "content_type": "code",
      "meta": {
        "file_path": "src/auth.py",
        "chunk_type": "function",
        "symbol_name": "authenticate_user",
        "relationships": [...]
      },
      "rank": 1
    }
  ],
  "search_type": "hybrid",
  "graph_expanded": false,
  "task_scope": null,
  "total_results": 10
}
```

### POST /query (API Gateway — port 8080)

```json
{
  "query": "How does authentication work?",
  "max_tokens": 512,
  "top_k": 10,
  "task_scope": "explain",
  "enable_web_search": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Question to answer |
| `max_tokens` | int | 512 | Max LLM output tokens (up to `MAX_OUTPUT_TOKENS`) |
| `top_k` | int | 10 | Context chunks to retrieve |
| `task_scope` | string | null | Task scope (find_bugs, explain, refactor, test) |
| `enable_web_search` | bool | null | Include web search results |

---

## 8. Troubleshooting

### "Dimension mismatch" warning on startup

You changed the embedding model but have an existing index built with a different model. Clear and re-index:

```bash
curl -X DELETE http://localhost:8001/index/clear
curl -X POST http://localhost:8080/ingest -d '{"path": "/your/repo"}'
```

### Tree-sitter not chunking my files

Check that tree-sitter supports the language and the dependency is installed. The preprocessor logs which chunker is used per file. Force regex-only with `use_tree_sitter: false`.

### Graph expansion returning empty results

The code graph is populated during indexing. If you indexed before the code graph feature was added, clear and re-index.

### Slow indexing with large models

Large embedding models (2B+ params) are slower to encode. Options:
- Use GPU: ensure `torch` with CUDA is installed in the vector-index container
- Batch size: the system processes chunks in batches automatically
- Use a smaller model for development: `EMBEDDING_MODEL=all-MiniLM-L6-v2`

### High memory usage

- Disable code embeddings: `USE_CODE_EMBEDDINGS=false`
- Use a smaller model: `EMBEDDING_MODEL=all-MiniLM-L6-v2`
- Reduce HNSW neighbors: `FAISS_HNSW_NEIGHBORS=16`

---

## 9. Cross-Encoder Re-Ranking

After hybrid search returns candidate results, an optional cross-encoder re-ranks them for higher relevance. This is especially effective for queries where BM25 and dense scores disagree.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RERANK_ENABLED` | `false` | Enable cross-encoder re-ranking |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Re-ranking model |
| `RERANK_TOP_K` | `50` | Candidates to re-rank (search retrieves this many, returns `top_k`) |

### How It Works

1. Hybrid search retrieves `RERANK_TOP_K` candidates (default 50).
2. Each candidate is scored by the cross-encoder against the original query.
3. Results are re-sorted by cross-encoder score.
4. The top `top_k` results are returned.

### Enabling

```bash
RERANK_ENABLED=true
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

For code-specific re-ranking, use a code-trained cross-encoder if available.

---

## 10. Token Budgeting

The RAG pipeline enforces a token budget to ensure context fits within the LLM's context window.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_CONTEXT_BUDGET` | `16384` | Max tokens allocated for retrieved context |
| `PROMPT_BUILDER_MAX_TOKENS` | `32768` | Total prompt budget (includes system prompt + context + query) |
| `MAX_CONTEXT_TOKENS` | `32768` | Hierarchical retriever budget |

### How It Works

The `_budget_contexts()` function in the RAG pipeline:

1. Takes the list of ranked contexts from search.
2. Estimates token count for each chunk (characters / 4 approximation).
3. Greedily adds chunks until the budget is exhausted.
4. Returns only the chunks that fit.

This prevents prompt truncation or LLM errors from overly long contexts.

---

## 11. Hierarchical Retrieval

For large codebases, the hierarchical retriever performs multi-stage retrieval: module-level, then file-level, then symbol-level.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_CONTEXT_TOKENS` | `32768` | Total token budget for hierarchical retrieval |

### How It Works

1. **Stage 1 (Module)**: Retrieve top modules relevant to the query.
2. **Stage 2 (File)**: Within those modules, retrieve relevant files.
3. **Stage 3 (Symbol)**: Within those files, retrieve specific functions/classes.
4. **Budget enforcement**: At each stage, results are trimmed to fit the remaining token budget.

This avoids the problem of retrieving scattered, low-relevance chunks from unrelated parts of a large codebase.

---

## 12. Editor Context

The RAG pipeline accepts editor state from the VS Code extension to improve context selection.

### Editor Context Fields

| Field | Source | Description |
|-------|--------|-------------|
| `current_file` | Active editor | Currently open file path |
| `current_selection` | Editor selection | Selected code text |
| `open_files` | Tab group | All open file paths |
| `cursor_position` | Cursor | Line and column |
| `git_diff` | `git diff` | Staged and unstaged changes |
| `recent_files` | History | Recently viewed files |

### How It's Used

- **Current file** is boosted in search results (higher relevance score).
- **Selection** is prepended to the query for better semantic matching.
- **Git diff** provides change awareness for code review and bug-finding queries.
- **Open files** are used as secondary context signals.

### API Usage

Editor context is automatically gathered by the VS Code extension and sent with every `/query`, `/chat`, `/completion`, and `/inline-edit` request.

---

## 13. Incremental Indexing on Save

Files are automatically re-indexed when saved in VS Code, keeping the search index up to date.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `contextforge.incrementalIndexing` | `true` | Enable file-save indexing |

### How It Works

1. The VS Code extension listens for `onDidSaveTextDocument` events.
2. After a 2-second debounce, it sends the saved file to `POST /ingest` with a single-file path.
3. The preprocessor re-chunks the file and the vector index updates the embeddings.
4. Stale chunks for the old version of the file are replaced.

This means you never need to manually re-ingest after making changes.
