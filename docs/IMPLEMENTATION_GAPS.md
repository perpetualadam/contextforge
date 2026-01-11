# ContextForge Implementation Gaps

**Document Version:** 1.1
**Date:** 2026-01-11
**Status:** Implementation Complete (Gaps 1-4, 6)

---

## Overview

This document specifies the missing components in ContextForge that must be implemented to achieve a stable, predictable agent system.

## Implementation Status

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| 1 | Context Schema & Validation | Critical | ✅ **COMPLETE** |
| 2 | Context Mutation Controls | Critical | ✅ **COMPLETE** |
| 3 | Debugging Agent | High | ✅ **COMPLETE** |
| 4 | Coordinator Safeguards | Medium | ✅ **COMPLETE** |
| 5 | Testing Agent Improvements | Low | ⏳ Pending |
| 6 | Index Module Separation | Low | ✅ **COMPLETE** |
| 7 | Schema/Type Safety (Pydantic) | Medium | ⏳ Pending |

---

## Completed Implementations

### 1. Context Schema & Validation ✅

**Location:** `services/core/__init__.py`

Added:
- `ContextType` enum with known context types
- `ContextScope` enum (global, agent, session)
- `Context` frozen dataclass with mandatory fields: `type`, `provenance`, `id`, `scope`, `created_at`
- `validate_context()` function for validation

### 2. Context Mutation Controls ✅

**Location:** `services/core/__init__.py`

Added:
- `ContextBundle` now uses tuples internally for immutability
- `contexts` property returns copies to prevent external mutation
- `add_context()` generates IDs and tracks in mutation log
- Backwards compatible with existing `contexts=` parameter

### 3. Debugging Agent ✅

**Location:** `services/core/__init__.py`

Added:
- `DiagnosticConfig` dataclass for configuration
- `DebuggingAgent` class with:
  - Context counting by type and agent
  - Lineage tracing from mutation log
  - Stale context detection
  - Contradiction detection
  - Health assessment
  - `format_report()` for human-readable output

### 4. Coordinator Safeguards ✅

**Location:** `services/core/__init__.py`

Added:
- `CoordinatorConfig` dataclass with configurable limits
- Exception classes: `CoordinatorError`, `RecursionLimitError`, `ContextLimitError`, `AgentTimeoutError`, `LoopDetectedError`
- `CoordinatorAgent` enhanced with:
  - `invoke_agent()` method with safety checks
  - Loop detection via content hashing
  - Recursion depth limiting
  - Context count limiting
  - Agent invocation timeout
  - Scope filtering
  - Invocation history tracking

### 6. Index Module Separation ✅

**Location:** `services/index/__init__.py`

Extracted code indexing functionality into a dedicated module:

**Classes:**
- `CodeFragment` - Dataclass representing indexed code units (functions, classes, modules)
- `IndexStats` - Dataclass with indexing statistics
- `CodeIndex` - Main indexing class with incremental, metadata-first indexing

**Features:**
- **Incremental Indexing**: Hash-based change detection to only re-index modified files
- **Multi-Language Support**: Python (AST), JavaScript/TypeScript (regex), with fallback for other languages
- **Symbol Extraction**: Functions, classes, modules with docstrings and line numbers
- **Dependency Tracking**: Extract imports and track dependencies between files
- **Persistence**: Save/load index to JSON files for fast startup
- **Search**: Symbol name, partial match, and path-based search

**Backwards Compatibility:**
- All classes are re-exported from `services/core` for backwards compatibility
- New code should import directly from `services/index`

**Test Coverage:** 39 tests in `tests/test_index.py`

---

## Remaining Work

### 5. Testing Agent Improvements (Low Priority)

Add structured `test_result` context type with pass/fail/skip counts.

### 7. Schema/Type Safety (Medium Priority)

Add Pydantic `ContextModel` for runtime validation at API boundaries.

---

## Usage Examples

### Creating Validated Contexts

```python
from services.core import Context, ContextType, validate_context

# Create directly
ctx = Context(
    type=ContextType.ANALYSIS.value,
    provenance="reasoning",
    content={"result": "analysis complete"}
)

# Validate from dict
ctx = validate_context({
    "type": "analysis",
    "provenance": "reasoning"
})
```

### Using Debugging Agent

```python
from services.core import DebuggingAgent, ContextBundle

agent = DebuggingAgent()
bundle = ContextBundle(contexts=[...])
result = await agent.invoke(bundle)

# Or get a human-readable report
print(agent.format_report(bundle))
```

### Coordinator with Safeguards

```python
from services.core import CoordinatorAgent, CoordinatorConfig

config = CoordinatorConfig(
    max_depth=5,
    max_contexts=500,
    agent_timeout_seconds=30.0
)
coord = CoordinatorAgent(config=config)
coord.register_agent(my_agent)

result = await coord.invoke_agent("my_agent", bundle)
```

### Using the Code Index

```python
from services.index import CodeIndex, get_code_index

# Create a new index
index = CodeIndex(storage_path="/path/to/storage")

# Index a repository
stats = index.index_repository(
    "/path/to/repo",
    extensions=['.py', '.js', '.ts'],
    incremental=True  # Only re-index changed files
)
print(f"Indexed {stats.total_files} files, {stats.total_symbols} symbols")

# Search for symbols
results = index.search("UserService", top_k=10)
for result in results:
    print(f"{result['type']} {result['symbol']} in {result['path']}")

# Get dependencies for a file
deps = index.get_dependencies("src/api/handler.py")
print(f"Dependencies: {deps}")

# Get files that depend on a module
dependents = index.get_dependents("utils")
print(f"Files using utils: {dependents}")

# Use the global singleton
global_index = get_code_index("/path/to/storage")
```

