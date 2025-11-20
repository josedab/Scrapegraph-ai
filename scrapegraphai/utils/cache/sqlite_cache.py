"""
SQLite Cache Backend Implementation

This module provides a SQLite-based cache backend for storing content
fingerprints and cached content for incremental scraping.
"""

import sqlite3
import json
import gzip
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from .base_cache import CacheBackend


class SQLiteCache(CacheBackend):
    """
    SQLite-based cache backend for content fingerprints.

    This implementation stores cache data in a SQLite database file,
    providing persistent storage with efficient querying and compression.

    Attributes:
        db_path: Path to the SQLite database file
    """

    def __init__(self, db_path: str):
        """
        Initialize SQLite cache backend.

        Args:
            db_path: Path to SQLite database file (will be created if doesn't exist)
        """
        self.db_path = db_path

        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_fingerprints (
                url TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                last_checked TIMESTAMP NOT NULL,
                last_modified TIMESTAMP NOT NULL,
                content BLOB,
                content_size INTEGER,
                fetch_count INTEGER DEFAULT 1,
                etag TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_checked
            ON content_fingerprints(last_checked)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fingerprint
            ON content_fingerprints(fingerprint)
        """)

        conn.commit()
        conn.close()

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached entry for URL.

        Args:
            url: The URL to retrieve the cached entry for

        Returns:
            Dictionary with cache metadata, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fingerprint, last_checked, last_modified,
                   content_size, fetch_count, etag, metadata
            FROM content_fingerprints
            WHERE url = ?
        """, (url,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "fingerprint": row[0],
            "last_checked": row[1],
            "last_modified": row[2],
            "content_size": row[3],
            "fetch_count": row[4],
            "etag": row[5],
            "metadata": json.loads(row[6]) if row[6] else {}
        }

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
            content: Optional full content to store (will be compressed)
            metadata: Optional additional metadata to store
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        # Compress content if provided
        compressed_content = None
        content_size = 0
        if content:
            compressed_content = gzip.compress(content.encode('utf-8'))
            content_size = len(content)

        # Extract ETag from metadata if available
        etag = None
        if metadata:
            etag = metadata.get("etag")

        cursor.execute("""
            INSERT INTO content_fingerprints
            (url, fingerprint, last_checked, last_modified, content,
             content_size, etag, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                last_checked = excluded.last_checked,
                last_modified = excluded.last_modified,
                content = excluded.content,
                content_size = excluded.content_size,
                fetch_count = fetch_count + 1,
                etag = excluded.etag,
                metadata = excluded.metadata
        """, (
            url,
            fingerprint,
            now,
            now,
            compressed_content,
            content_size,
            etag,
            json.dumps(metadata) if metadata else None
        ))

        conn.commit()
        conn.close()

    def get_content(self, url: str) -> Optional[str]:
        """
        Retrieve cached content for URL.

        Args:
            url: The URL to retrieve content for

        Returns:
            Decompressed content string, or None if not cached
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT content FROM content_fingerprints WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return None

        # Decompress content
        try:
            return gzip.decompress(row[0]).decode('utf-8')
        except Exception:
            return None

    def update_last_checked(self, url: str) -> None:
        """
        Update the last_checked timestamp.

        Args:
            url: The URL to update
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE content_fingerprints
            SET last_checked = ?
            WHERE url = ?
        """, (datetime.utcnow().isoformat(), url))

        conn.commit()
        conn.close()

    def delete(self, url: str) -> None:
        """
        Remove cached entry.

        Args:
            url: The URL to remove from cache
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM content_fingerprints WHERE url = ?", (url,))
        conn.commit()
        conn.close()

    def clear(self) -> None:
        """Clear all cached entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM content_fingerprints")
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_entries,
                SUM(fetch_count) as total_fetches,
                SUM(content_size) as total_size,
                AVG(fetch_count) as avg_fetches_per_url
            FROM content_fingerprints
        """)

        row = cursor.fetchone()
        conn.close()

        return {
            "total_entries": row[0] or 0,
            "total_fetches": row[1] or 0,
            "total_size_bytes": row[2] or 0,
            "avg_fetches_per_url": round(row[3], 2) if row[3] else 0
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

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.utcnow().timestamp() - max_age
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        cursor.execute("""
            DELETE FROM content_fingerprints
            WHERE last_checked < ?
        """, (cutoff_iso,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted
