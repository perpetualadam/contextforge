# Retrieval Quality Configuration Guide

This document describes the enhanced retrieval features in ContextForge, including hybrid search, embedding models, and smart chunking.

## Overview

ContextForge v2.0 includes significant improvements to retrieval quality:

- **Dual Embedding Models**: Primary model for general text + CodeBERT for code
- **Hybrid Retrieval**: Combines dense vector search with BM25 lexical search
- **Recency Boost**: Prioritizes recently indexed content
- **Smart Chunking**: 512-1024 token chunks with 50-100 token overlap

## Configuration

### Environment Variables

All settings can be configured via environment variables in `docker-compose.yml` or `.env` file.

#### Vector Index Service

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Primary embedding model |
| `CODE_EMBEDDING_MODEL` | `microsoft/codebert-base` | Code-specific embedding model |
| `USE_CODE_EMBEDDINGS` | `true` | Enable code-specific embeddings |
| `HYBRID_SEARCH_ENABLED` | `true` | Enable hybrid (dense + lexical) search |
| `DENSE_WEIGHT` | `0.7` | Weight for dense vector search (0-1) |
| `LEXICAL_WEIGHT` | `0.3` | Weight for BM25 lexical search (0-1) |
| `RECENCY_BOOST_ENABLED` | `true` | Enable recency boost for recent content |
| `RECENCY_BOOST_FACTOR` | `0.1` | Maximum boost factor for recent items |

#### Preprocessor Service

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_CHUNK_SIZE` | `512` | Minimum chunk size in characters (~128 tokens) |
| `MAX_CHUNK_SIZE` | `4096` | Maximum chunk size in characters (~1024 tokens) |
| `DEFAULT_CHUNK_SIZE` | `2048` | Default target chunk size (~512 tokens) |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks (~50 tokens) |
| `MAX_OVERLAP` | `400` | Maximum overlap allowed (~100 tokens) |

## Embedding Models

### Primary Model: all-mpnet-base-v2

- **Dimension**: 768
- **Quality**: Highest quality general-purpose embeddings
- **Use case**: Documentation, comments, natural language

### Code Model: microsoft/codebert-base

- **Dimension**: 768
- **Quality**: Optimized for source code understanding
- **Use case**: Python, JavaScript, TypeScript, and other code files

The system automatically selects the appropriate model based on file extension.

## Hybrid Retrieval

Hybrid retrieval combines two search strategies:

### 1. Dense Vector Search (70% weight by default)

Uses embedding similarity to find semantically related content. Excellent for:
- Finding conceptually similar code
- Understanding intent behind queries
- Handling synonyms and paraphrases

### 2. BM25 Lexical Search (30% weight by default)

Uses keyword matching with TF-IDF scoring. Excellent for:
- Exact function/class name matches
- Specific variable names
- API endpoint names

### Result Fusion

Results are combined using Reciprocal Rank Fusion (RRF), which:
- Merges rankings from both search methods
- Prioritizes documents that rank well in both
- Handles score normalization automatically

## Recency Boost

Recent content receives a boost to prioritize:
- Recently modified files
- New code additions
- Fresh documentation

Boost formula: `score * (1 + boost_factor * exp(-age_hours / 24))`

## Smart Chunking

### Token-Based Sizing

Chunks are sized for optimal embedding quality:
- **512-1024 tokens**: Sweet spot for transformer models
- **~4 characters per token**: Approximate ratio

### Semantic Boundaries

Chunks respect code structure:
- Function boundaries
- Class definitions
- Import blocks
- Docstrings and comments

### Enhanced Metadata

Each chunk includes rich metadata:
- `content_type`: test, config, documentation, code
- `module_context`: file name, directory, package
- `symbols`: extracted function/class names
- `indexed_at`: timestamp for recency boost

## API Usage

### Search with Hybrid Retrieval

```python
# Enable hybrid search (default)
results = index.search(
    query="user authentication function",
    top_k=10,
    enable_hybrid=True,
    recency_boost=True
)

# Dense-only search
results = index.search(
    query="user authentication function",
    enable_hybrid=False
)
```

### Response Format

```json
{
  "query": "user authentication function",
  "results": [
    {
      "text": "def authenticate_user(...)...",
      "score": 0.85,
      "dense_score": 0.82,
      "lexical_score": 0.45,
      "recency_boost": 0.08,
      "content_type": "code",
      "meta": {...},
      "rank": 1
    }
  ],
  "search_type": "hybrid",
  "recency_boost_applied": true
}
```

## Performance Tuning

### For Better Recall

```bash
DENSE_WEIGHT=0.5
LEXICAL_WEIGHT=0.5
```

### For Exact Matches

```bash
DENSE_WEIGHT=0.3
LEXICAL_WEIGHT=0.7
```

### For Semantic Understanding

```bash
DENSE_WEIGHT=0.9
LEXICAL_WEIGHT=0.1
```

### Disable Code Embeddings (faster)

```bash
USE_CODE_EMBEDDINGS=false
```

## Troubleshooting

### High Memory Usage

- Disable code embeddings: `USE_CODE_EMBEDDINGS=false`
- Use smaller embedding model: `EMBEDDING_MODEL=all-MiniLM-L6-v2`

### Slow Indexing

- Reduce chunk size: `DEFAULT_CHUNK_SIZE=1024`
- Disable hybrid search during bulk indexing

### Poor Exact Match Results

- Increase lexical weight: `LEXICAL_WEIGHT=0.5`
- Ensure hybrid search is enabled

