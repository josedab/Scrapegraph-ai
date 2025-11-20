# Incremental Scraping with Content Fingerprinting

## Overview

Incremental scraping is an optimization feature that detects content changes through cryptographic fingerprinting, allowing ScrapeGraph-AI to only re-scrape pages when actual content modifications occur. This can reduce operational costs by 60-80% for monitoring and change-detection use cases while maintaining data accuracy.

## Features

- **Content Fingerprinting**: SHA-256/MD5 hash-based change detection
- **Multiple Cache Backends**: SQLite (persistent) and in-memory caching
- **HTTP Header Optimization**: Uses ETag and Last-Modified headers for quick checks
- **Content Normalization**: Reduces false positives from dynamic elements
- **Flexible Configuration**: Customizable normalization and caching strategies

## Benefits

- **Cost Reduction**: 60-80% reduction in API calls and LLM token usage
- **Faster Execution**: Skip processing unchanged content
- **Better Rate Limit Management**: Reduced request frequency
- **Lower Infrastructure Costs**: Reduced compute and storage requirements

## Quick Start

### Basic Usage

```python
from scrapegraphai.graphs import SmartScraperGraph

# Enable incremental scraping with default settings
graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
        "cache_path": ".scrapegraph_cache/fingerprints.db",
    }
}

scraper = SmartScraperGraph(
    prompt="Extract product prices",
    source="https://example.com/products",
    config=graph_config
)

# First run: Fetches and caches content
result1 = scraper.run()

# Second run: Uses cached content if unchanged (much faster!)
result2 = scraper.run()
```

## Configuration

### Full Configuration Options

```python
graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        # Enable/disable incremental scraping
        "enabled": True,

        # Cache backend: "sqlite" or "memory"
        "cache_backend": "sqlite",

        # Cache location (for SQLite)
        "cache_path": ".scrapegraph_cache/fingerprints.db",

        # Normalization strategy: "full", "normalized", or "custom"
        "normalization": "normalized",

        # Custom normalization function (if normalization="custom")
        "normalize_fn": None,

        # Use HTTP headers (ETag, Last-Modified) for quick checks
        "use_http_headers": True,

        # Force refetch if cached entry older than X seconds (0 = no expiration)
        "max_age": 86400,  # 24 hours

        # Fingerprint algorithm: "sha256" or "md5"
        "hash_algorithm": "sha256",

        # Store full content in cache for instant retrieval
        "cache_content": True,
    }
}
```

### Configuration Parameters Explained

#### `enabled` (bool, default: False)
Enable or disable incremental scraping. When disabled, FetchNode behaves normally.

#### `cache_backend` (str, default: "sqlite")
- **"sqlite"**: Persistent file-based cache (recommended for production)
- **"memory"**: In-memory cache (faster but lost when process ends)

#### `cache_path` (str, default: ".scrapegraph_cache/fingerprints.db")
Path to SQLite database file. Directory will be created if it doesn't exist.

#### `normalization` (str, default: "normalized")
- **"full"**: No normalization, detect any change
- **"normalized"**: Remove timestamps, session IDs, ads (recommended)
- **"custom"**: Use custom normalization function

#### `use_http_headers` (bool, default: True)
Use HTTP ETag and Last-Modified headers for quick change detection before fetching full content.

#### `max_age` (int, default: 0)
Maximum age in seconds for cached entries. After this time, content will be refetched regardless of fingerprint. Set to 0 for no expiration.

#### `hash_algorithm` (str, default: "sha256")
- **"sha256"**: More secure, 64-character hash
- **"md5"**: Faster, 32-character hash (less collision-resistant)

#### `cache_content` (bool, default: True)
Store full processed content in cache for instant retrieval. If False, only fingerprints are stored.

## Use Cases

### 1. Website Monitoring

Monitor competitor pricing or product availability:

```python
graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
        "max_age": 3600,  # Check hourly
    }
}

scraper = SmartScraperGraph(
    prompt="Extract product name, price, and availability",
    source="https://competitor.com/product",
    config=graph_config
)

# Run periodically (e.g., via cron)
result = scraper.run()
```

### 2. News Aggregation

Only process updated articles:

```python
urls = [
    "https://news.example.com/article1",
    "https://news.example.com/article2",
    "https://news.example.com/article3",
]

graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
        "normalization": "normalized",  # Ignore timestamps
    }
}

for url in urls:
    scraper = SmartScraperGraph(
        prompt="Extract article title and content",
        source=url,
        config=graph_config
    )
    result = scraper.run()

    # Check if content was from cache
    if result.get("from_cache"):
        print(f"Skipped {url} - no changes")
    else:
        print(f"Processed {url} - new content")
```

### 3. Custom Normalization

Remove site-specific dynamic elements:

```python
def custom_normalize(html: str) -> str:
    """Remove site-specific dynamic elements."""
    from scrapegraphai.utils.content_normalizer import normalize_html
    import re

    # Start with standard normalization
    text = normalize_html(html, aggressive=True)

    # Remove custom patterns
    text = re.sub(r'Last updated: .*', '', text)
    text = re.sub(r'Viewed \d+ times', '', text)
    text = re.sub(r'User \d+ is online', '', text)

    return text

graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        "enabled": True,
        "normalization": "custom",
        "normalize_fn": custom_normalize,
    }
}
```

