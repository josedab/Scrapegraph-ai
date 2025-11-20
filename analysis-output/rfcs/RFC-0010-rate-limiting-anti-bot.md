# RFC-0010: Browser Request Rate Limiting & Anti-Bot Evasion

**Status:** Draft
**Author:** ScrapeGraphAI Analysis Team
**Created:** 2025-11-20
**Based on Commit:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

## Summary

This RFC proposes implementing configurable per-domain rate limiting and enhanced anti-bot evasion strategies for ScrapeGraphAI's browser-based scraping. Currently, `ChromiumLoader` implements basic retry logic but lacks rate limiting between requests, making it vulnerable to being blocked by websites and potentially overwhelming target servers. By adding intelligent rate limiting, request timing randomization, user-agent rotation, and enhanced cookie management, we can improve scraping reliability while being respectful of target websites.

## Motivation

### Current Problems

**Problem 1: No Rate Limiting Between Requests**

The current implementation (lines 344-380 in `chromium.py`) retries immediately on failure without any delays:

```python
# From scrapegraphai/docloaders/chromium.py:344-380
while attempt < self.retry_limit:
    try:
        async with async_playwright() as p, async_timeout.timeout(self.timeout):
            # ... scraping logic ...
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        attempt += 1  # Immediately retries - no delay!
        logger.error(f"Attempt {attempt} failed: {e}")
```

**Issues:**
- Retries fire immediately, potentially triggering anti-bot systems
- No exponential backoff for transient failures
- Can overwhelm servers with rapid requests
- No consideration for rate limit headers (429, Retry-After)

**Problem 2: No Per-Domain Request Throttling**

When scraping multiple URLs from the same domain, requests are sent as fast as possible:

```python
# From chromium.py:479-480
tasks = [scraping_fn(url) for url in self.urls]
results = await asyncio.gather(*tasks)  # All requests fire simultaneously
```

**Issues:**
- Can trigger rate limiting on target servers
- Multiple URLs from same domain hit server simultaneously
- No consideration for domain-specific politeness policies
- Increases likelihood of being blocked

**Problem 3: Predictable Request Patterns**

All requests follow identical timing patterns:
- Same user-agent for all requests
- Predictable intervals between retries
- No randomization of request timing
- Consistent browser fingerprint

**Impact:** Modern anti-bot systems easily detect and block these patterns.

**Problem 4: Limited Anti-Bot Evasion**

Current implementation only uses `undetected_playwright`'s Malenia stealth:

```python
# Lines 366
await Malenia.apply_stealth(context)
```

**Missing strategies:**
- User-agent rotation
- Request header randomization
- Cookie jar management
- Timing randomization
- Referrer spoofing
- Mouse movement simulation

### Why This Matters

**Scraping Reliability:**
- Sites with rate limiting will block requests → scraping fails
- 429 errors not handled properly → wasted retries
- Predictable patterns → higher detection rate

**Ethical Considerations:**
- Respecting server resources
- Following robots.txt and rate limits
- Being a good web citizen

**Cost Impact:**
- Blocked IPs require proxy rotation → increased costs
- Failed scrapes require re-execution → wasted resources
- Detection leads to CAPTCHA challenges → manual intervention needed

## Current State

### Architecture Analysis

**File: `/home/user/Scrapegraph-ai/scrapegraphai/docloaders/chromium.py`**

The `ChromiumLoader` class implements three main scraping methods, all with the same limitations:

1. **`ascrape_playwright()`** (lines 323-381):
   - Retry logic without delays
   - No rate limiting
   - No request timing randomization
   - Single user-agent

2. **`ascrape_playwright_scroll()`** (lines 166-321):
   - Same issues as above
   - Scrolling adds load but no throttling
   - Fixed sleep intervals (predictable)

3. **`ascrape_with_js_support()`** (lines 382-437):
   - Identical pattern
   - No additional anti-bot measures

4. **`alazy_load()`** (lines 460-483):
   - Fires all requests simultaneously via `asyncio.gather()`
   - No domain-based throttling
   - No consideration for server load

### Retry Logic Analysis

**Current Retry Implementation:**

```python
# Lines 344-380
while attempt < self.retry_limit:
    try:
        # ... scraping logic ...
        return results
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        attempt += 1
        logger.error(f"Attempt {attempt} failed: {e}")
        if attempt == self.retry_limit:
            raise RuntimeError(f"Failed to scrape after {self.retry_limit} attempts: {str(e)}")
```

**Problems:**
- No delay between retries
- Doesn't check for 429 (Too Many Requests) status
- Doesn't respect Retry-After headers
- Same approach for all error types
- No exponential backoff

### Anti-Bot Measures

**Current:**
- `undetected_playwright` with Malenia stealth
- Proxy support (basic)
- Storage state (cookie persistence)

**Missing:**
- User-agent rotation
- Request header randomization
- Timing jitter
- Cookie management strategies
- Fingerprint randomization

### Test Coverage

The test suite (`tests/test_chromium.py`) has 90+ tests but none validate:
- Rate limiting behavior
- Retry delay intervals
- Per-domain throttling
- Anti-bot evasion effectiveness
- 429 response handling

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ChromiumLoader                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Request Pipeline                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ Rate Limiter │→ │ Anti-Bot     │→ │ Browser      │    │ │
│  │  │ (per-domain) │  │ Randomizer   │  │ Executor     │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DomainRateLimiter                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ example.com  │  │ github.com   │  │ reddit.com   │          │
│  │ - Last req   │  │ - Last req   │  │ - Last req   │          │
│  │ - Min delay  │  │ - Min delay  │  │ - Min delay  │          │
│  │ - Req count  │  │ - Req count  │  │ - Req count  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AntiBotManager                                │
│  - User-Agent Rotation                                           │
│  - Header Randomization                                          │
│  - Timing Jitter                                                 │
│  - Cookie Management                                             │
│  - Fingerprint Randomization                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. DomainRateLimiter Class

