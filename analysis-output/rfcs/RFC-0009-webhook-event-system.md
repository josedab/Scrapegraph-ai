# RFC-0009: Webhook & Event System for Async Workflows

**Status:** Draft
**Author:** ScrapeGraphAI Analysis Team
**Created:** 2025-11-20
**Based on Commit:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

## Summary

This RFC proposes implementing a webhook and event emission system for ScrapeGraphAI to enable asynchronous workflow integrations with tools like Zapier, n8n, Make, and queue systems (RabbitMQ, Redis, Kafka). Currently, scraping is tightly coupled with result processing, requiring users to wait synchronously for completion. By adding event emission at key lifecycle points, we enable async processing patterns, background job systems, and integration with modern workflow automation platforms. This will transform ScrapeGraphAI from a synchronous library into an event-driven framework that can power complex automation workflows.

## Motivation

### Current Limitations

**Problem 1: Synchronous Execution Model**

All scraping operations in ScrapeGraphAI are synchronous from the caller's perspective:

```python
# Current approach - blocks until complete
from scrapegraphai.graphs import SmartScraperGraph

scraper = SmartScraperGraph(
    prompt="Extract product details",
    source="https://example.com/products",
    config=graph_config
)

result = scraper.run()  # Blocks for 10-60 seconds
# User must wait for entire pipeline to complete
```

**Issues:**
- Long-running scrapes block API requests
- Cannot return response to user while processing continues
- Difficult to build responsive web applications
- No way to notify users when scraping completes
- Retry logic must be handled by caller

**Problem 2: No Integration with Workflow Automation**

Modern businesses use workflow automation tools extensively:
- Zapier: 6+ million users
- n8n: Open-source workflow automation
- Make (formerly Integrimat): Visual workflow builder
- IFTTT: Consumer automation platform

**Current challenges:**
- Cannot trigger workflows when scraping completes
- No way to chain ScrapeGraphAI with other services
- Manual polling required to check completion
- Difficult to build multi-step automations

**Problem 3: Tight Coupling of Concerns**

Current architecture couples scraping with result processing:

```python
# Everything happens in one call
result = scraper.run()

# No way to process incrementally or asynchronously
save_to_database(result)
send_email_notification(result)
update_cache(result)
trigger_analysis(result)
```

**Issues:**
- Cannot process results as they arrive
- All processing happens in-band
- Errors in processing affect scraping
- Cannot scale processing independently

**Problem 4: Limited Error Notification**

When scraping fails, there's no built-in notification mechanism:

```python
try:
    result = scraper.run()
except Exception as e:
    # User must implement their own error handling
    # No standard way to notify external systems
    send_slack_alert(str(e))  # Manual implementation
```

**Problem 5: No Support for Background Jobs**

Cannot easily integrate with job queue systems:

```python
# Current: Everything happens inline
def scrape_endpoint():
    result = scraper.run()  # Blocks web server
    return jsonify(result)

# Desired: Async processing
def scrape_endpoint():
    job_id = queue_scraping_job()  # Returns immediately
    return jsonify({"job_id": job_id, "status": "queued"})
```

### Why This Matters

**User Experience Impact:**
- API endpoints timeout on long scrapes (>30s)
- Users cannot get immediate feedback
- No progress updates during execution
- Poor integration with modern SaaS tools

**Business Impact:**
- Cannot build responsive applications on ScrapeGraphAI
- Difficult to integrate into existing workflows
- Limited appeal to no-code/low-code users
- Missing market opportunity (workflow automation)

**Technical Impact:**
- Difficult to scale processing independently
- Cannot leverage queue-based architectures
- Hard to implement retry logic
- Limited observability into execution

### Use Cases

**Use Case 1: E-commerce Price Monitoring**

A business wants to monitor competitor prices and update their own pricing:

```
1. Scrape competitor websites (10 minutes)
2. When complete, send results to Zapier
3. Zapier compares with internal prices
4. If competitor is cheaper, create Slack notification
5. If significant change, create Jira ticket
```

Currently impossible without custom polling infrastructure.

**Use Case 2: Content Aggregation Pipeline**

A content platform scrapes news sites and processes articles:

```
1. User submits URLs to scrape
2. API returns immediately with job ID
3. Scraping happens in background
4. On completion, webhook triggers
5. Content is analyzed by another service
6. User receives email when processed
```

Requires custom job queue implementation today.

**Use Case 3: Research Data Collection**

Researchers need to scrape academic websites periodically:

```
1. Cron job triggers scraping daily
2. Results are emitted as events
3. n8n workflow receives events
4. Data is transformed and cleaned
5. Loaded into research database
6. Team receives summary report
```

Currently requires custom glue code.

**Use Case 4: Real-time Dashboard Updates**

A monitoring dashboard shows live scraping status:

```
1. Scraping job starts
2. "scraping.started" event updates dashboard
3. "node.completed" events show progress
4. "scraping.completed" event shows final status
5. Dashboard updates in real-time via WebSockets
```

No event mechanism exists today.

## Current State

### Architecture Analysis

**Graph Execution Model**

File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`

Current execution is purely synchronous:

```python
# Lines ~200-250 (approximate)
def run(self) -> dict:
    """Execute the graph and return results."""
    state = self.initial_state.copy()

    for node in self.nodes:
        # Execute each node synchronously
        state = node.execute(state)

        # No events emitted
        # No hooks for external systems
        # Caller blocked until complete

    return state
```

**No Event Infrastructure:**
- No event emitter class
- No event types defined
- No webhook configuration
- No async callback mechanism

**Node Execution**

File: `/home/user/Scrapegraph-ai/scrapegraphai/nodes/base_node.py`

Nodes execute without lifecycle events:

```python
def execute(self, state: dict) -> dict:
    """Execute node logic."""
    # Pre-execution: no event
    result = self._execute(state)
    # Post-execution: no event
    return result
```

**Opportunities for Events:**
- Before node execution
- After node execution
- On node error
- On state changes

### Integration Points

**Current External Integrations:**

1. **LLM Providers (OpenAI, Anthropic, etc.)**
   - Uses callbacks in some cases
   - Synchronous request/response
   - No event emission

2. **Browser Automation (Playwright)**
   - No event hooks exposed
   - Cannot notify on scraping progress

3. **Document Loaders**
   - Silent execution
   - No progress events

**Missing Integrations:**
- Workflow automation platforms
- Message queues
- Webhook endpoints
- Event streaming platforms

### Configuration System

File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`

Current configuration has no event/webhook support:

```python
graph_config = {
    "llm": {...},
    "embeddings": {...},
    "verbose": True,
    # No webhook configuration
    # No event handlers
    # No callback URLs
}
```

**Needs:**
- Webhook URL configuration
- Event subscription settings
- Retry policies for webhook delivery
- Authentication for webhooks

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ScrapeGraphAI Application                     │
│                                                                  │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐            │
│  │   Graph    │───▶│   Nodes    │───▶│   State    │            │
│  └─────┬──────┘    └─────┬──────┘    └────────────┘            │
│        │                 │                                       │
│        │ emit events     │ emit events                           │
│        ▼                 ▼                                       │
│  ┌─────────────────────────────────────────────────┐            │
│  │           EventEmitter (Core)                   │            │
│  │  - Collects events from graph & nodes           │            │
│  │  - Routes to configured handlers                │            │
│  │  - Manages async delivery                       │            │
│  └──────────────────┬──────────────────────────────┘            │
│                     │                                            │
└─────────────────────┼────────────────────────────────────────────┘
                      │
          ┌───────────┴────────────┬──────────────┬──────────────┐
          ▼                        ▼              ▼              ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────┐  ┌─────────┐
│ WebhookHandler   │  │  QueueHandler    │  │ Logging │  │ Custom  │
│  - POST to URL   │  │  - Redis/RabbitMQ│  │ Handler │  │ Handler │
│  - Retry logic   │  │  - Kafka         │  │         │  │         │
│  - Auth headers  │  │  - SQS           │  │         │  │         │
└────────┬─────────┘  └────────┬─────────┘  └────┬────┘  └────┬────┘
         │                     │                  │            │
         ▼                     ▼                  ▼            ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────┐  ┌─────────┐
│  Zapier/n8n/Make │  │  Queue Systems   │  │  Files  │  │ Custom  │
│  Workflows       │  │  Background Jobs │  │  Logs   │  │ Systems │
└──────────────────┘  └──────────────────┘  └─────────┘  └─────────┘
```

### Event Types

```python
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

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
        import json
        return json.dumps(self.to_dict(), indent=2)
```

### Event Emitter Core

**Location:** `scrapegraphai/events/emitter.py`

```python
import asyncio
import logging
from typing import List, Callable, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import uuid

logger = logging.getLogger(__name__)

class EventEmitter:
    """
    Core event emission system for ScrapeGraphAI.

    Manages event handlers and dispatches events to configured destinations.
    Supports both synchronous and asynchronous handlers.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the event emitter.

        Args:
            config: Configuration dictionary with handler settings
        """
        self.config = config or {}
        self._handlers: List[EventHandler] = []
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._async_mode = self.config.get("async_delivery", True)
        self._enabled = self.config.get("events_enabled", True)

        # Initialize handlers from config
        self._initialize_handlers()

    def _initialize_handlers(self):
        """Initialize event handlers from configuration."""
        handlers_config = self.config.get("event_handlers", [])

        for handler_config in handlers_config:
            handler_type = handler_config.get("type")

            if handler_type == "webhook":
                from .handlers.webhook import WebhookHandler
                self._handlers.append(WebhookHandler(handler_config))

            elif handler_type == "queue":
                from .handlers.queue import QueueHandler
                self._handlers.append(QueueHandler(handler_config))

            elif handler_type == "log":
                from .handlers.log import LogHandler
                self._handlers.append(LogHandler(handler_config))

            elif handler_type == "custom":
                # Load custom handler from module path
                handler_class = self._load_custom_handler(handler_config.get("class"))
                self._handlers.append(handler_class(handler_config))

    def add_handler(self, handler: 'EventHandler'):
        """Add an event handler."""
        self._handlers.append(handler)

    def remove_handler(self, handler: 'EventHandler'):
        """Remove an event handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def emit(self, event: Event, blocking: bool = False):
        """
        Emit an event to all registered handlers.

        Args:
            event: The event to emit
            blocking: If True, wait for all handlers to complete (default: False)
        """
        if not self._enabled:
            return

        logger.debug(f"Emitting event: {event.event_type} (id: {event.event_id})")

        if self._async_mode and not blocking:
            # Async delivery - don't block caller
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self._emit_async(event))
            else:
                self._executor.submit(self._emit_sync, event)
        else:
            # Synchronous delivery
            self._emit_sync(event)

    def _emit_sync(self, event: Event):
        """Emit event to all handlers synchronously."""
        for handler in self._handlers:
            # Check if handler wants this event type
            if handler.should_handle(event):
                try:
                    handler.handle(event)
                except Exception as e:
                    logger.error(f"Handler {handler.__class__.__name__} failed: {e}")

    async def _emit_async(self, event: Event):
        """Emit event to all handlers asynchronously."""
        tasks = []

        for handler in self._handlers:
            if handler.should_handle(event):
                if asyncio.iscoroutinefunction(handler.handle):
                    tasks.append(handler.handle(event))
                else:
                    # Run sync handler in executor
                    tasks.append(
                        asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            handler.handle,
                            event
                        )
                    )

        # Wait for all handlers to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Handler failed: {result}")

    def shutdown(self):
        """Shutdown the event emitter and cleanup resources."""
        self._executor.shutdown(wait=True)

        for handler in self._handlers:
            if hasattr(handler, 'cleanup'):
                handler.cleanup()

    def _load_custom_handler(self, class_path: str):
        """Dynamically load a custom handler class."""
        import importlib

        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)


class EventHandler:
    """Base class for event handlers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the handler.

        Args:
            config: Handler-specific configuration
        """
        self.config = config
        self.event_types = config.get("event_types", [])  # Empty = all events

    def should_handle(self, event: Event) -> bool:
        """
        Determine if this handler should handle the event.

        Args:
            event: The event to check

        Returns:
            True if handler should process this event
        """
        # If no event types specified, handle all events
        if not self.event_types:
            return True

        # Check if event type is in handler's list
        return event.event_type.value in self.event_types or event.event_type in self.event_types

    def handle(self, event: Event):
        """
        Handle the event.

        Args:
            event: The event to handle
        """
        raise NotImplementedError("Handlers must implement handle()")

    def cleanup(self):
        """Cleanup handler resources."""
        pass
```

### Webhook Handler

**Location:** `scrapegraphai/events/handlers/webhook.py`

```python
import requests
import logging
from typing import Dict, Any, Optional
import time
from .base import EventHandler, Event

logger = logging.getLogger(__name__)

class WebhookHandler(EventHandler):
    """
    Sends events to webhook URLs via HTTP POST.

    Features:
    - Automatic retries with exponential backoff
    - Custom headers and authentication
    - Timeout configuration
    - Payload transformation
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize webhook handler.

        Config options:
            url: Webhook URL to POST to (required)
            method: HTTP method (default: POST)
            headers: Custom headers dict
            auth: Auth tuple (username, password) for basic auth
            timeout: Request timeout in seconds (default: 30)
            retry_count: Number of retries on failure (default: 3)
            retry_backoff: Backoff multiplier for retries (default: 2)
            verify_ssl: Verify SSL certificates (default: True)
            payload_template: Jinja2 template for payload customization
        """
        super().__init__(config)

        self.url = config.get("url")
        if not self.url:
            raise ValueError("Webhook handler requires 'url' in config")

        self.method = config.get("method", "POST").upper()
        self.headers = config.get("headers", {})
        self.auth = config.get("auth")
        self.timeout = config.get("timeout", 30)
        self.retry_count = config.get("retry_count", 3)
        self.retry_backoff = config.get("retry_backoff", 2)
        self.verify_ssl = config.get("verify_ssl", True)
        self.payload_template = config.get("payload_template")

        # Set default content type if not specified
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

    def handle(self, event: Event):
        """Send event to webhook URL."""
        payload = self._prepare_payload(event)

        for attempt in range(self.retry_count + 1):
            try:
                response = requests.request(
                    method=self.method,
                    url=self.url,
                    json=payload,
                    headers=self.headers,
                    auth=self.auth,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )

                response.raise_for_status()

                logger.info(
                    f"Webhook delivered successfully: {event.event_type} "
                    f"(id: {event.event_id}, status: {response.status_code})"
                )
                return

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Webhook delivery failed (attempt {attempt + 1}/{self.retry_count + 1}): {e}"
                )

                if attempt < self.retry_count:
                    # Exponential backoff
                    sleep_time = (self.retry_backoff ** attempt)
                    time.sleep(sleep_time)
                else:
                    # Final attempt failed
                    logger.error(
                        f"Webhook delivery failed after {self.retry_count + 1} attempts: "
                        f"{event.event_type} (id: {event.event_id})"
                    )

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare the webhook payload."""
        if self.payload_template:
            # Use custom template
            from jinja2 import Template
            template = Template(self.payload_template)
            import json
            return json.loads(template.render(event=event))
        else:
            # Use default event dictionary
            return event.to_dict()


