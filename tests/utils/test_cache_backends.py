"""
Unit tests for cache backends used in incremental scraping.
"""

import pytest
import tempfile
import os
from datetime import datetime

from scrapegraphai.utils.cache.memory_cache import MemoryCache
from scrapegraphai.utils.cache.sqlite_cache import SQLiteCache


class TestMemoryCache:
    """Test suite for MemoryCache backend."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MemoryCache()

    def test_set_and_get(self):
        """Test storing and retrieving cache entries."""
        url = "https://example.com"
        fingerprint = "abc123def456"
        content = "<html>test content</html>"
        metadata = {"size": 100}

        self.cache.set(url, fingerprint, content, metadata)

        entry = self.cache.get(url)
        assert entry is not None
        assert entry["fingerprint"] == fingerprint
        assert entry["content_size"] == len(content)
        assert entry["fetch_count"] == 1

        # Test content retrieval
        cached_content = self.cache.get_content(url)
        assert cached_content == content

    def test_get_nonexistent(self):
        """Test retrieving non-existent entry returns None."""
        entry = self.cache.get("https://nonexistent.com")
        assert entry is None

    def test_update_increments_fetch_count(self):
        """Test that updating an entry increments fetch count."""
        url = "https://example.com"

        self.cache.set(url, "hash1", "content1")
        entry = self.cache.get(url)
        assert entry["fetch_count"] == 1

        self.cache.set(url, "hash2", "content2")
        entry = self.cache.get(url)
        assert entry["fetch_count"] == 2

    def test_update_last_checked(self):
        """Test updating last_checked timestamp."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        entry1 = self.cache.get(url)
        original_time = entry1["last_checked"]

        # Update last checked
        self.cache.update_last_checked(url)

        entry2 = self.cache.get(url)
        updated_time = entry2["last_checked"]

        # Time should have changed
        assert updated_time >= original_time

    def test_delete(self):
        """Test deleting a cache entry."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        assert self.cache.get(url) is not None

        self.cache.delete(url)

        assert self.cache.get(url) is None
        assert self.cache.get_content(url) is None

    def test_clear(self):
        """Test clearing all cache entries."""
        self.cache.set("https://example1.com", "hash1", "content1")
        self.cache.set("https://example2.com", "hash2", "content2")

        stats = self.cache.get_stats()
        assert stats["total_entries"] == 2

        self.cache.clear()

        stats = self.cache.get_stats()
        assert stats["total_entries"] == 0

    def test_get_stats(self):
        """Test cache statistics."""
        self.cache.set("https://example1.com", "hash1", "content1", {"size": 100})
        self.cache.set("https://example2.com", "hash2", "content2", {"size": 200})
        self.cache.set("https://example1.com", "hash1b", "content1b", {"size": 150})

        stats = self.cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["total_fetches"] == 3  # 1 + 1 + update
        assert stats["total_size_bytes"] > 0

    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        # Entry should not be expired with max_age=0
        deleted = self.cache.cleanup_expired(max_age=0)
        assert deleted == 0
        assert self.cache.get(url) is not None

        # Entry should not be expired with very long max_age
        deleted = self.cache.cleanup_expired(max_age=86400)
        assert deleted == 0
        assert self.cache.get(url) is not None


class TestSQLiteCache:
    """Test suite for SQLiteCache backend."""

    def setup_method(self):
        """Set up test fixtures with temporary database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_file.close()
        self.cache = SQLiteCache(self.temp_file.name)

    def teardown_method(self):
        """Clean up temporary files."""
        try:
            os.unlink(self.temp_file.name)
        except Exception:
            pass

    def test_set_and_get(self):
        """Test storing and retrieving cache entries."""
        url = "https://example.com"
        fingerprint = "abc123def456"
        content = "<html>test content</html>"
        metadata = {"size": 100, "etag": "etag123"}

        self.cache.set(url, fingerprint, content, metadata)

        entry = self.cache.get(url)
        assert entry is not None
        assert entry["fingerprint"] == fingerprint
        assert entry["content_size"] == len(content)
        assert entry["fetch_count"] == 1
        assert entry["etag"] == "etag123"

        # Test content retrieval
        cached_content = self.cache.get_content(url)
        assert cached_content == content

    def test_get_nonexistent(self):
        """Test retrieving non-existent entry returns None."""
        entry = self.cache.get("https://nonexistent.com")
        assert entry is None

    def test_compression(self):
        """Test that content is compressed in storage."""
        url = "https://example.com"
        large_content = "<html>" + ("x" * 10000) + "</html>"

        self.cache.set(url, "hash1", large_content)

        # Get file size
        file_size = os.path.getsize(self.temp_file.name)

        # Compressed size should be much smaller than original content
        assert file_size < len(large_content)

        # But we should still get the full content back
        cached_content = self.cache.get_content(url)
        assert cached_content == large_content

    def test_update_increments_fetch_count(self):
        """Test that updating an entry increments fetch count."""
        url = "https://example.com"

        self.cache.set(url, "hash1", "content1")
        entry = self.cache.get(url)
        assert entry["fetch_count"] == 1

        self.cache.set(url, "hash2", "content2")
        entry = self.cache.get(url)
        assert entry["fetch_count"] == 2

    def test_update_last_checked(self):
        """Test updating last_checked timestamp."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        entry1 = self.cache.get(url)
        original_time = entry1["last_checked"]

        # Update last checked
        self.cache.update_last_checked(url)

        entry2 = self.cache.get(url)
        updated_time = entry2["last_checked"]

        # Time should have changed
        assert updated_time >= original_time

    def test_delete(self):
        """Test deleting a cache entry."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        assert self.cache.get(url) is not None

        self.cache.delete(url)

        assert self.cache.get(url) is None
        assert self.cache.get_content(url) is None

    def test_clear(self):
        """Test clearing all cache entries."""
        self.cache.set("https://example1.com", "hash1", "content1")
        self.cache.set("https://example2.com", "hash2", "content2")

        stats = self.cache.get_stats()
        assert stats["total_entries"] == 2

        self.cache.clear()

        stats = self.cache.get_stats()
        assert stats["total_entries"] == 0

    def test_get_stats(self):
        """Test cache statistics."""
        self.cache.set("https://example1.com", "hash1", "content1")
        self.cache.set("https://example2.com", "hash2", "content2")
        self.cache.set("https://example1.com", "hash1b", "content1b")

        stats = self.cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["total_fetches"] == 3  # 1 + 1 + update
        assert stats["total_size_bytes"] > 0

    def test_persistence(self):
        """Test that data persists across cache instances."""
        url = "https://example.com"
        fingerprint = "hash123"
        content = "test content"

        # Create first cache instance and store data
        cache1 = SQLiteCache(self.temp_file.name)
        cache1.set(url, fingerprint, content)

        # Create second cache instance and verify data
        cache2 = SQLiteCache(self.temp_file.name)
        entry = cache2.get(url)

        assert entry is not None
        assert entry["fingerprint"] == fingerprint
        assert cache2.get_content(url) == content

    def test_database_initialization(self):
        """Test that database is properly initialized."""
        # Create cache with new file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        try:
            cache = SQLiteCache(temp_file.name)

            # Verify file was created
            assert os.path.exists(temp_file.name)

            # Verify we can use it
            cache.set("https://test.com", "hash", "content")
            entry = cache.get("https://test.com")
            assert entry is not None
        finally:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

    def test_no_content_storage(self):
        """Test storing fingerprint without content."""
        url = "https://example.com"
        fingerprint = "hash123"

        self.cache.set(url, fingerprint, content=None)

        entry = self.cache.get(url)
        assert entry is not None
        assert entry["fingerprint"] == fingerprint

        cached_content = self.cache.get_content(url)
        assert cached_content is None

    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        url = "https://example.com"
        self.cache.set(url, "hash1", "content1")

        # Entry should not be expired with max_age=0
        deleted = self.cache.cleanup_expired(max_age=0)
        assert deleted == 0
        assert self.cache.get(url) is not None

        # Entry should not be expired with very long max_age
        deleted = self.cache.cleanup_expired(max_age=86400)
        assert deleted == 0
        assert self.cache.get(url) is not None


def test_cache_backend_interface():
    """Test that both implementations follow the same interface."""
    memory_cache = MemoryCache()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        temp_path = f.name

    try:
        sqlite_cache = SQLiteCache(temp_path)

        # Test both caches have same methods
        for method in ["get", "set", "update_last_checked", "get_content",
                       "delete", "clear", "get_stats"]:
            assert hasattr(memory_cache, method)
            assert hasattr(sqlite_cache, method)
            assert callable(getattr(memory_cache, method))
            assert callable(getattr(sqlite_cache, method))
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