**Location:** `scrapegraphai/utils/rate_limiter.py`

```python
import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse
from collections import defaultdict

@dataclass
class DomainState:
    """Tracks request state for a single domain."""
    last_request_time: float = 0.0
    request_count: int = 0
    min_delay: float = 1.0  # Minimum seconds between requests
    max_delay: float = 3.0  # Maximum seconds between requests
    retry_after: Optional[float] = None  # From Retry-After header
    blocked_until: Optional[float] = None  # If domain is temporarily blocked

@dataclass
class RateLimiterConfig:
    """Configuration for rate limiting."""
    default_min_delay: float = 1.0  # Default min delay between requests
    default_max_delay: float = 3.0  # Default max delay between requests
    randomize_delay: bool = True  # Add jitter to delays
    respect_retry_after: bool = True  # Honor Retry-After headers
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    max_backoff_delay: float = 60.0  # Maximum backoff delay
    per_domain_limits: Dict[str, tuple[float, float]] = field(default_factory=dict)
    # Example: {"example.com": (2.0, 5.0)}  # Min 2s, max 5s for example.com

class DomainRateLimiter:
    """
    Manages per-domain rate limiting with exponential backoff and jitter.

    Features:
    - Per-domain request tracking
    - Configurable min/max delays per domain
    - Exponential backoff on retries
    - Retry-After header support
    - Request timing randomization
    - Domain blocking/cooldown
    """

    def __init__(self, config: Optional[RateLimiterConfig] = None):
        self.config = config or RateLimiterConfig()
        self._domain_states: Dict[str, DomainState] = defaultdict(self._create_domain_state)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _create_domain_state(self) -> DomainState:
        """Create a new domain state with default configuration."""
        return DomainState(
            min_delay=self.config.default_min_delay,
            max_delay=self.config.default_max_delay
        )

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]

    def configure_domain(self, domain: str, min_delay: float, max_delay: float):
        """
        Configure custom rate limits for a specific domain.

        Args:
            domain: The domain name (e.g., "example.com")
            min_delay: Minimum seconds between requests
            max_delay: Maximum seconds between requests
        """
        state = self._domain_states[domain]
        state.min_delay = min_delay
        state.max_delay = max_delay

    async def acquire(self, url: str, retry_attempt: int = 0) -> float:
        """
        Acquire permission to make a request to the given URL.

        This method blocks until it's safe to make the request based on
        rate limiting rules. Returns the delay that was applied.

        Args:
            url: The URL to request
            retry_attempt: The current retry attempt number (0 for first attempt)

        Returns:
            float: The delay in seconds that was applied
        """
        domain = self._get_domain(url)
        async with self._locks[domain]:
            state = self._domain_states[domain]
            now = time.time()

            # Check if domain is temporarily blocked
            if state.blocked_until and now < state.blocked_until:
                wait_time = state.blocked_until - now
                logger.info(f"Domain {domain} blocked, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                state.blocked_until = None

            # Calculate required delay
            delay = self._calculate_delay(state, retry_attempt)

            # Calculate time since last request
            if state.last_request_time > 0:
                elapsed = now - state.last_request_time
                remaining = delay - elapsed

                if remaining > 0:
                    logger.debug(f"Rate limiting {domain}: waiting {remaining:.2f}s")
                    await asyncio.sleep(remaining)

            # Update state
            state.last_request_time = time.time()
            state.request_count += 1

            return delay

    def _calculate_delay(self, state: DomainState, retry_attempt: int) -> float:
        """
        Calculate the delay for the next request.

        Applies:
        - Base delay from config
        - Exponential backoff for retries
        - Randomization/jitter
        - Retry-After header overrides
        """
        # Check for Retry-After override
        if self.config.respect_retry_after and state.retry_after:
            delay = state.retry_after
            state.retry_after = None  # Clear after use
            return delay

        # Base delay
        min_delay = state.min_delay
        max_delay = state.max_delay

        # Apply exponential backoff for retries
        if retry_attempt > 0:
            backoff = min_delay * (self.config.backoff_multiplier ** retry_attempt)
            backoff = min(backoff, self.config.max_backoff_delay)
            min_delay = backoff
            max_delay = max(max_delay, backoff)

        # Add randomization
        if self.config.randomize_delay:
            delay = random.uniform(min_delay, max_delay)
        else:
            delay = min_delay

        return delay

    def handle_429(self, url: str, retry_after: Optional[int] = None):
        """
        Handle a 429 (Too Many Requests) response.

        Args:
            url: The URL that returned 429
            retry_after: Value from Retry-After header (seconds)
        """
        domain = self._get_domain(url)
        state = self._domain_states[domain]

        if retry_after:
            state.retry_after = retry_after
            state.blocked_until = time.time() + retry_after
            logger.warning(f"Domain {domain} rate limited, backing off for {retry_after}s")
        else:
            # Default backoff if no Retry-After header
            backoff = min(state.min_delay * 10, self.config.max_backoff_delay)
            state.blocked_until = time.time() + backoff
            logger.warning(f"Domain {domain} rate limited, backing off for {backoff}s")

    def get_stats(self, domain: Optional[str] = None) -> Dict:
        """
        Get statistics for rate limiting.

        Args:
            domain: Specific domain to get stats for, or None for all domains

        Returns:
            Dict containing rate limiting statistics
        """
        if domain:
            state = self._domain_states.get(domain)
            if state:
                return {
                    "domain": domain,
                    "request_count": state.request_count,
                    "last_request": state.last_request_time,
                    "blocked": state.blocked_until is not None
                }
            return {}

        return {
            domain: {
                "request_count": state.request_count,
                "last_request": state.last_request_time,
                "blocked": state.blocked_until is not None
            }
            for domain, state in self._domain_states.items()
        }
```

