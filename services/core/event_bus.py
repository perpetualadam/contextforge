"""
Lightweight in-process event bus for ContextForge.

Replaces point-to-point HTTP calls with async event-driven communication.
Includes structured logging for event flow tracing.
"""

import asyncio
import logging
import structlog
from enum import Enum
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# Use structlog for structured event tracing
logger = structlog.get_logger(__name__)


class EventType(Enum):
    """Event types for inter-service communication."""
    
    # Indexing events
    INDEX_STARTED = "index.started"
    INDEX_UPDATED = "index.updated"
    INDEX_COMPLETED = "index.completed"
    INDEX_FAILED = "index.failed"
    
    # Query events
    QUERY_RECEIVED = "query.received"
    QUERY_COMPLETED = "query.completed"
    QUERY_FAILED = "query.failed"
    
    # LLM events
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"
    
    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    
    # System events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    HEALTH_CHECK = "health.check"


@dataclass
class Event:
    """
    Event object passed through the event bus.
    
    Attributes:
        type: Event type
        payload: Event data
        source: Service/component that emitted the event
        timestamp: When the event was created
        trace_id: Optional trace ID for request correlation
        metadata: Additional metadata
    """
    type: EventType
    payload: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            "type": self.type.value,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "metadata": self.metadata
        }


class EventBus:
    """
    Lightweight in-process event bus.
    
    Decouples services while keeping everything in-memory for low latency.
    Includes structured logging for debugging event flows.
    """
    
    def __init__(self):
        """Initialize event bus."""
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_count: Dict[EventType, int] = defaultdict(int)
        self._error_count: Dict[EventType, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Async function to call when event is published
        """
        self._subscribers[event_type].append(handler)
        logger.info(
            "event_subscription",
            event_type=event_type.value,
            handler=handler.__name__,
            total_subscribers=len(self._subscribers[event_type])
        )
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.info(
                "event_unsubscription",
                event_type=event_type.value,
                handler=handler.__name__
            )
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
        """
        async with self._lock:
            self._event_count[event.type] += 1
        
        handlers = self._subscribers.get(event.type, [])
        
        # Log event publication with trace context
        logger.info(
            "event_published",
            event_type=event.type.value,
            source=event.source,
            trace_id=event.trace_id,
            subscriber_count=len(handlers),
            payload_keys=list(event.payload.keys())
        )
        
        if not handlers:
            logger.debug(
                "event_no_subscribers",
                event_type=event.type.value,
                source=event.source
            )
            return
        
        # Execute all handlers concurrently
        results = await asyncio.gather(
            *[self._execute_handler(handler, event) for handler in handlers],
            return_exceptions=True
        )
        
        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                async with self._lock:
                    self._error_count[event.type] += 1
                
                logger.error(
                    "event_handler_error",
                    event_type=event.type.value,
                    handler=handlers[i].__name__,
                    error=str(result),
                    trace_id=event.trace_id
                )
    
    async def _execute_handler(self, handler: Callable, event: Event) -> Any:
        """Execute a single event handler with logging."""
        handler_name = handler.__name__
        
        logger.debug(
            "event_handler_start",
            handler=handler_name,
            event_type=event.type.value,
            trace_id=event.trace_id
        )
        
        try:
            result = await handler(event)
            
            logger.debug(
                "event_handler_complete",
                handler=handler_name,
                event_type=event.type.value,
                trace_id=event.trace_id
            )
            
            return result
        except Exception as e:
            logger.error(
                "event_handler_exception",
                handler=handler_name,
                event_type=event.type.value,
                error=str(e),
                trace_id=event.trace_id
            )
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_event_types": len(self._subscribers),
            "total_subscribers": sum(len(handlers) for handlers in self._subscribers.values()),
            "event_counts": {k.value: v for k, v in self._event_count.items()},
            "error_counts": {k.value: v for k, v in self._error_count.items()}
        }


# Global singleton event bus
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

