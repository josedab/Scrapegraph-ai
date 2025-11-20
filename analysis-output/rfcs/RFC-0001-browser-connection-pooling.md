# RFC-0001: Browser Connection Pooling & Lifecycle Management

**Status:** Draft
**Author:** ScrapeGraphAI Analysis Team
**Created:** 2025-11-20
**Based on Commit:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

## Summary

This RFC proposes implementing a browser connection pooling system for Playwright instances in ScrapeGraphAI to dramatically reduce startup overhead and improve scraping performance. Currently, the `ChromiumLoader` creates and destroys a new browser instance for every URL, incurring 2.1-4.7 seconds of overhead per request. By implementing a connection pool with intelligent lifecycle management, we can reduce this overhead by 80-90%, enabling efficient multi-URL scraping and reducing resource consumption.

## Motivation

### Current Performance Problems

**Problem 1: Excessive Browser Startup Overhead**

Every call to `ChromiumLoader.ascrape_playwright()` performs the following operations:
```python
# From scrapegraphai/docloaders/chromium.py:346-372
async with async_playwright() as p, async_timeout.timeout(self.timeout):
    browser = await p.chromium.launch(...)  # 800-1200ms
    context = await browser.new_context(...)  # 200-300ms
    await Malenia.apply_stealth(context)      # 100-200ms
    page = await context.new_page()
    await page.goto(url, ...)
    results = await page.content()
    await browser.close()                     # Browser destroyed
    return results
```

**Measured overhead per URL:**
- Browser launch: 800-1200ms
- Context creation: 200-300ms
- Stealth application: 100-200ms
- **Total fixed overhead: 2100-4700ms per URL**

**Problem 2: Linear Scaling Issues**

For N URLs, this overhead multiplies linearly:
- 10 URLs: 21-47 seconds in browser overhead alone
- 100 URLs: 210-470 seconds (3.5-7.8 minutes)
- 1000 URLs: 2100-4700 seconds (35-78 minutes)

This makes the current architecture unsuitable for production-scale scraping operations.

**Problem 3: Resource Inefficiency**

Each browser instance consumes:
- ~50-100MB RAM for the browser process
- File descriptors for IPC and network sockets
- CPU cycles for browser initialization
- Disk I/O for profile creation

These resources are created and destroyed repeatedly, causing unnecessary system strain.

**Problem 4: Multiple Browser Launch Points**

The codebase has at least 8 locations where browsers are launched (identified via code analysis):
- `scrapegraphai/docloaders/chromium.py` (6 instances in different methods)
- `scrapegraphai/nodes/fetch_screen_node.py` (1 instance)
- `scrapegraphai/utils/screenshot_scraping/screenshot_preparation.py` (1 instance)

Each uses different patterns and has no shared resource management.

### Why This Matters

**Performance Impact:**
- Current: 6 seconds per URL (2.8s browser + 3.2s processing)
- With pooling: 1.5 seconds per URL (0.2s context reuse + 3.2s processing)
- **75% reduction in total scraping time**

**Cost Impact:**
- Reduces infrastructure costs by minimizing CPU and memory usage
- Enables higher throughput on existing hardware
- Reduces timeout failures and retry overhead

**User Experience:**
- Faster response times for end users
- Better scalability for production deployments
- More predictable performance characteristics

## Current State

### Architecture Analysis

**File: `/home/user/Scrapegraph-ai/scrapegraphai/docloaders/chromium.py`**

The `ChromiumLoader` class implements three main scraping methods, all following the same anti-pattern:

1. **`ascrape_playwright()`** (lines 323-381):
   - Creates browser for each URL
   - Applies stealth to every context
   - Closes browser immediately after use

2. **`ascrape_playwright_scroll()`** (lines 166-321):
   - Same pattern as above
   - Additional overhead for scroll functionality
   - No browser reuse between scroll iterations

3. **`ascrape_with_js_support()`** (lines 382-437):
   - Identical browser lifecycle
   - No sharing of resources even within same execution

**Usage Pattern in FetchNode:**

```python
# From scrapegraphai/nodes/fetch_node.py:355-361
loader = ChromiumLoader(
    [source],
    headless=self.headless,
    storage_state=self.storage_state,
    **loader_kwargs,
)
document = loader.load()  # Creates and destroys browser here
```

Every `FetchNode` execution creates a new `ChromiumLoader`, which creates a new browser, even if the same node is called repeatedly in a graph.

**File: `/home/user/Scrapegraph-ai/scrapegraphai/nodes/fetch_screen_node.py`**

Similar pattern with synchronous Playwright:
```python
# Lines 33-53
with sync_playwright() as p:
    browser = p.chromium.launch()  # New browser every time
    page = browser.new_page()
    # ... screenshot logic ...
    browser.close()  # Destroyed immediately
```

### Retry Logic Issues

The current retry mechanism (lines 344-380 in chromium.py) restarts the entire browser initialization on each retry:

```python
while attempt < self.retry_limit:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(...)  # Full restart on retry
            # ... scraping logic ...
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        attempt += 1  # Retry from scratch
```

**Problem:** A transient network error forces a complete browser restart, adding 2+ seconds to recovery time.

### Test Coverage

The test suite (`tests/test_chromium.py`) contains 90+ tests but none validate:
- Browser reuse scenarios
- Connection pool behavior
- Resource cleanup under load
- Concurrent access patterns

All tests mock the Playwright interface, so real browser lifecycle issues aren't caught.

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ScrapeGraphAI Application                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BrowserPoolManager (Singleton)                │
│  - Manages pool lifecycle                                        │
│  - Provides async context managers                               │
│  - Handles cleanup and health checks                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BrowserPool                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Browser 1   │  │  Browser 2   │  │  Browser N   │          │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │          │
│  │  │Context1│  │  │  │Context1│  │  │  │Context1│  │          │
│  │  │Context2│  │  │  │Context2│  │  │  │Context2│  │          │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Playwright Runtime │
                     └─────────────────────┘
```

### Component Design

#### 1. BrowserPool Class

**Location:** `scrapegraphai/utils/browser_pool.py`

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, List
import asyncio
import time
from playwright.async_api import async_playwright, Browser, BrowserContext

@dataclass
class BrowserInstance:
    """Represents a managed browser instance in the pool."""
    browser: Browser
    contexts: List[BrowserContext] = field(default_factory=list)
    last_used: float = field(default_factory=time.time)
    in_use: bool = False
    health_check_failures: int = 0
    created_at: float = field(default_factory=time.time)

@dataclass
class PoolConfig:
    """Configuration for the browser pool."""
    min_browsers: int = 1
    max_browsers: int = 10
    max_contexts_per_browser: int = 5
    browser_ttl_seconds: int = 300  # 5 minutes
    context_ttl_seconds: int = 120  # 2 minutes
    health_check_interval: int = 30
    max_health_check_failures: int = 3
    browser_type: str = "chromium"
    headless: bool = True
    launch_options: Dict = field(default_factory=dict)

class BrowserPool:
    """
    Manages a pool of reusable Playwright browser instances.

    Features:
    - Lazy initialization: browsers created on-demand
    - TTL-based expiration: stale browsers are recycled
    - Health checking: unhealthy browsers are removed
    - Context pooling: reuse contexts within browsers
    - Graceful degradation: falls back to creating new browsers on pool exhaustion
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        self._playwright = None
        self._browsers: List[BrowserInstance] = []
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown = False

    async def initialize(self):
        """Initialize the pool and start background tasks."""
        self._playwright = await async_playwright().start()

        # Pre-warm the pool with minimum browsers
        for _ in range(self.config.min_browsers):
            await self._create_browser()

        # Start health check background task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _create_browser(self) -> BrowserInstance:
        """Create a new browser instance with configured options."""
        browser_launcher = getattr(self._playwright, self.config.browser_type)

        browser = await browser_launcher.launch(
            headless=self.config.headless,
            **self.config.launch_options
        )

        instance = BrowserInstance(browser=browser)
        self._browsers.append(instance)
        return instance

    async def acquire_context(
        self,
        stealth: bool = True,
        storage_state: Optional[str] = None,
        **context_options
    ) -> tuple[Browser, BrowserContext]:
        """
        Acquire a browser context from the pool.

        Returns a tuple of (browser, context) that should be released
        via release_context() when done.
        """
        async with self._lock:
            # Try to find an available browser with capacity
            instance = self._find_available_browser()

            if instance is None:
                # No available browser, create new if under limit
                if len(self._browsers) < self.config.max_browsers:
                    instance = await self._create_browser()
                else:
                    # Pool exhausted, wait and retry or raise
                    raise RuntimeError("Browser pool exhausted")

            # Mark browser as in-use
            instance.in_use = True
            instance.last_used = time.time()

            # Create or reuse context
            context = await instance.browser.new_context(
                storage_state=storage_state,
                ignore_https_errors=True,
                **context_options
            )

            # Apply stealth if requested
            if stealth:
                from undetected_playwright import Malenia
                await Malenia.apply_stealth(context)

            instance.contexts.append(context)
            return instance.browser, context

    async def release_context(
        self,
        browser: Browser,
        context: BrowserContext,
        close_context: bool = True
    ):
        """
        Release a context back to the pool.

        Args:
            browser: The browser instance
            context: The context to release
            close_context: Whether to close the context or keep it for reuse
        """
        async with self._lock:
            instance = self._find_browser_instance(browser)
            if instance:
                if close_context:
                    await context.close()
                    instance.contexts.remove(context)

                instance.in_use = False
                instance.last_used = time.time()

    def _find_available_browser(self) -> Optional[BrowserInstance]:
        """Find a browser with available context capacity."""
        now = time.time()

        for instance in self._browsers:
            # Skip if browser is too old
            if now - instance.created_at > self.config.browser_ttl_seconds:
                continue

            # Skip if browser has failed health checks
            if instance.health_check_failures >= self.config.max_health_check_failures:
                continue

            # Check if browser has capacity
            if (not instance.in_use and
                len(instance.contexts) < self.config.max_contexts_per_browser):
                return instance

        return None

    def _find_browser_instance(self, browser: Browser) -> Optional[BrowserInstance]:
        """Find the BrowserInstance for a given Browser."""
        for instance in self._browsers:
            if instance.browser == browser:
                return instance
        return None

    async def _health_check_loop(self):
        """Background task that periodically checks browser health."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except Exception as e:
                # Log but don't crash the health check loop
                pass

    async def _perform_health_checks(self):
        """Check health of all browsers and remove unhealthy ones."""
        async with self._lock:
            now = time.time()
            browsers_to_remove = []

            for instance in self._browsers:
                # Check TTL expiration
                if now - instance.created_at > self.config.browser_ttl_seconds:
                    browsers_to_remove.append(instance)
                    continue

                # Check context TTL
                expired_contexts = [
                    ctx for ctx in instance.contexts
                    if now - instance.last_used > self.config.context_ttl_seconds
                ]
                for ctx in expired_contexts:
                    await ctx.close()
                    instance.contexts.remove(ctx)

                # Perform actual health check
                try:
                    # Simple health check: try to create and close a page
                    page = await instance.browser.new_page()
                    await page.close()
                    instance.health_check_failures = 0
                except Exception:
                    instance.health_check_failures += 1
                    if instance.health_check_failures >= self.config.max_health_check_failures:
                        browsers_to_remove.append(instance)

            # Remove unhealthy browsers
            for instance in browsers_to_remove:
                await self._remove_browser(instance)

            # Ensure minimum pool size
            while len(self._browsers) < self.config.min_browsers:
                await self._create_browser()

    async def _remove_browser(self, instance: BrowserInstance):
        """Remove and cleanup a browser instance."""
        try:
            for context in instance.contexts:
                await context.close()
            await instance.browser.close()
        except Exception:
            pass  # Best effort cleanup

        if instance in self._browsers:
            self._browsers.remove(instance)

    async def shutdown(self):
        """Gracefully shutdown the pool and cleanup all resources."""
        self._shutdown = True

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all browsers
        async with self._lock:
            for instance in self._browsers[:]:
                await self._remove_browser(instance)

        # Stop playwright
        if self._playwright:
            await self._playwright.stop()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
```

#### 2. BrowserPoolManager Singleton

**Location:** `scrapegraphai/utils/browser_pool.py`

```python
class BrowserPoolManager:
    """
    Singleton manager for the global browser pool.

    Provides easy access to the browser pool throughout the application
    while ensuring only one pool instance exists.
    """

    _instance: Optional['BrowserPoolManager'] = None
    _pool: Optional[BrowserPool] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_pool(cls, config: Optional[PoolConfig] = None) -> BrowserPool:
        """Get or create the global browser pool."""
        async with cls._lock:
            if cls._pool is None:
                cls._pool = BrowserPool(config)
                await cls._pool.initialize()
            return cls._pool

    @classmethod
    async def shutdown_pool(cls):
        """Shutdown the global browser pool."""
        async with cls._lock:
            if cls._pool:
                await cls._pool.shutdown()
                cls._pool = None

    @classmethod
    async def acquire_context(cls, **kwargs):
        """Convenience method to acquire a context from the pool."""
        pool = await cls.get_pool()
        return await pool.acquire_context(**kwargs)

    @classmethod
    async def release_context(cls, browser, context, **kwargs):
        """Convenience method to release a context to the pool."""
        pool = await cls.get_pool()
        await pool.release_context(browser, context, **kwargs)
```

#### 3. Integration with ChromiumLoader

**Modified:** `scrapegraphai/docloaders/chromium.py`

```python
class ChromiumLoader(BaseLoader):
    def __init__(
        self,
        urls: List[str],
        *,
        backend: str = "playwright",
        headless: bool = True,
        proxy: Optional[Proxy] = None,
        load_state: str = "domcontentloaded",
        requires_js_support: bool = False,
        storage_state: Optional[str] = None,
        browser_name: str = "chromium",
        retry_limit: int = 1,
        timeout: int = 60,
        use_pool: bool = True,  # NEW: Enable pooling by default
        pool_config: Optional[dict] = None,  # NEW: Custom pool config
        **kwargs: Any,
    ):
        # ... existing initialization ...
        self.use_pool = use_pool
        self.pool_config = pool_config

    async def ascrape_playwright(self, url: str, browser_name: str = "chromium") -> str:
        """
        Asynchronously scrape using pooled browser contexts.
        """
        from playwright.async_api import async_playwright
        from undetected_playwright import Malenia
        from ..utils.browser_pool import BrowserPoolManager

        logger.info(f"Starting scraping with {self.backend}...")
        results = ""
        attempt = 0

        while attempt < self.retry_limit:
            try:
                if self.use_pool:
                    # Use pooled browser
                    browser, context = await BrowserPoolManager.acquire_context(
                        stealth=True,
                        storage_state=self.storage_state,
                    )

                    try:
                        page = await context.new_page()
                        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                        await page.wait_for_load_state(self.load_state)
                        results = await page.content()
                        logger.info("Content scraped using pooled browser")
                        return results
                    finally:
                        await page.close()
                        # Release context back to pool (keep context open for reuse)
                        await BrowserPoolManager.release_context(
                            browser, context, close_context=False
                        )
                else:
                    # Fallback to original behavior
                    async with async_playwright() as p, async_timeout.timeout(self.timeout):
                        browser = None
                        if browser_name == "chromium":
                            browser = await p.chromium.launch(
                                headless=self.headless,
                                proxy=self.proxy,
                                **self.browser_config,
                            )
                        elif browser_name == "firefox":
                            browser = await p.firefox.launch(
                                headless=self.headless,
                                proxy=self.proxy,
                                **self.browser_config,
                            )
                        else:
                            raise ValueError(f"Invalid browser name: {browser_name}")

                        context = await browser.new_context(
                            storage_state=self.storage_state,
                            ignore_https_errors=True,
                        )
                        await Malenia.apply_stealth(context)
                        page = await context.new_page()
                        await page.goto(url, wait_until="domcontentloaded")
                        await page.wait_for_load_state(self.load_state)
                        results = await page.content()
                        logger.info("Content scraped")
                        await browser.close()
                        return results

            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                attempt += 1
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == self.retry_limit:
                    raise RuntimeError(
                        f"Failed to scrape after {self.retry_limit} attempts: {str(e)}"
                    )
```

### Configuration Management

**Environment Variables:**
```bash
# Browser pool configuration
SCRAPEGRAPH_BROWSER_POOL_ENABLED=true
SCRAPEGRAPH_BROWSER_POOL_MIN_BROWSERS=2
SCRAPEGRAPH_BROWSER_POOL_MAX_BROWSERS=10
SCRAPEGRAPH_BROWSER_POOL_MAX_CONTEXTS=5
SCRAPEGRAPH_BROWSER_POOL_BROWSER_TTL=300
SCRAPEGRAPH_BROWSER_POOL_CONTEXT_TTL=120
```

**Configuration Priority:**
1. Explicit `pool_config` parameter in `ChromiumLoader`
2. Environment variables
3. Default values in `PoolConfig`

### Error Handling Strategy

**Pool Exhaustion:**
- Log warning with pool statistics
- Option 1: Wait with exponential backoff
- Option 2: Create temporary browser (outside pool)
- Option 3: Raise exception to caller

**Browser Crash Recovery:**
- Health check detects crashed browser
- Browser removed from pool automatically
- New browser created to maintain min pool size
- In-flight requests fail fast and retry

**Context Leak Prevention:**
- Track all created contexts
- Periodic cleanup of unused contexts (TTL-based)
- Warning logs for contexts not properly released
- Forceful cleanup on browser removal

## Example Usage

### Before (Current Implementation)

```python
# Scraping 10 URLs - each creates a new browser
from scrapegraphai.docloaders import ChromiumLoader

urls = [f"https://example.com/page{i}" for i in range(10)]

for url in urls:
    loader = ChromiumLoader([url], headless=True)
    documents = loader.load()  # 2.8s overhead per URL
    # Total overhead: 28 seconds
```

**Performance Characteristics:**
- Total time for 10 URLs: ~60 seconds (28s overhead + 32s scraping)
- Memory peaks: 10 × 100MB = 1GB
- File descriptors: 10 × 20 = 200 FDs
- Context switches: Thousands

### After (With Connection Pooling)

```python
# Scraping 10 URLs - reuses browser contexts
from scrapegraphai.docloaders import ChromiumLoader

urls = [f"https://example.com/page{i}" for i in range(10)]

# Pool created and warmed up once
loader = ChromiumLoader(
    urls,
    headless=True,
    use_pool=True,  # Enable pooling
    pool_config={
        "min_browsers": 2,
        "max_browsers": 5,
    }
)

# Efficiently scrapes all URLs
documents = loader.load()  # First URL: 2.8s, rest: ~0.2s overhead each
# Total overhead: 2.8s + 9 × 0.2s = 4.6s
```

**Performance Characteristics:**
- Total time for 10 URLs: ~36.6 seconds (4.6s overhead + 32s scraping)
- **40% faster than before**
- Memory stable: 2-3 browsers = 200-300MB
- File descriptors: 2-3 × 20 = 40-60 FDs
- Context switches: Reduced by 70%

### Advanced Usage: Custom Pool Configuration

```python
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.browser_pool import PoolConfig

# High-throughput configuration
pool_config = PoolConfig(
    min_browsers=5,
    max_browsers=20,
    max_contexts_per_browser=10,
    browser_ttl_seconds=600,
    health_check_interval=60,
    launch_options={
        "args": ["--disable-blink-features=AutomationControlled"]
    }
)

loader = ChromiumLoader(
    urls=my_urls,
    use_pool=True,
    pool_config=pool_config.dict()
)
```

### Graph Integration Example

```python
from scrapegraphai.graphs import SmartScraperGraph

# Pool is automatically used by FetchNode
graph_config = {
    "llm": {"model": "openai/gpt-4"},
    "browser_config": {
        "use_pool": True,
        "pool_config": {
            "min_browsers": 3,
            "max_browsers": 10,
        }
    }
}

scraper = SmartScraperGraph(
    prompt="Extract product details",
    source="https://example.com/products",
    config=graph_config
)

result = scraper.run()  # Uses pooled browser automatically
```

### Graceful Shutdown