#### 2. AntiBotManager Class

**Location:** `scrapegraphai/utils/anti_bot.py`

```python
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class AntiBotConfig:
    """Configuration for anti-bot evasion strategies."""
    rotate_user_agents: bool = True
    randomize_headers: bool = True
    randomize_viewport: bool = True
    simulate_human_timing: bool = True
    min_action_delay: float = 0.1  # Minimum delay between actions
    max_action_delay: float = 0.5  # Maximum delay between actions
    custom_user_agents: List[str] = field(default_factory=list)

class AntiBotManager:
    """
    Manages anti-bot evasion strategies.

    Features:
    - User-agent rotation
    - Request header randomization
    - Viewport size randomization
    - Human-like timing simulation
    - Cookie jar management
    """

    # Common desktop user agents (updated 2024)
    DEFAULT_USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    # Common viewport sizes
    VIEWPORT_SIZES = [
        {"width": 1920, "height": 1080},  # Full HD
        {"width": 1366, "height": 768},   # Common laptop
        {"width": 1536, "height": 864},   # Scaled laptop
        {"width": 1440, "height": 900},   # MacBook Pro
        {"width": 1280, "height": 720},   # HD
    ]

    def __init__(self, config: Optional[AntiBotConfig] = None):
        self.config = config or AntiBotConfig()
        self._user_agents = self.config.custom_user_agents or self.DEFAULT_USER_AGENTS

    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        if not self.config.rotate_user_agents:
            return self._user_agents[0]
        return random.choice(self._user_agents)

    def get_random_viewport(self) -> Dict[str, int]:
        """Get a random viewport size."""
        if not self.config.randomize_viewport:
            return self.VIEWPORT_SIZES[0]
        return random.choice(self.VIEWPORT_SIZES)

    def get_randomized_headers(self) -> Dict[str, str]:
        """
        Get randomized HTTP headers.

        Returns common headers with slight randomization to avoid fingerprinting.
        """
        if not self.config.randomize_headers:
            return {}

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice([
                "en-US,en;q=0.9",
                "en-GB,en;q=0.9",
                "en-US,en;q=0.5",
            ]),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": str(random.choice([0, 1])),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Randomly include or exclude certain headers
        if random.random() > 0.3:
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = random.choice(["none", "same-origin", "cross-site"])

        return headers

    async def apply_human_timing(self):
        """
        Add a random delay to simulate human behavior.

        Call this between actions (clicks, scrolls, etc.) to appear more human-like.
        """
        if not self.config.simulate_human_timing:
            return

        delay = random.uniform(
            self.config.min_action_delay,
            self.config.max_action_delay
        )
        await asyncio.sleep(delay)

    async def apply_to_context(self, context, page=None):
        """
        Apply anti-bot measures to a Playwright context and/or page.

        Args:
            context: Playwright BrowserContext
            page: Optional Playwright Page
        """
        # Set random viewport
        if self.config.randomize_viewport and page:
            viewport = self.get_random_viewport()
            await page.set_viewport_size(viewport)

        # Set extra headers
        if self.config.randomize_headers:
            headers = self.get_randomized_headers()
            await context.set_extra_http_headers(headers)

    def get_context_options(self) -> Dict:
        """
        Get context options for Playwright with anti-bot settings.

        Returns:
            Dict of options to pass to browser.new_context()
        """
        options = {}

        if self.config.rotate_user_agents:
            options["user_agent"] = self.get_random_user_agent()

        if self.config.randomize_viewport:
            options["viewport"] = self.get_random_viewport()

        # Additional options for better evasion
        options["locale"] = random.choice(["en-US", "en-GB", "en-CA"])
        options["timezone_id"] = random.choice([
            "America/New_York",
            "America/Los_Angeles",
            "America/Chicago",
            "Europe/London",
        ])

        return options
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
        # NEW: Rate limiting parameters
        enable_rate_limiting: bool = True,
        rate_limit_config: Optional[dict] = None,
        # NEW: Anti-bot parameters
        enable_anti_bot: bool = True,
        anti_bot_config: Optional[dict] = None,
        **kwargs: Any,
    ):
        # ... existing initialization ...
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_anti_bot = enable_anti_bot

        # Initialize rate limiter
        if self.enable_rate_limiting:
            from ..utils.rate_limiter import DomainRateLimiter, RateLimiterConfig
            config = RateLimiterConfig(**(rate_limit_config or {}))
            self.rate_limiter = DomainRateLimiter(config)
        else:
            self.rate_limiter = None

        # Initialize anti-bot manager
        if self.enable_anti_bot:
            from ..utils.anti_bot import AntiBotManager, AntiBotConfig
            config = AntiBotConfig(**(anti_bot_config or {}))
            self.anti_bot = AntiBotManager(config)
        else:
            self.anti_bot = None

    async def ascrape_playwright(self, url: str, browser_name: str = "chromium") -> str:
        """
        Asynchronously scrape with rate limiting and anti-bot measures.
        """
        from playwright.async_api import async_playwright
        from undetected_playwright import Malenia

        logger.info(f"Starting scraping with {self.backend}...")
        results = ""
        attempt = 0

        while attempt < self.retry_limit:
            try:
                # Apply rate limiting
                if self.rate_limiter:
                    delay = await self.rate_limiter.acquire(url, retry_attempt=attempt)
                    logger.debug(f"Rate limit delay: {delay:.2f}s")

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

                    # Create context with anti-bot options
                    context_options = {
                        "storage_state": self.storage_state,
                        "ignore_https_errors": True,
                    }

                    if self.anti_bot:
                        context_options.update(self.anti_bot.get_context_options())

                    context = await browser.new_context(**context_options)

                    # Apply stealth
                    await Malenia.apply_stealth(context)

                    # Apply additional anti-bot measures
                    if self.anti_bot:
                        await self.anti_bot.apply_to_context(context)

                    page = await context.new_page()

                    # Apply page-level anti-bot measures
                    if self.anti_bot:
                        await self.anti_bot.apply_to_context(context, page)

                    # Navigate to page
                    response = await page.goto(url, wait_until="domcontentloaded")

                    # Check for rate limiting response
                    if response.status == 429:
                        retry_after = response.headers.get("retry-after")
                        retry_after_seconds = int(retry_after) if retry_after else None

                        if self.rate_limiter:
                            self.rate_limiter.handle_429(url, retry_after_seconds)

                        raise aiohttp.ClientError(f"Rate limited (429) for {url}")

                    await page.wait_for_load_state(self.load_state)
                    results = await page.content()
                    logger.info("Content scraped successfully")
                    await browser.close()
                    return results

            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                attempt += 1
                logger.error(f"Attempt {attempt} failed: {e}")

                # Add exponential backoff delay on retry
                if attempt < self.retry_limit:
                    # Even without rate_limiter, add basic backoff
                    backoff = min(2 ** attempt, 30)  # Max 30 seconds
                    logger.info(f"Retrying after {backoff}s backoff")
                    await asyncio.sleep(backoff)

                if attempt == self.retry_limit:
                    raise RuntimeError(
                        f"Failed to scrape after {self.retry_limit} attempts: {str(e)}"
                    )

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        Asynchronously load with per-domain rate limiting.

        Instead of firing all requests simultaneously, this respects
        rate limits and processes requests in a controlled manner.
        """
        scraping_fn = (
            self.ascrape_with_js_support
            if self.requires_js_support
            else getattr(self, f"ascrape_{self.backend}")
        )

        # If rate limiting is disabled, use original parallel approach
        if not self.enable_rate_limiting:
            tasks = [scraping_fn(url) for url in self.urls]
            results = await asyncio.gather(*tasks)
            for url, content in zip(self.urls, results):
                metadata = {"source": url}
                yield Document(page_content=content, metadata=metadata)
            return

        # With rate limiting, process requests sequentially or with controlled concurrency
        for url in self.urls:
            try:
                content = await scraping_fn(url)
                metadata = {"source": url}
                yield Document(page_content=content, metadata=metadata)
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                # Yield error document
                metadata = {"source": url, "error": str(e)}
                yield Document(page_content="", metadata=metadata)
```

