# RFC-0004: Structured Logging with Correlation IDs

## Status
**Status:** Proposed
**Author:** ScrapeGraphAI Team
**Created:** 2025-11-20
**Updated:** 2025-11-20

## Summary
Replace the current basic text-based logging system with structured JSON logging that includes correlation IDs, enabling production debugging, distributed tracing, and better observability across the ScrapeGraphAI platform.

## Context
The current logging implementation (`scrapegraphai/utils/logging.py`) provides basic text-based logging with simple formatters. While functional for development, it lacks the structure and metadata needed for:

- **Production debugging**: Difficult to parse and analyze logs programmatically
- **Distributed tracing**: No way to track requests across multiple components or nodes
- **Observability**: Limited context about the execution environment and state
- **Log aggregation**: Text-based logs are hard to query and correlate in log management systems
- **Performance analysis**: No built-in support for timing and performance metrics

Current limitations:
```python
# Current logging format
"[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s >> %(message)s"
# Output: [INFO|scraper.py:42] 2025-11-20 10:30:45 >> Scraping completed
```

## Problem Statement
As ScrapeGraphAI scales and is deployed in production environments, the current logging system creates several challenges:

1. **Lack of Structure**: Text-based logs are difficult to parse, query, and analyze programmatically
2. **No Request Tracking**: Cannot trace a single scraping job across multiple components, nodes, or LLM calls
3. **Limited Context**: Missing critical metadata like user IDs, graph IDs, node types, execution times
4. **Poor Observability**: Difficult to correlate logs from different parts of the system
5. **No Performance Metrics**: Cannot easily extract timing information for optimization
6. **Integration Challenges**: Hard to integrate with modern observability platforms (DataDog, Elastic, Grafana)

### Use Cases Requiring Better Logging
- Debugging multi-node graph executions
- Tracking LLM API calls and costs across a scraping session
- Monitoring performance bottlenecks in production
- Correlating errors across distributed components
- Auditing and compliance requirements
- Cost attribution per user/project

## Proposed Solution
Implement a structured logging system based on JSON with the following features:

1. **Structured JSON Output**: All logs output as parseable JSON objects
2. **Correlation IDs**: Every scraping job gets a unique correlation ID that flows through all components
3. **Rich Context**: Automatic inclusion of execution metadata (graph_id, node_id, user_id, etc.)
4. **Performance Tracking**: Built-in support for timing and performance metrics
5. **Backward Compatibility**: Maintain existing API while adding new capabilities
6. **Configurable Output**: Support both JSON (production) and human-readable (development) formats

### Key Benefits
- **Production-Ready**: JSON logs can be easily ingested by log aggregation platforms
- **Distributed Tracing**: Track requests end-to-end across all components
- **Better Debugging**: Rich context makes troubleshooting faster and more effective
- **Performance Insights**: Built-in metrics enable optimization opportunities
- **Compliance**: Structured logs support audit trails and compliance requirements

## Design Details

### 1. Core Components

#### 1.1 Correlation ID Management
```python
import uuid
from contextvars import ContextVar

# Thread-safe correlation ID storage
correlation_id: ContextVar[str] = ContextVar('correlation_id', default=None)

def get_correlation_id() -> str:
    """Get or create correlation ID for current execution context."""
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid

def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current execution context."""
    correlation_id.set(cid)
```

#### 1.2 Structured Log Record
```python
from typing import Any, Dict, Optional
from datetime import datetime

class StructuredLogRecord:
    """Enhanced log record with structured data."""

    def __init__(
        self,
        level: str,
        message: str,
        correlation_id: Optional[str] = None,
        **context: Any
    ):
        self.timestamp = datetime.utcnow().isoformat()
        self.level = level
        self.message = message
        self.correlation_id = correlation_id or get_correlation_id()
        self.context = context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "correlation_id": self.correlation_id,
            **self.context
        }
```

#### 1.3 JSON Formatter
```python
import json
import logging

class JSONFormatter(logging.Formatter):
    """Format log records as JSON with correlation IDs."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields if available
        if self.include_extra and hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)
```

#### 1.4 Human-Readable Formatter (Development)
```python
class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development environments."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """Add correlation ID to record before formatting."""
        record.correlation_id = get_correlation_id()[:8]  # Shortened for readability
        return super().format(record)
```

### 2. Enhanced Logger Interface

