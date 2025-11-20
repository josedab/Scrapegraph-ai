"""
Base Cache Backend Interface

This module provides the abstract base class for cache backends used in
incremental scraping with content fingerprinting.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime


class CacheBackend(ABC):
    """
    Abstract base class for cache backends used in incremental scraping.

    This interface defines the contract that all cache backend implementations
    must follow. It provides methods for storing, retrieving, and managing
    content fingerprints and cached content.
    """

    @abstractmethod
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached entry for a given URL.

        Args:
            url: The URL to retrieve the cached entry for

        Returns:
            Dictionary containing cached metadata including:
                - fingerprint: Content hash
                - last_checked: Last time the URL was checked
                - last_modified: Last time content was modified
                - content_size: Size of content in bytes
                - fetch_count: Number of times fetched
                - etag: HTTP ETag header value (if available)
                - metadata: Additional metadata
            Returns None if no cached entry exists
        """
        pass

    @abstractmethod
    def set(
        self,
        url: str,
        fingerprint: str,
        content: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Store fingerprint and optional content for a URL.

        Args:
            url: The URL to cache
            fingerprint: SHA-256 hash of the normalized content
            content: Optional full content to store
            metadata: Optional additional metadata to store
        """
        pass

    @abstractmethod
    def update_last_checked(self, url: str) -> None:
        """
        Update the last_checked timestamp for a cached URL.

        This is used when content hasn't changed but we want to track
        that we checked it.

        Args:
            url: The URL to update
        """
        pass

    @abstractmethod
    def get_content(self, url: str) -> Optional[str]:
        """
        Retrieve cached content for a URL.

        Args:
            url: The URL to retrieve content for

        Returns:
            Cached content string, or None if not cached or content not stored
        """
        pass

    @abstractmethod
    def delete(self, url: str) -> None:
        """
        Remove cached entry for a URL.

        Args:
            url: The URL to remove from cache
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Clear all cached entries.

        This removes all data from the cache backend.
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing:
                - total_entries: Total number of cached URLs
                - total_fetches: Total number of fetches across all URLs
                - total_size_bytes: Total size of cached content
                - avg_fetches_per_url: Average fetches per URL
        """
        pass

    def is_expired(self, url: str, max_age: int) -> bool:
        """
        Check if a cached entry is expired based on max age.

        Args:
            url: The URL to check
            max_age: Maximum age in seconds (0 = no expiration)

        Returns:
            True if expired or not found, False otherwise
        """
        if max_age == 0:
            return False

        entry = self.get(url)
        if not entry:
            return True

        try:
            last_checked = datetime.fromisoformat(entry["last_checked"])
            age = (datetime.utcnow() - last_checked).total_seconds()
            return age > max_age
        except (KeyError, ValueError):
            return True
