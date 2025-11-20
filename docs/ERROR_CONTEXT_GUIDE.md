# Enhanced Error Context & Recovery Guide

This guide explains how to use the enhanced error context capture and retry features in ScrapeGraphAI.

## Overview

ScrapeGraphAI now includes powerful error debugging capabilities that automatically capture:

- **Screenshots** of the page at failure time
- **HTML content** that was actually loaded
- **Browser console logs** (JavaScript errors)
- **Network activity** (failed requests, blocked resources)
- **Page state** (cookies, localStorage, sessionStorage)
- **Request/response metadata** (status codes, headers)

Additionally, intelligent **retry strategies** help recover from transient failures automatically.

## Quick Start

### Basic Usage with Default Settings

Error context capture is **enabled by default** with sensible defaults:

```python
from scrapegraphai.graphs import SmartScraperGraph

graph_config = {
    "llm": {"model": "openai/gpt-4"},
}

scraper = SmartScraperGraph(
    prompt="Extract product details",
    source="https://example.com/product",
    config=graph_config
)

try:
    result = scraper.run()
except Exception as e:
    # Error context is automatically captured
    print(f"Error: {e}")
```

### Accessing Error Context

When a scraping error occurs, you can access rich debugging information:

```python
from scrapegraphai.utils.error_context import ScrapingException

try:
    result = scraper.run()
except ScrapingException as e:
    # Print error summary
    print(e.context.get_summary())

    # Access specific context fields
    print(f"Screenshot: {e.context.screenshot_path}")
    print(f"HTML length: {e.context.html_length} bytes")
    print(f"Status code: {e.context.status_code}")
    print(f"Console errors: {len(e.context.console_logs)}")

    # Full context as JSON
    print(e.context.to_json())
```

## Configuration

### Error Context Configuration

Customize error context capture behavior:

```python
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "capture_error_context": True,  # Enable/disable error context
    "error_artifacts_dir": "./my_debug_files",  # Where to save artifacts
}
```

### Node-Level Configuration

Configure error context for specific nodes:

```python
from scrapegraphai.nodes import FetchNode

node_config = {
    "headless": True,
    "capture_error_context": True,
    "error_artifacts_dir": "./fetch_errors",
}

fetch_node = FetchNode(
    input="url",
    output=["document"],
    node_config=node_config,
)
```

### ChromiumLoader Configuration

Configure error context directly in ChromiumLoader:

```python
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.retry_policy import RetryPolicy

loader = ChromiumLoader(
    urls=["https://example.com"],
    headless=True,
    capture_error_context=True,
    error_artifacts_dir="./loader_errors",
    retry_policy=RetryPolicy(max_attempts=5),
)
```

## Retry Policies

### Using Default Retry Policy

The default retry policy uses exponential backoff with jitter:

```python
# Default: 3 attempts with exponential backoff
graph_config = {
    "llm": {"model": "openai/gpt-4"},
}
```

### Custom Retry Policy

Configure retry behavior for your specific needs:

```python
from scrapegraphai.utils.retry_policy import RetryPolicy, RetryStrategy

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "retry_policy": {
        "max_attempts": 5,
        "strategy": "exponential_jitter",
        "base_delay": 2.0,  # Start with 2 second delay
        "max_delay": 60.0,  # Cap at 60 seconds
    },
}
```

### Retry Strategies

Available retry strategies:

#### Immediate Retry
```python
retry_policy = {
    "max_attempts": 3,
    "strategy": "immediate",  # No delay between retries
}
```

#### Fixed Delay
```python
retry_policy = {
    "max_attempts": 3,
    "strategy": "fixed",
    "base_delay": 5.0,  # Always wait 5 seconds
}
```

#### Exponential Backoff
```python
retry_policy = {
    "max_attempts": 5,
    "strategy": "exponential",
    "base_delay": 1.0,  # 1s, 2s, 4s, 8s, 16s
    "exponential_base": 2.0,
}
```

#### Exponential Backoff with Jitter (Recommended)
```python
retry_policy = {
    "max_attempts": 5,
    "strategy": "exponential_jitter",
    "base_delay": 1.0,
    "max_delay": 30.0,
    "jitter_range": 0.1,  # ±10% randomness
}
```

### Custom Error Classification

Define which errors should be retried:

