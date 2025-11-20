"""SQLite backend for LLM response caching."""

import sqlite3
import json
import pickle
import os
from typing import Optional, Dict, Any
from datetime import datetime
from .llm_cache_manager import LLMCacheBackend


class SQLiteLLMCache(LLMCacheBackend):
    """SQLite-based cache backend for LLM responses."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize SQLite cache."""
        self.db_path = config.get("db_path", ".scrapegraph_cache/llm_responses.db")

        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_responses (
                cache_key TEXT PRIMARY KEY,
                response BLOB NOT NULL,
                model TEXT NOT NULL,
                generation_time REAL,
                cached_at TIMESTAMP NOT NULL,
                accessed_at TIMESTAMP NOT NULL,
                access_count INTEGER DEFAULT 1,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_model
            ON llm_responses(model)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cached_at
            ON llm_responses(cached_at)
        """)

        conn.commit()
        conn.close()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT response, model, generation_time, cached_at, metadata
            FROM llm_responses
            WHERE cache_key = ?
        """, (key,))

        row = cursor.fetchone()

        if row:
            # Update access stats
            cursor.execute("""
                UPDATE llm_responses
                SET accessed_at = ?, access_count = access_count + 1
                WHERE cache_key = ?
            """, (datetime.utcnow().isoformat(), key))
            conn.commit()

        conn.close()

        if not row:
            return None

        # Deserialize response
        response_data = pickle.loads(row[0])

        return {
            "response": response_data,
            "compressed": False,  # Already decompressed
            "model": row[1],
            "generation_time": row[2],
            "cached_at": row[3],
            "metadata": json.loads(row[4]) if row[4] else {}
        }

    def set(self, key: str, value: Dict[str, Any], ttl: int = 0) -> None:
        """Store response in cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Serialize response
        response_blob = pickle.dumps(value["response"])

        cursor.execute("""
            INSERT INTO llm_responses
            (cache_key, response, model, generation_time, cached_at, accessed_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response = excluded.response,
                model = excluded.model,
                generation_time = excluded.generation_time,
                cached_at = excluded.cached_at,
                accessed_at = excluded.accessed_at,
                access_count = access_count + 1,
                metadata = excluded.metadata
        """, (
            key,
            response_blob,
            value["model"],
            value["generation_time"],
            value["cached_at"],
            datetime.utcnow().isoformat(),
            json.dumps(value.get("metadata", {}))
        ))

        conn.commit()
        conn.close()

    def delete(self, key: str) -> None:
        """Delete cached entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM llm_responses WHERE cache_key = ?", (key,))
        conn.commit()
        conn.close()

    def clear(self) -> None:
        """Clear all cached entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM llm_responses")
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_entries,
                SUM(access_count) as total_accesses,
                AVG(generation_time) as avg_generation_time,
                SUM(LENGTH(response)) as total_size_bytes
            FROM llm_responses
        """)

        row = cursor.fetchone()

        # Get per-model stats
        cursor.execute("""
            SELECT model, COUNT(*) as count
            FROM llm_responses
            GROUP BY model
        """)

        model_stats = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "total_entries": row[0] or 0,
            "total_accesses": row[1] or 0,
            "avg_generation_time": f"{row[2]:.2f}s" if row[2] else "0.00s",
            "total_size_bytes": row[3] or 0,
            "models": model_stats
        }
