# Multi-Mode Agent Architecture

## Overview

The ContextForge agent system has been refactored from multiple specialized agents to a **single multi-mode agent per process** with comprehensive safety mechanisms.

### Key Improvements

1. **Single Agent, Multiple Modes**: Each process runs one agent with 5 operational modes
2. **Drift Detection**: Automatic detection of external file changes
3. **Fingerprint Tracking**: File hashing and symbol tracking for consistency
4. **Diff-Based Edits**: Only operates on diffs, never overwrites unrelated code
5. **Confidence Scoring**: Per-file confidence with automatic re-grounding
6. **Loop Safety**: Prevents infinite loops and enforces resource limits
7. **Token Efficiency**: Only reads affected files + diffs

## Architecture

### Agent Modes

Each multi-mode agent supports 5 operational modes:

- **PLAN**: Task decomposition and planning (≤5 bullets)
- **IMPLEMENT**: Code implementation with diff-based edits
- **REVIEW**: Code review and static analysis
- **INDEX**: Embedding and index updates
- **TEST**: Test execution and validation

### Process Model

```
┌─────────────────────────────────────────────────────────┐
│ Remote Worker Process (Docker Container)               │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ RemoteMultiModeAgent                              │ │
│  │                                                   │ │
│  │  Modes: PLAN │ IMPLEMENT │ REVIEW │ INDEX │ TEST │ │
│  │                                                   │ │
│  │  Components:                                      │ │
│  │  • DriftDetector                                  │ │
│  │  • DiffEngine                                     │ │
│  │  • ConfidenceTracker                              │ │
│  │  • LoopDetector                                   │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Local Process (Core Service)                           │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ LocalMultiModeAgent                               │ │
│  │                                                   │ │
│  │  Modes: PLAN │ IMPLEMENT │ REVIEW │ INDEX │ TEST │ │
│  │                                                   │ │
│  │  Components:                                      │ │
│  │  • DriftDetector                                  │ │
│  │  • DiffEngine                                     │ │
│  │  • ConfidenceTracker                              │ │
│  │  • LoopDetector                                   │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Fingerprint Tracking (`services/core/fingerprint.py`)

Tracks file state with:
- **SHA256 hash**: Content verification
- **mtime**: Last modified timestamp
- **size**: File size in bytes
- **symbols**: Extracted function/class names

```python
fingerprint = capture_fingerprint("path/to/file.py")
if not fingerprint.matches_filesystem():
    # File has changed externally
    trigger_reground()
```

### 2. Drift Detection (`services/core/drift_detection.py`)

Detects external changes with severity levels:
- **NONE**: No changes
- **MINOR**: Timestamp changed, content same
- **MODERATE**: Content changed, symbols intact
- **MAJOR**: Symbols changed or file deleted

```python
drift_result = drift_detector.detect_drift(files)
if drift_result.has_drift:
    scoped_reground(drift_result.get_affected_files())
```

### 3. Diff Engine (`services/core/diff_engine.py`)

Operates only on diffs:
- Computes unified diffs
- Applies changes incrementally
- Prevents overwriting unrelated code

```python
file_diff = diff_engine.compute_diff(file_path, new_content)
success = diff_engine.apply_diff(file_diff, dry_run=False)
```

### 4. Safety Mechanisms (`services/core/safety.py`)

#### Confidence Scoring
- **100-90**: High confidence, proceed normally
- **89-80**: Medium confidence, proceed with caution
- **79-40**: Low confidence, re-read files
- **<40**: Critical, stop and request human confirmation

#### Resource Limits
- Max tool calls: 50
- Max revisions: 10
- Max tokens: 100,000
- Max files per operation: 20
- Max loop iterations: 5
- Timeout: 300 seconds

#### Loop Detection
Tracks state hashes to detect infinite loops after 3 identical states.

## Usage

### Remote Agent (Docker)

```python
from services.remote_agent.multi_mode_worker import RemoteMultiModeAgent, AgentMode

