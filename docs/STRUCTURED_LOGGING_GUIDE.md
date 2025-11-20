# Structured Logging Guide

## Overview

ScrapeGraphAI now includes a comprehensive structured logging system with correlation IDs for production debugging, distributed tracing, and better observability. This guide covers everything you need to know to use the new logging system effectively.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [Basic Usage](#basic-usage)
4. [Advanced Features](#advanced-features)
5. [Configuration](#configuration)
6. [Migration Guide](#migration-guide)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Using Structured Logging in Your Code

```python
from scrapegraphai.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)

# Simple logging (backward compatible)
logger.info("Processing started")

# Structured logging with context
logger.info(
    "Processing completed",
    user_id="user123",
    records_processed=42,
    duration_ms=1234.56
)
```

### Enabling JSON Logging for Production

```bash
# Set environment variables
export LOG_FORMAT=json
export LOG_LEVEL=INFO

# Run your application
python your_script.py
```

---

## Core Concepts

### Correlation IDs

Every graph execution automatically gets a unique correlation ID (UUID) that flows through all components. This enables:

- **End-to-end tracing**: Track a single request across all nodes
- **Debugging**: Correlate logs from different parts of the system
- **Monitoring**: Aggregate metrics by correlation ID

### Structured Logs

Instead of plain text, logs are structured as JSON objects:

**Traditional Logging:**
```
[INFO|scraper.py:42] 2025-11-20 10:30:45 >> Scraping completed
```

**Structured Logging (JSON):**
```json
{
  "timestamp": "2025-11-20T10:30:45.123456Z",
  "level": "INFO",
  "logger": "scrapegraphai.graphs.smart_scraper",
  "message": "Scraping completed",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "module": "smart_scraper_graph",
  "function": "run",
  "line": 42,
  "url": "https://example.com",
  "items_scraped": 15,
  "duration_ms": 2333.45
}
```

### Output Formats

- **JSON Format** (production): Machine-readable, perfect for log aggregation platforms
- **Human Format** (development): Human-readable with shortened correlation IDs

---

## Basic Usage

### Getting a Logger

```python
from scrapegraphai.utils.logging import get_structured_logger

# Get a logger for your module
logger = get_structured_logger(__name__)
```

### Logging with Context

Add context fields to any log message:

```python
logger.info(
    "User action completed",
    user_id="user123",
    action="scrape",
    target_url="https://example.com"
)

logger.error(
    "Failed to process data",
    error_code="E001",
    retry_count=3,
    exc_info=True  # Include exception traceback
)
```

### Log Levels

```python
logger.debug("Detailed debug information", variable=value)
logger.info("General information", status="running")
logger.warning("Warning message", threshold_exceeded=True)
logger.error("Error occurred", error_type="ValidationError")
logger.critical("Critical system failure", system="database")

# For exceptions, use exception() to automatically include traceback
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed", operation="data_sync")
```

---

## Advanced Features

### Performance Timing

Automatically log execution time of operations:

```python
from scrapegraphai.utils.logging import get_structured_logger, log_execution_time

logger = get_structured_logger(__name__)

with log_execution_time(logger, "data_processing", batch_id="B001"):
    process_large_dataset()

# Logs:
# INFO: Starting data_processing (operation=data_processing, batch_id=B001)
# INFO: Completed data_processing (operation=data_processing, batch_id=B001, duration_ms=1234.56)
```

If an exception occurs, it's automatically logged with timing:

```python
try:
    with log_execution_time(logger, "risky_operation"):
        might_fail()
except Exception:
    pass  # Exception is already logged by log_execution_time
```

### Correlation IDs

#### Automatic Correlation IDs

Graph execution automatically sets a correlation ID:

```python
from scrapegraphai.graphs import SmartScraperGraph

graph = SmartScraperGraph(
    prompt="Extract product information",
    source="https://example.com",
    config={"llm": {"model": "openai/gpt-4"}}
)

# Correlation ID is automatically created and propagated
result = graph.run()
```

#### Manual Correlation IDs

Set a custom correlation ID for tracking:

```python
from scrapegraphai.utils.logging import set_correlation_id, get_correlation_id

# Set a custom correlation ID (e.g., from an incoming request)
set_correlation_id("request-id-from-api")

# Get the current correlation ID
current_id = get_correlation_id()
logger.info("Processing request", correlation_id=current_id)
```

#### Clearing Correlation IDs

```python
from scrapegraphai.utils.logging import clear_correlation_id

# Clear the correlation ID (new one will be generated on next use)
clear_correlation_id()
```

### Using in Custom Nodes

```python
from scrapegraphai.nodes import BaseNode

class MyCustomNode(BaseNode):
    def __init__(self, node_name: str):
        super().__init__(
            node_name=node_name,
            node_type="node",
            input="data",
            output=["result"]
        )

    def execute(self, state: dict) -> dict:
        # Use structured logger (recommended)
        self.structured_logger.info(
            "Processing node",
            node_name=self.node_name,
            input_size=len(state.get("data", []))
        )

        # Process data with timing
        from scrapegraphai.utils.logging import log_execution_time

        with log_execution_time(
            self.structured_logger,
            "data_transformation",
            node_name=self.node_name
        ):
            result = transform_data(state["data"])

        state["result"] = result

        self.structured_logger.info(
            "Node completed",
            node_name=self.node_name,
            output_size=len(result)
        )

        return state
```

---

## Configuration

### Environment Variables

Configure logging behavior with environment variables:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `LOG_FORMAT` | `json`, `human` | `human` | Output format |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` | Minimum log level |
| `LOG_CORRELATION_ID` | `true`, `false` | `true` | Include correlation IDs |
| `LOG_CONTEXT` | `true`, `false` | `true` | Include extra context fields |

### Examples

**Development (human-readable):**
```bash
export LOG_FORMAT=human
export LOG_LEVEL=DEBUG
```

**Production (JSON):**
```bash
export LOG_FORMAT=json
export LOG_LEVEL=WARNING
export LOG_CORRELATION_ID=true
export LOG_CONTEXT=true
```

### Programmatic Configuration

```python
from scrapegraphai.utils.logging import LogConfig, LogFormat, configure_logging

# Create custom configuration
config = LogConfig()
config.format = LogFormat.JSON
config.level = "DEBUG"
config.include_correlation_id = True
config.include_context = True

# Apply configuration
configure_logging(config)
```

---

## Migration Guide

### Backward Compatibility

**Good news!** The new system is fully backward compatible. Existing code continues to work without changes:

```python
# Old code still works
from scrapegraphai.utils.logging import get_logger

logger = get_logger(__name__)
logger.info("This still works!")
```

### Gradual Migration

Migrate incrementally by replacing loggers as you touch code:

**Before:**
```python
from scrapegraphai.utils.logging import get_logger

logger = get_logger(__name__)

def process_data(data):
    logger.info("Processing started")
    # ... processing ...
    logger.info("Processing completed")
```

**After:**
```python
from scrapegraphai.utils.logging import get_structured_logger

logger = get_structured_logger(__name__)

def process_data(data):
    logger.info(
        "Processing started",
        data_size=len(data),
        operation="process_data"
    )
    # ... processing ...
    logger.info(
        "Processing completed",
        records_processed=len(results),
        operation="process_data"
    )
```

### Migration Checklist

- [ ] Update imports to use `get_structured_logger`
- [ ] Add context fields to log messages
- [ ] Use `log_execution_time` for performance-critical operations
- [ ] Configure production environment for JSON logging
- [ ] Update monitoring dashboards to parse JSON logs
- [ ] Train team on new logging practices

---

## Best Practices

### 1. Always Include Context

**Bad:**
```python
logger.info("User logged in")
```

**Good:**
```python
logger.info(
    "User logged in",
    user_id=user.id,
    session_id=session.id,
    ip_address=request.ip
)
```

### 2. Use Semantic Field Names

Use consistent, descriptive field names:

```python
# Good field names
logger.info("API call completed",
    endpoint="/api/scrape",
    method="POST",
    status_code=200,
    duration_ms=1234.56,
    user_id="user123"
)

# Avoid generic names like 'data', 'info', 'value'
```

### 3. Log at Appropriate Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

### 4. Use Timing for Performance-Critical Code

```python
with log_execution_time(logger, "database_query", query_type="complex"):
    results = execute_complex_query()
```

### 5. Don't Log Sensitive Information

**Never log:**
- Passwords
- API keys
- Personal Identifiable Information (PII) without proper redaction
- Credit card numbers
- Session tokens

**Example with redaction:**
```python
logger.info(
    "User action",
    user_id=hash_user_id(user.id),  # Hash instead of raw ID
    email=redact_email(user.email),  # Redact email
    action="purchase"
)
```

### 6. Use Structured Errors

```python
try:
    result = risky_operation()
except ValidationError as e:
    logger.error(
        "Validation failed",
        error_type="ValidationError",
        error_message=str(e),
        field=e.field,
        value_type=type(e.value).__name__,
        exc_info=True  # Include full traceback
    )
except Exception as e:
    logger.exception(
        "Unexpected error",
        operation="risky_operation",
        error_type=type(e).__name__
    )
```

### 7. Log Graph and Node Context

```python
# In nodes
self.structured_logger.info(
    "Node processing",
    node_name=self.node_name,
    node_type=self.node_type,
    graph_name=graph_name
)

# In graphs
logger.info(
    "Graph execution",
    graph_name=self.graph_name,
    node_count=len(self.nodes),
    execution_mode="burr" if self.use_burr else "standard"
)
```

---

## Integration with Log Aggregation Platforms

### DataDog

```python
# DataDog automatically parses JSON logs
# Set up DD_LOGS_INJECTION for correlation
export LOG_FORMAT=json
export DD_LOGS_INJECTION=true
```

### Elasticsearch / Kibana

```json
# Logstash configuration for JSON logs
input {
  file {
    path => "/var/log/scrapegraphai/*.log"
    codec => "json"
  }
}

filter {
  # Correlation ID for distributed tracing
  mutate {
    add_field => { "trace.id" => "%{correlation_id}" }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "scrapegraphai-logs-%{+YYYY.MM.dd}"
  }
}
```

### CloudWatch

```python
# AWS CloudWatch Logs with JSON format
export LOG_FORMAT=json

# Use AWS SDK to push structured logs
# Correlation IDs map to AWS X-Ray trace IDs
```

### Sample Queries

**Find all logs for a specific correlation ID:**
```
correlation_id:"a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**Find slow operations (>5 seconds):**
```
duration_ms:>5000
```

**Find all errors for a specific user:**
```
level:"ERROR" AND user_id:"user123"
```

---

## Troubleshooting

### Logs Not Appearing

**Check log level:**
```python
from scrapegraphai.utils.logging import get_verbosity
import logging

current_level = get_verbosity()
print(f"Current log level: {logging.getLevelName(current_level)}")
```

**Set log level:**
```python
from scrapegraphai.utils.logging import set_verbosity_debug
set_verbosity_debug()
```

### JSON Format Not Working

**Verify environment variable:**
```bash
echo $LOG_FORMAT
```

**Force JSON format:**
```python
from scrapegraphai.utils.logging import LogConfig, LogFormat, configure_logging

config = LogConfig()
config.format = LogFormat.JSON
configure_logging(config)
```

### Correlation IDs Not Propagating

**Ensure you're using graph.execute():**
```python
# Correct - correlation ID is set automatically
graph = SmartScraperGraph(...)
result = graph.run()  # This calls graph.execute() internally

# If executing manually, correlation ID should be set
from scrapegraphai.utils.logging import set_correlation_id
import uuid

set_correlation_id(str(uuid.uuid4()))
state, info = graph.graph.execute(initial_state)
```

### Context Fields Not Appearing

**Check LOG_CONTEXT setting:**
```bash
export LOG_CONTEXT=true
```

**Verify formatter configuration:**
```python
from scrapegraphai.utils.logging import configure_logging, LogConfig

config = LogConfig()
config.include_context = True
configure_logging(config)
```

---

## Examples

### Example 1: Simple Script with Structured Logging

```python
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils.logging import (
    get_structured_logger,
    configure_logging,
    LogConfig,
    LogFormat
)

# Configure logging
config = LogConfig()
config.format = LogFormat.JSON
config.level = "INFO"
configure_logging(config)

logger = get_structured_logger(__name__)

# Log application start
logger.info(
    "Application started",
    script="scraper.py",
    version="1.0.0"
)

try:
    # Create and run graph
    graph = SmartScraperGraph(
        prompt="Extract all product names",
        source="https://example.com/products",
        config={"llm": {"model": "openai/gpt-4"}}
    )

    logger.info("Starting scraping job", url="https://example.com/products")

    result = graph.run()

    logger.info(
        "Scraping completed successfully",
        products_found=len(result.get("products", [])),
        url="https://example.com/products"
    )

except Exception as e:
    logger.exception(
        "Scraping failed",
        url="https://example.com/products",
        error_type=type(e).__name__
    )
    raise
```

### Example 2: Custom Node with Rich Logging

```python
from scrapegraphai.nodes import BaseNode
from scrapegraphai.utils.logging import log_execution_time

class DataEnrichmentNode(BaseNode):
    def __init__(self):
        super().__init__(
            node_name="data_enrichment",
            node_type="node",
            input="raw_data",
            output=["enriched_data"]
        )

    def execute(self, state: dict) -> dict:
        raw_data = state.get("raw_data", [])

        self.structured_logger.info(
            "Starting data enrichment",
            node_name=self.node_name,
            input_records=len(raw_data)
        )

        enriched_records = []

        for idx, record in enumerate(raw_data):
            try:
                with log_execution_time(
                    self.structured_logger,
                    "enrich_record",
                    record_index=idx,
                    node_name=self.node_name
                ):
                    enriched = self.enrich_record(record)
                    enriched_records.append(enriched)

            except Exception as e:
                self.structured_logger.error(
                    "Failed to enrich record",
                    record_index=idx,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    node_name=self.node_name
                )
                # Continue with next record

        self.structured_logger.info(
            "Data enrichment completed",
            node_name=self.node_name,
            input_records=len(raw_data),
            output_records=len(enriched_records),
            success_rate=len(enriched_records) / len(raw_data) if raw_data else 0
        )

        state["enriched_data"] = enriched_records
        return state

    def enrich_record(self, record):
        # Enrichment logic here
        pass
```

### Example 3: Production Deployment

```python
# production_config.py
import os
from scrapegraphai.utils.logging import configure_logging, LogConfig, LogFormat

def setup_production_logging():
    """Configure logging for production environment."""
    config = LogConfig()

    # JSON format for log aggregation
    config.format = LogFormat.JSON

    # Only log warnings and above in production
    config.level = os.getenv("LOG_LEVEL", "WARNING")

    # Enable all features
    config.include_correlation_id = True
    config.include_context = True

    configure_logging(config)

# main.py
from production_config import setup_production_logging
from scrapegraphai.utils.logging import get_structured_logger

setup_production_logging()
logger = get_structured_logger(__name__)

logger.info("Production service started", environment="production")
```

---

## Additional Resources

- [RFC-0004: Structured Logging Specification](../analysis-output/rfcs/RFC-0004-structured-logging.md)
- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Structured Logging Best Practices](https://engineering.grab.com/structured-logging)
- [Correlation IDs for Microservices](https://www.rapid7.com/blog/post/2016/12/23/the-value-of-correlation-ids/)

---

## Support

For issues or questions:
- GitHub Issues: [scrapegraphai/issues](https://github.com/VinciGit00/Scrapegraph-ai/issues)
- Documentation: [ScrapeGraphAI Docs](https://scrapegraphai.com/docs)

---

**Version:** 1.0.0
**Last Updated:** 2025-11-20