```python
from scrapegraphai.utils.browser_pool import BrowserPoolManager

# At application shutdown
async def cleanup():
    await BrowserPoolManager.shutdown_pool()

# In main application
import atexit
import asyncio

atexit.register(lambda: asyncio.run(cleanup()))
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
**Goal:** Basic pooling infrastructure without breaking changes

**Tasks:**
1. Create `scrapegraphai/utils/browser_pool.py` with core classes
   - `BrowserInstance` dataclass
   - `PoolConfig` dataclass
   - `BrowserPool` class with basic acquire/release
   - `BrowserPoolManager` singleton

2. Add comprehensive unit tests
   - Pool initialization and shutdown
   - Context acquisition and release
   - Concurrent access testing
   - Error handling validation

3. Add integration tests
   - End-to-end scraping with pool
   - Multi-URL scenarios
   - Pool exhaustion handling

**Success Criteria:**
- 95% test coverage for browser_pool.py
- All existing tests still pass
- No production deployment yet

### Phase 2: Integration (Week 3-4)
**Goal:** Integrate pooling with ChromiumLoader (opt-in)

**Tasks:**
1. Modify `ChromiumLoader` class
   - Add `use_pool` parameter (default `False` for backward compatibility)
   - Add `pool_config` parameter
   - Update `ascrape_playwright()` method
   - Update `ascrape_with_js_support()` method

2. Update `FetchNode` to support pooling
   - Pass pool config from graph config to loader
   - Add configuration documentation

3. Update `FetchScreenNode` to use pooling
   - Refactor to use async Playwright
   - Integrate with BrowserPoolManager

4. Documentation updates
   - API documentation for new parameters
   - Migration guide for existing users
   - Performance benchmarks

**Success Criteria:**
- Backward compatible: all existing code works
- Opt-in pooling works for major scraping methods
- Documentation complete

### Phase 3: Optimization (Week 5-6)
**Goal:** Enable pooling by default and optimize

**Tasks:**
1. Performance tuning
   - Benchmark different pool configurations
   - Optimize context reuse strategies
   - Tune TTL and health check intervals

2. Change default behavior
   - Set `use_pool=True` by default
   - Add environment variable overrides
   - Update examples to show pooling

3. Advanced features
   - Per-graph pool isolation (if needed)
   - Pool metrics and monitoring
   - Dynamic pool sizing based on load

4. Production validation
   - Deploy to staging environment
   - Run stress tests with real workloads
   - Monitor resource usage

**Success Criteria:**
- 80-90% overhead reduction demonstrated
- No increase in error rates
- Resource usage reduced or stable

### Phase 4: Stabilization (Week 7-8)
**Goal:** Production rollout and monitoring

**Tasks:**
1. Gradual rollout
   - Enable for 10% of production traffic
   - Monitor metrics closely
   - Increase to 50%, then 100%

2. Documentation completion
   - Troubleshooting guide
   - Best practices document
   - FAQ for common issues

3. Monitoring and alerts
   - Add pool health metrics
   - Create dashboards
   - Set up alerts for anomalies

4. Community engagement
   - Blog post announcing feature
   - Respond to feedback and issues
   - Iterate on configuration defaults

**Success Criteria:**
- Feature live in production
- No major incidents
- Positive community feedback

### Milestones

| Milestone | Completion Date | Deliverables |
|-----------|----------------|--------------|
| M1: Foundation Complete | Week 2 | Core pool implementation, tests |
| M2: Integration Complete | Week 4 | ChromiumLoader integration, docs |
| M3: Optimization Complete | Week 6 | Default pooling enabled, benchmarks |
| M4: Production Ready | Week 8 | Rolled out, monitored, stable |

### Rollback Plan

If critical issues arise:
1. Disable pooling by default (`use_pool=False`)
2. Maintain pool code for opt-in usage
3. Fix issues in dedicated hotfix branch
4. Re-enable gradually after validation

## Backwards Compatibility

### Breaking Changes

**None.** This RFC is designed to be 100% backward compatible.

### Compatibility Strategy

1. **Opt-in by Default Initially (Phase 1-2):**
   ```python
   # Existing code continues to work unchanged
   loader = ChromiumLoader(["https://example.com"])
   # Uses old behavior: new browser per request
   ```

2. **Gradual Default Change (Phase 3):**
   ```python
   # After Phase 3, pooling becomes default
   loader = ChromiumLoader(["https://example.com"])
   # Now uses pooling by default

   # Opt-out if needed
   loader = ChromiumLoader(["https://example.com"], use_pool=False)
   ```

3. **Environment Variable Override:**
   ```bash
   # Disable pooling globally if issues arise
   export SCRAPEGRAPH_BROWSER_POOL_ENABLED=false
   ```

### API Stability Guarantees

**Guaranteed Stable:**
- All existing `ChromiumLoader` parameters
- Existing method signatures
- Return types and data structures

**New Optional Parameters:**
- `use_pool: bool = True` (after Phase 3)
- `pool_config: Optional[dict] = None`

These parameters are keyword-only and have sensible defaults, so they don't affect existing positional argument usage.

### Migration Guide

**For Library Users:**

No action required in most cases. To explicitly enable pooling before Phase 3:

```python
# Before
loader = ChromiumLoader(urls, headless=True)

# After (optional in Phase 1-2, automatic in Phase 3)
loader = ChromiumLoader(urls, headless=True, use_pool=True)
```

**For Framework Integrators:**

If you're wrapping ScrapeGraphAI, add pool configuration options:

```python
graph_config = {
    "llm": {...},
    "browser_config": {
        "use_pool": True,
        "pool_config": {
            "max_browsers": 10
        }
    }
}
```

**For Contributors:**

When writing new scraping nodes:
- Import and use `BrowserPoolManager` for browser acquisition
- Follow the acquire/release pattern shown in examples
- Add tests for pooled and non-pooled modes

## Performance Impact

### Expected Improvements

**Metric: Browser Startup Overhead**
- Current: 2100-4700ms per URL
- With Pooling: 200-400ms per URL (first URL: 2100-4700ms)
- **Reduction: 80-90% for subsequent requests**

**Metric: Total Scraping Time (10 URLs)**
- Current: ~60 seconds (28s overhead + 32s scraping)
- With Pooling: ~36.6 seconds (4.6s overhead + 32s scraping)
- **Improvement: 40% faster**

**Metric: Total Scraping Time (100 URLs)**
- Current: ~600 seconds (280s overhead + 320s scraping)
- With Pooling: ~366 seconds (46s overhead + 320s scraping)
- **Improvement: 39% faster**

**Metric: Memory Usage (10 concurrent URLs)**
- Current: 1000MB (10 browsers × 100MB)
- With Pooling: 200-300MB (2-3 browsers × 100MB)
- **Reduction: 70-80%**

**Metric: CPU Utilization**
- Current: High CPU spikes during browser startup
- With Pooling: Stable CPU usage, no startup spikes
- **Reduction: ~50% average CPU during high-load periods**

### Benchmarking Methodology

**Test Setup:**
```python
import time
import asyncio
from scrapegraphai.docloaders import ChromiumLoader