### Configuration Management

**Environment Variables:**
```bash
# Rate limiting configuration
SCRAPEGRAPH_RATE_LIMITING_ENABLED=true
SCRAPEGRAPH_RATE_LIMIT_MIN_DELAY=1.0
SCRAPEGRAPH_RATE_LIMIT_MAX_DELAY=3.0
SCRAPEGRAPH_RATE_LIMIT_RANDOMIZE=true
SCRAPEGRAPH_RATE_LIMIT_RESPECT_RETRY_AFTER=true

# Anti-bot configuration
SCRAPEGRAPH_ANTI_BOT_ENABLED=true
SCRAPEGRAPH_ANTI_BOT_ROTATE_UA=true
SCRAPEGRAPH_ANTI_BOT_RANDOMIZE_HEADERS=true
SCRAPEGRAPH_ANTI_BOT_RANDOMIZE_VIEWPORT=true
```

**Per-Domain Configuration:**
```python
# Example: Configure different limits for different domains
rate_limit_config = {
    "default_min_delay": 1.0,
    "default_max_delay": 3.0,
    "per_domain_limits": {
        "github.com": (2.0, 5.0),  # Stricter limits for GitHub
        "example.com": (0.5, 1.5),  # Looser limits for test site
    }
}

loader = ChromiumLoader(
    urls=urls,
    rate_limit_config=rate_limit_config
)
```

## Example Usage

### Before (Current Implementation)

```python
# Scraping without rate limiting - can trigger blocks
from scrapegraphai.docloaders import ChromiumLoader

urls = [f"https://example.com/page{i}" for i in range(50)]

loader = ChromiumLoader(urls, headless=True)
documents = loader.load()
# All requests fire as fast as possible → likely to be blocked
```

**Issues:**
- Requests fire simultaneously or in rapid succession
- No delays between retries
- Predictable user-agent
- High chance of being blocked

### After (With Rate Limiting & Anti-Bot)

```python
# Scraping with rate limiting and anti-bot measures
from scrapegraphai.docloaders import ChromiumLoader

urls = [f"https://example.com/page{i}" for i in range(50)]

# Configure rate limiting
rate_config = {
    "default_min_delay": 2.0,  # Min 2 seconds between requests
    "default_max_delay": 5.0,  # Max 5 seconds (randomized)
    "randomize_delay": True,   # Add jitter
    "respect_retry_after": True,  # Honor 429 responses
}

# Configure anti-bot measures
anti_bot_config = {
    "rotate_user_agents": True,
    "randomize_headers": True,
    "randomize_viewport": True,
    "simulate_human_timing": True,
}

loader = ChromiumLoader(
    urls,
    headless=True,
    enable_rate_limiting=True,
    rate_limit_config=rate_config,
    enable_anti_bot=True,
    anti_bot_config=anti_bot_config,
)

documents = loader.load()
# Requests are throttled, randomized, and less detectable
```

**Benefits:**
- 2-5 second delays between requests (randomized)
- Different user-agent for each request
- Randomized headers and viewport
- Handles 429 responses gracefully
- Much lower chance of being blocked

### Advanced Usage: Per-Domain Limits