class ZapierWebhookHandler(WebhookHandler):
    """Specialized webhook handler for Zapier integration."""

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare Zapier-optimized payload."""
        payload = event.to_dict()

        # Zapier-specific transformations
        # Flatten nested structures for easier field mapping
        if "data" in payload and isinstance(payload["data"], dict):
            for key, value in payload["data"].items():
                # Prefix data fields to avoid collisions
                payload[f"data_{key}"] = value

        return payload


class N8nWebhookHandler(WebhookHandler):
    """Specialized webhook handler for n8n integration."""

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare n8n-optimized payload."""
        # n8n expects specific structure for easy processing
        return {
            "event": event.event_type.value,
            "id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "body": event.data,
            "metadata": {
                "graph_id": event.graph_id,
                "graph_name": event.graph_name,
                "node_name": event.node_name,
            },
            "error": {
                "message": event.error,
                "type": event.error_type,
            } if event.error else None,
        }
```

### Queue Handler

**Location:** `scrapegraphai/events/handlers/queue.py`

```python
import logging
from typing import Dict, Any, Optional
import json
from .base import EventHandler, Event

logger = logging.getLogger(__name__)

class QueueHandler(EventHandler):
    """
    Sends events to message queue systems.

    Supported queues:
    - Redis (using redis-py)
    - RabbitMQ (using pika)
    - AWS SQS (using boto3)
    - Apache Kafka (using kafka-python)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize queue handler.

        Config options:
            queue_type: Type of queue (redis, rabbitmq, sqs, kafka)
            connection_string: Connection URL/details
            queue_name: Name of queue/topic
            **kwargs: Queue-specific options
        """
        super().__init__(config)

        self.queue_type = config.get("queue_type")
        if not self.queue_type:
            raise ValueError("Queue handler requires 'queue_type' in config")

        self.connection_string = config.get("connection_string")
        self.queue_name = config.get("queue_name", "scrapegraph_events")

        # Initialize queue connection
        self._client = self._initialize_client()

    def _initialize_client(self):
        """Initialize the appropriate queue client."""
        if self.queue_type == "redis":
            return self._initialize_redis()
        elif self.queue_type == "rabbitmq":
            return self._initialize_rabbitmq()
        elif self.queue_type == "sqs":
            return self._initialize_sqs()
        elif self.queue_type == "kafka":
            return self._initialize_kafka()
        else:
            raise ValueError(f"Unsupported queue type: {self.queue_type}")

    def _initialize_redis(self):
        """Initialize Redis client."""
        try:
            import redis
            return redis.from_url(self.connection_string)
        except ImportError:
            raise ImportError("redis package required for Redis queue handler")

    def _initialize_rabbitmq(self):
        """Initialize RabbitMQ client."""
        try:
            import pika
            params = pika.URLParameters(self.connection_string)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)
            return channel
        except ImportError:
            raise ImportError("pika package required for RabbitMQ queue handler")

    def _initialize_sqs(self):
        """Initialize AWS SQS client."""
        try:
            import boto3
            return boto3.client('sqs')
        except ImportError:
            raise ImportError("boto3 package required for SQS queue handler")

    def _initialize_kafka(self):
        """Initialize Kafka producer."""
        try:
            from kafka import KafkaProducer
            return KafkaProducer(
                bootstrap_servers=self.connection_string,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except ImportError:
            raise ImportError("kafka-python package required for Kafka queue handler")

    def handle(self, event: Event):
        """Send event to queue."""
        payload = json.dumps(event.to_dict())

        try:
            if self.queue_type == "redis":
                self._client.lpush(self.queue_name, payload)

            elif self.queue_type == "rabbitmq":
                self._client.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=payload,
                    properties=pika.BasicProperties(delivery_mode=2)
                )

            elif self.queue_type == "sqs":
                queue_url = self.config.get("queue_url")
                self._client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=payload
                )

            elif self.queue_type == "kafka":
                self._client.send(self.queue_name, event.to_dict())

            logger.debug(f"Event sent to {self.queue_type} queue: {event.event_type}")

        except Exception as e:
            logger.error(f"Failed to send event to {self.queue_type} queue: {e}")

    def cleanup(self):
        """Cleanup queue connections."""
        if self.queue_type == "rabbitmq" and self._client:
            self._client.connection.close()
        elif self.queue_type == "kafka" and self._client:
            self._client.close()
```

### Graph Integration

**Modified:** `scrapegraphai/graphs/base_graph.py`

```python
from typing import Optional
from ..events.emitter import EventEmitter, Event, EventType

class BaseGraph:
    """Base graph with event emission support."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Initialize event emitter
        events_config = config.get("events", {})
        self.event_emitter = EventEmitter(events_config) if events_config.get("enabled", False) else None

        # Generate unique graph ID
        self.graph_id = config.get("graph_id", str(uuid.uuid4()))
        self.graph_name = self.__class__.__name__

        # ... existing initialization ...

    def run(self) -> dict:
        """Execute the graph with event emission."""

        # Emit graph started event
        if self.event_emitter:
            self.event_emitter.emit(Event(
                event_type=EventType.GRAPH_STARTED,
                graph_id=self.graph_id,
                graph_name=self.graph_name,
                data={
                    "prompt": self.prompt,
                    "source": self.source,
                    "config": self._get_safe_config(),
                }
            ))

        try:
            # Execute graph
            state = self.initial_state.copy()
            total_nodes = len(self.nodes)

            for idx, node in enumerate(self.nodes):
                # Emit node started event
                if self.event_emitter:
                    self.event_emitter.emit(Event(
                        event_type=EventType.NODE_STARTED,
                        graph_id=self.graph_id,
                        graph_name=self.graph_name,
                        node_name=node.node_name,
                        data={
                            "node_type": node.__class__.__name__,
                            "progress": (idx / total_nodes) * 100,
                        }
                    ))

                try:
                    # Execute node
                    state = node.execute(state)

                    # Emit node completed event
                    if self.event_emitter:
                        self.event_emitter.emit(Event(
                            event_type=EventType.NODE_COMPLETED,
                            graph_id=self.graph_id,
                            graph_name=self.graph_name,
                            node_name=node.node_name,
                            data={
                                "node_type": node.__class__.__name__,
                                "progress": ((idx + 1) / total_nodes) * 100,
                            }
                        ))

                except Exception as e:
                    # Emit node failed event
                    if self.event_emitter:
                        self.event_emitter.emit(Event(
                            event_type=EventType.NODE_FAILED,
                            graph_id=self.graph_id,
                            graph_name=self.graph_name,
                            node_name=node.node_name,
                            error=str(e),
                            error_type=e.__class__.__name__,
                            data={"node_type": node.__class__.__name__}
                        ))
                    raise

            # Emit graph completed event
            if self.event_emitter:
                self.event_emitter.emit(Event(
                    event_type=EventType.GRAPH_COMPLETED,
                    graph_id=self.graph_id,
                    graph_name=self.graph_name,
                    data={
                        "result": self._get_safe_result(state),
                        "nodes_executed": total_nodes,
                    }
                ))

            return state

        except Exception as e:
            # Emit graph failed event
            if self.event_emitter:
                self.event_emitter.emit(Event(
                    event_type=EventType.GRAPH_FAILED,
                    graph_id=self.graph_id,
                    graph_name=self.graph_name,
                    error=str(e),
                    error_type=e.__class__.__name__,
                    stack_trace=traceback.format_exc(),
                ))
            raise

        finally:
            # Cleanup event emitter
            if self.event_emitter:
                self.event_emitter.shutdown()

    def _get_safe_config(self) -> Dict[str, Any]:
        """Get sanitized config for event emission (remove sensitive data)."""
        safe_config = self.config.copy()

        # Remove sensitive keys
        sensitive_keys = ["api_key", "password", "secret", "token"]
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = "***REDACTED***"

        return safe_config

    def _get_safe_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get sanitized result for event emission."""
        # Limit size of result in events
        max_length = self.config.get("events", {}).get("max_result_length", 1000)

        result_str = str(state.get("result", ""))
        if len(result_str) > max_length:
            result_str = result_str[:max_length] + "... (truncated)"

        return {"result_preview": result_str}
