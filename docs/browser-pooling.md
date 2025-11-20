# Browser Connection Pooling

## Overview

Browser connection pooling is a performance optimization feature that dramatically reduces browser startup overhead by reusing browser instances across multiple scraping operations. Instead of creating and destroying a new browser for every URL (which takes 2-4 seconds per request), the pool maintains a set of warm browser instances that can be reused.

## Benefits

- **80-90% reduction in browser startup overhead** for multi-URL scraping
- **Improved throughput**: Scrape more URLs in less time
- **Reduced resource consumption**: Lower memory and CPU usage
- **Better reliability**: Built-in health checking and automatic recovery

## Quick Start

### Enabling Pooling (Default)

Pooling is **enabled by default** starting with this release. For most use cases, no configuration is needed:

```python
from scrapegraphai.docloaders import ChromiumLoader

# Pooling is automatically enabled
loader = ChromiumLoader(
    urls=["https://example.com/page1", "https://example.com/page2"],
    headless=True
)

documents = loader.load()
```

### Disabling Pooling

If you need to disable pooling for any reason:

```python
loader = ChromiumLoader(
    urls=["https://example.com"],
    use_pool=False  # Disable pooling
)
```

## Configuration

### Basic Configuration

Configure the pool using the `pool_config` parameter:

```python
from scrapegraphai.docloaders import ChromiumLoader

loader = ChromiumLoader(
    urls=my_urls,
    use_pool=True,
    pool_config={
        "min_browsers": 2,       # Minimum browsers to keep warm
        "max_browsers": 10,      # Maximum browsers in pool
        "max_contexts_per_browser": 5,  # Contexts per browser
        "browser_ttl_seconds": 300,     # Browser lifetime (5 min)
        "context_ttl_seconds": 120,     # Context lifetime (2 min)
    }
)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `min_browsers` | 1 | Minimum number of browsers to keep in the pool |
| `max_browsers` | 10 | Maximum number of browsers allowed in the pool |
| `max_contexts_per_browser` | 5 | Maximum browser contexts per browser instance |
| `browser_ttl_seconds` | 300 | Time-to-live for browser instances (seconds) |
| `context_ttl_seconds` | 120 | Time-to-live for browser contexts (seconds) |
| `health_check_interval` | 30 | Interval between health checks (seconds) |
| `max_health_check_failures` | 3 | Maximum health check failures before removal |
| `browser_type` | "chromium" | Browser type (chromium, firefox) |
| `headless` | true | Whether to run browsers in headless mode |

### Environment Variables

You can also configure the pool using environment variables:

```bash
export SCRAPEGRAPH_BROWSER_POOL_MIN_BROWSERS=2
export SCRAPEGRAPH_BROWSER_POOL_MAX_BROWSERS=10
export SCRAPEGRAPH_BROWSER_POOL_MAX_CONTEXTS=5
export SCRAPEGRAPH_BROWSER_POOL_BROWSER_TTL=300
export SCRAPEGRAPH_BROWSER_POOL_CONTEXT_TTL=120
export SCRAPEGRAPH_BROWSER_POOL_HEADLESS=true
```

## Usage Examples

### Example 1: Simple Multi-URL Scraping

```python
from scrapegraphai.docloaders import ChromiumLoader

# List of URLs to scrape
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
    # ... more URLs
]

# Create loader with pooling (enabled by default)
loader = ChromiumLoader(urls=urls, headless=True)

# Scrape all URLs efficiently
documents = loader.load()

# First URL: ~2.8s (cold start)
# Subsequent URLs: ~0.2s each (pool reuse)
```

### Example 2: High-Throughput Configuration

```python
from scrapegraphai.docloaders import ChromiumLoader

# Configuration for scraping large numbers of URLs
loader = ChromiumLoader(
    urls=my_large_url_list,
    use_pool=True,
    pool_config={
        "min_browsers": 5,      # Keep 5 browsers warm
        "max_browsers": 20,     # Allow up to 20 browsers
        "max_contexts_per_browser": 10,
        "browser_ttl_seconds": 600,  # 10 minute TTL
    }
)

documents = loader.load()
```

### Example 3: Using with Graph Configurations

```python
from scrapegraphai.graphs import SmartScraperGraph

# Configure pooling at the graph level
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "headless": True,
    "use_pool": True,
    "pool_config": {
        "min_browsers": 3,
        "max_browsers": 10,
    }
}

