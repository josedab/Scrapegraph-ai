"""
Memory Cache Backend Implementation

This module provides an in-memory cache backend for storing content
fingerprints and cached content for incremental scraping.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from .base_cache import CacheBackend


class MemoryCache(CacheBackend):
    """
    In-memory cache backend for content fingerprints.

    This implementation stores cache data in memory using dictionaries,
    providing fast access but no persistence. Data is lost when the
    process terminates.

    This is useful for:
    - Testing and development
    - Short-lived scraping sessions
    - When persistence is not required
    """

    def __init__(self):
        """Initialize memory cache backend."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._content_cache: Dict[str, str] = {}

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached entry for URL.

        Args:
            url: The URL to retrieve the cached entry for

        Returns:
            Dictionary with cache metadata, or None if not found
        """
        return self._cache.get(url)

    def set(
        self,
        url: str,
        fingerprint: str,
        content: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Store fingerprint and optional content for URL.

        Args:
            url: The URL to cache
            fingerprint: SHA-256 hash of the normalized content
            content: Optional full content to store
            metadata: Optional additional metadata to store
        """
        now = datetime.utcnow().isoformat()

        # Get existing entry or create new one
        if url in self._cache:
            entry = self._cache[url]
            entry["fingerprint"] = fingerprint
            entry["last_checked"] = now
            entry["last_modified"] = now
            entry["fetch_count"] = entry.get("fetch_count", 0) + 1
            entry["metadata"] = metadata or {}
            if content:
                entry["content_size"] = len(content)
        else:
            entry = {
                "fingerprint": fingerprint,
                "last_checked": now,
                "last_modified": now,
                "content_size": len(content) if content else 0,
                "fetch_count": 1,
                "etag": metadata.get("etag") if metadata else None,
                "metadata": metadata or {},
            }

        self._cache[url] = entry

        # Store content separately
        if content:
            self._content_cache[url] = content

    def get_content(self, url: str) -> Optional[str]:
        """
        Retrieve cached content for URL.

        Args:
            url: The URL to retrieve content for

        Returns:
            Content string, or None if not cached
        """
        return self._content_cache.get(url)

    def update_last_checked(self, url: str) -> None:
        """
        Update the last_checked timestamp.

        Args:
            url: The URL to update
        """
        if url in self._cache:
            self._cache[url]["last_checked"] = datetime.utcnow().isoformat()

    def delete(self, url: str) -> None:
        """
        Remove cached entry.

        Args:
            url: The URL to remove from cache
        """
        self._cache.pop(url, None)
        self._content_cache.pop(url, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._content_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        if not self._cache:
            return {
                "total_entries": 0,
                "total_fetches": 0,
                "total_size_bytes": 0,
                "avg_fetches_per_url": 0,
            }

        total_fetches = sum(entry.get("fetch_count", 0) for entry in self._cache.values())
        total_size = sum(entry.get("content_size", 0) for entry in self._cache.values())
        total_entries = len(self._cache)

        return {
            "total_entries": total_entries,
            "total_fetches": total_fetches,
            "total_size_bytes": total_size,
            "avg_fetches_per_url": round(total_fetches / total_entries, 2) if total_entries > 0 else 0,
        }

    def cleanup_expired(self, max_age: int) -> int:
        """
        Remove expired cache entries.

        Args:
            max_age: Maximum age in seconds

        Returns:
            Number of entries removed
        """
        if max_age == 0:
            return 0

        now = datetime.utcnow()
        to_delete = []

        for url, entry in self._cache.items():
            try:
                last_checked = datetime.fromisoformat(entry["last_checked"])
                age = (now - last_checked).total_seconds()
                if age > max_age:
                    to_delete.append(url)
            except (KeyError, ValueError):
                to_delete.append(url)

        for url in to_delete:
            self.delete(url)

        return len(to_delete)