#### 2.1 Structured Logger Wrapper
```python
class StructuredLogger:
    """Wrapper around standard logger with structured logging support."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, message: str, **context: Any) -> None:
        """Log with structured context."""
        extra = {"extra": context} if context else {}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **context: Any) -> None:
        """Log debug message with context."""
        self._log(logging.DEBUG, message, **context)

    def info(self, message: str, **context: Any) -> None:
        """Log info message with context."""
        self._log(logging.INFO, message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning message with context."""
        self._log(logging.WARNING, message, **context)

    def error(self, message: str, **context: Any) -> None:
        """Log error message with context."""
        self._log(logging.ERROR, message, **context)

    def critical(self, message: str, **context: Any) -> None:
        """Log critical message with context."""
        self._log(logging.CRITICAL, message, **context)

    def with_context(self, **context: Any) -> 'StructuredLogger':
        """Create a new logger with additional context."""
        return StructuredLoggerAdapter(self._logger, context)
```

#### 2.2 Performance Timing Context Manager
```python
import time
from contextlib import contextmanager

@contextmanager
def log_execution_time(logger: StructuredLogger, operation: str, **context: Any):
    """Context manager to log execution time of operations."""
    start_time = time.perf_counter()
    logger.info(f"Starting {operation}", operation=operation, **context)

    try:
        yield
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"Failed {operation}",
            operation=operation,
            duration_ms=duration_ms,
            error=str(e),
            **context
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Completed {operation}",
            operation=operation,
            duration_ms=duration_ms,
            **context
        )
```

### 3. Integration with Graph Execution

#### 3.1 Base Graph Integration
```python
class BaseGraph:
    """Enhanced with correlation ID propagation."""

    def run(self, *args, **kwargs):
        """Run graph with correlation ID."""
        # Set correlation ID if not already set
        if correlation_id.get() is None:
            cid = str(uuid.uuid4())
            set_correlation_id(cid)

        logger.info(
            "Starting graph execution",
            graph_name=self.__class__.__name__,
            graph_id=getattr(self, 'graph_id', None),
            correlation_id=get_correlation_id()
        )

        with log_execution_time(logger, "graph_execution", graph_name=self.__class__.__name__):
            result = self._execute(*args, **kwargs)

        return result
```

#### 3.2 Node Execution Integration
```python
class BaseNode:
    """Enhanced with structured logging."""

    def execute(self, state: dict) -> dict:
        """Execute node with structured logging."""
        logger = get_logger(__name__)

        logger.info(
            "Executing node",
            node_type=self.__class__.__name__,
            node_id=getattr(self, 'node_id', None),
            input_keys=list(state.keys())
        )

        with log_execution_time(logger, "node_execution", node_type=self.__class__.__name__):
            result = self._execute_impl(state)

        logger.info(
            "Node execution complete",
            node_type=self.__class__.__name__,
            output_keys=list(result.keys())
        )

        return result
```

### 4. Configuration System

#### 4.1 Environment-Based Configuration
```python
import os
from enum import Enum

class LogFormat(Enum):
    JSON = "json"
    HUMAN = "human"

class LogConfig:
    """Logging configuration."""

    def __init__(self):
        self.format = LogFormat(os.getenv("LOG_FORMAT", "human"))
        self.level = os.getenv("LOG_LEVEL", "INFO")
        self.include_correlation_id = os.getenv("LOG_CORRELATION_ID", "true").lower() == "true"
        self.include_context = os.getenv("LOG_CONTEXT", "true").lower() == "true"

def configure_logging(config: Optional[LogConfig] = None) -> None:
    """Configure structured logging system."""
    config = config or LogConfig()

    # Set up formatter based on environment
    if config.format == LogFormat.JSON:
        formatter = JSONFormatter(include_extra=config.include_context)
    else:
        formatter = DevelopmentFormatter()

    # Configure root logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = _get_library_root_logger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, config.level.upper()))
```

### 5. Example Log Outputs

#### 5.1 JSON Format (Production)
```json
{
  "timestamp": "2025-11-20T10:30:45.123456",
  "level": "INFO",
  "logger": "scrapegraphai.graphs.smart_scraper",
  "message": "Starting graph execution",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "graph_name": "SmartScraperGraph",
  "graph_id": "graph_001",
  "module": "smart_scraper_graph",
  "function": "run",
  "line": 145
}
```

#### 5.2 Human-Readable Format (Development)
```
2025-11-20 10:30:45 [INFO] [a1b2c3d4] scrapegraphai.graphs.smart_scraper - Starting graph execution
```

