"""
Event types and event data structures for ScrapeGraphAI.
"""

from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import json


class EventType(str, Enum):
    """Standard event types emitted by ScrapeGraphAI."""

    # Graph lifecycle events
    GRAPH_STARTED = "graph.started"
    GRAPH_COMPLETED = "graph.completed"
    GRAPH_FAILED = "graph.failed"

    # Node lifecycle events
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"

    # Data events
    DATA_EXTRACTED = "data.extracted"
    DATA_TRANSFORMED = "data.transformed"

    # Scraping events
    SCRAPING_STARTED = "scraping.started"
    SCRAPING_COMPLETED = "scraping.completed"
    SCRAPING_FAILED = "scraping.failed"
    SCRAPING_RETRY = "scraping.retry"

    # Progress events
    PROGRESS_UPDATE = "progress.update"

    # Custom events
    CUSTOM = "custom"


@dataclass
class Event:
    """Represents a single event in the system."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Context information
    graph_id: Optional[str] = None
    graph_name: Optional[str] = None
    node_name: Optional[str] = None

    # Event data
    data: Dict[str, Any] = field(default_factory=dict)

    # Error information (for failure events)
    error: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "graph_id": self.graph_id,
            "graph_name": self.graph_name,
            "node_name": self.node_name,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
