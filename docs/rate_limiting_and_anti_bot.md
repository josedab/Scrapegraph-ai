# Rate Limiting and Anti-Bot Features

This document describes the rate limiting and anti-bot evasion features added to ScrapeGraphAI's `ChromiumLoader`.

## Overview

The `ChromiumLoader` now includes:
- **Per-domain rate limiting** with exponential backoff and jitter
- **Anti-bot evasion strategies** including user-agent rotation, header randomization, and viewport randomization
- **429 response handling** with proper Retry-After header support
- **Exponential backoff** on retries

These features improve scraping reliability while being respectful of target websites.

## Features

### 1. Rate Limiting

The rate limiter provides:
- Per-domain request tracking
- Configurable min/max delays between requests
- Exponential backoff on retries
- Retry-After header support (HTTP 429 responses)
- Request timing randomization (jitter)
- Domain blocking/cooldown after rate limit errors

### 2. Anti-Bot Evasion

The anti-bot manager provides:
- User-agent rotation from a pool of realistic agents
- Request header randomization
- Viewport size randomization
- Human-like timing simulation
- Locale and timezone randomization

## Basic Usage

### Default Configuration (Recommended)

By default, both rate limiting and anti-bot features are **enabled**:

```python
from scrapegraphai.docloaders import ChromiumLoader

urls = ["https://example.com/page1", "https://example.com/page2"]

# Both features enabled by default
loader = ChromiumLoader(urls, headless=True)
documents = loader.load()
```

### Disabling Features

You can disable either or both features if needed:

```python
# Disable rate limiting only
loader = ChromiumLoader(
    urls,
    enable_rate_limiting=False,
    enable_anti_bot=True
)

# Disable anti-bot only
loader = ChromiumLoader(
    urls,
    enable_rate_limiting=True,
    enable_anti_bot=False
)

# Disable both
loader = ChromiumLoader(
    urls,
    enable_rate_limiting=False,
    enable_anti_bot=False
)
```

## Advanced Configuration

### Rate Limiting Configuration

Configure rate limiting behavior:

```python
from scrapegraphai.docloaders import ChromiumLoader

urls = ["https://example.com/page1", "https://example.com/page2"]

rate_config = {
    "default_min_delay": 2.0,          # Min 2 seconds between requests
    "default_max_delay": 5.0,          # Max 5 seconds (randomized)
    "randomize_delay": True,           # Add jitter to delays
    "respect_retry_after": True,       # Honor 429 Retry-After headers
    "backoff_multiplier": 2.0,         # Exponential backoff multiplier
    "max_backoff_delay": 60.0,         # Maximum backoff delay
}

loader = ChromiumLoader(
    urls,
    enable_rate_limiting=True,
    rate_limit_config=rate_config
)

documents = loader.load()
```

### Per-Domain Rate Limiting

Configure different rate limits for different domains:

```python
rate_config = {
    "default_min_delay": 1.0,
    "default_max_delay": 3.0,
    "per_domain_limits": {
        "github.com": (2.0, 5.0),      # Stricter limits for GitHub
        "example.com": (0.5, 1.5),     # Looser limits for test site
    }
}

loader = ChromiumLoader(
    urls,
    rate_limit_config=rate_config
)
```

### Anti-Bot Configuration

Configure anti-bot behavior:

```python
anti_bot_config = {
    "rotate_user_agents": True,        # Rotate user agents
    "randomize_headers": True,         # Randomize HTTP headers
    "randomize_viewport": True,        # Randomize viewport size
    "simulate_human_timing": True,     # Add human-like delays
    "min_action_delay": 0.1,          # Min delay between actions
    "max_action_delay": 0.5,          # Max delay between actions
}

loader = ChromiumLoader(
    urls,
    enable_anti_bot=True,
    anti_bot_config=anti_bot_config
)
```

### Custom User Agents

Provide your own user agent pool:

```python
custom_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...",
    # Add more user agents
]

anti_bot_config = {
    "rotate_user_agents": True,
    "custom_user_agents": custom_agents,
}

loader = ChromiumLoader(
    urls,
    anti_bot_config=anti_bot_config
)
```