#### 5.3 Performance Metrics
```json
{
  "timestamp": "2025-11-20T10:30:47.456789",
  "level": "INFO",
  "message": "Completed graph_execution",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "operation": "graph_execution",
  "duration_ms": 2333.45,
  "graph_name": "SmartScraperGraph"
}
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] Implement correlation ID management with ContextVars
- [ ] Create JSONFormatter and DevelopmentFormatter
- [ ] Add StructuredLogger wrapper
- [ ] Implement configuration system
- [ ] Add comprehensive unit tests

### Phase 2: Integration (Week 2)
- [ ] Integrate with BaseGraph for automatic correlation ID propagation
- [ ] Add structured logging to all BaseNode implementations
- [ ] Implement performance timing decorators and context managers
- [ ] Update FetchNode, ParseNode, GenerateAnswerNode with structured logging

### Phase 3: Enhanced Features (Week 3)
- [ ] Add LLM call tracking (tokens, costs, latency)
- [ ] Implement request/response logging for external APIs
- [ ] Add sampling and rate limiting for high-volume logs
- [ ] Create utility functions for common logging patterns

### Phase 4: Documentation & Migration (Week 4)
- [ ] Write migration guide for existing code
- [ ] Create logging best practices documentation
- [ ] Add examples for common use cases
- [ ] Update existing code to use structured logging
- [ ] Add environment variable documentation

### Phase 5: Monitoring Integration (Week 5)
- [ ] Document integration with DataDog, Elastic, CloudWatch
- [ ] Create sample dashboards and queries
- [ ] Add alerting examples based on structured logs
- [ ] Performance tuning and optimization

## Testing Strategy

### Unit Tests
```python
def test_correlation_id_persistence():
    """Test correlation ID persists across function calls."""
    cid = str(uuid.uuid4())
    set_correlation_id(cid)

    assert get_correlation_id() == cid