agent = RemoteMultiModeAgent(name="worker-1")

# Execute in IMPLEMENT mode
result = agent.execute(AgentMode.IMPLEMENT, {
    "target_files": ["src/module.py"],
    "changes": [{
        "file_path": "src/module.py",
        "new_content": "...",
    }]
})

if result.success:
    print(f"Applied {len(result.diffs_applied)} diffs")
else:
    print(f"Error: {result.error_message}")
```

### Local Agent (In-Process)

```python
from services.core.local_multi_mode_agent import LocalMultiModeAgent, AgentMode

agent = LocalMultiModeAgent(
    name="local-agent",
    workspace_root="/path/to/workspace"
)

# Execute in TEST mode
result = agent.execute(AgentMode.TEST, {
    "test_files": ["tests/test_module.py"],
    "test_command": "pytest -v"
})
```

### Backward Compatibility

Use adapters for existing code:

```python
from services.core.agent_adapter import create_multi_mode_agent_for_role

# Create adapter for legacy IndexingAgent
indexing_agent = create_multi_mode_agent_for_role("indexing", workspace_root)

# Execute task (automatically routes to INDEX mode)
result = indexing_agent.execute(task, agent_name="indexing")
```

## Safety Workflow

```
1. Begin Operation
   ├─ Register fingerprints for all files in scope
   ├─ Set initial confidence to 100
   └─ Reset metrics and loop detector

2. Check Drift
   ├─ Compare fingerprints with filesystem
   ├─ Detect severity (NONE/MINOR/MODERATE/MAJOR)
   └─ If drift: trigger scoped re-grounding

3. Scoped Re-Grounding
   ├─ Re-read only changed files + dependents
   ├─ Update fingerprints
   └─ Reset confidence to 100

4. Safety Check
   ├─ Check resource limits (calls, tokens, time)
   ├─ Check confidence levels
   └─ Check for loops

5. Prepare Diff
   ├─ Check drift again
   ├─ Compute diff from current state
   └─ Add to planned diffs

6. Apply Diff
   ├─ Final drift check
   ├─ Apply changes incrementally
   └─ Update fingerprint

7. End Operation
   ├─ Collect metrics and confidence scores
   ├─ Generate operation result
   └─ Clear context
```

## Migration Guide

### Old Code
```python
# Multiple specialized agents
coordinator.register_agent(IndexingAgent())
coordinator.register_agent(TestingAgent())
coordinator.register_agent(ReviewAgent())
```

### New Code
```python
# Single multi-mode agent with adapters
from services.core.agent_adapter import create_multi_mode_agent_for_role

indexing = create_multi_mode_agent_for_role("indexing", workspace_root)
testing = create_multi_mode_agent_for_role("testing", workspace_root)
review = create_multi_mode_agent_for_role("review", workspace_root)

# Or use directly
from services.core.local_multi_mode_agent import LocalMultiModeAgent, AgentMode

agent = LocalMultiModeAgent(workspace_root=workspace_root)
agent.execute(AgentMode.INDEX, task)
agent.execute(AgentMode.TEST, task)
agent.execute(AgentMode.REVIEW, task)
```

## Benefits

1. **Reduced Token Usage**: Only reads diffs and affected files
2. **Multi-Tool Safety**: Detects external changes from humans, CI, other tools
3. **Auditable**: Full execution logs and drift events
4. **Bounded Resources**: Hard limits prevent runaway operations
5. **Confidence-Driven**: Automatic re-grounding when confidence drops
6. **Loop Prevention**: Detects and stops infinite loops
7. **Backward Compatible**: Adapters work with existing code

## Testing

See `tests/test_multi_mode_agent.py` for comprehensive tests covering:
- Drift detection
- Fingerprint tracking
- Diff application
- Confidence scoring
- Loop detection
- Resource limits