### 4. Monitoring Multiple URLs

```python
from scrapegraphai.nodes import FetchNode

urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
]

node_config = {
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
    }
}

fetch_node = FetchNode(
    input="url",
    output=["document"],
    node_config=node_config
)

for url in urls:
    state = {"url": url}
    result = fetch_node.execute(state)

    if result.get("from_cache"):
        print(f"✓ {url}: Cached (unchanged)")
    else:
        print(f"↻ {url}: Fetched (changed or new)")

# View cache statistics
stats = fetch_node.cache.get_stats()
print(f"\nCache Statistics:")
print(f"  Total URLs: {stats['total_entries']}")
print(f"  Total Fetches: {stats['total_fetches']}")
print(f"  Cache Size: {stats['total_size_bytes'] / 1024:.2f} KB")
```

## Cache Management

### View Cache Statistics

```python
from scrapegraphai.utils.cache import get_cache

cache = get_cache("sqlite", cache_path="./cache/fingerprints.db")

stats = cache.get_stats()
print(f"Total cached URLs: {stats['total_entries']}")
print(f"Total fetches: {stats['total_fetches']}")
print(f"Average fetches per URL: {stats['avg_fetches_per_url']}")
print(f"Total cache size: {stats['total_size_bytes'] / (1024*1024):.2f} MB")
```

### Clear Cache

```python
from scrapegraphai.utils.cache import get_cache

cache = get_cache("sqlite", cache_path="./cache/fingerprints.db")

# Clear entire cache
cache.clear()

# Delete specific URL
cache.delete("https://example.com")
```

### Cleanup Expired Entries

```python
cache = get_cache("sqlite", cache_path="./cache/fingerprints.db")

# Remove entries older than 7 days
max_age = 7 * 24 * 3600  # 7 days in seconds
deleted = cache.cleanup_expired(max_age)
print(f"Deleted {deleted} expired entries")
```

## Content Normalization

### Understanding Normalization

Normalization reduces false positives by removing dynamic elements that don't represent real content changes:

- **Timestamps and dates**: `2023-10-15T14:30:00Z` → `[TIMESTAMP]`
- **Session IDs**: `session_id=abc123` → `session_id=[ID]`
- **CSRF tokens**: `csrf_token=xyz789` → `csrf_token=[TOKEN]`
- **UUIDs**: `550e8400-e29b-41d4-a716-446655440000` → `[UUID]`
- **Tracking parameters**: `utm_source=google` → `utm_param=[TRACKING]`
- **Scripts and styles**: Completely removed
- **Whitespace**: Normalized to single spaces

### Normalization Strategies

#### Full (No Normalization)
```python
"normalization": "full"
```
Detects any change, including timestamps and session IDs.

#### Normalized (Recommended)
```python
"normalization": "normalized"
```
Removes common dynamic elements while preserving content structure.

#### Custom
```python
def my_normalizer(html: str) -> str:
    # Your custom logic
    return normalized_html

"normalization": "custom"
"normalize_fn": my_normalizer
```

## Performance Considerations

### Cache Hit Rate

Monitor cache effectiveness:

```python
stats = cache.get_stats()
total_fetches = stats['total_fetches']
total_entries = stats['total_entries']

# If avg_fetches_per_url is close to 1, most content is changing
# If it's much higher, cache is working well
cache_efficiency = stats['avg_fetches_per_url']
print(f"Cache efficiency: {cache_efficiency:.2f} fetches per URL")
```

### Cache Size Management

For SQLite cache, monitor disk usage:

```python
import os

cache_path = ".scrapegraph_cache/fingerprints.db"
size_mb = os.path.getsize(cache_path) / (1024 * 1024)
print(f"Cache database size: {size_mb:.2f} MB")

# Clean up if too large
if size_mb > 100:  # 100 MB threshold
    cache.cleanup_expired(max_age=7*24*3600)  # Remove old entries
```

### Memory Cache vs SQLite

**Use Memory Cache when:**
- Single process/session
- Don't need persistence
- Want fastest possible access
- Cache size is manageable

**Use SQLite when:**
- Need persistence across restarts
- Multiple processes/sessions
- Large number of URLs
- Production environments

## Troubleshooting

### Cache Not Working

1. **Verify incremental is enabled**:
   ```python
   print(fetch_node.cache is not None)  # Should be True
   ```

2. **Check cache backend**:
   ```python
   print(fetch_node.incremental_config.get("cache_backend"))
   ```

3. **Verify file permissions** (SQLite):
   ```python
   import os
   cache_path = ".scrapegraph_cache/fingerprints.db"
   print(os.access(cache_path, os.W_OK))  # Should be True
   ```

### False Positives (Too Many Refetches)

Content is being refetched even when unchanged:

1. **Use normalized mode**:
   ```python
   "normalization": "normalized"
   ```

2. **Check what's changing**:
   ```python
   # Before normalization
   from scrapegraphai.utils.content_normalizer import normalize_html

   html1 = "..."  # First fetch
   html2 = "..."  # Second fetch

   norm1 = normalize_html(html1)
   norm2 = normalize_html(html2)

   if norm1 != norm2:
       print("Normalized content differs")
       # Inspect the differences
   ```

3. **Add custom normalization**:
   ```python
   def my_normalizer(html):
       from scrapegraphai.utils.content_normalizer import normalize_html
       text = normalize_html(html, aggressive=True)
       # Add site-specific patterns
       return text
   ```

### False Negatives (Missing Changes)

Real content changes are not detected:

1. **Use full normalization mode**:
   ```python
   "normalization": "full"
   ```

2. **Reduce normalization aggressiveness**:
   ```python
   "normalization": "normalized"  # instead of aggressive custom
   ```

3. **Force refetch periodically**:
   ```python
   "max_age": 86400  # Force refetch after 24 hours
   ```

## Advanced Topics

### Distributed Caching

For multi-process scenarios, use a shared SQLite database:

```python
# Process 1
graph_config = {
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
        "cache_path": "/shared/cache/fingerprints.db",
    }
}

# Process 2 (same cache)
graph_config = {
    "incremental": {
        "enabled": True,
        "cache_backend": "sqlite",
        "cache_path": "/shared/cache/fingerprints.db",
    }
}
```

### Monitoring Cache Performance

```python
import time

start = time.time()
result = scraper.run()
elapsed = time.time() - start

if result.get("from_cache"):
    print(f"Cache hit! Completed in {elapsed:.2f}s")
else:
    print(f"Cache miss. Fetched in {elapsed:.2f}s")

# Track over time
cache_hits = 0
total_runs = 0

for _ in range(100):
    result = scraper.run()
    total_runs += 1
    if result.get("from_cache"):
        cache_hits += 1

hit_rate = cache_hits / total_runs * 100
print(f"Cache hit rate: {hit_rate:.1f}%")
```

## API Reference

### Cache Backends

All cache backends implement the `CacheBackend` interface:

```python
from scrapegraphai.utils.cache import CacheBackend

class CacheBackend(ABC):
    def get(self, url: str) -> Optional[Dict[str, Any]]: ...
    def set(self, url: str, fingerprint: str, content: Optional[str], metadata: Optional[Dict]): ...
    def update_last_checked(self, url: str): ...
    def get_content(self, url: str) -> Optional[str]: ...
    def delete(self, url: str): ...
    def clear(self): ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### Content Normalizer

```python
from scrapegraphai.utils.content_normalizer import (
    normalize_html,
    normalize_custom,
    normalize_whitespace_only,
    extract_main_content,
)

# Normalize HTML with standard rules
normalized = normalize_html(html, aggressive=False)

# Apply custom patterns
patterns = [(r'pattern', 'replacement')]
normalized = normalize_custom(html, patterns)

# Extract main content area
main_content = extract_main_content(html)
```

## Best Practices

1. **Start with normalized mode**: Begin with `"normalization": "normalized"` and adjust based on results

2. **Monitor cache statistics**: Regularly check cache hit rates to verify effectiveness

3. **Set appropriate max_age**: Balance freshness with cost savings

4. **Use SQLite for production**: Memory cache is great for testing, SQLite for production

5. **Test normalization thoroughly**: Verify that important changes are still detected

6. **Clean up old entries**: Periodically run `cleanup_expired()` to manage cache size

7. **Handle errors gracefully**: Incremental scraping automatically falls back to standard mode on errors

## Migration from Non-Incremental

Existing code works unchanged. To enable incremental scraping, just add the config:

```python
# Before (existing code)
graph_config = {
    "llm": {"model": "gpt-4"}
}

# After (with incremental scraping)
graph_config = {
    "llm": {"model": "gpt-4"},
    "incremental": {
        "enabled": True  # That's it!
    }
}
```

## FAQ

**Q: Does incremental scraping work with all graph types?**
A: Yes, it works with any graph that uses FetchNode internally.

**Q: Can I use Redis as a cache backend?**
A: Currently only SQLite and memory are supported. Redis support may be added in future versions.

**Q: What happens if the cache becomes corrupted?**
A: FetchNode gracefully falls back to standard (non-incremental) mode on cache errors.

**Q: How much storage does the cache use?**
A: Depends on `cache_content` setting. With content storage disabled, ~1KB per URL. With storage enabled and compression, ~10-50KB per URL.

**Q: Can I share cache across different graphs?**
A: Yes! Use the same `cache_path` for all graphs.

**Q: Is cache thread-safe?**
A: SQLite cache is thread-safe. Memory cache should use separate instances per thread.

## Support

For issues, questions, or feature requests, please visit:
- GitHub Issues: https://github.com/ScrapeGraphAI/Scrapegraph-ai/issues
- Documentation: https://scrapegraph-ai.readthedocs.io/

## Version

This feature is available in ScrapeGraph-AI v1.65.0 and later.
