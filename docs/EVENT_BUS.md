# Event Bus Guide

## Overview

The **Event Bus** is a lightweight in-process pub/sub system that replaces point-to-point HTTP calls between services. It provides:

- **Low latency** - In-memory async communication
- **Decoupling** - Services don't need to know about each other
- **Tracing** - Structured logging for debugging event flows
- **Simplicity** - No external message broker required

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Service   │         │  Event Bus  │         │   Service   │
│      A      │────────▶│             │────────▶│      B      │
│ (Publisher) │ publish │  (In-Proc)  │ deliver │ (Subscriber)│
└─────────────┘         └─────────────┘         └─────────────┘
```

## Event Types

```python
from services.core.event_bus import EventType

# Indexing events
EventType.INDEX_STARTED
EventType.INDEX_UPDATED
EventType.INDEX_COMPLETED
EventType.INDEX_FAILED

# Query events
EventType.QUERY_RECEIVED
EventType.QUERY_COMPLETED
EventType.QUERY_FAILED

# LLM events
EventType.LLM_REQUEST
EventType.LLM_RESPONSE
EventType.LLM_ERROR

# Agent events
EventType.AGENT_STARTED
EventType.AGENT_COMPLETED
EventType.AGENT_FAILED

# System events
EventType.SERVICE_STARTED
EventType.SERVICE_STOPPED
EventType.HEALTH_CHECK
```

## Usage

### Publishing Events

```python
from services.core.event_bus import get_event_bus, Event, EventType
from datetime import datetime

# Get the global event bus
bus = get_event_bus()

# Create and publish an event
event = Event(
    type=EventType.INDEX_UPDATED,
    payload={
        "repo_path": "/path/to/repo",
        "files_indexed": 150,
        "chunks_created": 1200
    },
    source="vector_index_service",
    trace_id="req-12345"  # Optional: for request correlation
)

await bus.publish(event)
```

### Subscribing to Events

```python
from services.core.event_bus import get_event_bus, Event, EventType

bus = get_event_bus()

# Define an async handler
async def on_index_updated(event: Event):
    """Handle index update events."""
    print(f"Index updated: {event.payload['files_indexed']} files")
    print(f"Source: {event.source}")
    print(f"Trace ID: {event.trace_id}")

# Subscribe to event type
bus.subscribe(EventType.INDEX_UPDATED, on_index_updated)
```

### Unsubscribing

```python
# Unsubscribe when no longer needed
bus.unsubscribe(EventType.INDEX_UPDATED, on_index_updated)
```

## Real-World Examples

### Example 1: Vector Index Service

```python
# services/vector_index/app.py
from services.core.event_bus import get_event_bus, Event, EventType

bus = get_event_bus()

@app.post("/index")
async def index_repository(request: IndexRequest):
    # Publish start event
    await bus.publish(Event(
        type=EventType.INDEX_STARTED,
        payload={"repo_path": request.path},
        source="vector_index"
    ))
    
    try:
        # Do indexing...
        result = await do_indexing(request.path)
        
        # Publish completion event
        await bus.publish(Event(
            type=EventType.INDEX_COMPLETED,
            payload={
                "repo_path": request.path,
                "files_indexed": result.file_count,
                "duration_seconds": result.duration
            },
            source="vector_index"
        ))
        
        return result
        
    except Exception as e:
        # Publish failure event
        await bus.publish(Event(
            type=EventType.INDEX_FAILED,
            payload={
                "repo_path": request.path,
                "error": str(e)
            },
            source="vector_index"
        ))
        raise
```

### Example 2: Metrics Service Subscriber

```python
# services/metrics/app.py
from services.core.event_bus import get_event_bus, Event, EventType

bus = get_event_bus()

async def track_index_metrics(event: Event):
    """Track indexing metrics."""
    if event.type == EventType.INDEX_COMPLETED:
        await record_metric(
            "index_duration",
            event.payload["duration_seconds"],
            tags={"repo": event.payload["repo_path"]}
        )

async def track_llm_metrics(event: Event):
    """Track LLM usage metrics."""
    if event.type == EventType.LLM_RESPONSE:
        await record_metric(
            "llm_tokens",
            event.payload.get("total_tokens", 0),
            tags={"model": event.payload.get("model")}
        )

# Subscribe to events
bus.subscribe(EventType.INDEX_COMPLETED, track_index_metrics)
bus.subscribe(EventType.LLM_RESPONSE, track_llm_metrics)
```

### Example 3: Notification Service

```python
# services/notifications/app.py
from services.core.event_bus import get_event_bus, Event, EventType

bus = get_event_bus()

async def notify_on_failure(event: Event):
    """Send notifications on failures."""
    if event.type in [EventType.INDEX_FAILED, EventType.AGENT_FAILED]:
        await send_notification(
            title=f"{event.type.value}",
            message=event.payload.get("error", "Unknown error"),
            severity="error"
        )

# Subscribe to all failure events
bus.subscribe(EventType.INDEX_FAILED, notify_on_failure)
bus.subscribe(EventType.AGENT_FAILED, notify_on_failure)
bus.subscribe(EventType.LLM_ERROR, notify_on_failure)
```

## Structured Logging & Tracing

The event bus automatically logs all events with structured data:

```json
{
  "event": "event_published",
  "event_type": "index.updated",
  "source": "vector_index_service",
  "trace_id": "req-12345",
  "subscriber_count": 2,
  "payload_keys": ["repo_path", "files_indexed", "chunks_created"],
  "timestamp": "2025-01-23T10:30:00Z"
}
```

### Following Event Flows

Use `trace_id` to follow a request through the system:

```bash
# Filter logs by trace ID
grep "req-12345" logs/contextforge.log | jq .
```

## Statistics

```python
# Get event bus statistics
stats = bus.get_stats()
print(stats)
# {
#     "total_event_types": 15,
#     "total_subscribers": 8,
#     "event_counts": {
#         "index.updated": 42,
#         "query.completed": 156,
#         "llm.response": 89
#     },
#     "error_counts": {
#         "index.failed": 2,
#         "llm.error": 1
#     }
# }
```

## Benefits vs HTTP Calls

| Aspect | HTTP Calls | Event Bus |
|--------|-----------|-----------|
| Latency | 5-50ms | <1ms |
| Coupling | Tight (URLs, ports) | Loose (event types) |
| Debugging | Multiple logs | Single trace |
| Scalability | Network limited | In-memory |
| Reliability | Network failures | No network |

## Best Practices

1. **Use trace_id** - Pass through requests for correlation
2. **Keep payloads small** - Event bus is in-memory
3. **Handle errors** - Subscribers should not throw
4. **Async handlers** - All handlers must be async
5. **Unsubscribe** - Clean up when services stop