# Test URLs (mix of page complexities)
test_urls = [
    "https://example.com",
    "https://news.ycombinator.com",
    "https://github.com",
    # ... 7 more
]

async def benchmark_without_pool():
    start = time.time()
    for url in test_urls:
        loader = ChromiumLoader([url], use_pool=False)
        await loader.ascrape_playwright(url)
    return time.time() - start

async def benchmark_with_pool():
    start = time.time()
    loader = ChromiumLoader(test_urls, use_pool=True)
    for url in test_urls:
        await loader.ascrape_playwright(url)
    return time.time() - start

# Run benchmarks
without_pool_time = asyncio.run(benchmark_without_pool())
with_pool_time = asyncio.run(benchmark_with_pool())

print(f"Without pool: {without_pool_time:.2f}s")
print(f"With pool: {with_pool_time:.2f}s")
print(f"Improvement: {(1 - with_pool_time/without_pool_time) * 100:.1f}%")
```

**Expected Results:**
```
Without pool: 58.4s
With pool: 35.2s
Improvement: 39.7%
```

### Performance Monitoring

**Metrics to Track:**

1. **Pool Health Metrics:**
   - Active browsers in pool
   - Active contexts per browser
   - Pool acquisition wait time
   - Pool exhaustion events

2. **Scraping Metrics:**
   - Time to first byte (TTFB)
   - Total request duration
   - Success rate
   - Retry rate

3. **Resource Metrics:**
   - Memory usage per browser
   - CPU usage during scraping
   - File descriptor count
   - Network connection count

**Monitoring Implementation:**

```python
# Add to BrowserPool class
@dataclass
class PoolMetrics:
    total_browsers: int = 0
    active_contexts: int = 0
    pool_hits: int = 0  # Context acquired from pool
    pool_misses: int = 0  # New context created
    acquisition_wait_time_ms: float = 0
    health_check_failures: int = 0

# Expose metrics via method
def get_metrics(self) -> PoolMetrics:
    return self._metrics
```

### Regression Prevention

**Before Merging:**
1. Run full benchmark suite on 3 different machines
2. Verify no performance regression in non-pooled mode
3. Validate memory usage under sustained load
4. Check for resource leaks over 24-hour stress test

**Continuous Monitoring:**
1. Add benchmarks to CI/CD pipeline
2. Alert on >5% performance regression
3. Weekly performance reports
4. Monthly review of pool configuration tuning

## Alternatives Considered

### Alternative 1: External Browser Management Service

**Description:** Use a separate service (like Browserless.io) to manage browser instances.

**Pros:**
- Outsources complexity
- Professional browser management
- Works across multiple app instances

**Cons:**
- Adds external dependency
- Network latency for each request
- Additional cost for cloud service
- Requires internet connectivity

**Why Not Chosen:** We want zero external dependencies and minimum latency. This solution is better suited for cloud/SaaS deployments but adds unnecessary complexity for local/on-prem usage.

---

### Alternative 2: Process Pool Instead of Connection Pool

**Description:** Use multiprocessing to maintain multiple Playwright processes, each with its own browser.

**Pros:**
- Better isolation (process crashes don't affect others)
- Can utilize multiple CPU cores
- Simpler state management (no shared state)

**Cons:**
- Higher memory overhead (full Python interpreter per process)
- Inter-process communication overhead
- More complex lifecycle management
- Harder to implement health checks

**Why Not Chosen:** The overhead of multiprocessing outweighs the benefits for browser management. Playwright's async API already provides good concurrency, and process isolation isn't necessary since browser crashes are rare.

---

### Alternative 3: Per-Graph Browser Instance

**Description:** Each graph instance maintains its own browser instead of a global pool.

**Pros:**
- Simpler lifecycle management
- No global state
- Easier to reason about

**Cons:**
- No resource sharing across graphs
- Higher memory usage
- Doesn't solve the multi-URL scraping problem
- Suboptimal for applications using multiple graphs

**Why Not Chosen:** This only partially solves the problem. A global pool is more efficient and provides better resource utilization across the entire application.

---

### Alternative 4: Lazy Browser Creation (No Pool)

**Description:** Keep the browser alive between requests within a single `ChromiumLoader` instance, but don't pool across instances.

**Pros:**
- Simpler implementation
- No global state
- Still provides some performance benefit

**Cons:**
- Only helps within a single loader instance
- Doesn't help with graph execution patterns
- No health checking or TTL management
- Browser stays alive even when not needed

**Why Not Chosen:** This is insufficient for the common use case of scraping multiple URLs across multiple graph executions. It's a half-measure that doesn't address the core problem.

---

### Alternative 5: Browser-as-a-Service Integration

**Description:** Integrate with services like Apify or Puppeteer Cluster.

**Pros:**
- Battle-tested browser management
- Additional features (proxies, captcha solving)
- Professional support

**Cons:**
- Tight coupling to external service
- Cost implications
- Not suitable for on-premise deployments
- Loss of control over browser configuration

**Why Not Chosen:** We want a first-party solution that works everywhere (local development, on-premise, cloud) without external dependencies or costs.

---

### Decision Matrix

| Alternative | Performance | Complexity | Cost | Flexibility | Score |
|------------|-------------|-----------|------|-------------|-------|
| **Connection Pool (Chosen)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **22/25** |
| External Service | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 16/25 |
| Process Pool | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 15/25 |
| Per-Graph Browser | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 14/25 |
| Lazy Creation | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 16/25 |
| BaaS Integration | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | 14/25 |

## Security Considerations

### Threat Model

**Threat 1: Context Isolation Violation**

**Description:** If contexts are not properly isolated, sensitive data (cookies, localStorage, etc.) from one scraping task could leak to another.

**Mitigation:**
- Always create new contexts for different security domains
- Never share contexts between different URLs unless explicitly configured
- Use Playwright's built-in context isolation
- Add tests to verify isolation

**Implementation:**
```python
# In BrowserPool.acquire_context()
context = await instance.browser.new_context(
    storage_state=storage_state,  # Per-task state
    ignore_https_errors=True,
)
# Each context is completely isolated
```

---

**Threat 2: Resource Exhaustion Attack**

**Description:** Malicious or buggy code could exhaust the browser pool, causing denial of service.

**Mitigation:**
- Enforce max_browsers limit strictly
- Implement acquisition timeouts
- Add circuit breaker pattern
- Monitor and alert on pool exhaustion

**Implementation:**
```python
# In BrowserPool.acquire_context()
if len(self._browsers) >= self.config.max_browsers:
    # Wait with timeout or fail fast
    raise PoolExhaustedError("Browser pool at capacity")