```

## Example Usage

### Example 1: Webhook Integration with Zapier

```python
from scrapegraphai.graphs import SmartScraperGraph

# Configure graph with webhook events
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "async_delivery": True,
        "event_handlers": [
            {
                "type": "webhook",
                "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
                "event_types": [
                    "graph.completed",
                    "graph.failed"
                ],
                "retry_count": 3,
                "headers": {
                    "X-Custom-Header": "my-value"
                }
            }
        ]
    }
}

# Run scraper - Zapier will be notified on completion
scraper = SmartScraperGraph(
    prompt="Extract all product prices",
    source="https://example.com/products",
    config=graph_config
)

result = scraper.run()

# Zapier receives:
# {
#   "event_type": "graph.completed",
#   "event_id": "uuid-here",
#   "timestamp": "2025-11-20T10:30:00Z",
#   "graph_name": "SmartScraperGraph",
#   "data": {
#     "result_preview": "{'products': [...]}"
#   }
# }
```

### Example 2: n8n Workflow Integration

```python
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.events.handlers.webhook import N8nWebhookHandler

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "webhook",
                "class": "scrapegraphai.events.handlers.webhook.N8nWebhookHandler",
                "url": "https://myinstance.n8n.cloud/webhook/scrapegraph",
                "event_types": ["graph.completed"]
            }
        ]
    }
}

scraper = SmartScraperGraph(
    prompt="Extract news articles",
    source="https://news.example.com",
    config=graph_config
)

result = scraper.run()

# n8n receives optimized payload:
# {
#   "event": "graph.completed",
#   "id": "uuid-here",
#   "body": { ... extracted data ... },
#   "metadata": {
#     "graph_name": "SmartScraperGraph",
#     ...
#   }
# }
```

### Example 3: Background Job Queue

```python
from scrapegraphai.graphs import SmartScraperGraph
from flask import Flask, jsonify, request
import uuid

app = Flask(__name__)

@app.route("/scrape", methods=["POST"])
def start_scraping():
    """API endpoint that starts scraping and returns immediately."""

    job_id = str(uuid.uuid4())
    url = request.json.get("url")
    prompt = request.json.get("prompt")

    # Configure to emit events to Redis queue
    graph_config = {
        "llm": {"model": "openai/gpt-4"},
        "graph_id": job_id,
        "events": {
            "enabled": True,
            "async_delivery": True,
            "event_handlers": [
                {
                    "type": "queue",
                    "queue_type": "redis",
                    "connection_string": "redis://localhost:6379",
                    "queue_name": "scraping_results",
                    "event_types": ["graph.completed", "graph.failed"]
                }
            ]
        }
    }

    # Start scraping in background thread
    import threading
    def run_scraper():
        scraper = SmartScraperGraph(
            prompt=prompt,
            source=url,
            config=graph_config
        )
        scraper.run()

    thread = threading.Thread(target=run_scraper)
    thread.start()

    # Return immediately
    return jsonify({
        "job_id": job_id,
        "status": "processing",
        "message": "Scraping started. Check job status or wait for webhook."
    })

@app.route("/job/<job_id>", methods=["GET"])
def check_job_status(job_id):
    """Check job status from Redis queue."""
    import redis
    r = redis.from_url("redis://localhost:6379")

    # Check if completion event exists for this job
    # (This is simplified - production would use proper job tracking)

    return jsonify({
        "job_id": job_id,
        "status": "completed",  # or "processing", "failed"
        "result": "..."
    })
```

### Example 4: Progress Monitoring Dashboard

```python
from scrapegraphai.graphs import SmartScraperGraph
import websocket
import json

# Dashboard receives real-time updates via WebSocket
# connected to a service that consumes events

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "webhook",
                "url": "http://localhost:8000/events",
                "event_types": [
                    "graph.started",
                    "node.started",
                    "node.completed",
                    "graph.completed"
                ]
            }
        ]
    }
}

scraper = SmartScraperGraph(
    prompt="Extract company information",
    source="https://example.com",
    config=graph_config
)

result = scraper.run()

# Dashboard receives events:
# 1. graph.started → "Scraping started..."
# 2. node.started (FetchNode) → "Fetching content... (0%)"
# 3. node.completed (FetchNode) → "Content fetched (33%)"
# 4. node.started (ParseNode) → "Parsing content... (33%)"
# 5. node.completed (ParseNode) → "Content parsed (66%)"
# 6. node.started (GenerateNode) → "Generating answer... (66%)"
# 7. node.completed (GenerateNode) → "Answer generated (100%)"
# 8. graph.completed → "Scraping completed!"
```

### Example 5: Multi-Handler Configuration

```python
from scrapegraphai.graphs import SmartScraperGraph

# Send events to multiple destinations
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "async_delivery": True,
        "event_handlers": [
            # Webhook for Zapier
            {
                "type": "webhook",
                "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
                "event_types": ["graph.completed"],
            },
            # Redis queue for background processing
            {
                "type": "queue",
                "queue_type": "redis",
                "connection_string": "redis://localhost:6379",
                "queue_name": "scraping_jobs",
                "event_types": ["graph.completed", "graph.failed"],
            },
            # File logging for audit trail
            {
                "type": "log",
                "log_file": "/var/log/scrapegraph/events.log",
                "event_types": [],  # Log all events
            },
            # Custom handler for internal monitoring
            {
                "type": "custom",
                "class": "myapp.monitoring.MetricsHandler",
                "event_types": ["node.completed", "node.failed"],
            }
        ]
    }
}

scraper = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config=graph_config
)

result = scraper.run()
# Events sent to all 4 destinations simultaneously
```

### Example 6: Custom Event Handler

```python
from scrapegraphai.events.handlers.base import EventHandler, Event
from scrapegraphai.graphs import SmartScraperGraph