def test_json_formatter():
    """Test JSON formatter outputs valid JSON."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None
    )

    formatter = JSONFormatter()
    output = formatter.format(record)

    # Should be valid JSON
    data = json.loads(output)
    assert data["message"] == "Test message"
    assert "correlation_id" in data

def test_structured_logger_context():
    """Test structured logger includes context."""
    logger = get_logger("test")

    with patch('logging.Logger.log') as mock_log:
        logger.info("Test", user_id="user123", graph_id="graph456")

        # Verify context was included
        call_args = mock_log.call_args
        assert "user_id" in call_args.kwargs.get("extra", {}).get("extra", {})
```

### Integration Tests
```python
async def test_graph_execution_correlation():
    """Test correlation ID flows through graph execution."""
    graph = SmartScraperGraph(prompt="Test", source="http://example.com")

    # Capture logs
    with capture_logs() as logs:
        result = await graph.run()

    # All logs should have same correlation ID
    correlation_ids = {log["correlation_id"] for log in logs}
    assert len(correlation_ids) == 1

def test_performance_logging():
    """Test execution time is logged correctly."""
    logger = get_logger("test")

    with capture_logs() as logs:
        with log_execution_time(logger, "test_operation"):
            time.sleep(0.1)

    # Should have start and complete logs
    assert len(logs) == 2
    assert "duration_ms" in logs[1]
    assert logs[1]["duration_ms"] >= 100  # At least 100ms
```

## Migration Strategy

### Backward Compatibility
Maintain existing API while adding new capabilities:

```python
# Old API continues to work
logger = get_logger(__name__)
logger.info("Simple message")

# New API available for structured logging
logger.info("Structured message", user_id="123", graph_id="456")
```

### Migration Steps
1. Deploy new logging system with human-readable format by default
2. No code changes required for existing functionality
3. Teams can opt-in to structured logging incrementally
4. Switch to JSON format in production via environment variable
5. Gradually update code to include rich context

### Environment Variables
```bash
# Development (default)
LOG_FORMAT=human
LOG_LEVEL=INFO

# Production
LOG_FORMAT=json
LOG_LEVEL=WARNING
LOG_CORRELATION_ID=true
LOG_CONTEXT=true
```

## Performance Considerations

### Overhead Analysis
- **Correlation ID lookup**: ~0.1μs (ContextVar is very fast)
- **JSON serialization**: ~10-50μs per log (negligible compared to I/O)
- **Context enrichment**: ~1-5μs per field

### Optimization Strategies
1. **Lazy evaluation**: Only serialize to JSON when actually logging
2. **Sampling**: Log only percentage of high-volume events
3. **Async logging**: Use QueueHandler for non-blocking logging
4. **Rate limiting**: Limit logs per second for chatty operations

### Memory Impact
- Correlation ID storage: ~100 bytes per execution context
- Log buffer: Configurable, default to system defaults
- No significant memory overhead expected

## Alternatives Considered

### Alternative 1: Use structlog Library
**Pros:**
- Mature, well-tested library
- Rich features out of the box
- Strong community support

**Cons:**
- External dependency
- Learning curve for team
- May be overkill for current needs
- Harder to customize for specific needs

**Decision:** Build custom solution for now, migrate to structlog if complexity grows

### Alternative 2: Use OpenTelemetry
**Pros:**
- Industry standard
- Comprehensive tracing and metrics
- Great ecosystem

**Cons:**
- Much heavier dependency
- Significant complexity
- Overkill for logging-only solution

**Decision:** Consider for future distributed tracing initiative

### Alternative 3: Keep Current System
**Pros:**
- No work required
- No learning curve

**Cons:**
- Doesn't solve production debugging problems
- No correlation across components
- Limited observability

**Decision:** Not viable for production needs

## Open Questions

1. **Log Retention**: How long should we retain logs in production?
   - *Suggestion:* 30 days in hot storage, 1 year in cold storage

2. **PII Handling**: How to handle personally identifiable information in logs?
   - *Suggestion:* Implement PII redaction filters, document which fields to avoid

3. **Cost Impact**: What's the cost impact of JSON logging on log storage?
   - *Action:* Run benchmarks with realistic workloads

4. **External Services**: Should we log full request/response bodies for external APIs?
   - *Suggestion:* Log headers always, bodies only at DEBUG level with size limits

5. **Sampling Strategy**: What percentage of logs should we sample in high-volume scenarios?
   - *Suggestion:* 100% for errors, 10% for info, 1% for debug, configurable per logger

## Success Metrics

- **Debugging Time**: Reduce average time to diagnose production issues by 50%
- **Log Query Time**: 90% of log queries complete in <5 seconds
- **Correlation Coverage**: 100% of graph executions have correlation IDs
- **Adoption Rate**: 80% of new code uses structured logging within 3 months
- **Performance Impact**: <5% overhead on execution time
- **Storage Efficiency**: Log storage costs increase <20% despite richer data

## References

- [Python Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)
- [Structured Logging Best Practices](https://engineering.grab.com/structured-logging)
- [Correlation IDs for Microservices](https://www.rapid7.com/blog/post/2016/12/23/the-value-of-correlation-ids/)
- [JSON Logging in Python](https://github.com/madzak/python-json-logger)
- [ContextVars in Python](https://docs.python.org/3/library/contextvars.html)
- [12-Factor App: Logs](https://12factor.net/logs)
- [Google Cloud Structured Logging](https://cloud.google.com/logging/docs/structured-logging)

## Appendix: Code Examples

### Example 1: Basic Usage
```python
from scrapegraphai.utils.logging import get_logger

logger = get_logger(__name__)

# Simple logging (backward compatible)
logger.info("Scraping started")

# Structured logging with context
logger.info(
    "Scraping completed",
    url="https://example.com",
    items_scraped=42,
    duration_ms=1234.56
)
```

### Example 2: Graph Execution
```python
class CustomGraph(BaseGraph):
    def run(self, user_id: str):
        # Correlation ID automatically set
        logger = get_logger(__name__)

        logger.info(
            "Custom graph execution",
            user_id=user_id,
            graph_type="custom"
        )

        with log_execution_time(logger, "custom_processing"):
            result = self._process()

        return result
```

### Example 3: Error Tracking
```python
try:
    result = scrape_website(url)
except Exception as e:
    logger.error(
        "Scraping failed",
        url=url,
        error_type=type(e).__name__,
        error_message=str(e),
        retry_count=retry_count,
        exc_info=True  # Include stack trace
    )
    raise
```

### Example 4: LLM Call Tracking
```python
def call_llm(prompt: str, model: str):
    logger = get_logger(__name__)

    logger.debug(
        "LLM request",
        model=model,
        prompt_length=len(prompt),
        correlation_id=get_correlation_id()
    )

    start_time = time.perf_counter()
    response = llm_client.generate(prompt, model)
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "LLM response received",
        model=model,
        tokens_used=response.tokens,
        duration_ms=duration_ms,
        estimated_cost=calculate_cost(response.tokens, model)
    )

    return response
```

---

**Document Status:** Ready for Review
**Next Steps:** Review by architecture team, gather feedback, create implementation tickets
