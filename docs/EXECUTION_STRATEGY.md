# Execution Strategy Guide

## Overview

ContextForge uses a **simplified execution strategy** that reduces complexity from 9 combinations (3 modes × 3 hints) to **3 clear strategies**.

## Execution Strategies

### 1. LOCAL_ONLY (Offline Mode)

**Use when:**
- No internet connection
- Privacy-critical environments
- Air-gapped systems

**Behavior:**
- All processing happens locally
- Uses Ollama/LM Studio for LLM
- No cloud API calls
- All agents run locally

**Configuration:**
```python
from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver

resolver = ExecutionResolver(ExecutionStrategy.LOCAL_ONLY)
```

**Environment:**
```bash
OPERATION_MODE=offline
```

---

### 2. HYBRID_AUTO (Default)

**Use when:**
- You want automatic cloud/local switching
- Internet may be intermittent
- Cost optimization (use local when possible)

**Behavior:**
- Automatically detects internet connectivity
- Uses cloud LLM if available and API keys configured
- Falls back to local LLM if offline
- Reasoning-heavy agents (ReasoningAgent, DocAgent, RefactorAgent, CritiqueAgent) use cloud when available
- Filesystem agents always run locally

**Configuration:**
```python
resolver = ExecutionResolver(ExecutionStrategy.HYBRID_AUTO)
```

**Environment:**
```bash
OPERATION_MODE=auto  # Default
```

---

### 3. CLOUD_PREFERRED

**Use when:**
- You want best quality results
- Internet is reliable
- Cost is not a primary concern

**Behavior:**
- Prefers cloud LLM when available
- Falls back to local if offline or no API keys
- Reasoning agents run remotely when possible
- Filesystem agents still run locally

**Configuration:**
```python
resolver = ExecutionResolver(ExecutionStrategy.CLOUD_PREFERRED)
```

**Environment:**
```bash
OPERATION_MODE=online
```

---

## Agent Execution Decisions

### Reasoning-Heavy Agents (Cloud-Preferred)

These agents benefit from cloud LLM quality:
- `ReasoningAgent` - Complex code analysis
- `DocAgent` - Documentation generation
- `RefactorAgent` - Code refactoring suggestions
- `CritiqueAgent` - Code review

### Filesystem Agents (Always Local)

These agents must run locally:
- `IndexAgent` - File indexing
- `PreprocessorAgent` - File processing
- Any agent with `requires_filesystem=True`

---

## Usage Examples

### Check Execution Decision

```python
from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver

resolver = ExecutionResolver(ExecutionStrategy.HYBRID_AUTO)

# Check if cloud LLM will be used
if resolver.should_use_cloud_llm():
    print("Using cloud LLM")
else:
    print("Using local LLM")

# Get decision for specific agent
decision = resolver.get_decision("ReasoningAgent", requires_filesystem=False)
print(f"Cloud LLM: {decision.use_cloud_llm}")
print(f"Remote execution: {decision.use_remote_agent}")
print(f"Reason: {decision.reason}")
```

### Get Strategy Status

```python
status = resolver.get_status()
print(status)
# {
#     "strategy": "auto",
#     "online": True,
#     "has_cloud_keys": True,
#     "will_use_cloud_llm": True,
#     "reasoning_agents": ["ReasoningAgent", "DocAgent", "RefactorAgent", "CritiqueAgent"]
# }
```

---

## Migration from Old System

### Before (Complex)

```python
# Old: 3 modes × 3 hints = 9 combinations
mode = OperationMode.AUTO
hint = ExecutionHint.HYBRID

# Complex resolution logic
if mode == OperationMode.AUTO:
    if hint == ExecutionHint.HYBRID:
        if check_internet():
            # ... complex logic
```

### After (Simple)

```python
# New: 3 strategies
strategy = ExecutionStrategy.HYBRID_AUTO
resolver = ExecutionResolver(strategy)

# Simple decision
decision = resolver.get_decision("ReasoningAgent")
use_cloud = decision.use_cloud_llm
```

---

## Benefits

1. **Reduced Complexity**: 3 strategies instead of 9 combinations
2. **Predictable Behavior**: Clear rules for each strategy
3. **Better Defaults**: HYBRID_AUTO works well for most users
4. **Easier Testing**: Fewer code paths to test
5. **Clearer Documentation**: Users understand the options

---

## Troubleshooting

### "Using local LLM but I want cloud"

**Check:**
1. Internet connectivity: `resolver._is_online`
2. API keys configured: `resolver._has_cloud_keys`
3. Strategy is not LOCAL_ONLY

**Fix:**
```bash
# Set cloud API key
export OPENAI_API_KEY=sk-...

# Use CLOUD_PREFERRED or HYBRID_AUTO
export OPERATION_MODE=online
```

### "Agent running remotely but I want local"

**Fix:**
```bash
# Use LOCAL_ONLY strategy
export OPERATION_MODE=offline
```