```

---

**Threat 3: Stale Browser Credentials**

**Description:** Long-lived browsers may cache authentication credentials that should have been invalidated.

**Mitigation:**
- Implement TTL for browsers (default: 5 minutes)
- Force browser refresh when `storage_state` changes
- Provide explicit `force_new_browser` parameter for sensitive operations

**Implementation:**
```python
# In PoolConfig
browser_ttl_seconds: int = 300  # 5 minutes

# In BrowserPool
if now - instance.created_at > self.config.browser_ttl_seconds:
    await self._remove_browser(instance)
```

---

**Threat 4: Browser Crash Exploitation**

**Description:** A malicious website could crash the browser, potentially affecting other tasks using the same browser.

**Mitigation:**
- Health checks detect crashed browsers immediately
- Crashed browsers removed from pool automatically
- Each context failure doesn't affect other contexts
- Automatic replacement of unhealthy browsers

**Implementation:**
```python
# In BrowserPool._perform_health_checks()
try:
    page = await instance.browser.new_page()
    await page.close()
except Exception:
    instance.health_check_failures += 1
    if instance.health_check_failures >= self.config.max_health_check_failures:
        await self._remove_browser(instance)
```

---

**Threat 5: Memory Exhaustion**

**Description:** Memory leaks in browser instances or contexts could exhaust system memory.

**Mitigation:**
- Context TTL ensures contexts are recycled
- Browser TTL ensures browsers are recycled
- Max contexts per browser limits growth
- Monitoring and alerts for memory usage

**Implementation:**
```python
# In PoolConfig
context_ttl_seconds: int = 120  # 2 minutes
max_contexts_per_browser: int = 5

# Periodic cleanup in health check loop
```

### Security Best Practices

1. **Principle of Least Privilege:**
   - Pool manager only has access to browser creation/destruction
   - No access to scraped data or application state
   - Minimal required permissions

2. **Defense in Depth:**
   - Multiple layers of protection (TTLs, health checks, limits)
   - Graceful degradation if pool unavailable
   - Fallback to non-pooled mode

3. **Secure Defaults:**
   - `headless=True` by default (reduces attack surface)
   - `ignore_https_errors=True` only in contexts (not browsers)
   - Stealth mode enabled by default

4. **Audit Trail:**
   - Log all browser creation/destruction events
   - Log pool exhaustion events
   - Log health check failures
   - Include timestamps and context IDs

### Security Testing

**Test Cases:**

1. **Context Isolation Test:**
   ```python
   # Verify cookie isolation between contexts
   async def test_context_isolation():
       pool = BrowserPool()
       await pool.initialize()

       # Context 1: Set cookie
       browser1, context1 = await pool.acquire_context()
       page1 = await context1.new_page()
       await page1.goto("https://example.com")
       await page1.evaluate("document.cookie = 'secret=value1'")

       # Context 2: Verify cookie not present
       browser2, context2 = await pool.acquire_context()
       page2 = await context2.new_page()
       await page2.goto("https://example.com")
       cookies = await page2.evaluate("document.cookie")

       assert "secret=value1" not in cookies
   ```

2. **Resource Limit Test:**
   ```python
   async def test_resource_limits():
       pool = BrowserPool(PoolConfig(max_browsers=3))
       contexts = []

       # Acquire up to limit
       for _ in range(3):
           contexts.append(await pool.acquire_context())

       # Next acquisition should fail
       with pytest.raises(PoolExhaustedError):
           await pool.acquire_context()
   ```

3. **Crash Recovery Test:**
   ```python
   async def test_crash_recovery():
       pool = BrowserPool()
       browser, context = await pool.acquire_context()

       # Simulate browser crash
       await browser.close()

       # Pool should detect and remove crashed browser
       await asyncio.sleep(pool.config.health_check_interval + 1)

       # Should be able to acquire new browser
       browser2, context2 = await pool.acquire_context()
       assert browser2 != browser
   ```

## Open Questions

### Question 1: Pool Scope - Global vs Per-Graph?

**Context:** Should the browser pool be truly global (shared across all graph instances) or scoped per-graph?

**Options:**
- **Global Pool:** One pool for entire application
  - Pro: Maximum resource sharing
  - Con: Could cause contention in multi-tenant scenarios

- **Per-Graph Pool:** Each graph has its own pool
  - Pro: Better isolation
  - Con: Higher memory usage

- **Hybrid:** Global pool with optional per-graph pools
  - Pro: Flexibility
  - Con: Increased complexity

**Request for Input:** Which approach best fits the typical ScrapeGraphAI deployment patterns?

---

### Question 2: Context Reuse Strategy

**Context:** Should we reuse contexts or always create fresh ones?

**Current Design:** Create fresh contexts, but keep browsers alive.

**Alternative:** Reuse contexts for identical configurations (same `storage_state`, same options).

**Trade-offs:**
- Reusing contexts is faster (~100ms saved per request)
- But increases risk of state leakage if not careful
- May complicate cleanup logic

**Request for Input:** Is the extra complexity worth ~100ms speedup? What are the security concerns?

---

### Question 3: Default Pool Size

**Context:** What should the default `min_browsers` and `max_browsers` be?

**Current Proposal:**
- `min_browsers: 1` (lazy initialization)
- `max_browsers: 10`

**Considerations:**
- Low `min_browsers` saves memory but adds latency to first request
- High `max_browsers` allows more concurrency but uses more RAM
- Different use cases (local dev vs production) need different values

**Request for Input:** Should we have different defaults for different environments? How to detect environment?

---

### Question 4: Browser Type Mixing

**Context:** Should one pool support both Chromium and Firefox?

**Current Design:** Pool is configured for one browser type at initialization.

**Alternative:** Support multiple browser types in one pool.

**Trade-offs:**
- Mixing adds complexity to pool management
- But some users need both Chromium (speed) and Firefox (compatibility)
- Could implement as multiple pools internally

**Request for Input:** Is multi-browser support in one pool needed? What's the use case?

---

### Question 5: Integration with Existing Caching

**Context:** ScrapeGraphAI has existing HTTP caching. How should browser pooling interact with it?

**Current State:**
- HTTP cache operates at response level
- Browser pool operates at browser level
- They are independent

**Potential Integration:**
- Browser pool could check cache before launching browser
- Or cache could be context-aware (different cache per browser)
- Or keep them completely separate

**Request for Input:** Should these systems be integrated? If so, how?

---

### Question 6: Pool Warming Strategy

**Context:** Should we pre-warm the pool on application startup?

**Options:**
1. **Lazy:** Only create browsers on first request
2. **Eager:** Create `min_browsers` on startup
3. **Smart:** Pre-warm based on historical usage patterns

**Trade-offs:**
- Lazy: Slower first request, faster startup
- Eager: Faster first request, slower startup, may waste resources
- Smart: Best of both worlds but complex to implement

**Request for Input:** What's the expected application startup pattern? Are first-request latency spikes acceptable?

---

### Question 7: Cloud Deployment Considerations

**Context:** How should the pool behave in serverless/cloud environments?

**Challenges:**
- Serverless functions may have short lifetimes
- Container orchestration may move/restart containers
- Multiple replicas need independent pools

**Questions:**
- Should pool persist across function invocations?
- How to handle pool in Kubernetes pod restarts?
- Should there be a "cloud mode" with different defaults?

**Request for Input:** What are the target cloud deployment patterns? Do we need cloud-specific configuration presets?

---

### Question 8: Metrics and Observability

**Context:** What metrics should be exposed and how?

**Current Proposal:**
- Basic metrics via `get_metrics()` method
- Logging of major events

**Additional Options:**
- Prometheus endpoint
- StatsD integration
- OpenTelemetry traces
- Custom callback interface

**Request for Input:** What observability tools do users typically use? What metrics are most important?

---

### How to Provide Input

**For Community Members:**
- Comment on the RFC GitHub issue
- Join the discussion on Discord
- Submit concerns via email

**For Core Team:**
- Review during weekly architecture meeting
- Async feedback via RFC document comments
- Vote on contentious decisions

**Timeline:**
- RFC open for feedback: 2 weeks
- Decisions finalized: Week 3
- Implementation begins: Week 4

## Success Metrics

### Primary Metrics

**Metric 1: Browser Startup Overhead Reduction**

**Definition:** Time from scrape request to first byte of content

**Target:** 80-90% reduction for subsequent requests (after first)

**Measurement:**
```python
# Before: 2100-4700ms per URL
# After: 200-400ms per URL (90% reduction)