## Complete Example

Here's a complete example with both features configured:

```python
from scrapegraphai.docloaders import ChromiumLoader

urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://github.com/user/repo",
]

# Configure rate limiting
rate_config = {
    "default_min_delay": 1.0,
    "default_max_delay": 3.0,
    "randomize_delay": True,
    "respect_retry_after": True,
    "per_domain_limits": {
        "github.com": (2.0, 5.0),  # More conservative for GitHub
    }
}

# Configure anti-bot
anti_bot_config = {
    "rotate_user_agents": True,
    "randomize_headers": True,
    "randomize_viewport": True,
    "simulate_human_timing": True,
}

# Create loader with both features
loader = ChromiumLoader(
    urls,
    headless=True,
    retry_limit=3,
    timeout=60,
    enable_rate_limiting=True,
    rate_limit_config=rate_config,
    enable_anti_bot=True,
    anti_bot_config=anti_bot_config,
)

# Load documents
# - Requests are rate-limited per domain
# - Each request uses randomized user-agent and headers
# - 429 errors trigger exponential backoff
# - All retries use exponential backoff
documents = loader.load()

for doc in documents:
    print(f"Scraped: {doc.metadata['source']}")
    if "error" in doc.metadata:
        print(f"  Error: {doc.metadata['error']}")
```

## Async Usage

The rate limiting and anti-bot features work seamlessly with async operations:

```python
import asyncio
from scrapegraphai.docloaders import ChromiumLoader

async def scrape_with_rate_limiting():
    urls = ["https://example.com/page1", "https://example.com/page2"]

    loader = ChromiumLoader(
        urls,
        enable_rate_limiting=True,
        rate_limit_config={"default_min_delay": 2.0}
    )

    # When rate limiting is enabled, requests are processed sequentially
    documents = []
    async for doc in loader.alazy_load():
        documents.append(doc)
        print(f"Loaded: {doc.metadata['source']}")

    return documents

# Run async
documents = asyncio.run(scrape_with_rate_limiting())
```

## Monitoring and Statistics

Get rate limiting statistics:

```python
from scrapegraphai.docloaders import ChromiumLoader

loader = ChromiumLoader(
    urls,
    enable_rate_limiting=True
)

# Access rate limiter directly
if loader.rate_limiter:
    # Get stats for all domains
    all_stats = loader.rate_limiter.get_stats()
    print(all_stats)

    # Get stats for specific domain
    domain_stats = loader.rate_limiter.get_stats("example.com")
    print(f"Requests to example.com: {domain_stats.get('request_count', 0)}")
```

## How It Works

### Rate Limiting Flow

1. **Request Initiated**: When a URL is scraped, the rate limiter is consulted
2. **Domain Extracted**: The domain is extracted from the URL
3. **Check Last Request**: The time since the last request to this domain is checked
4. **Apply Delay**: If needed, the scraper waits before proceeding
5. **Handle 429**: If a 429 response is received, the domain is temporarily blocked
6. **Exponential Backoff**: Retries use exponential backoff delays

### Anti-Bot Flow

1. **Context Creation**: When creating the browser context, anti-bot options are applied
2. **User-Agent**: A random user agent is selected from the pool
3. **Viewport**: A random viewport size is chosen
4. **Headers**: HTTP headers are randomized
5. **Locale/Timezone**: Random locale and timezone are set
6. **Stealth**: Undetected Playwright stealth is applied
7. **Human Timing**: Random delays simulate human behavior

### Sequential vs Parallel Processing

**With Rate Limiting Enabled** (default):
- URLs are processed **sequentially**
- Each request waits for the appropriate delay
- Per-domain limits are respected
- Safer for production scraping

**With Rate Limiting Disabled**:
- URLs are processed **in parallel**
- Maximum speed, but higher risk of blocks
- Use only for testing or trusted domains

## Best Practices

### 1. Use Default Settings

For most use cases, the defaults work well:

```python
loader = ChromiumLoader(urls)  # Both features enabled with sensible defaults
```

### 2. Configure Per-Domain Limits

For mixed scraping (multiple domains), configure per-domain limits:

```python
rate_config = {
    "per_domain_limits": {
        "high-traffic-site.com": (3.0, 6.0),  # More conservative
        "low-traffic-site.com": (1.0, 2.0),   # Less conservative
    }
}
```

### 3. Respect Retry-After Headers

Always enable `respect_retry_after`:

```python
rate_config = {
    "respect_retry_after": True,  # Default, but make it explicit
}
```

### 4. Use Appropriate Retry Limits

Set retry limits based on importance:

```python
# Critical data - more retries
loader = ChromiumLoader(urls, retry_limit=5)

# Best-effort scraping - fewer retries
loader = ChromiumLoader(urls, retry_limit=2)
```

### 5. Monitor for Blocks

Check for errors in metadata:

```python
for doc in documents:
    if "error" in doc.metadata:
        print(f"Failed to scrape {doc.metadata['source']}: {doc.metadata['error']}")
```

## Troubleshooting

### Still Getting Blocked?

1. **Increase delays**: Use higher `min_delay` and `max_delay`
2. **Add custom user agents**: Provide more realistic user agents
3. **Use proxies**: Combine with proxy rotation
4. **Check robots.txt**: Ensure you're allowed to scrape

### Scraping Too Slow?

1. **Adjust delays**: Lower `min_delay` and `max_delay`
2. **Disable for trusted domains**: If scraping your own sites
3. **Use parallel processing**: Disable rate limiting for internal sites

### 429 Errors Not Handled?

1. **Check retry limit**: Ensure `retry_limit` is > 1
2. **Verify config**: Ensure `respect_retry_after: True`
3. **Check logs**: Look for rate limiter warnings

## Environment Variables

You can configure defaults via environment variables:

```bash
# Rate limiting
export SCRAPEGRAPH_RATE_LIMITING_ENABLED=true
export SCRAPEGRAPH_RATE_LIMIT_MIN_DELAY=1.0
export SCRAPEGRAPH_RATE_LIMIT_MAX_DELAY=3.0
export SCRAPEGRAPH_RATE_LIMIT_RANDOMIZE=true
export SCRAPEGRAPH_RATE_LIMIT_RESPECT_RETRY_AFTER=true

# Anti-bot
export SCRAPEGRAPH_ANTI_BOT_ENABLED=true
export SCRAPEGRAPH_ANTI_BOT_ROTATE_UA=true
export SCRAPEGRAPH_ANTI_BOT_RANDOMIZE_HEADERS=true
export SCRAPEGRAPH_ANTI_BOT_RANDOMIZE_VIEWPORT=true
```

## API Reference

### ChromiumLoader Parameters

- `enable_rate_limiting` (bool): Enable rate limiting. Default: `True`
- `rate_limit_config` (dict): Rate limiter configuration. Optional.
- `enable_anti_bot` (bool): Enable anti-bot features. Default: `True`
- `anti_bot_config` (dict): Anti-bot configuration. Optional.

### Rate Limiter Config Options

- `default_min_delay` (float): Minimum delay between requests. Default: 1.0
- `default_max_delay` (float): Maximum delay between requests. Default: 3.0
- `randomize_delay` (bool): Add jitter to delays. Default: True
- `respect_retry_after` (bool): Honor Retry-After headers. Default: True
- `backoff_multiplier` (float): Exponential backoff multiplier. Default: 2.0
- `max_backoff_delay` (float): Maximum backoff delay. Default: 60.0
- `per_domain_limits` (dict): Per-domain (min, max) tuples. Default: {}

### Anti-Bot Config Options

- `rotate_user_agents` (bool): Rotate user agents. Default: True
- `randomize_headers` (bool): Randomize headers. Default: True
- `randomize_viewport` (bool): Randomize viewport. Default: True
- `simulate_human_timing` (bool): Add human-like delays. Default: True
- `min_action_delay` (float): Min delay between actions. Default: 0.1
- `max_action_delay` (float): Max delay between actions. Default: 0.5
- `custom_user_agents` (list): Custom user agent pool. Default: []

## License

These features are part of ScrapeGraphAI and follow the same license.

## Contributing

Contributions are welcome! Please see the main CONTRIBUTING.md for guidelines.