class SlackNotificationHandler(EventHandler):
    """Custom handler that sends Slack notifications."""

    def __init__(self, config):
        super().__init__(config)
        self.webhook_url = config.get("slack_webhook_url")
        self.channel = config.get("channel", "#scraping-alerts")

    def handle(self, event: Event):
        """Send Slack notification."""
        import requests

        # Format message based on event type
        if event.event_type == "graph.completed":
            message = f"✅ Scraping completed: {event.graph_name}"
            color = "good"
        elif event.event_type == "graph.failed":
            message = f"❌ Scraping failed: {event.error}"
            color = "danger"
        else:
            return  # Only handle completion/failure

        payload = {
            "channel": self.channel,
            "attachments": [{
                "color": color,
                "title": message,
                "fields": [
                    {"title": "Graph ID", "value": event.graph_id, "short": True},
                    {"title": "Timestamp", "value": event.timestamp.isoformat(), "short": True}
                ]
            }]
        }

        requests.post(self.webhook_url, json=payload)

# Use custom handler
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "custom",
                "class": "myapp.handlers.SlackNotificationHandler",
                "slack_webhook_url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
                "channel": "#scraping-alerts",
                "event_types": ["graph.completed", "graph.failed"]
            }
        ]
    }
}
```

## Implementation Plan

### Phase 1: Core Event Infrastructure (Week 1-2)
**Goal:** Build foundational event system

**Tasks:**
1. Create event classes and types
   - `Event` dataclass with all fields
   - `EventType` enum with standard events
   - Serialization methods (to_dict, to_json)

2. Implement `EventEmitter` core
   - Handler registration
   - Sync and async event dispatch
   - Handler filtering by event type

3. Create base `EventHandler` class
   - Abstract interface
   - Event filtering logic
   - Cleanup lifecycle

4. Add comprehensive unit tests
   - Event serialization
   - Emitter functionality
   - Handler registration
   - Async dispatch

**Success Criteria:**
- 95% test coverage for event core
- Can emit and handle events in memory
- No external dependencies yet

### Phase 2: Basic Handlers (Week 3)
**Goal:** Implement webhook and log handlers

**Tasks:**
1. Implement `WebhookHandler`
   - HTTP POST delivery
   - Retry logic with backoff
   - Timeout handling
   - Custom headers

2. Implement `LogHandler`
   - File-based logging
   - JSON event formatting
   - Log rotation support

3. Add integration tests
   - Mock webhook server
   - Test retry logic
   - Test log file output

**Success Criteria:**
- Webhook handler can POST events
- Retries work correctly
- Log handler writes events to file

### Phase 3: Graph Integration (Week 4)
**Goal:** Integrate events into graph execution

**Tasks:**
1. Modify `BaseGraph` class
   - Add event emitter initialization
   - Emit graph lifecycle events
   - Emit node lifecycle events
   - Handle errors and emit failure events

2. Update graph configuration
   - Add events configuration schema
   - Validate event handler configs
   - Document configuration options

3. Add end-to-end tests
   - Test full graph execution with events
   - Verify all event types are emitted
   - Test multiple handlers simultaneously

**Success Criteria:**
- All graph executions emit events
- Events contain correct data
- No performance degradation

### Phase 4: Queue Handlers (Week 5)
**Goal:** Support message queue integrations

**Tasks:**
1. Implement `QueueHandler` base
   - Redis support
   - RabbitMQ support
   - SQS support (AWS)

2. Add Kafka support (optional)
   - KafkaProducer integration
   - Topic management

3. Add queue-specific tests
   - Test Redis publish
   - Test RabbitMQ delivery
   - Test SQS message sending

**Success Criteria:**
- Events can be sent to queues
- All major queue systems supported
- Optional dependencies (don't break if not installed)

### Phase 5: Workflow Tool Optimizations (Week 6)
**Goal:** Optimize for Zapier, n8n, Make

**Tasks:**
1. Create specialized webhook handlers
   - `ZapierWebhookHandler`
   - `N8nWebhookHandler`
   - `MakeWebhookHandler`

2. Add payload templates
   - Jinja2 template support
   - Platform-specific defaults

3. Create integration guides
   - Zapier integration tutorial
   - n8n workflow examples
   - Make.com setup guide

**Success Criteria:**
- Easy setup for each platform
- Optimized payloads for each tool
- Working example workflows

### Phase 6: Documentation & Examples (Week 7)
**Goal:** Comprehensive documentation

**Tasks:**
1. API documentation
   - All event types documented
   - Handler configuration reference
   - Code examples for each handler

2. Tutorial content
   - Getting started with events
   - Common use cases
   - Best practices

3. Example projects
   - Flask API with background jobs
   - Real-time dashboard
   - Multi-stage workflow

**Success Criteria:**
- Complete API reference
- 5+ working examples
- Tutorial covers all major features

### Phase 7: Production Hardening (Week 8)
**Goal:** Production-ready features

**Tasks:**
1. Error handling improvements
   - Circuit breaker for failing webhooks
   - Dead letter queue support
   - Better error reporting

2. Performance optimization
   - Batch event delivery
   - Connection pooling
   - Memory usage optimization

3. Monitoring and metrics
   - Event delivery metrics
   - Handler performance tracking
   - Error rate monitoring

**Success Criteria:**
- Handles failures gracefully
- No memory leaks
- Production monitoring in place

### Milestones

| Milestone | Completion Date | Deliverables |
|-----------|----------------|--------------|
| M1: Core Infrastructure | Week 2 | Event classes, emitter, basic handlers |
| M2: Graph Integration | Week 4 | Events emitted from all graphs |
| M3: Queue Support | Week 5 | All major queue systems supported |
| M4: Workflow Tools | Week 6 | Zapier, n8n, Make optimized |
| M5: Documentation | Week 7 | Complete docs and examples |
| M6: Production Ready | Week 8 | Hardened, monitored, deployed |

### Rollback Plan

If issues arise:
1. Events can be disabled via config (`events.enabled = false`)
2. No breaking changes to existing API
3. Async delivery can be disabled (`async_delivery = false`)
4. Individual handlers can be removed from config
5. Complete rollback: remove event emitter initialization

## Backwards Compatibility

### Breaking Changes

**None.** This RFC introduces only additive changes.

### Compatibility Strategy

1. **Opt-in by Default:**
   ```python
   # Existing code works unchanged (events disabled)
   scraper = SmartScraperGraph(
       prompt="Extract data",
       source="https://example.com",
       config={"llm": {...}}
   )

   # Must explicitly enable events
   scraper = SmartScraperGraph(
       prompt="Extract data",
       source="https://example.com",
       config={
           "llm": {...},
           "events": {"enabled": True}  # Opt-in
       }
   )
   ```

2. **No API Changes:**
   - All existing methods unchanged
   - No new required parameters
   - Return types unchanged

3. **Graceful Degradation:**
   ```python
   # If event handler fails, scraping continues
   # Events are fire-and-forget by default
   # Errors logged but don't affect execution
   ```

4. **Optional Dependencies:**
   - Event system uses only stdlib by default
   - Queue handlers require opt-in packages
   - Import errors handled gracefully

### Migration Guide

**For Library Users:**

No action required unless you want events:

```python
# Before (still works)
result = scraper.run()

# After (with events)
config["events"] = {
    "enabled": True,
    "event_handlers": [...]
}
result = scraper.run()  # Same API, now emits events
```

**For Framework Integrators:**

Add event configuration to your wrapper:

```python
class MyScraperWrapper:
    def __init__(self, webhook_url=None):
        self.config = {"llm": {...}}

        if webhook_url:
            self.config["events"] = {
                "enabled": True,
                "event_handlers": [{
                    "type": "webhook",
                    "url": webhook_url
                }]
            }