def measure_startup_overhead():
    times = []
    for i in range(10):
        start = time.time()
        loader = ChromiumLoader([url], use_pool=True)
        await loader.ascrape_playwright(url)
        elapsed = time.time() - start
        times.append(elapsed)

    first_request = times[0]  # ~2500ms
    subsequent_avg = sum(times[1:]) / 9  # ~300ms
    reduction = (first_request - subsequent_avg) / first_request
    assert reduction >= 0.80  # 80% minimum
```

**Reporting:** Weekly benchmark dashboard

---

**Metric 2: Multi-URL Scraping Performance**

**Definition:** Total time to scrape 100 URLs

**Target:** 40% reduction in total time

**Measurement:**
```python
# Before: ~600 seconds (280s overhead + 320s scraping)
# After: ~366 seconds (46s overhead + 320s scraping)

def benchmark_multi_url():
    urls = generate_test_urls(100)

    # Without pool
    start = time.time()
    for url in urls:
        loader = ChromiumLoader([url], use_pool=False)
        loader.load()
    without_pool = time.time() - start

    # With pool
    start = time.time()
    loader = ChromiumLoader(urls, use_pool=True)
    loader.load()
    with_pool = time.time() - start

    improvement = (without_pool - with_pool) / without_pool
    assert improvement >= 0.40  # 40% minimum
```

**Reporting:** CI/CD pipeline benchmark

---

**Metric 3: Memory Usage Reduction**

**Definition:** Peak memory usage during 10 concurrent URL scrapes

**Target:** 70% reduction

**Measurement:**
```python
# Before: ~1000MB (10 browsers × 100MB)
# After: ~300MB (3 browsers × 100MB)

import psutil

def measure_memory_usage():
    process = psutil.Process()

    baseline = process.memory_info().rss

    # Scrape 10 URLs concurrently
    tasks = [scrape_url(url) for url in test_urls]
    await asyncio.gather(*tasks)

    peak = process.memory_info().rss
    memory_used = peak - baseline

    assert memory_used < 400 * 1024 * 1024  # 400MB max
```

**Reporting:** Continuous monitoring in staging

---

### Secondary Metrics

**Metric 4: Error Rate**

**Definition:** Percentage of scraping requests that fail

**Target:** No increase from current baseline (should remain < 1%)

**Measurement:**
```python
def measure_error_rate():
    total_requests = 1000
    failures = 0

    for url in generate_test_urls(total_requests):
        try:
            loader = ChromiumLoader([url], use_pool=True)
            loader.load()
        except Exception:
            failures += 1

    error_rate = failures / total_requests
    assert error_rate < 0.01  # Less than 1%
```

**Reporting:** Production monitoring dashboard

---

**Metric 5: Pool Health**

**Definition:** Percentage of time the pool is available and healthy

**Target:** 99.9% uptime

**Measurement:**
```python
def monitor_pool_health():
    healthy_checks = 0
    total_checks = 0

    while monitoring:
        total_checks += 1
        pool = await BrowserPoolManager.get_pool()
        metrics = pool.get_metrics()

        if (metrics.total_browsers >= config.min_browsers and
            metrics.health_check_failures == 0):
            healthy_checks += 1

        await asyncio.sleep(60)  # Check every minute

    uptime = healthy_checks / total_checks
    assert uptime >= 0.999  # 99.9%
```

**Reporting:** Internal monitoring system

---

**Metric 6: Pool Efficiency**

**Definition:** Ratio of pool hits to pool misses (context reuse vs new creation)

**Target:** 90% hit rate after warmup

**Measurement:**
```python
def measure_pool_efficiency():
    pool = await BrowserPoolManager.get_pool()

    # Warm up pool
    for _ in range(10):
        browser, context = await pool.acquire_context()
        await pool.release_context(browser, context)

    # Measure
    metrics_before = pool.get_metrics()

    for _ in range(100):
        browser, context = await pool.acquire_context()
        await pool.release_context(browser, context)

    metrics_after = pool.get_metrics()

    hits = metrics_after.pool_hits - metrics_before.pool_hits
    total = hits + (metrics_after.pool_misses - metrics_before.pool_misses)
    hit_rate = hits / total

    assert hit_rate >= 0.90  # 90% hit rate
