# ContextForge Codebase Index

**Last Updated:** 2026-01-23  
**Version:** 1.0.0  
**Total Phases Completed:** 7/7

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Performance & Indexing](#performance--indexing)
4. [Language Support](#language-support)
5. [Security & Reliability](#security--reliability)
6. [Offline Mode](#offline-mode)
7. [Tree-sitter Integration](#tree-sitter-integration)
8. [API & Services](#api--services)
9. [Configuration](#configuration)
10. [Testing](#testing)

---

## Architecture Overview

### Design Pattern
- **Monolith-with-modules** - In-memory communication instead of microservices
- **Event-driven architecture** - Pub/sub pattern using EventBus
- **Agent-based system** - Multi-agent orchestration for code analysis
- **Fail-fast validation** - Validate at startup, not runtime

### Key Principles
- Local-first (works offline)
- Incremental indexing (only re-index changes)
- Metadata-first (AST parsing before embeddings)
- Hybrid retrieval (dense + lexical search)

---

## Core Components

### 1. Context Schema & Validation (`services/core/__init__.py`)

**ContextBundle** - Immutable context container
- Contexts: List of Context objects
- Mutation log: Tracks all changes
- Lineage tracking: Parent-child relationships

**Context Types:**
- `CODE_FRAGMENT`, `ANALYSIS`, `REVIEW`, `INDEX_SUMMARY`
- `ERROR`, `DIAGNOSTIC`, `TEST_RESULT`, `PLAN`
- `RECOMMENDATION`, `FINDINGS`, `SUGGESTIONS`
- `TASK_REQUEST`, `ORCHESTRATION_RESULT`

**Agents:**
- `CoordinatorAgent` - Orchestrates other agents with safety limits
- `IndexingAgent`, `TestingAgent`, `DebuggingAgent` - Local agents
- `ReasoningAgent`, `DocAgent`, `RefactorAgent` - Remote-preferred agents
- `CritiqueAgent`, `ReviewAgent` - Hybrid agents

### 2. Event Bus (`services/core/event_bus.py`)

**Features:**
- Lightweight in-process pub/sub
- Async event handling
- Structured logging with trace IDs
- Event statistics tracking

**Event Types:**
- Indexing: `INDEX_STARTED`, `INDEX_UPDATED`, `INDEX_COMPLETED`, `INDEX_FAILED`
- Query: `QUERY_RECEIVED`, `QUERY_COMPLETED`, `QUERY_FAILED`
- LLM: `LLM_REQUEST`, `LLM_RESPONSE`, `LLM_ERROR`
- Agent: `AGENT_STARTED`, `AGENT_COMPLETED`, `AGENT_FAILED`
- System: `SERVICE_STARTED`, `SERVICE_STOPPED`, `HEALTH_CHECK`

### 3. Execution Strategy (`services/core/execution_strategy.py`)

**Simplified from 9 to 3 strategies:**
- `LOCAL_ONLY` - All local, no network (offline mode)
- `HYBRID_AUTO` - Smart routing based on connectivity (default)
- `CLOUD_PREFERRED` - Prefer cloud, fallback to local

**ExecutionResolver:**
- Determines where agents run (local vs remote)
- Determines which LLM to use (cloud vs local)
- Provides execution decisions with reasoning

---

## Performance & Indexing

### 1. Code Index (`services/index/__init__.py`)

**CodeIndex** - Incremental, metadata-first code indexing
- **Incremental updates** - Hash-based change detection
- **AST parsing** - Python (ast), JavaScript (regex)
- **Symbol extraction** - Functions, classes, methods, imports
- **Dependency tracking** - Import graph analysis
- **Search strategies** - Exact, partial, path matching

**IndexStats:**
- Total files, symbols, dependencies
- Languages detected
- Last update timestamp

### 2. Vector Index (`services/vector_index/index.py`)

**FAISS Integration with HNSW:**
- ✅ **IndexHNSWFlat** - Approximate nearest neighbor search
- **M parameter** - Number of neighbors (default: 32)
- **efConstruction** - Index build quality (40)
- **efSearch** - Search quality (configurable via nprobe)
- **Performance** - Optimized for 100k+ vectors

**Embedding Models:**
- **Primary:** `all-mpnet-base-v2` (768 dim) - General text
- **Code:** `microsoft/codebert-base` - Code-specific embeddings
- **Auto-selection** - Based on content type

**Hybrid Retrieval:**
- **Dense search** - FAISS vector similarity
- **Lexical search** - BM25 keyword matching
- **Reciprocal Rank Fusion (RRF)** - Combines both results
- **Weights** - Dense: 0.7, Lexical: 0.3 (configurable)

**Recency Boosting:**
- Boosts recently modified files
- Configurable boost factor (default: 0.1)
- Time-based decay

### 3. Parallel Indexing (`services/orchestrator/__init__.py`)

**ModuleAgent:**
- Indexes individual modules
- Parallel execution with semaphore
- Task result tracking

**Orchestrator:**
- Coordinates multiple ModuleAgents
- Configurable concurrency (default: 4)
- Result aggregation and ranking

---

## Language Support

### Supported Languages (15+)

**Tree-sitter Support (Phase 7):**
- Python, JavaScript, TypeScript, Java, Rust, Go
- C++, C, C#, Ruby, PHP, Kotlin, Julia, HTML, CSS

**Regex-based Chunkers:**
- Python (AST + regex), JavaScript/TypeScript, Java, Rust, Go
- Kotlin, C#, HTML, CSS, Julia, R, Swift, Markdown

### Chunking Strategies

**1. Regex Chunkers** (`services/preprocessor/lang_chunkers.py`)
- Pattern-based parsing
- Fast batch processing
- 13+ language-specific implementations

**2. Tree-sitter Chunkers** (`services/preprocessor/tree_sitter_chunker.py`)
- AST-based semantic chunking
- Preserves code structure
- Better for incremental updates

**3. Hybrid Chunker** (`services/preprocessor/hybrid_chunker.py`)
- **AUTO mode** - Tree-sitter for incremental, regex for batch
- **TREE_SITTER mode** - Force AST parsing
- **REGEX mode** - Force regex parsing
- Automatic fallback on errors