```

## Performance Impact

### Expected Impact

**Metric: Event Emission Overhead**
- Sync mode: ~0.5-1ms per event
- Async mode: ~0.1ms per event (fire-and-forget)
- Impact: <1% on total execution time

**Metric: Webhook Delivery Time**
- Local network: 10-50ms
- Internet: 100-500ms
- With async delivery: No impact on graph execution

**Metric: Memory Usage**
- Event objects: ~1KB each
- Event queue (async): ~100KB max
- Handler connections: ~10KB per handler
- Impact: <1MB total

**Metric: Queue Handler Performance**
- Redis: ~1ms per event
- RabbitMQ: ~2-5ms per event
- Kafka: ~2-10ms per event
- All async: No blocking

### Benchmarking

```python
import time
from scrapegraphai.graphs import SmartScraperGraph

# Benchmark without events
start = time.time()
scraper_no_events = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config={"llm": {...}}
)
result = scraper_no_events.run()
time_no_events = time.time() - start

# Benchmark with events (async delivery)
start = time.time()
scraper_with_events = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config={
        "llm": {...},
        "events": {
            "enabled": True,
            "async_delivery": True,
            "event_handlers": [
                {"type": "webhook", "url": "http://localhost:8000/webhook"}
            ]
        }
    }
)
result = scraper_with_events.run()
time_with_events = time.time() - start

overhead = (time_with_events - time_no_events) / time_no_events * 100
print(f"Overhead: {overhead:.2f}%")  # Expected: <1%
```

### Performance Best Practices

1. **Use Async Delivery:**
   ```python
   "events": {"async_delivery": True}  # Default, recommended
   ```

2. **Filter Events by Type:**
   ```python
   "event_types": ["graph.completed"]  # Only subscribe to needed events
   ```

3. **Limit Result Size in Events:**
   ```python
   "events": {"max_result_length": 500}  # Truncate large results
   ```

4. **Batch Queue Delivery:**
   ```python
   "queue_config": {"batch_size": 10}  # Send events in batches
   ```

## Alternatives Considered

### Alternative 1: Polling-Based Status Checking

**Description:** Store job status in database, require clients to poll for updates.

**Pros:**
- Simpler implementation
- No webhook infrastructure needed
- Client controls polling frequency

**Cons:**
- Inefficient (constant polling)
- Delayed notifications
- Higher server load
- Poor user experience

**Why Not Chosen:** Webhooks and events provide instant notifications and are the industry standard for async workflows.

---

### Alternative 2: Callback Functions Only

**Description:** Accept callback functions as parameters instead of full event system.

```python
def on_complete(result):
    print("Done!")

scraper = SmartScraperGraph(
    prompt="...",
    source="...",
    on_complete=on_complete
)
```

**Pros:**
- Simpler API
- Familiar pattern
- No configuration needed

**Cons:**
- Callbacks must be in same process
- Cannot integrate with external systems
- No support for webhooks
- Limited to Python functions

**Why Not Chosen:** Doesn't support external integrations (Zapier, n8n) which is a primary goal.

---

### Alternative 3: GraphQL Subscriptions

**Description:** Use GraphQL subscriptions for real-time updates.

**Pros:**
- Modern, standardized approach
- Great client support
- Query flexibility

**Cons:**
- Requires GraphQL server
- More complex infrastructure
- Overkill for simple notifications
- Doesn't integrate with Zapier/n8n

**Why Not Chosen:** Adds significant complexity and doesn't solve workflow tool integration.

---

### Alternative 4: Server-Sent Events (SSE)

**Description:** Use SSE for streaming updates to clients.

**Pros:**
- Simple HTTP-based
- Built-in browser support
- Real-time updates

**Cons:**
- Client must maintain connection
- Only works for browser clients
- Doesn't support webhooks
- No integration with workflow tools

**Why Not Chosen:** Limited to browser clients, doesn't enable async workflow integrations.

---

### Alternative 5: Message Queue Only (No Webhooks)

**Description:** Only support message queues, skip webhook support.

**Pros:**
- Simpler implementation
- More reliable delivery
- Better for high-throughput

**Cons:**
- Requires queue infrastructure
- Harder for users to set up
- Doesn't work with Zapier/n8n
- Higher barrier to entry

**Why Not Chosen:** Webhooks are more accessible for most users and are required for workflow tool integration.

---

### Decision Matrix

| Alternative | Ease of Use | Integration | Performance | Flexibility | Score |
|------------|-------------|-------------|-------------|-------------|-------|
| **Events + Webhooks (Chosen)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **23/25** |
| Polling | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | 11/25 |
| Callbacks Only | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 16/25 |
| GraphQL Subscriptions | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 15/25 |
| SSE | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 15/25 |
| Queue Only | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 17/25 |

## Security Considerations

### Threat Model

**Threat 1: Webhook URL Exposure**

**Description:** Webhook URLs might contain secrets and could be logged or exposed.

**Mitigation:**
- Never log full webhook URLs
- Support auth headers instead of URL-embedded secrets
- Redact URLs in error messages
- Use environment variables for URLs

**Implementation:**
```python
# In EventEmitter
def _sanitize_config(self, config):
    """Remove sensitive data from config."""
    if "url" in config:
        config["url"] = self._redact_url(config["url"])
    if "auth" in config:
        config["auth"] = "***REDACTED***"
    return config
```

---

**Threat 2: Event Data Leakage**

**Description:** Events might contain sensitive scraped data sent to third parties.

**Mitigation:**
- Truncate large results in events
- Provide data filtering options
- Allow users to exclude sensitive fields
- Document what data is sent

**Implementation:**
```python
# In BaseGraph
def _get_safe_result(self, state):
    """Sanitize result before including in event."""
    result = state.get("result", {})

    # Remove sensitive fields
    exclude_fields = self.config.get("events", {}).get("exclude_fields", [])
    for field in exclude_fields:
        result.pop(field, None)

    # Truncate
    max_length = self.config.get("events", {}).get("max_result_length", 1000)
    # ... truncation logic ...
```

---

**Threat 3: Webhook Server Authentication**

**Description:** Anyone who knows the webhook URL can send fake events.

**Mitigation:**
- Support signing events with HMAC
- Include shared secret in headers
- Support OAuth for webhook delivery
- Document authentication best practices

**Implementation:**
```python
class WebhookHandler(EventHandler):
    def _sign_payload(self, payload):
        """Sign payload with HMAC."""
        import hmac
        import hashlib

        secret = self.config.get("webhook_secret")
        if not secret:
            return payload

        signature = hmac.new(
            secret.encode(),
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        self.headers["X-Signature"] = signature
        return payload
```

---

**Threat 4: Denial of Service via Event Flood**

**Description:** Malicious code could emit thousands of events, overwhelming external systems.

**Mitigation:**
- Rate limit event emission
- Implement event queue size limits
- Add circuit breaker for failing handlers
- Monitor event rates

**Implementation:**
```python
class EventEmitter:
    def __init__(self, config):
        self.rate_limiter = RateLimiter(
            max_events=config.get("max_events_per_minute", 1000)
        )

    def emit(self, event):
        if not self.rate_limiter.allow():
            logger.warning("Event rate limit exceeded, dropping event")
            return
        # ... emit logic ...
```

---

**Threat 5: Webhook Endpoint SSRF**

**Description:** User-provided webhook URLs could target internal services.

**Mitigation:**
- Validate webhook URLs
- Block private IP ranges
- Implement URL allowlist option
- Add DNS resolution checks

**Implementation:**
```python
import ipaddress
from urllib.parse import urlparse

class WebhookHandler(EventHandler):
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
    ]

    def _validate_url(self, url):
        """Validate webhook URL to prevent SSRF."""
        parsed = urlparse(url)

        # Resolve hostname
        import socket
        try:
            ip = socket.gethostbyname(parsed.hostname)
            ip_obj = ipaddress.ip_address(ip)

            # Check if IP is in blocked ranges
            for network in self.BLOCKED_NETWORKS:
                if ip_obj in network:
                    raise ValueError(f"Webhook URL resolves to blocked network: {ip}")
        except socket.gaierror:
            raise ValueError(f"Cannot resolve webhook hostname: {parsed.hostname}")
```

### Security Best Practices

1. **Use HTTPS for Webhooks:**
   ```python
   "url": "https://hooks.zapier.com/...",  # Always HTTPS
   "verify_ssl": True  # Always verify
   ```

2. **Implement Webhook Signing:**
   ```python
   "webhook_secret": os.environ.get("WEBHOOK_SECRET"),
   # Events signed with HMAC SHA256
   ```

3. **Limit Event Data:**
   ```python
   "events": {
       "max_result_length": 500,
       "exclude_fields": ["password", "api_key", "token"]
   }
   ```

4. **Use Environment Variables:**
   ```python
   "url": os.environ.get("ZAPIER_WEBHOOK_URL"),
   "webhook_secret": os.environ.get("WEBHOOK_SECRET"),
   ```

5. **Monitor for Anomalies:**
   ```python
   # Alert on excessive event rates
   # Alert on webhook delivery failures
   # Alert on authentication failures
   ```

## Open Questions

### Question 1: Event Persistence

**Context:** Should events be persisted to disk for replay capability?

**Options:**
- **No Persistence:** Events are fire-and-forget
  - Pro: Simpler, lower overhead
  - Con: Events lost if handler fails

- **Optional Persistence:** Store events in database/file
  - Pro: Can replay failed events
  - Con: Adds storage requirements

- **Queue-Based:** Use queue system as persistence layer
  - Pro: Queue handles persistence
  - Con: Requires queue infrastructure

**Request for Input:** Is event replay important? What's the expected failure rate?

---

### Question 2: Event Schema Evolution

**Context:** How to handle event schema changes without breaking integrations?

**Options:**
- **Versioned Events:** Include schema version in each event
- **Strict Backwards Compatibility:** Never remove fields
- **Opt-in Schema Changes:** Allow users to choose schema version

**Request for Input:** How important is long-term webhook compatibility?

---

### Question 3: Batch Event Delivery

**Context:** Should we support batching multiple events into single webhook call?

**Options:**
- **Individual Events:** One HTTP request per event
  - Pro: Simple, immediate
  - Con: More HTTP overhead

- **Batching:** Send multiple events in array
  - Pro: Fewer requests, more efficient
  - Con: Delayed delivery, more complex

**Request for Input:** Do users prefer immediate delivery or efficiency?

---

### Question 4: Event Filtering Language

**Context:** Should we support complex event filtering beyond event type?

**Options:**
- **Type-Only:** Filter by event_type only
- **Field Matching:** Filter by field values (e.g., node_name="FetchNode")
- **Expression Language:** Full expression language (e.g., "error != null")

**Request for Input:** What filtering capabilities do users need?

---

### Question 5: Dead Letter Queue

**Context:** What to do with events that fail to deliver after retries?

**Options:**
- **Drop:** Just log and drop failed events
- **File Backup:** Write to file for manual retry
- **DLQ:** Send to dead letter queue
- **Callback:** Call error callback handler

**Request for Input:** How should failed event delivery be handled?

---

### Question 6: Event Ordering Guarantees

**Context:** Should we guarantee event order?

**Options:**
- **No Guarantee:** Events may arrive out of order (async delivery)
- **Best Effort:** Try to maintain order
- **Strict Order:** Guarantee order (synchronous delivery required)

**Request for Input:** Do workflow tools require ordered events?

---

### Question 7: Multi-Tenancy

**Context:** In multi-tenant deployments, how to isolate events?

**Options:**
- **Tenant ID in Events:** Include tenant_id in all events
- **Separate Emitters:** Each tenant gets own emitter
- **URL-Based Routing:** Different webhook URLs per tenant

**Request for Input:** What multi-tenancy patterns are needed?

---

### Question 8: Event Rate Limiting

**Context:** Should there be limits on event frequency?

**Current Proposal:**
- Default: 1000 events/minute per graph
- Configurable per handler

**Questions:**
- Is 1000/minute appropriate?
- Should it be global or per-handler?
- Should it be per-graph or system-wide?

**Request for Input:** What rate limits make sense?

### How to Provide Input

**For Community Members:**
- Comment on RFC GitHub issue
- Join Discord #feature-requests
- Email: team@scrapegraph.ai

**Timeline:**
- RFC feedback period: 2 weeks
- Decisions finalized: Week 3
- Implementation begins: Week 4

## Success Metrics

### Primary Metrics

**Metric 1: Integration Adoption**

**Definition:** Percentage of users who enable events

**Target:** 30% of active users within 3 months

**Measurement:**
```python
# Track via telemetry (opt-in only)
users_with_events = count_users_with_config("events.enabled = true")
total_users = count_total_users()
adoption_rate = users_with_events / total_users

assert adoption_rate >= 0.30  # 30% target
```

---

**Metric 2: Webhook Delivery Success Rate**

**Definition:** Percentage of webhook deliveries that succeed

**Target:** 99% success rate (after retries)

**Measurement:**
```python
# Track in WebhookHandler
def handle(self, event):
    # ... delivery logic ...
    metrics.record("webhook.delivery", success=True/False)

# Aggregate metrics
success_rate = webhook_successes / total_webhook_attempts
assert success_rate >= 0.99
```

---

**Metric 3: Event Overhead**

**Definition:** Performance overhead from event emission

**Target:** <2% increase in total execution time

**Measurement:**
```python
# Benchmark with/without events
time_with_events = benchmark_with_events()
time_without_events = benchmark_without_events()

overhead = (time_with_events - time_without_events) / time_without_events
assert overhead < 0.02  # <2%
```

---

### Secondary Metrics

**Metric 4: Workflow Tool Integrations**

**Definition:** Number of public Zapier/n8n/Make templates created

**Target:** 10 public templates within 6 months

**Measurement:**
- Track templates on Zapier
- Track workflows on n8n
- Track scenarios on Make

---

**Metric 5: Event Handler Diversity**

**Definition:** Percentage of users using each handler type

**Target:** Webhook 60%, Queue 25%, Custom 15%

**Measurement:**
```python
# Track handler usage
handler_counts = {
    "webhook": count_handler_type("webhook"),
    "queue": count_handler_type("queue"),
    "custom": count_handler_type("custom"),
}
```

---

**Metric 6: Error Rate**

**Definition:** Percentage of graphs that fail due to event system

**Target:** <0.1% (event errors shouldn't affect scraping)

**Measurement:**
```python
# Track event-related failures
event_failures = count_failures(cause="event_system")
total_runs = count_total_runs()