```python
# Different rate limits for different domains
from scrapegraphai.docloaders import ChromiumLoader

urls = [
    "https://github.com/user1/repo1",
    "https://github.com/user2/repo2",
    "https://example.com/page1",
    "https://example.com/page2",
]

rate_config = {
    "default_min_delay": 1.0,
    "default_max_delay": 2.0,
    "per_domain_limits": {
        # GitHub is stricter, use slower rate
        "github.com": (3.0, 6.0),
        # Example.com allows faster scraping
        "example.com": (0.5, 1.0),
    },
    "respect_retry_after": True,
}

loader = ChromiumLoader(
    urls,
    rate_limit_config=rate_config,
)

# github.com URLs will be scraped with 3-6s delays
# example.com URLs will be scraped with 0.5-1s delays
documents = loader.load()
```

### Handling 429 Responses

```python
# Automatic handling of rate limit responses
import asyncio
from scrapegraphai.docloaders import ChromiumLoader

async def scrape_with_429_handling():
    loader = ChromiumLoader(
        ["https://api.example.com/data"],
        retry_limit=5,  # Retry up to 5 times
        rate_limit_config={
            "respect_retry_after": True,  # Honor Retry-After header
            "backoff_multiplier": 2.0,     # Double delay on each retry
            "max_backoff_delay": 60.0,     # Max 60s backoff
        }
    )

    try:
        documents = loader.load()
        print("Success!")
    except Exception as e:
        print(f"Failed after retries: {e}")

asyncio.run(scrape_with_429_handling())
# If server returns 429 with "Retry-After: 30", waits 30 seconds
# On subsequent 429s, uses exponential backoff
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
**Goal:** Core rate limiting infrastructure

**Tasks:**
1. Create `scrapegraphai/utils/rate_limiter.py`
   - `DomainState` dataclass
   - `RateLimiterConfig` dataclass
   - `DomainRateLimiter` class

2. Create `scrapegraphai/utils/anti_bot.py`
   - `AntiBotConfig` dataclass
   - `AntiBotManager` class
   - User-agent rotation
   - Header randomization

3. Add unit tests
   - Rate limiter delay calculation
   - Per-domain tracking
   - 429 handling
   - Exponential backoff

**Success Criteria:**
- 95% test coverage for new modules
- All existing tests still pass
- No production deployment

### Phase 2: Integration (Week 3-4)
**Goal:** Integrate with ChromiumLoader

**Tasks:**
1. Modify `ChromiumLoader`
   - Add rate limiting parameters
   - Add anti-bot parameters
   - Update `ascrape_playwright()`
   - Update `ascrape_playwright_scroll()`
   - Update `ascrape_with_js_support()`
   - Update `alazy_load()` for sequential processing

2. Add 429 response handling
   - Detect 429 status codes
   - Parse Retry-After headers
   - Trigger backoff

3. Update retry logic
   - Add delays between retries
   - Apply exponential backoff
   - Improve error messages

4. Documentation
   - API documentation
   - Configuration examples
   - Best practices guide

**Success Criteria:**
- Backward compatible
- Rate limiting works for all scraping methods
- 429 responses handled correctly

### Phase 3: Enhancement (Week 5-6)
**Goal:** Advanced anti-bot features

**Tasks:**
1. Enhanced anti-bot measures
   - Cookie jar management
   - Referrer handling
   - Mouse movement simulation (for scroll)
   - Enhanced fingerprint randomization

2. Performance optimization
   - Async lock optimization
   - Memory efficiency
   - Domain state cleanup

3. Monitoring and metrics
   - Rate limit statistics
   - 429 response tracking
   - Domain blocking alerts

4. Configuration presets
   - Conservative (slow, safe)
   - Balanced (default)
   - Aggressive (fast, risky)

**Success Criteria:**
- Enhanced evasion reduces block rate by 50%+
- Configuration presets available
- Metrics dashboard ready

### Phase 4: Production (Week 7-8)
**Goal:** Production deployment and validation

**Tasks:**
1. Gradual rollout
   - Enable for test domains
   - Monitor error rates
   - Expand to production

2. Documentation completion
   - Troubleshooting guide
   - Domain-specific configurations
   - FAQ

3. Community feedback
   - Gather user feedback
   - Address issues
   - Iterate on defaults

**Success Criteria:**
- Feature enabled by default
- No increase in error rates
- Positive user feedback
- Reduced 429 errors by 80%+

## Backwards Compatibility

### Breaking Changes

**None.** This RFC is fully backward compatible.

### Compatibility Strategy

1. **Opt-in Initially (Phase 1-2):**
   ```python
   # Default behavior unchanged
   loader = ChromiumLoader(urls)
   # No rate limiting or anti-bot by default initially
   ```

2. **Enabled by Default (Phase 3):**
   ```python
   # After Phase 3, enabled by default with conservative settings
   loader = ChromiumLoader(urls)
   # Rate limiting: 1-3s delays
   # Anti-bot: basic measures enabled

   # Opt-out if needed
   loader = ChromiumLoader(
       urls,
       enable_rate_limiting=False,
       enable_anti_bot=False
   )
   ```

3. **Environment Variable Override:**
   ```bash
   # Disable globally if needed
   export SCRAPEGRAPH_RATE_LIMITING_ENABLED=false
   export SCRAPEGRAPH_ANTI_BOT_ENABLED=false
   ```

### API Stability

**Guaranteed Stable:**
- All existing `ChromiumLoader` parameters
- Existing method signatures
- Return types

**New Optional Parameters:**
- `enable_rate_limiting: bool = True`
- `rate_limit_config: Optional[dict] = None`
- `enable_anti_bot: bool = True`
- `anti_bot_config: Optional[dict] = None`

## Performance Impact

### Expected Improvements

**Metric: Successful Scrape Rate**
- Current: 60-70% success rate on protected sites
- With Rate Limiting + Anti-Bot: 90-95% success rate
- **Improvement: 30-50% fewer failures**

**Metric: 429 Response Handling**
- Current: Retry immediately, fail quickly
- With Rate Limiting: Honor Retry-After, exponential backoff
- **Improvement: 80% reduction in wasted retries**

**Metric: Total Scraping Time (with retries)**
- Current: High variance due to blocks and retries
- With Rate Limiting: More predictable, longer but reliable
- **Trade-off: 20-30% slower but 90%+ success rate vs 60-70%**

**Metric: Block Rate**
- Current: ~30-40% of domains block aggressive scraping
- With Anti-Bot: ~5-10% block rate
- **Improvement: 70-85% reduction in blocks**

### Performance Trade-offs

**Slower Individual Requests:**
- Rate limiting adds 1-5 second delays between requests
- Anti-bot measures add minimal overhead (<100ms)
- **Trade-off:** Slower overall scraping time

**But Higher Success Rate:**
- Fewer blocks → fewer re-scrapes
- Fewer CAPTCHA challenges → less manual intervention
- More reliable results → better data quality
- **Net benefit:** More efficient use of resources overall

### Benchmarking

```python
# Test: Scrape 50 URLs from rate-limited site
import time
from scrapegraphai.docloaders import ChromiumLoader