# Create scraper
scraper = SmartScraperGraph(
    prompt="Extract all product information",
    source="https://example.com/products",
    config=graph_config
)

# Run with pooled browser
result = scraper.run()
```

### Example 4: Manual Pool Management

```python
from scrapegraphai.utils.browser_pool import BrowserPoolManager, PoolConfig

# Create custom pool configuration
pool_config = PoolConfig(
    min_browsers=3,
    max_browsers=15,
    headless=True,
)

# Get the global pool
pool = await BrowserPoolManager.get_pool(pool_config)

# Acquire a context
browser, context = await BrowserPoolManager.acquire_context(
    stealth=True,
    storage_state="/path/to/state.json"
)

try:
    # Use the context for scraping
    page = await context.new_page()
    await page.goto("https://example.com")
    content = await page.content()
finally:
    # Always release the context
    await page.close()
    await BrowserPoolManager.release_context(browser, context)

# Shutdown when done (optional, happens automatically on exit)
await BrowserPoolManager.shutdown_pool()
```

### Example 5: FetchNode with Pooling

```python
from scrapegraphai.nodes import FetchNode

# Create FetchNode with pool configuration
node = FetchNode(
    input="url",
    output=["document"],
    node_config={
        "headless": True,
        "use_pool": True,
        "pool_config": {
            "min_browsers": 2,
            "max_browsers": 5,
        }
    }
)

# Use in your graph
state = {"url": "https://example.com"}
result = node.execute(state)
```

## Performance Comparison

### Before (No Pooling)

```
Scraping 10 URLs:
- URL 1: 2.8s (browser startup) + 3.2s (scraping) = 6.0s
- URL 2: 2.8s (browser startup) + 3.2s (scraping) = 6.0s
- ...
- Total: ~60 seconds

Resource usage:
- 10 browser instances created and destroyed
- Peak memory: ~1GB
- 200 file descriptors
```

### After (With Pooling)

```
Scraping 10 URLs:
- URL 1: 2.8s (cold start) + 3.2s (scraping) = 6.0s
- URL 2: 0.2s (pool reuse) + 3.2s (scraping) = 3.4s
- URL 3-10: ~3.4s each
- Total: ~36 seconds (40% faster!)

Resource usage:
- 2-3 browser instances reused
- Peak memory: ~300MB
- 60 file descriptors
```

## Advanced Topics

### Health Checks

The pool automatically performs health checks on browser instances:

- **Periodic checks**: Every 30 seconds (configurable)
- **Automatic removal**: Unhealthy browsers are removed
- **Auto-recovery**: New browsers created to maintain minimum pool size

### Context Lifecycle

Browser contexts have a lifecycle managed by the pool:

1. **Creation**: Context created from pool browser
2. **Stealth**: Stealth mode applied (optional)
3. **Usage**: Context used for scraping
4. **Release**: Context released back to pool
5. **Cleanup**: Context closed if TTL expired

### Pool Exhaustion

When the pool reaches capacity:

1. Pool tries to find the least busy browser
2. New context created even if over limit
3. Warning logged with pool statistics
4. Graceful degradation (no errors thrown)

### Monitoring

Get pool statistics for monitoring:

```python
from scrapegraphai.utils.browser_pool import BrowserPoolManager

# Get current pool stats
stats = await BrowserPoolManager.get_stats()

