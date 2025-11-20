"""In-memory backend for LLM response caching."""

from typing import Optional, Dict, Any
from datetime import datetime
from collections import OrderedDict
from .llm_cache_manager import LLMCacheBackend


class MemoryLLMCache(LLMCacheBackend):
    """In-memory cache backend for LLM responses with LRU eviction."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize memory cache."""
        self.max_size_mb = config.get("max_size_mb", 100)
        self.max_size_bytes = self.max_size_mb * 1024 * 1024
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.current_size_bytes = 0
        self.access_counts: Dict[str, int] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response."""
        if key not in self.cache:
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)

        # Update access stats
        self.access_counts[key] = self.access_counts.get(key, 0) + 1

        return self.cache[key]

    def set(self, key: str, value: Dict[str, Any], ttl: int = 0) -> None:
        """Store response in cache."""
        import sys

        # Estimate size of the value
        value_size = sys.getsizeof(str(value))

        # Evict entries if needed to make room
        while self.current_size_bytes + value_size > self.max_size_bytes and self.cache:
            # Remove least recently used item
            oldest_key, oldest_value = self.cache.popitem(last=False)
            self.current_size_bytes -= sys.getsizeof(str(oldest_value))
            if oldest_key in self.access_counts:
                del self.access_counts[oldest_key]

        # If entry exists, update it
        if key in self.cache:
            old_size = sys.getsizeof(str(self.cache[key]))
            self.current_size_bytes -= old_size

        # Add new entry
        self.cache[key] = value
        self.current_size_bytes += value_size
        self.access_counts[key] = self.access_counts.get(key, 0) + 1

        # Move to end (most recently used)
        self.cache.move_to_end(key)

    def delete(self, key: str) -> None:
        """Delete cached entry."""
        if key in self.cache:
            import sys
            value_size = sys.getsizeof(str(self.cache[key]))
            self.current_size_bytes -= value_size
            del self.cache[key]
            if key in self.access_counts:
                del self.access_counts[key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()
        self.access_counts.clear()
        self.current_size_bytes = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_accesses = sum(self.access_counts.values())

        # Group by model
        model_stats: Dict[str, int] = {}
        total_generation_time = 0.0

        for entry in self.cache.values():
            model = entry.get("model", "unknown")
            model_stats[model] = model_stats.get(model, 0) + 1
            total_generation_time += entry.get("generation_time", 0)

        avg_generation_time = (
            total_generation_time / len(self.cache) if self.cache else 0
        )

        return {
            "total_entries": len(self.cache),
            "total_accesses": total_accesses,
            "avg_generation_time": f"{avg_generation_time:.2f}s",
            "total_size_bytes": self.current_size_bytes,
            "max_size_bytes": self.max_size_bytes,
            "utilization": f"{(self.current_size_bytes / self.max_size_bytes * 100):.2f}%",
            "models": model_stats
        }
