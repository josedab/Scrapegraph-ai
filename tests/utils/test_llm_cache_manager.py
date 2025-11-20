"""
Unit tests for LLM Cache Manager
"""

import pytest
import time
import tempfile
import os
from scrapegraphai.utils.cache.llm_cache_manager import LLMCacheManager


class TestLLMCacheManager:
    """Test suite for LLM Cache Manager."""

    def test_cache_disabled_by_default(self):
        """Test that cache is disabled by default."""
        cache = LLMCacheManager({})
        assert cache.enabled is False
        assert cache.backend is None

    def test_cache_key_generation(self):
        """Test that cache keys are generated consistently."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        key1 = cache.generate_cache_key(
            prompt="What is this?",
            content="Test content",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="What is this?",
            content="Test content",
            model="gpt-4"
        )

        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex digest

    def test_cache_key_normalization(self):
        """Test that whitespace normalization works."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "normalization": {"prompt": True, "content": True}
        })

        key1 = cache.generate_cache_key(
            prompt="What  is   this?",
            content="Test   content",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="What is this?",
            content="Test content",
            model="gpt-4"
        )

        assert key1 == key2

    def test_cache_key_case_insensitive(self):
        """Test case insensitive cache key generation."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "normalization": {"case_sensitive": False}
        })

        key1 = cache.generate_cache_key(
            prompt="What is this?",
            content="Test Content",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="WHAT IS THIS?",
            content="TEST CONTENT",
            model="gpt-4"
        )

        assert key1 == key2

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        result = cache.get_cached_response(
            prompt="Test",
            content="Content",
            model="gpt-4"
        )

        assert result is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_cache_hit(self):
        """Test cache hit returns stored response."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        # Store response
        cache.cache_response(
            prompt="Test",
            content="Content",
            model="gpt-4",
            response={"answer": "42"},
            generation_time=2.5
        )

        # Retrieve response
        result = cache.get_cached_response(
            prompt="Test",
            content="Content",
            model="gpt-4"
        )

        assert result is not None
        assert result == {"answer": "42"}
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_disabled_bypassed(self):
        """Test that caching is bypassed when disabled."""
        cache = LLMCacheManager({"enabled": False})

        cache.cache_response(
            prompt="Test",
            content="Content",
            model="gpt-4",
            response={"answer": "42"}
        )

        result = cache.get_cached_response(
            prompt="Test",
            content="Content",
            model="gpt-4"
        )

        assert result is None

    def test_ttl_expiration(self):
        """Test that expired entries are not returned."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "ttl": 1  # 1 second TTL
        })

        cache.cache_response(
            prompt="Test",
            content="Content",
            model="gpt-4",
            response={"answer": "42"}
        )

        # Wait for expiration
        time.sleep(2)

        result = cache.get_cached_response(
            prompt="Test",
            content="Content",
            model="gpt-4"
        )

        assert result is None
        assert cache.misses == 1

    def test_different_models_different_keys(self):
        """Test that different models generate different cache keys."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        key1 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="claude-3"
        )

        assert key1 != key2

    def test_different_prompts_different_keys(self):
        """Test that different prompts generate different cache keys."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        key1 = cache.generate_cache_key(
            prompt="Test prompt 1",
            content="Content",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="Test prompt 2",
            content="Content",
            model="gpt-4"
        )

        assert key1 != key2

    def test_different_content_different_keys(self):
        """Test that different content generates different cache keys."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        key1 = cache.generate_cache_key(
            prompt="Test",
            content="Content 1",
            model="gpt-4"
        )

        key2 = cache.generate_cache_key(
            prompt="Test",
            content="Content 2",
            model="gpt-4"
        )

        assert key1 != key2

    def test_metrics_tracking(self):
        """Test that metrics are tracked correctly."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        # Cache miss
        cache.get_cached_response("test", "content", "gpt-4")

        # Cache response
        cache.cache_response("test", "content", "gpt-4", {"answer": "42"}, 2.5)

        # Cache hit
        cache.get_cached_response("test", "content", "gpt-4")

        metrics = cache.get_metrics()

        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["total_time_saved"] == "2.50s"
        assert metrics["enabled"] is True

    def test_temperature_in_cache_key(self):
        """Test that temperature affects cache key."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "cache_key_components": ["prompt", "content", "model", "temperature"]
        })

        key1 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="gpt-4",
            temperature=0.0
        )

        key2 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="gpt-4",
            temperature=0.7
        )

        assert key1 != key2

    def test_ignore_temperature(self):
        """Test ignoring temperature in cache key."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "ignore_temperature": True
        })

        key1 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="gpt-4",
            temperature=0.0
        )

        key2 = cache.generate_cache_key(
            prompt="Test",
            content="Content",
            model="gpt-4",
            temperature=0.7
        )

        assert key1 == key2

    def test_clear_cache(self):
        """Test clearing cache."""
        cache = LLMCacheManager({"enabled": True, "backend": "memory"})

        # Store multiple responses
        cache.cache_response("test1", "content1", "gpt-4", {"answer": "1"})
        cache.cache_response("test2", "content2", "gpt-4", {"answer": "2"})

        # Verify they're cached
        assert cache.get_cached_response("test1", "content1", "gpt-4") is not None
        assert cache.get_cached_response("test2", "content2", "gpt-4") is not None

        # Clear cache
        cache.clear_cache()

        # Verify cache is empty
        assert cache.get_cached_response("test1", "content1", "gpt-4") is None
        assert cache.get_cached_response("test2", "content2", "gpt-4") is None

    def test_max_content_size(self):
        """Test that large content is not cached."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "max_content_size": 100
        })

        large_content = "x" * 200  # Larger than max

        cache.cache_response(
            prompt="Test",
            content=large_content,
            model="gpt-4",
            response={"answer": "42"}
        )

        # Should not be cached
        result = cache.get_cached_response(
            prompt="Test",
            content=large_content,
            model="gpt-4"
        )

        assert result is None


class TestSQLiteLLMCache:
    """Test suite for SQLite cache backend."""

    def test_sqlite_cache_basic_operations(self):
        """Test basic SQLite cache operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_cache.db")

            cache = LLMCacheManager({
                "enabled": True,
                "backend": "sqlite",
                "backend_config": {"db_path": db_path}
            })

            # Store response
            cache.cache_response(
                prompt="Test",
                content="Content",
                model="gpt-4",
                response={"answer": "42"},
                generation_time=2.5
            )

            # Retrieve response
            result = cache.get_cached_response(
                prompt="Test",
                content="Content",
                model="gpt-4"
            )

            assert result is not None
            assert result == {"answer": "42"}

            # Check stats
            stats = cache.backend.get_stats()
            assert stats["total_entries"] == 1
            assert stats["total_accesses"] == 1

    def test_sqlite_persistence(self):
        """Test that SQLite cache persists across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_cache.db")

            # Create first cache and store data
            cache1 = LLMCacheManager({
                "enabled": True,
                "backend": "sqlite",
                "backend_config": {"db_path": db_path}
            })

            cache1.cache_response(
                prompt="Test",
                content="Content",
                model="gpt-4",
                response={"answer": "42"}
            )

            # Create second cache instance
            cache2 = LLMCacheManager({
                "enabled": True,
                "backend": "sqlite",
                "backend_config": {"db_path": db_path}
            })

            # Should retrieve from persistent storage
            result = cache2.get_cached_response(
                prompt="Test",
                content="Content",
                model="gpt-4"
            )

            assert result is not None
            assert result == {"answer": "42"}


class TestMemoryLLMCache:
    """Test suite for Memory cache backend."""

    def test_memory_cache_lru_eviction(self):
        """Test LRU eviction in memory cache."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory",
            "backend_config": {"max_size_mb": 0.001}  # Very small size
        })

        # Store multiple responses
        for i in range(10):
            cache.cache_response(
                prompt=f"Test {i}",
                content=f"Content {i}",
                model="gpt-4",
                response={"answer": str(i)}
            )

        # Due to small size, early entries should be evicted
        stats = cache.backend.get_stats()
        assert stats["total_entries"] < 10

    def test_memory_cache_stats(self):
        """Test memory cache statistics."""
        cache = LLMCacheManager({
            "enabled": True,
            "backend": "memory"
        })

        cache.cache_response(
            prompt="Test",
            content="Content",
            model="gpt-4",
            response={"answer": "42"},
            generation_time=2.5
        )

        stats = cache.backend.get_stats()

        assert stats["total_entries"] == 1
        assert "utilization" in stats
        assert "models" in stats
        assert "gpt-4" in stats["models"]
