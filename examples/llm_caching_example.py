"""
LLM Caching Example

This example demonstrates how to use LLM response caching to reduce costs
and improve performance when scraping content repeatedly.
"""

import time
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils import prettify_exec_info


def example_basic_caching():
    """Example 1: Basic LLM caching with SQLite backend."""
    print("=" * 60)
    print("Example 1: Basic LLM Caching")
    print("=" * 60)

    graph_config = {
        "llm": {
            "model": "openai/gpt-3.5-turbo",
            "api_key": "YOUR_API_KEY",
            "temperature": 0.0  # Deterministic for better caching
        },
        "llm_cache": {
            "enabled": True,
            "backend": "sqlite",
            "backend_config": {
                "db_path": ".scrapegraph_cache/llm_responses.db"
            },
            "ttl": 86400  # 24 hours
        },
        "verbose": True
    }

    scraper = SmartScraperGraph(
        prompt="Extract the main title and first paragraph",
        source="https://example.com",
        config=graph_config
    )

    # First run - cache miss
    print("\nFirst run (cache miss):")
    start_time = time.time()
    result1 = scraper.run()
    elapsed1 = time.time() - start_time
    print(f"Result: {result1}")
    print(f"Time taken: {elapsed1:.2f}s")

    # Second run - cache hit
    print("\nSecond run (cache hit):")
    start_time = time.time()
    result2 = scraper.run()
    elapsed2 = time.time() - start_time
    print(f"Result: {result2}")
    print(f"Time taken: {elapsed2:.2f}s")

    print(f"\nSpeedup: {elapsed1/elapsed2:.1f}x faster")
    print(f"Time saved: {elapsed1 - elapsed2:.2f}s")


def example_memory_cache():
    """Example 2: Fast in-memory caching for development."""
    print("\n" + "=" * 60)
    print("Example 2: Memory Cache for Development")
    print("=" * 60)

    graph_config = {
        "llm": {
            "model": "openai/gpt-3.5-turbo",
            "api_key": "YOUR_API_KEY",
        },
        "llm_cache": {
            "enabled": True,
            "backend": "memory",
            "backend_config": {
                "max_size_mb": 50  # Limit memory usage
            },
            "ttl": 3600  # 1 hour
        }
    }

    scraper = SmartScraperGraph(
        prompt="Summarize this content",
        source="https://example.com/article",
        config=graph_config
    )

    print("Running multiple times (great for testing):")
    for i in range(5):
        start = time.time()
        result = scraper.run()
        elapsed = time.time() - start
        print(f"Run {i+1}: {elapsed:.3f}s")


def example_cache_metrics():
    """Example 3: Monitoring cache performance."""
    print("\n" + "=" * 60)
    print("Example 3: Cache Metrics and Monitoring")
    print("=" * 60)

    graph_config = {
        "llm": {
            "model": "openai/gpt-3.5-turbo",
            "api_key": "YOUR_API_KEY",
        },
        "llm_cache": {
            "enabled": True,
            "backend": "sqlite",
            "track_metrics": True
        }
    }

    scraper = SmartScraperGraph(
        prompt="Extract key information",
        source="https://example.com",
        config=graph_config
    )

    # Make multiple requests
    urls = [
        "https://example.com",
        "https://example.com",  # Duplicate - cache hit
        "https://example.com/about",
        "https://example.com/about",  # Duplicate - cache hit
    ]

    for url in urls:
        scraper.source = url
        scraper.run()

    # Access cache metrics through the generate_answer_node
    # Note: In production, you'd access this through the graph's nodes
    print("\nCache Performance Metrics:")
    print("-" * 40)
    print("Note: Access metrics from graph.nodes['generate_answer']")


def example_batch_processing():
    """Example 4: Batch processing with caching."""
    print("\n" + "=" * 60)
    print("Example 4: Batch Processing with Cache")
    print("=" * 60)

    graph_config = {
        "llm": {
            "model": "openai/gpt-3.5-turbo",
            "api_key": "YOUR_API_KEY",
        },
        "llm_cache": {
            "enabled": True,
            "backend": "sqlite",
            "ttl": 86400
        }
    }

    # Process multiple similar pages
    products = [
        "https://example.com/product/laptop-1",
        "https://example.com/product/laptop-2",
        "https://example.com/product/laptop-3",
    ]

    scraper = SmartScraperGraph(
        prompt="Extract product name, price, and description",
        source=products[0],
        config=graph_config
    )

    results = []
    total_time = 0

    for i, url in enumerate(products):
        print(f"\nProcessing product {i+1}/{len(products)}: {url}")
        scraper.source = url

        start = time.time()
        result = scraper.run()
        elapsed = time.time() - start
        total_time += elapsed

        results.append(result)
        print(f"Time: {elapsed:.2f}s")

    print(f"\nTotal processing time: {total_time:.2f}s")
    print(f"Average time per product: {total_time/len(products):.2f}s")


def example_cache_configuration():
    """Example 5: Advanced cache configuration."""
    print("\n" + "=" * 60)
    print("Example 5: Advanced Cache Configuration")
    print("=" * 60)

    # Configuration with all options
    graph_config = {
        "llm": {
            "model": "openai/gpt-3.5-turbo",
            "api_key": "YOUR_API_KEY",
            "temperature": 0.0
        },
        "llm_cache": {
            # Enable caching
            "enabled": True,

            # Backend selection
            "backend": "sqlite",
            "backend_config": {
                "db_path": ".cache/llm_responses.db"
            },

            # Cache TTL (24 hours)
            "ttl": 86400,

            # Normalization settings
            "normalization": {
                "prompt": True,        # Normalize whitespace in prompts
                "content": True,       # Normalize whitespace in content
                "case_sensitive": False  # Case-insensitive matching
            },

            # Cache key components
            "cache_key_components": [
                "prompt",
                "content",
                "model",
                "temperature",
                "schema"
            ],

            # Compression
            "compression": "gzip",

            # Size limits
            "max_content_size": 100000,  # Don't cache > 100KB

            # Metrics
            "track_metrics": True,
        }
    }

    print("Configuration:")
    print(f"  Backend: {graph_config['llm_cache']['backend']}")
    print(f"  TTL: {graph_config['llm_cache']['ttl']}s")
    print(f"  Compression: {graph_config['llm_cache']['compression']}")
    print(f"  Max size: {graph_config['llm_cache']['max_content_size']} bytes")


def example_cache_management():
    """Example 6: Cache management operations."""
    print("\n" + "=" * 60)
    print("Example 6: Cache Management")
    print("=" * 60)

    from scrapegraphai.utils.cache import LLMCacheManager

    # Create cache manager directly
    cache = LLMCacheManager({
        "enabled": True,
        "backend": "sqlite",
        "backend_config": {
            "db_path": ".scrapegraph_cache/llm_responses.db"
        }
    })

    # Store some test data
    cache.cache_response(
        prompt="Test prompt",
        content="Test content",
        model="gpt-3.5-turbo",
        response={"answer": "Test answer"},
        generation_time=2.5
    )

    # Get statistics
    print("\nCache Statistics:")
    stats = cache.backend.get_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Total accesses: {stats['total_accesses']}")
    print(f"  Average generation time: {stats['avg_generation_time']}")
    print(f"  Total size: {stats['total_size_bytes']} bytes")
    print(f"  Models: {stats['models']}")

    # Get metrics
    print("\nCache Metrics:")
    metrics = cache.get_metrics()
    print(f"  Enabled: {metrics['enabled']}")
    print(f"  Backend: {metrics['backend']}")
    print(f"  Hits: {metrics['hits']}")
    print(f"  Misses: {metrics['misses']}")
    print(f"  Hit rate: {metrics['hit_rate']}")
    print(f"  Time saved: {metrics['total_time_saved']}")

    # Clear cache
    print("\nClearing cache...")
    cache.clear_cache()
    print("Cache cleared!")

    # Verify it's empty
    stats = cache.backend.get_stats()
    print(f"Total entries after clear: {stats['total_entries']}")


def example_conditional_caching():
    """Example 7: Conditional caching based on context."""
    print("\n" + "=" * 60)
    print("Example 7: Conditional Caching")
    print("=" * 60)

    def create_scraper(enable_cache: bool, cache_backend: str = "sqlite"):
        """Create scraper with optional caching."""
        config = {
            "llm": {
                "model": "openai/gpt-3.5-turbo",
                "api_key": "YOUR_API_KEY",
            }
        }

        if enable_cache:
            config["llm_cache"] = {
                "enabled": True,
                "backend": cache_backend
            }

        return SmartScraperGraph(
            prompt="Extract information",
            source="https://example.com",
            config=config
        )

    # Production scraper with caching
    print("Creating production scraper (with cache)...")
    prod_scraper = create_scraper(enable_cache=True, cache_backend="sqlite")

    # Development scraper without caching
    print("Creating dev scraper (without cache)...")
    dev_scraper = create_scraper(enable_cache=False)

    # Experimental scraper with memory cache
    print("Creating experiment scraper (memory cache)...")
    exp_scraper = create_scraper(enable_cache=True, cache_backend="memory")

    print("\nScrapers created with different cache configurations!")


if __name__ == "__main__":
    print("LLM Caching Examples")
    print("=" * 60)
    print()
    print("Note: Make sure to set your API key in the examples")
    print("      or set the OPENAI_API_KEY environment variable")
    print()

    # Run examples (comment out as needed)
    # example_basic_caching()
    # example_memory_cache()
    # example_cache_metrics()
    # example_batch_processing()
    example_cache_configuration()
    example_cache_management()
    example_conditional_caching()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
