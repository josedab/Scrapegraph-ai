# ScrapeGraphAI Events System

The ScrapeGraphAI Events System enables asynchronous workflow integrations with tools like Zapier, n8n, Make, and queue systems (RabbitMQ, Redis, Kafka). This allows you to build responsive applications, integrate with workflow automation platforms, and implement background job processing.

## Overview

The events system emits events at key points during graph execution:

- **Graph Lifecycle**: `graph.started`, `graph.completed`, `graph.failed`
- **Node Lifecycle**: `node.started`, `node.completed`, `node.failed`
- **Progress**: Real-time progress updates during execution

Events can be sent to:
- **Webhooks**: POST events to any HTTP endpoint (Zapier, n8n, Make, custom)
- **Message Queues**: Send events to Redis, RabbitMQ, AWS SQS, or Kafka
- **Log Files**: Record events to files in JSON format
- **Custom Handlers**: Implement your own event processing logic

## Quick Start

### Basic Webhook Example

```python
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,  # Enable events
        "event_handlers": [
            {
                "type": "webhook",
                "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
                "event_types": ["graph.completed", "graph.failed"]
            }
        ]
    }
}

scraper = SmartScraperGraph(
    prompt="Extract product data",
    source="https://example.com",
    config=config
)

result = scraper.run()
# Webhook is automatically called when scraping completes!
```

## Event Types

### Graph Events

- `graph.started`: Emitted when graph execution begins
- `graph.completed`: Emitted when graph execution completes successfully
- `graph.failed`: Emitted when graph execution fails

### Node Events

- `node.started`: Emitted before each node executes
- `node.completed`: Emitted after each node completes
- `node.failed`: Emitted when a node fails

### Event Structure

All events have this structure:

```json
{
  "event_type": "graph.completed",
  "event_id": "uuid-here",
  "timestamp": "2025-11-20T10:30:00Z",
  "graph_id": "graph-uuid",
  "graph_name": "SmartScraperGraph",
  "node_name": "NodeName",
  "data": {
    "result_preview": "...",
    "progress": 75,
    "exec_time": 2.5
  },
  "error": null,
  "error_type": null,
  "metadata": {}
}
```

## Event Handlers

### Webhook Handler

Send events to HTTP endpoints with automatic retries:

```python
{
    "type": "webhook",
    "url": "https://example.com/webhook",
    "method": "POST",  # Optional, default: POST
    "headers": {  # Optional custom headers
        "X-API-Key": "your-key"
    },
    "auth": ("username", "password"),  # Optional basic auth
    "timeout": 30,  # Optional, default: 30 seconds
    "retry_count": 3,  # Optional, default: 3
    "retry_backoff": 2,  # Optional, default: 2
    "verify_ssl": true,  # Optional, default: true
    "event_types": ["graph.completed"]  # Optional, default: all events
}
```

### Specialized Webhook Handlers

#### Zapier

Optimized payload for Zapier integration:

```python
{
    "type": "webhook",
    "class": "scrapegraphai.events.handlers.webhook.ZapierWebhookHandler",
    "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
    "event_types": ["graph.completed"]
}
```

#### n8n

Optimized payload for n8n workflows:

```python
{
    "type": "webhook",
    "class": "scrapegraphai.events.handlers.webhook.N8nWebhookHandler",
    "url": "https://myinstance.n8n.cloud/webhook/scrapegraph",
    "event_types": ["graph.completed"]
}
```

### Queue Handler

Send events to message queues:

#### Redis

```python
{
    "type": "queue",
    "queue_type": "redis",
    "connection_string": "redis://localhost:6379",
    "queue_name": "scraping_events",
    "event_types": ["graph.completed", "graph.failed"]
}
```

#### RabbitMQ

```python
{
    "type": "queue",
    "queue_type": "rabbitmq",
    "connection_string": "amqp://user:pass@localhost:5672/",
    "queue_name": "scraping_events"
}
```

#### AWS SQS

```python
{
    "type": "queue",
    "queue_type": "sqs",
    "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/queue-name",
    "event_types": ["graph.completed"]
}
```

#### Apache Kafka

```python
{
    "type": "queue",
    "queue_type": "kafka",
    "connection_string": "localhost:9092",
    "queue_name": "scraping_events"
}
```

### Log Handler

Record events to files:

```python
{
    "type": "log",
    "log_file": "/var/log/scrapegraph/events.log",
    "log_format": "json",  # Optional: "json" or "text"
    "append": true,  # Optional, default: true
    "event_types": []  # Empty = log all events
}
```

### Custom Handler

Create your own event handler:

```python
from scrapegraphai.events import EventHandler, Event

class MyCustomHandler(EventHandler):
    def handle(self, event: Event):
        # Your custom logic here
        print(f"Received event: {event.event_type}")

# Use in config:
{
    "type": "custom",
    "class": "mymodule.MyCustomHandler",
    "event_types": ["graph.completed"]
}
```

## Configuration Options

### Event Configuration

```python
"events": {
    "enabled": True,  # Enable/disable events (default: False)
    "async_delivery": True,  # Async delivery (default: True)
    "max_result_length": 1000,  # Truncate large results (default: 1000)
    "event_handlers": [...]  # List of handlers
}
```

### Graph Configuration

```python
"graph_id": "custom-id",  # Custom graph ID for tracking (default: auto-generated UUID)
```

## Use Cases

### 1. Zapier Integration

Trigger Zapier workflows when scraping completes:

```python
config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [{
            "type": "webhook",
            "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
            "event_types": ["graph.completed"]
        }]
    }
}
```

### 2. Background Job Processing

Queue scraping jobs for async processing:

```python
config = {
    "llm": {"model": "openai/gpt-4"},
    "graph_id": "job-123",
    "events": {
        "enabled": True,
        "event_handlers": [{
            "type": "queue",
            "queue_type": "redis",
            "connection_string": "redis://localhost:6379",
            "queue_name": "scraping_jobs"
        }]
    }
}
```

### 3. Real-time Progress Monitoring

Track scraping progress in real-time:

```python
config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [{
            "type": "webhook",
            "url": "http://localhost:8000/progress",
            "event_types": [
                "graph.started",
                "node.started",
                "node.completed",
                "graph.completed"
            ]
        }]
    }
}
```

### 4. Multi-Destination Events

Send events to multiple destinations:

```python
config = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            # Webhook for notifications
            {
                "type": "webhook",
                "url": "https://hooks.zapier.com/...",
                "event_types": ["graph.completed"]
            },
            # Queue for background processing
            {
                "type": "queue",
                "queue_type": "redis",
                "connection_string": "redis://localhost:6379",
                "queue_name": "jobs"
            },
            # Log for audit trail
            {
                "type": "log",
                "log_file": "./events.log"
            }
        ]
    }
}
```

## Dependencies

The events system has optional dependencies based on which handlers you use:

- **Webhook Handler**: `requests` (for HTTP requests)
- **Redis Queue**: `redis`
- **RabbitMQ Queue**: `pika`
- **AWS SQS Queue**: `boto3`
- **Kafka Queue**: `kafka-python`
- **Payload Templates**: `jinja2`

Install only what you need:

```bash
# For webhooks
pip install requests

# For Redis
pip install redis

# For RabbitMQ
pip install pika

# For AWS SQS
pip install boto3

# For Kafka
pip install kafka-python

# For custom payload templates
pip install jinja2
```

## Security Considerations

### Webhook Security

1. **Use HTTPS**: Always use HTTPS for webhook URLs
2. **Verify SSL**: Keep `verify_ssl: true` (default)
3. **Environment Variables**: Store webhook URLs in environment variables
4. **Data Filtering**: Limit data sent in events using `max_result_length`

```python
{
    "url": os.environ.get("WEBHOOK_URL"),
    "verify_ssl": True,
    "event_types": ["graph.completed"],  # Only send necessary events
}
```

### Data Privacy

Control what data is sent in events:

```python
"events": {
    "max_result_length": 500,  # Limit result size
    "exclude_fields": ["password", "api_key"]  # Exclude sensitive fields
}
```

## Examples

See `examples/events_example.py` for comprehensive examples including:

- Zapier integration
- n8n workflows
- Redis background jobs
- File logging
- Custom handlers
- Flask API with events
- Progress monitoring

## Troubleshooting

### Events Not Being Sent

1. Check that `"enabled": True` in events config
2. Verify handler configuration is correct
3. Check logs for error messages
4. Test webhook URL manually

### Webhook Failures

1. Check webhook URL is accessible
2. Verify SSL certificate if using HTTPS
3. Increase `retry_count` for unreliable endpoints
4. Check webhook endpoint logs for errors

### Queue Connection Issues

1. Verify connection string is correct
2. Check queue service is running
3. Ensure required package is installed
4. Check network connectivity

## Performance

The events system has minimal performance impact:

- **Overhead**: <1% with async delivery (default)
- **Memory**: <1MB per graph execution
- **Network**: Async delivery doesn't block execution

## Architecture

For detailed architecture information, see RFC-0009-webhook-event-system.md

## Support

For issues or questions:
- GitHub Issues: https://github.com/ScrapeGraphAI/Scrapegraph-ai/issues
- Documentation: https://scrapegraphai.com
- Discord: Join our community

## License

Same as ScrapeGraphAI main license.