```python
from scrapegraphai.utils.retry_policy import RetryPolicy, ErrorCategory

def custom_classifier(error: Exception) -> ErrorCategory:
    """Classify errors for retry decisions."""
    error_str = str(error).lower()

    # Retry bot detection
    if "cloudflare" in error_str or "challenge" in error_str:
        return ErrorCategory.TRANSIENT

    # Don't retry missing content
    if "not found" in error_str:
        return ErrorCategory.PERMANENT

    return ErrorCategory.UNKNOWN

retry_policy = RetryPolicy(
    max_attempts=5,
    error_classifier=custom_classifier,
)
```

## Error Artifacts

### What's Saved

When `save_to_disk` is enabled, the following files are created:

- `error_YYYYMMDD_HHMMSS_context.json` - Full error context
- `error_YYYYMMDD_HHMMSS_screenshot.png` - Screenshot of page
- `error_YYYYMMDD_HHMMSS_page.html` - HTML content
- `error_YYYYMMDD_HHMMSS_console.json` - Console logs
- `error_YYYYMMDD_HHMMSS_network.json` - Network logs

### Accessing Saved Artifacts

```python
from scrapegraphai.utils.error_context import ScrapingException

try:
    result = scraper.run()
except ScrapingException as e:
    context = e.context

    # Check what was saved
    if "saved_files" in context.metadata:
        files = context.metadata["saved_files"]
        print(f"Context JSON: {files['context']}")
        print(f"Screenshot: {files['screenshot']}")
        print(f"HTML: {files['html']}")
```

### Manual Saving

Save error context manually:

```python
from pathlib import Path

saved_files = context.save_to_disk(Path("./my_errors"))
print(f"Saved files: {saved_files}")
```

## Use Cases

### Debugging Production Failures

```python
import logging
from scrapegraphai.utils.error_context import ScrapingException

# Configure logging
logger = logging.getLogger("scraper")

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "capture_error_context": True,
    "error_artifacts_dir": "./production_errors",
    "retry_policy": {"max_attempts": 5},
}

try:
    scraper = SmartScraperGraph(
        prompt="Extract data",
        source=url,
        config=graph_config
    )
    result = scraper.run()
    logger.info("Scraping successful")

except ScrapingException as e:
    # Log detailed error information
    logger.error(f"Scraping failed: {e.context.get_summary()}")

    # Alert if bot detection
    if e.context.status_code == 403:
        alert_team("Bot detection triggered", e.context)

    # Save for later analysis
    raise
```

### Handling Rate Limits

```python
from scrapegraphai.utils.retry_policy import RetryPolicy, ErrorCategory

def rate_limit_classifier(error):
    """Classify rate limit errors as transient."""
    if "429" in str(error) or "rate limit" in str(error).lower():
        return ErrorCategory.TRANSIENT
    return ErrorCategory.UNKNOWN

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "retry_policy": {
        "max_attempts": 10,
        "strategy": "exponential_jitter",
        "base_delay": 5.0,  # Start with 5s delay for rate limits
        "max_delay": 300.0,  # Up to 5 minutes
        "error_classifier": rate_limit_classifier,
    },
}
```

### Testing and Development

```python
# Aggressive retries for flaky test environments
test_config = {
    "llm": {"model": "openai/gpt-4"},
    "capture_error_context": True,
    "error_artifacts_dir": "./test_failures",
    "retry_policy": {
        "max_attempts": 10,
        "strategy": "exponential_jitter",
        "base_delay": 1.0,
    },
}

# No retries for unit tests
unit_test_config = {
    "llm": {"model": "openai/gpt-4"},
    "capture_error_context": False,
    "retry_policy": {
        "max_attempts": 1,  # Fail fast
    },
}
```

## Advanced Features

### Programmatic Retry Policy

Create retry policies programmatically:

```python
from scrapegraphai.utils.retry_policy import (
    RetryPolicy,
    RetryStrategy,
    DEFAULT_RETRY_POLICY,
    AGGRESSIVE_RETRY_POLICY,
    NO_RETRY_POLICY,
)

# Use predefined policies
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "retry_policy": AGGRESSIVE_RETRY_POLICY,
}

# Or create custom
custom_policy = RetryPolicy(
    max_attempts=7,
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    base_delay=2.0,
    max_delay=120.0,
)

graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "retry_policy": custom_policy,
}
```

### Error Context in State

Access error context from graph state:

```python
state = {"url": "https://example.com"}

try:
    result = graph.execute(state)
except Exception:
    # Error context is attached to state
    if "error_context" in state:
        context = state["error_context"]
        print(f"Error occurred at: {context.final_url}")
        print(f"Screenshot: {context.screenshot_path}")
```