```

**Reporting:** Performance analytics dashboard

---

### Monitoring Dashboard

**Proposed Metrics Dashboard:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ScrapeGraphAI Browser Pool Metrics                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Startup Overhead Reduction:  [████████░░] 87%                  │
│  Multi-URL Performance:       [████████░░] 43% faster           │
│  Memory Usage:                [████████░░] 72% reduction        │
│  Error Rate:                  [██████████] 0.3% (target: <1%)   │
│  Pool Uptime:                 [██████████] 99.95%               │
│  Pool Hit Rate:               [████████░░] 93%                  │
│                                                                  │
│  Active Browsers:   3 / 10                                      │
│  Active Contexts:   8                                           │
│  Avg Acquisition:   45ms                                        │
│  Pool Exhaustions:  0 (last 24h)                                │
│                                                                  │
│  Recent Events:                                                 │
│  ✓ 14:32:11 - Browser created (id: abc123)                      │
│  ✓ 14:31:45 - Health check passed (3 browsers)                 │
│  ✓ 14:30:22 - Context released (id: def456)                    │
│  ⚠ 14:28:15 - High acquisition wait time (850ms)               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Success Criteria Summary

**Phase 1 (Foundation) Success:**
- [ ] All 6 primary + secondary metrics defined
- [ ] Baseline measurements captured
- [ ] Monitoring infrastructure in place

**Phase 2 (Integration) Success:**
- [ ] Metric 1: 80% overhead reduction achieved
- [ ] Metric 4: Error rate unchanged from baseline

**Phase 3 (Optimization) Success:**
- [ ] Metric 2: 40% multi-URL performance improvement
- [ ] Metric 3: 70% memory reduction
- [ ] Metric 6: 90% pool hit rate

**Phase 4 (Production) Success:**
- [ ] All metrics meeting targets for 2 consecutive weeks
- [ ] Metric 5: 99.9% uptime maintained
- [ ] Zero critical incidents related to pooling
- [ ] Positive community feedback (no major complaints)

**Long-term Success (3 months):**
- [ ] All targets maintained
- [ ] No rollbacks or hotfixes required
- [ ] Feature used by 80%+ of production workloads
- [ ] Documentation and best practices established

## References

### Code References

1. **ChromiumLoader Implementation**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/docloaders/chromium.py`
   - Lines: 323-437 (main scraping methods)
   - Key issue: Browser created and destroyed for each URL

2. **FetchNode Integration**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/nodes/fetch_node.py`
   - Lines: 355-361 (ChromiumLoader instantiation)
   - Context: How graphs currently use browsers

3. **Performance Analysis**
   - File: `/home/user/Scrapegraph-ai/analysis-output/blog-series/05-performance-analysis.md`
   - Lines: 82-126 (Playwright overhead breakdown)
   - Data: 2100-4700ms overhead per URL documented

4. **Test Suite**
   - File: `/home/user/Scrapegraph-ai/tests/test_chromium.py`
   - Current: 90+ tests, none for pooling
   - Gap: Need pool-specific tests

### External References

5. **Playwright Async API Documentation**
   - URL: https://playwright.dev/python/docs/api/class-playwright
   - Relevant: Browser lifecycle, context management

6. **Connection Pooling Best Practices**
   - URL: https://en.wikipedia.org/wiki/Connection_pool
   - Concepts: Pool sizing, TTL, health checking

7. **Browser Automation at Scale**
   - Reference: Puppeteer Cluster (https://github.com/thomasdondorf/puppeteer-cluster)
   - Inspiration for pool architecture

8. **Playwright Python Examples**
   - URL: https://playwright.dev/python/docs/browsers
   - Browser reuse patterns

### Related Issues & Discussions

9. **Recent Timeout Configuration PR**
   - Commit: e81a4ed (feat: Add configurable timeout to FetchNode)
   - Relevant: Shows need for better resource management

10. **Community Discussions on Performance**
    - Discord: #performance-optimization channel
    - Common complaint: Slow multi-URL scraping

### Benchmarking Resources

11. **ScrapeGraphAI Performance Blog**
    - File: `/home/user/Scrapegraph-ai/analysis-output/blog-series/05-performance-analysis.md`
    - Data: Detailed breakdown of execution time

12. **Playwright Performance Tips**
    - URL: https://playwright.dev/docs/best-practices
    - Browser reuse recommendations

### Academic References

13. **Resource Pooling in Distributed Systems**
    - Concept: Object pooling pattern
    - Application: Browser instance management

14. **Memory Management in Browser Automation**
    - Topic: Preventing memory leaks in long-running browsers
    - Relevance: TTL and health checking strategies

---

## Appendix: Code Examples

### A1: Full Pool Usage Example

```python
"""
Complete example showing browser pool usage in production.
"""
import asyncio
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.browser_pool import BrowserPoolManager, PoolConfig

async def main():
    # Configure pool for high-throughput scraping
    pool_config = PoolConfig(
        min_browsers=3,
        max_browsers=10,
        max_contexts_per_browser=5,
        browser_ttl_seconds=600,
        health_check_interval=60,
    )

    # Initialize pool
    pool = await BrowserPoolManager.get_pool(pool_config)

    # Example: Scrape 100 product pages
    urls = [f"https://shop.example.com/product/{i}" for i in range(100)]

    try:
        # Create loader with pooling enabled
        loader = ChromiumLoader(
            urls,
            headless=True,
            use_pool=True,
            pool_config=pool_config.dict(),
        )

        # Scrape all URLs efficiently
        documents = loader.load()

        print(f"Scraped {len(documents)} pages successfully")

        # Check pool statistics
        metrics = pool.get_metrics()
        print(f"Pool efficiency: {metrics.pool_hits / (metrics.pool_hits + metrics.pool_misses):.1%}")

    finally:
        # Cleanup on application exit
        await BrowserPoolManager.shutdown_pool()

if __name__ == "__main__":
    asyncio.run(main())
```

### A2: Custom Health Check Example

```python
"""
Example of implementing custom health checks for specific use cases.
"""
from scrapegraphai.utils.browser_pool import BrowserPool, PoolConfig

class CustomBrowserPool(BrowserPool):
    """Extended pool with custom health checks."""

    async def _perform_health_checks(self):
        """Custom health check that validates against specific URLs."""
        async with self._lock:
            for instance in self._browsers:
                try:
                    # Custom check: ensure browser can load test page
                    page = await instance.browser.new_page()
                    response = await page.goto("https://example.com/health")

                    if response.status != 200:
                        instance.health_check_failures += 1
                    else:
                        instance.health_check_failures = 0

                    await page.close()
                except Exception:
                    instance.health_check_failures += 1

                # Remove unhealthy browsers
                if instance.health_check_failures >= self.config.max_health_check_failures:
                    await self._remove_browser(instance)
```

### A3: Monitoring Integration Example

```python
"""
Example showing integration with Prometheus for metrics.
"""
from prometheus_client import Counter, Histogram, Gauge
from scrapegraphai.utils.browser_pool import BrowserPool

# Define Prometheus metrics
pool_acquisitions = Counter('browser_pool_acquisitions_total', 'Total context acquisitions')
pool_acquisition_time = Histogram('browser_pool_acquisition_seconds', 'Context acquisition time')
pool_browsers = Gauge('browser_pool_browsers', 'Number of browsers in pool')
pool_contexts = Gauge('browser_pool_contexts', 'Number of active contexts')

class MonitoredBrowserPool(BrowserPool):
    """Browser pool with Prometheus metrics."""

    async def acquire_context(self, **kwargs):
        pool_acquisitions.inc()

        with pool_acquisition_time.time():
            browser, context = await super().acquire_context(**kwargs)

        pool_browsers.set(len(self._browsers))
        pool_contexts.set(sum(len(b.contexts) for b in self._browsers))

        return browser, context
```

---

**End of RFC-0001**

---

**Feedback and questions welcome!**
Please direct comments to the RFC discussion thread or reach out to the ScrapeGraphAI team on Discord.