error_rate = event_failures / total_runs
assert error_rate < 0.001  # <0.1%
```

### Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  ScrapeGraphAI Event System Metrics                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Integration Adoption:    [████████░░] 35% (target: 30%)        │
│  Webhook Success Rate:    [██████████] 99.2% (target: 99%)      │
│  Event Overhead:          [██████████] 1.3% (target: <2%)       │
│  Error Rate:              [██████████] 0.05% (target: <0.1%)    │
│                                                                  │
│  Handler Usage:                                                 │
│    Webhooks:    [████████████░░] 62%                            │
│    Queues:      [████████░░░░░░] 23%                            │
│    Custom:      [█████░░░░░░░░░] 15%                            │
│                                                                  │
│  Workflow Tool Integrations:                                    │
│    Zapier Templates:  7                                         │
│    n8n Workflows:     4                                         │
│    Make Scenarios:    2                                         │
│    Total:            13 (target: 10)                            │
│                                                                  │
│  Recent Events:                                                 │
│  ✓ 15:22:11 - graph.completed (webhook delivered)              │
│  ✓ 15:21:45 - node.completed (queued to Redis)                 │
│  ⚠ 15:20:22 - webhook retry (attempt 2/3)                      │
│  ✓ 15:19:15 - custom handler executed                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Success Criteria Summary

**Phase 1-2 Success:**
- [ ] Core event system functional
- [ ] Webhook handler working
- [ ] 95% test coverage

**Phase 3-4 Success:**
- [ ] Events integrated in all graphs
- [ ] Queue handlers functional
- [ ] <2% performance overhead

**Phase 5-6 Success:**
- [ ] Zapier/n8n/Make optimized
- [ ] Complete documentation
- [ ] 5+ working examples

**Phase 7 Success (Production):**
- [ ] 99% webhook success rate
- [ ] 30% adoption rate
- [ ] <0.1% error rate
- [ ] 10+ workflow templates

## References

### Code References

1. **BaseGraph Implementation**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Current execution model (synchronous)
   - Integration point for events

2. **Node Execution**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/nodes/base_node.py`
   - Node lifecycle hooks
   - State management

3. **Configuration System**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Config parsing
   - Need to add events section

### External References

4. **Zapier Webhooks Documentation**
   - URL: https://zapier.com/developer/documentation/v2/webhooks/
   - Standard webhook format
   - Best practices

5. **n8n Webhook Node**
   - URL: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
   - Webhook payload expectations
   - Integration patterns

6. **CloudEvents Specification**
   - URL: https://cloudevents.io/
   - Standard event format
   - Could adopt for interoperability

7. **RabbitMQ Tutorial**
   - URL: https://www.rabbitmq.com/tutorials/tutorial-one-python.html
   - Queue integration patterns

8. **Redis Pub/Sub**
   - URL: https://redis.io/docs/manual/pubsub/
   - Event streaming with Redis

9. **Webhook Security Best Practices**
   - URL: https://webhooks.fyi/security/introduction
   - HMAC signing
   - SSRF prevention

10. **Event-Driven Architecture Patterns**
    - Reference: Martin Fowler's "Event-Driven Architecture"
    - Design patterns for events

### Similar Projects

11. **Celery Task Events**
    - URL: https://docs.celeryq.dev/en/stable/userguide/monitoring.html
    - Event emission in task queues
    - Inspiration for our design

12. **Airflow Listeners**
    - URL: https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/listeners.html
    - DAG execution events
    - Similar lifecycle hooks

13. **Prefect Events**
    - URL: https://docs.prefect.io/latest/concepts/events/
    - Workflow event system
    - Modern event-driven design

---

## Appendix: Complete Example Application

### Flask API with Background Jobs

```python
"""
Complete example: Flask API with ScrapeGraphAI background jobs.
Uses Redis for job queue and webhooks for notifications.
"""

from flask import Flask, jsonify, request
from scrapegraphai.graphs import SmartScraperGraph
import redis
import threading
import uuid
import json

app = Flask(__name__)
redis_client = redis.from_url("redis://localhost:6379")

# Job status tracking
jobs = {}

@app.route("/scrape", methods=["POST"])
def start_scraping():
    """Start a scraping job."""
    data = request.json

    job_id = str(uuid.uuid4())
    url = data.get("url")
    prompt = data.get("prompt")
    webhook_url = data.get("webhook_url")  # Optional notification URL

    # Create job record
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "result": None,
        "error": None,
    }

    # Configure scraper with events
    graph_config = {
        "llm": {"model": "openai/gpt-4"},
        "graph_id": job_id,
        "events": {
            "enabled": True,
            "async_delivery": True,
            "event_handlers": [
                # Redis queue for job status updates
                {
                    "type": "queue",
                    "queue_type": "redis",
                    "connection_string": "redis://localhost:6379",
                    "queue_name": "scraping_events",
                    "event_types": [
                        "graph.started",
                        "node.completed",
                        "graph.completed",
                        "graph.failed"
                    ]
                },
                # Webhook for completion notification
                *([{
                    "type": "webhook",
                    "url": webhook_url,
                    "event_types": ["graph.completed", "graph.failed"]
                }] if webhook_url else [])
            ]
        }
    }

    # Start scraping in background
    def run_scraper():
        try:
            scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=graph_config
            )
            result = scraper.run()

            # Update job status
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result

        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)

    thread = threading.Thread(target=run_scraper)
    thread.start()

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "message": "Scraping started",
        "status_url": f"/job/{job_id}"
    }), 202

@app.route("/job/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Get job status."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(jobs[job_id])

@app.route("/webhook/events", methods=["POST"])
def receive_event():
    """Receive event from webhook."""
    event = request.json

    # Update job status based on event
    job_id = event.get("graph_id")
    if job_id in jobs:
        event_type = event.get("event_type")

        if event_type == "graph.started":
            jobs[job_id]["status"] = "running"

        elif event_type == "node.completed":
            progress = event.get("data", {}).get("progress", 0)
            jobs[job_id]["progress"] = progress

        elif event_type == "graph.completed":
            jobs[job_id]["status"] = "completed"

        elif event_type == "graph.failed":
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = event.get("error")

    return jsonify({"status": "received"})

# Background worker to process events from Redis
def event_processor():
    """Process events from Redis queue."""
    while True:
        # Blocking pop from queue
        _, event_json = redis_client.brpop("scraping_events")
        event = json.loads(event_json)

        # Process event (update job status, send notifications, etc.)
        print(f"Processing event: {event['event_type']}")

# Start event processor in background
processor_thread = threading.Thread(target=event_processor, daemon=True)
processor_thread.start()

if __name__ == "__main__":
    app.run(port=5000)
```

**Usage:**

```bash
# Start the API
python app.py

# Start a scraping job
curl -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "prompt": "Extract all products",
    "webhook_url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/"
  }'

# Response:
# {
#   "job_id": "uuid-here",
#   "status": "queued",
#   "message": "Scraping started",
#   "status_url": "/job/uuid-here"
# }

# Check job status
curl http://localhost:5000/job/uuid-here

# Response:
# {
#   "status": "running",
#   "progress": 66,
#   "result": null,
#   "error": null
# }
```

---

**End of RFC-0009**

---

**Feedback welcome!**
Please provide feedback on the RFC discussion thread or contact the ScrapeGraphAI team.