### Custom Error Handlers

Implement custom retry and failure handlers:

```python
from scrapegraphai.utils.error_context import ErrorContextManager

def on_retry(attempt, error, context):
    """Called before each retry."""
    print(f"Retry {attempt}: {error}")
    if context.screenshot_path:
        print(f"Screenshot saved: {context.screenshot_path}")

def on_failure(error, context):
    """Called when all retries exhausted."""
    print(f"Failed after {context.total_attempts} attempts")
    # Send alert, log to external service, etc.

manager = ErrorContextManager(
    retry_policy=retry_policy,
    on_retry=on_retry,
    on_failure=on_failure,
)
```

## Best Practices

### 1. Use Appropriate Retry Strategies

- **Exponential backoff with jitter** - Best for most cases
- **Fixed delay** - When you know the recovery time
- **Immediate** - For fast-failing tests

### 2. Set Reasonable Max Attempts

- **3-5 attempts** - Production scraping
- **1-2 attempts** - Development/testing
- **10+ attempts** - Handling rate limits

### 3. Classify Errors Correctly

Don't retry permanent errors:
- 404 Not Found
- 403 Forbidden
- Invalid URLs
- Bad input data

Do retry transient errors:
- Timeouts
- Network errors
- 429 Rate limits
- 503 Service Unavailable

### 4. Secure Error Artifacts

- Don't commit error artifacts to version control
- Add `error_artifacts/` to `.gitignore`
- Sanitize sensitive data before saving
- Set appropriate file permissions

### 5. Monitor Error Patterns

```python
# Track error metrics
error_counts = {}

try:
    result = scraper.run()
except ScrapingException as e:
    error_type = e.context.error_type
    error_counts[error_type] = error_counts.get(error_type, 0) + 1

    # Alert on patterns
    if error_counts[error_type] > 10:
        alert_team(f"High frequency of {error_type}")
```

## Troubleshooting

### Error Context Not Being Captured

Check that error context is enabled:

```python
# Verify configuration
loader = ChromiumLoader(...)
assert loader.capture_error_context is True
```

### Screenshots Not Saving

Ensure output directory is writable:

```python
from pathlib import Path

output_dir = Path("./error_artifacts")
output_dir.mkdir(parents=True, exist_ok=True)
```

### Retries Not Working

Verify retry policy configuration:

```python
assert loader.retry_policy is not None
assert loader.retry_policy.max_attempts > 1
```

### Large Artifact Files

Reduce artifact size:

```python
capture_config = {
    "capture_screenshot": True,
    "capture_html": True,
    "capture_console": True,
    "capture_network": False,  # Disable if too large
    "capture_storage": False,  # Disable if too large
}
```

## Performance Considerations

### Overhead

Error context capture only happens **on failures**, not successful scrapes:

- Screenshot capture: 100-300ms
- HTML export: 10-50ms
- Total overhead: ~120-370ms per failure

### Minimizing Impact

1. Disable in production if not needed:
```python
graph_config = {
    "capture_error_context": False,  # Disable for performance
}
```

2. Reduce capture scope:
```python
capture_config = {
    "capture_screenshot": True,  # Keep essential
    "capture_html": True,        # Keep essential
    "capture_console": False,    # Disable if not needed
    "capture_network": False,    # Disable if not needed
}
```

3. Don't save to disk in production:
```python
capture_config = {
    "save_to_disk": False,  # Keep in memory only
}
```

## Examples

See the `tests/` directory for comprehensive examples:

- `tests/utils/test_retry_policy.py` - Retry policy examples
- `tests/utils/test_error_context.py` - Error context examples
- `tests/test_error_context_integration.py` - Integration examples

## Support

For questions or issues:

1. Check the [GitHub Issues](https://github.com/ScrapeGraphAI/Scrapegraph-ai/issues)
2. Join the [Discord community](https://discord.gg/scrapegraphai)
3. Read the [main documentation](https://scrapegraphai.com/docs)

## Migration Guide

### From Previous Versions

The new error context features are **backward compatible**. Existing code will continue to work without changes.

To enable error context in existing code:

```python
# Before
graph_config = {
    "llm": {"model": "openai/gpt-4"},
}

# After (explicitly enable)
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "capture_error_context": True,
    "error_artifacts_dir": "./my_errors",
    "retry_policy": {
        "max_attempts": 5,
    },
}
```

No code changes required - error context is enabled by default!