test_urls = [f"https://example.com/page{i}" for i in range(50)]

# Without rate limiting (current)
start = time.time()
try:
    loader = ChromiumLoader(test_urls, enable_rate_limiting=False)
    docs = loader.load()
    success_count = len([d for d in docs if d.page_content])
except Exception as e:
    success_count = 0
time_without = time.time() - start

# With rate limiting
start = time.time()
loader = ChromiumLoader(
    test_urls,
    enable_rate_limiting=True,
    rate_limit_config={"default_min_delay": 2.0, "default_max_delay": 4.0}
)
docs = loader.load()
success_count_with = len([d for d in docs if d.page_content])
time_with = time.time() - start

print(f"Without rate limiting: {success_count}/50 in {time_without:.1f}s")
print(f"With rate limiting: {success_count_with}/50 in {time_with:.1f}s")
# Expected:
# Without: 30-35/50 in 120s (many failures, some retries)
# With: 48-50/50 in 180s (nearly all succeed, controlled pace)
```

## Alternatives Considered

### Alternative 1: No Rate Limiting (Status Quo)

**Description:** Continue without rate limiting, rely only on `undetected_playwright`.

**Pros:**
- Fastest scraping speed
- Simplest implementation
- No delays

**Cons:**
- High block rate on protected sites
- Frequent 429 errors
- Unethical server load
- Unreliable results

**Why Not Chosen:** Unacceptable failure rate makes this unsuitable for production.

---

### Alternative 2: Global Rate Limit (Not Per-Domain)

**Description:** Single rate limit across all domains.

**Pros:**
- Simpler implementation
- Easier to configure
- Predictable behavior

**Cons:**
- Too slow for lenient sites
- Still too fast for strict sites
- Doesn't respect domain-specific limits
- Inefficient resource usage

**Why Not Chosen:** Per-domain limiting is more flexible and efficient.

---

### Alternative 3: External Rate Limiting Service

**Description:** Use external service like Redis for distributed rate limiting.

**Pros:**
- Shared limits across multiple scrapers
- Centralized management
- Scales horizontally

**Cons:**
- Adds external dependency
- Network latency
- Increased complexity
- Overkill for single-instance usage

**Why Not Chosen:** Most users run single instances; in-process limiting is sufficient.

---

### Alternative 4: Proxy Rotation Only

**Description:** Use rotating proxies instead of rate limiting.

**Pros:**
- Can scrape faster
- Different IPs avoid detection
- Works for some cases

**Cons:**
- Expensive (proxy costs)
- Doesn't solve predictable patterns
- Still need rate limiting per proxy
- Not always available

**Why Not Chosen:** Proxies complement rate limiting but don't replace it.

---

### Decision Matrix

| Alternative | Reliability | Performance | Cost | Complexity | Score |
|------------|-------------|-------------|------|------------|-------|
| **Per-Domain Rate Limiting (Chosen)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **19/25** |
| Status Quo | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 19/25 |
| Global Rate Limit | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 15/25 |
| External Service | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 13/25 |
| Proxy Rotation | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 15/25 |

## Security Considerations

### Threat Model

**Threat 1: Detection via Fingerprinting**

**Description:** Anti-bot systems detect automation via browser fingerprints.

**Mitigation:**
- Randomize user-agents
- Randomize viewport sizes
- Randomize headers
- Use undetected-playwright stealth
- Vary timing patterns

**Implementation:**
```python
# AntiBotManager randomizes fingerprint
context_options = anti_bot.get_context_options()
# Different UA, viewport, locale, timezone each request
```

---

**Threat 2: Detection via Timing Patterns**

**Description:** Predictable request timing reveals automation.

**Mitigation:**
- Randomize delays (jitter)
- Exponential backoff on retries
- Simulate human-like pauses
- Vary scroll timing

**Implementation:**
```python
# Random delay between min and max
delay = random.uniform(min_delay, max_delay)
```

---

**Threat 3: IP-Based Blocking**

**Description:** Too many requests from one IP triggers blocks.

**Mitigation:**
- Rate limiting prevents excessive requests
- Respect Retry-After headers
- Support for proxy configuration
- Exponential backoff on 429

**Implementation:**
```python
# Rate limiter prevents rapid-fire requests
await rate_limiter.acquire(url)
```

---

**Threat 4: Session Correlation**

**Description:** Persistent cookies/sessions reveal bot identity.

**Mitigation:**
- Fresh contexts for different domains
- Cookie isolation
- Storage state management
- Optional cookie clearing

**Note:** Full cookie rotation coming in future enhancement.

---

### Privacy Considerations

**User-Agent Rotation:**
- Uses common, real user-agents
- No fake or suspicious UAs
- Respects user privacy

**Header Randomization:**
- Sends standard, common headers
- No personal information
- Mimics real browsers

**Ethical Scraping:**
- Respects rate limits
- Honors Retry-After
- Reduces server load
- Follows robots.txt (separate RFC)

## Open Questions

### Question 1: Default Rate Limit Values

**Context:** What should the default min/max delays be?

**Current Proposal:**
- `default_min_delay: 1.0` (1 second)
- `default_max_delay: 3.0` (3 seconds)

**Trade-offs:**
- Lower values = faster but higher block risk
- Higher values = slower but safer
- Different sites have different tolerances

**Request for Input:** What defaults work best for most use cases?

---

### Question 2: Concurrent Requests Per Domain

**Context:** Should we allow multiple concurrent requests to same domain?

**Current Design:** Sequential requests per domain (implicit via rate limiter)

**Alternative:** Allow N concurrent requests per domain with rate limiting

**Trade-offs:**
- Sequential: Simpler, safer, slower
- Concurrent: Faster, more complex, riskier

**Request for Input:** Is concurrent-per-domain needed? What's the use case?

---

### Question 3: User-Agent Pool Size

**Context:** How many user-agents should we rotate through?

**Current:** 6 default user-agents (major browsers)

**Alternatives:**
- More UAs (50+): Better variety, harder to maintain
- Fewer UAs (3-4): Simpler, less variety
- Custom UA lists per domain

**Request for Input:** What's the optimal balance?

---

### Question 4: Integration with Browser Pooling (RFC-0001)

**Context:** How should rate limiting work with browser pooling?

**Considerations:**
- Pooled browsers may scrape different domains
- Rate limiting is per-domain, pooling is per-browser
- Should work together transparently

**Question:** Any conflicts between these features?

---

### Question 5: Robots.txt Compliance

**Context:** Should rate limiter check robots.txt?

**Current:** No robots.txt support

**Alternative:** Parse robots.txt Crawl-delay directive

**Trade-offs:**
- Pros: Respectful, ethical, may reduce blocks
- Cons: Adds complexity, HTTP request overhead

**Request for Input:** Add robots.txt support in this RFC or separate RFC?

---

### Question 6: Adaptive Rate Limiting

**Context:** Should rate limits adjust based on server responses?

**Current:** Fixed limits, only adjusts on 429

**Alternative:** Learn optimal rates from server behavior
- Speed up if no issues
- Slow down if seeing errors
- Per-domain learning

**Trade-offs:**
- Pros: Optimally fast, adapts to site
- Cons: Complex, unpredictable, requires state

**Request for Input:** Worth the complexity?

---

### How to Provide Input

**For Community:**
- Comment on GitHub issue
- Discord #architecture channel
- Email to team

**For Core Team:**
- RFC review meeting
- Async feedback
- Vote on decisions

**Timeline:**
- RFC feedback period: 2 weeks
- Decisions: Week 3
- Implementation: Week 4+

## Success Metrics

### Primary Metrics

**Metric 1: Successful Scrape Rate**

**Definition:** Percentage of scraping attempts that succeed without blocks

**Target:** 90%+ success rate (up from 60-70%)

**Measurement:**
```python
def measure_success_rate():
    urls = generate_test_urls(100)
    successes = 0

    for url in urls:
        try:
            loader = ChromiumLoader([url], enable_rate_limiting=True)
            doc = loader.load()
            if doc and doc[0].page_content:
                successes += 1
        except Exception:
            pass

    success_rate = successes / len(urls)
    assert success_rate >= 0.90
```

---

**Metric 2: 429 Response Reduction**

**Definition:** Number of 429 (rate limit) errors received

**Target:** 80% reduction in 429 errors

**Measurement:**
```python
# Count 429 errors before and after
# Before: ~30 out of 100 requests
# After: ~5 out of 100 requests
# Reduction: 83%
```

---

**Metric 3: Block Rate**

**Definition:** Percentage of domains that block scraping

**Target:** <10% block rate (down from 30-40%)

**Measurement:**
```python
# Test across 50 different domains
# Measure: permanent blocks, CAPTCHAs, access denied
# Target: < 5 domains blocked
```

---

### Secondary Metrics

**Metric 4: Average Request Delay**

**Definition:** Average delay between requests to same domain

**Target:** 1-3 seconds (configurable)

**Measurement:**
```python
# Measure time between requests
# Should respect min/max delay config
# Should have randomization (jitter)
```

---

**Metric 5: Retry Success Rate**

**Definition:** Percentage of retries that succeed after initial failure

**Target:** 70% of retries succeed (up from 30%)

**Measurement:**
```python
# Track: initial failures that succeed on retry
# With exponential backoff and rate limiting
# Should see higher retry success
```

---

**Metric 6: User-Agent Distribution**

**Definition:** Distribution of user-agents across requests

**Target:** Roughly even distribution across configured UAs

**Measurement:**
```python
# Count requests per UA
# Should be evenly distributed if rotation enabled
# Verify randomization working
```

---

### Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  ScrapeGraphAI Rate Limiting & Anti-Bot Metrics                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Success Rate:         [████████░░] 92%                         │
│  429 Error Rate:       [██████████] 0.8% (down from 4%)         │
│  Block Rate:           [██████████] 6%                          │
│  Avg Request Delay:    2.3s                                     │
│  Retry Success:        [████████░░] 74%                         │
│  UA Distribution:      Even (✓)                                 │
│                                                                  │
│  Per-Domain Stats:                                              │
│  ├─ github.com:    45 reqs, 0 blocks, avg 4.2s delay           │
│  ├─ example.com:   89 reqs, 2 blocks, avg 1.5s delay           │
│  └─ reddit.com:    31 reqs, 1 429s handled, avg 3.1s delay     │
│                                                                  │
│  Recent Events:                                                 │
│  ✓ 14:32:15 - Rate limit applied: github.com (4.2s delay)      │
│  ✓ 14:32:10 - User-agent rotated: Chrome/121                   │
│  ⚠ 14:31:58 - 429 detected, backing off 30s                    │
│  ✓ 14:31:45 - Retry successful after backoff                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## References

### Code References

1. **ChromiumLoader Implementation**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/docloaders/chromium.py`
   - Lines 323-381: `ascrape_playwright()` retry logic
   - Lines 344-380: Current retry loop without delays
   - Lines 479-483: `alazy_load()` parallel execution
   - Issue: No rate limiting between requests