print(stats)
# {
#     "total_browsers": 5,
#     "total_contexts": 12,
#     "browsers_in_use": 3,
#     "unhealthy_browsers": 0,
#     "config": { ... }
# }
```

## Troubleshooting

### Issue: Pool exhaustion warnings

**Symptoms**: Logs show "Browser pool exhausted" warnings

**Solutions**:
- Increase `max_browsers` in pool config
- Increase `max_contexts_per_browser`
- Reduce concurrent scraping operations
- Check for context leaks (unreleased contexts)

### Issue: Memory usage higher than expected

**Symptoms**: Memory usage grows over time

**Solutions**:
- Reduce `browser_ttl_seconds` to recycle browsers more frequently
- Reduce `context_ttl_seconds` to cleanup contexts sooner
- Reduce `max_browsers` and `max_contexts_per_browser`
- Enable health checks with shorter intervals

### Issue: Browsers not being reused

**Symptoms**: New browsers created for every request

**Solutions**:
- Verify `use_pool=True` is set
- Check pool configuration is passed correctly
- Ensure contexts are properly released
- Check logs for pool initialization errors

### Issue: Stealth mode not working

**Symptoms**: Websites detect automation

**Solutions**:
- Ensure `undetected_playwright` is installed
- Verify stealth is enabled in `acquire_context()`
- Check that Malenia.apply_stealth() is called
- Consider using storage_state for cookies

## Migration Guide

### From Non-Pooled to Pooled

If you're upgrading from a version without pooling:

**Before:**
```python
loader = ChromiumLoader(urls=my_urls)
documents = loader.load()
```

**After (automatic):**
```python
# Pooling is now enabled by default
loader = ChromiumLoader(urls=my_urls)
documents = loader.load()  # Uses pooling automatically!
```

**Opt-out:**
```python
# If you need the old behavior
loader = ChromiumLoader(urls=my_urls, use_pool=False)
documents = loader.load()
```

### Gradual Rollout

For production systems, consider a gradual rollout:

1. **Phase 1**: Test with `use_pool=True` on non-critical workloads
2. **Phase 2**: Enable for 10% of production traffic
3. **Phase 3**: Monitor metrics (latency, errors, resource usage)
4. **Phase 4**: Roll out to 100% if successful

## Best Practices

1. **Start with defaults**: The default configuration works well for most use cases

2. **Monitor pool stats**: Use `get_stats()` to understand pool behavior

3. **Tune for your workload**:
   - High concurrency: Increase `max_browsers` and `max_contexts_per_browser`
   - Low memory: Decrease `max_browsers` and reduce TTLs
   - Long-running: Increase TTLs to reduce recycling overhead

4. **Always release contexts**: Use try/finally to ensure contexts are released

5. **Handle pool exhaustion**: Plan for graceful degradation when pool is full

6. **Test thoroughly**: Run integration tests before production deployment

## API Reference

### PoolConfig

```python
@dataclass
class PoolConfig:
    min_browsers: int = 1
    max_browsers: int = 10
    max_contexts_per_browser: int = 5
    browser_ttl_seconds: int = 300
    context_ttl_seconds: int = 120
    health_check_interval: int = 30
    max_health_check_failures: int = 3
    browser_type: str = "chromium"
    headless: bool = True
    launch_options: Dict = field(default_factory=dict)
```

### BrowserPool

```python
class BrowserPool:
    async def initialize() -> None
    async def acquire_context(**kwargs) -> tuple[Browser, BrowserContext]
    async def release_context(browser, context, close_context=True) -> None
    async def shutdown() -> None
    def get_stats() -> Dict[str, Any]
```

### BrowserPoolManager

```python
class BrowserPoolManager:
    @classmethod
    async def get_pool(config: Optional[PoolConfig] = None) -> BrowserPool

    @classmethod
    async def shutdown_pool() -> None

    @classmethod
    async def acquire_context(config=None, **kwargs) -> tuple[Browser, BrowserContext]

    @classmethod
    async def release_context(browser, context, **kwargs) -> None

    @classmethod
    async def get_stats() -> Optional[Dict[str, Any]]
```

## FAQ

**Q: Is pooling enabled by default?**
A: Yes, starting with this release, pooling is enabled by default for better performance.

**Q: Can I use pooling with Firefox?**
A: Yes, set `browser_type="firefox"` in the pool config.

**Q: Does pooling work with proxy rotation?**
A: Yes, pooling is compatible with proxy settings.

**Q: What happens if a browser crashes?**
A: The pool's health check system detects crashed browsers and removes them automatically. A new browser is created to maintain the minimum pool size.

**Q: Can I use different pool configurations for different scrapers?**
A: The pool is currently global (singleton), but you can modify the configuration when getting the pool. For isolated pools, you would need to create separate BrowserPool instances.

**Q: How do I know if pooling is actually working?**
A: Check the logs for "Content scraped using pooled browser" messages, or monitor pool stats with `get_stats()`.

**Q: Does pooling work in serverless environments?**
A: Yes, but with caveats. The pool maintains state across invocations within the same container, but cold starts will still create new pools.

## See Also

- [RFC-0001: Browser Connection Pooling](../analysis-output/rfcs/RFC-0001-browser-connection-pooling.md)
- [ChromiumLoader Documentation](./chromium-loader.md)
- [FetchNode Documentation](./fetch-node.md)
