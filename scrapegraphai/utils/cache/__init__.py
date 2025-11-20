"""
Cache Module for Incremental Scraping

This module provides cache backends for storing content fingerprints
and implementing incremental scraping with change detection.
"""

from .base_cache import CacheBackend
from .sqlite_cache import SQLiteCache
from .memory_cache import MemoryCache

__all__ = ["CacheBackend", "SQLiteCache", "MemoryCache"]


def get_cache(backend: str, **kwargs) -> CacheBackend:
    """
    Factory function to get a cache backend instance.

    Args:
        backend: Cache backend type ("sqlite", "memory")
        **kwargs: Backend-specific configuration

    Returns:
        CacheBackend instance

    Raises:
        ValueError: If backend type is not supported
    """
    if backend == "sqlite":
        cache_path = kwargs.get("cache_path", ".scrapegraph_cache/fingerprints.db")
        return SQLiteCache(cache_path)
    elif backend == "memory":
        return MemoryCache()
    else:
        raise ValueError(f"Unsupported cache backend: {backend}")