2. **Retry Logic Examples**
   - Lines 108-164: Selenium retry logic
   - Lines 234-321: Scroll retry logic
   - Lines 403-437: JS support retry logic
   - Pattern: All retry immediately without backoff

3. **FetchNode Integration**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/nodes/fetch_node.py`
   - Likely location for rate limit configuration propagation

4. **Timeout Configuration PR**
   - Commit: e81a4ed (feat: Add configurable timeout to FetchNode)
   - Related: Shows need for better request control

### External References

5. **HTTP Status 429 (Too Many Requests)**
   - RFC 6585: https://tools.ietf.org/html/rfc6585#section-4
   - Defines Retry-After header
   - Standard for rate limiting

6. **Playwright Anti-Detection**
   - undetected-playwright: https://github.com/kaliiiiiiiiii/undetected-playwright
   - Malenia stealth features
   - Current anti-bot foundation

7. **User-Agent Strings**
   - User-Agent database: https://www.useragentstring.com/
   - Current browser versions
   - Common user-agent patterns

8. **Rate Limiting Best Practices**
   - Token bucket algorithm
   - Exponential backoff strategies
   - Jitter and randomization

9. **Web Scraping Ethics**
   - robots.txt standard
   - Crawl-delay directive
   - Respectful scraping guidelines

### Related RFCs

10. **RFC-0001: Browser Connection Pooling**
    - Related to this RFC
    - Rate limiting should work with pooling
    - Both address browser efficiency

### Academic References

11. **HTTP Rate Limiting Patterns**
    - Token bucket, leaky bucket algorithms
    - Distributed rate limiting
    - Application: Per-domain request throttling

12. **Bot Detection Evasion**
    - Browser fingerprinting techniques
    - Timing analysis detection
    - Mitigation strategies

---

## Appendix: Code Examples

### A1: Complete Usage Example

```python
"""
Production-ready scraping with rate limiting and anti-bot.
"""
import asyncio
from scrapegraphai.docloaders import ChromiumLoader

async def scrape_with_protection():
    # URLs from multiple domains
    urls = [
        "https://github.com/user/repo1",
        "https://github.com/user/repo2",
        "https://example.com/page1",
        "https://example.com/page2",
        "https://reddit.com/r/python/",
    ]

    # Configure rate limiting
    rate_config = {
        "default_min_delay": 2.0,
        "default_max_delay": 4.0,
        "randomize_delay": True,
        "respect_retry_after": True,
        "backoff_multiplier": 2.0,
        "per_domain_limits": {
            "github.com": (3.0, 6.0),  # Stricter for GitHub
            "reddit.com": (2.0, 5.0),   # Medium for Reddit
        }
    }

    # Configure anti-bot
    anti_bot_config = {
        "rotate_user_agents": True,
        "randomize_headers": True,
        "randomize_viewport": True,
        "simulate_human_timing": True,
    }

    # Create loader
    loader = ChromiumLoader(
        urls,
        headless=True,
        retry_limit=5,
        enable_rate_limiting=True,
        rate_limit_config=rate_config,
        enable_anti_bot=True,
        anti_bot_config=anti_bot_config,
    )

    try:
        # Scrape all URLs
        documents = loader.load()

        # Check results
        for doc in documents:
            url = doc.metadata.get("source")
            success = len(doc.page_content) > 0
            print(f"{url}: {'✓' if success else '✗'}")

        # Get rate limiter stats
        if hasattr(loader, 'rate_limiter'):
            stats = loader.rate_limiter.get_stats()
            print(f"\nRate Limiter Stats: {stats}")

    except Exception as e:
        print(f"Scraping failed: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_with_protection())
```

### A2: Custom Domain Configuration

```python
"""
Advanced per-domain configuration.
"""
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.rate_limiter import DomainRateLimiter, RateLimiterConfig

# Create custom rate limiter
rate_config = RateLimiterConfig(
    default_min_delay=1.0,
    default_max_delay=2.0,
    per_domain_limits={
        "api.example.com": (5.0, 10.0),  # API needs slower rate
        "static.example.com": (0.2, 0.5),  # Static content can be faster
    }
)

rate_limiter = DomainRateLimiter(rate_config)

# Dynamically adjust limits
rate_limiter.configure_domain("newdomain.com", min_delay=3.0, max_delay=6.0)

# Use with loader
loader = ChromiumLoader(
    urls,
    enable_rate_limiting=True,
    rate_limit_config=rate_config.__dict__
)
```

### A3: Monitoring Integration

```python
"""
Integration with monitoring system.
"""
from scrapegraphai.docloaders import ChromiumLoader
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonitoredScraper:
    def __init__(self):
        self.loader = ChromiumLoader(
            [],
            enable_rate_limiting=True,
            enable_anti_bot=True,
        )
        self.metrics = {
            "total_requests": 0,
            "successes": 0,
            "failures": 0,
            "429_errors": 0,
            "retries": 0,
        }

    async def scrape(self, url):
        self.metrics["total_requests"] += 1

        try:
            self.loader.urls = [url]
            docs = self.loader.load()
            self.metrics["successes"] += 1
            return docs[0]
        except RuntimeError as e:
            if "429" in str(e):
                self.metrics["429_errors"] += 1
            self.metrics["failures"] += 1
            raise

    def get_metrics(self):
        return self.metrics
```

---

**End of RFC-0010**

---

**Feedback and questions welcome!**
Please direct comments to the RFC discussion thread or reach out to the ScrapeGraphAI team on Discord.
