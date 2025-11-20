"""
LLM Response Cache Manager

Provides caching layer for LLM responses to reduce costs and improve performance.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMCacheBackend(ABC):
    """Abstract base class for LLM cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response."""
        pass

    @abstractmethod
    def set(self, key: str, value: Dict[str, Any], ttl: int = 0) -> None:
        """Store response in cache."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete cached entry."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class LLMCacheManager:
    """
    Manages LLM response caching with configurable backends.

    Features:
    - Cryptographic cache key generation
    - Multiple storage backends (Redis, SQLite, Disk, Memory)
    - TTL-based expiration
    - Compression support
    - Metrics tracking
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM cache manager.

        Args:
            config: Cache configuration dictionary
        """
        self.config = config
        self.enabled = config.get("enabled", False)

        if not self.enabled:
            self.backend = None
            return

        # Initialize backend
        backend_type = config.get("backend", "sqlite")
        backend_config = config.get("backend_config", {})

        if backend_type == "redis":
            from .llm_redis_cache import RedisLLMCache
            self.backend = RedisLLMCache(backend_config)
        elif backend_type == "sqlite":
            from .llm_sqlite_cache import SQLiteLLMCache
            self.backend = SQLiteLLMCache(backend_config)
        elif backend_type == "disk":
            from .llm_disk_cache import DiskLLMCache
            self.backend = DiskLLMCache(backend_config)
        elif backend_type == "memory":
            from .llm_memory_cache import MemoryLLMCache
            self.backend = MemoryLLMCache(backend_config)
        else:
            raise ValueError(f"Unsupported cache backend: {backend_type}")

        self.ttl = config.get("ttl", 86400)
        self.normalization = config.get("normalization", {})
        self.compression = config.get("compression", "gzip")

        # Metrics
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.total_time_saved = 0.0

        logger.info(f"LLM cache initialized with {backend_type} backend")

    def generate_cache_key(
        self,
        prompt: str,
        content: str,
        model: str,
        temperature: float = 0.0,
        schema: Optional[Any] = None,
        additional_info: Optional[str] = None
    ) -> str:
        """
        Generate cache key from inputs.

        Args:
            prompt: User prompt/question
            content: Content being processed
            model: Model identifier
            temperature: LLM temperature setting
            schema: Pydantic schema if present
            additional_info: Additional information in prompt

        Returns:
            SHA-256 hash string
        """
        # Normalize inputs
        if self.normalization.get("prompt", True):
            prompt = self._normalize_text(prompt)

        if self.normalization.get("content", True):
            content = self._normalize_text(content)

        if not self.normalization.get("case_sensitive", False):
            prompt = prompt.lower()
            content = content.lower()

        # Build key components
        key_parts = []

        cache_components = self.config.get("cache_key_components", [
            "prompt", "content", "model", "temperature", "schema", "additional_info"
        ])

        if "prompt" in cache_components:
            key_parts.append(f"prompt:{prompt}")

        if "content" in cache_components:
            key_parts.append(f"content:{content}")

        if "model" in cache_components:
            key_parts.append(f"model:{model}")

        if "temperature" in cache_components and not self.config.get("ignore_temperature", False):
            key_parts.append(f"temp:{temperature}")

        if "schema" in cache_components and schema is not None:
            schema_hash = self._hash_schema(schema)
            key_parts.append(f"schema:{schema_hash}")

        if "additional_info" in cache_components and additional_info:
            key_parts.append(f"info:{additional_info}")

        # Generate hash
        key_string = "|".join(key_parts)
        cache_key = hashlib.sha256(key_string.encode('utf-8')).hexdigest()

        return cache_key

    def get_cached_response(
        self,
        prompt: str,
        content: str,
        model: str,
        **kwargs
    ) -> Optional[Any]:
        """
        Retrieve cached LLM response if available.

        Args:
            prompt: User prompt
            content: Content being processed
            model: Model identifier
            **kwargs: Additional cache key components

        Returns:
            Cached response or None if not found
        """
        if not self.enabled:
            return None

        try:
            # Generate cache key
            cache_key = self.generate_cache_key(
                prompt=prompt,
                content=content,
                model=model,
                temperature=kwargs.get("temperature", 0.0),
                schema=kwargs.get("schema"),
                additional_info=kwargs.get("additional_info")
            )

            # Check cache
            cached_entry = self.backend.get(cache_key)

            if cached_entry is None:
                self.misses += 1
                logger.debug(f"Cache MISS for key: {cache_key[:16]}...")
                return None

            # Validate TTL
            if self.ttl > 0:
                cached_time = datetime.fromisoformat(cached_entry["cached_at"])
                age = (datetime.utcnow() - cached_time).total_seconds()

                if age > self.ttl:
                    logger.debug(f"Cache entry expired (age: {age}s)")
                    self.backend.delete(cache_key)
                    self.misses += 1
                    return None

            # Cache hit
            self.hits += 1
            self.total_time_saved += cached_entry.get("generation_time", 0)

            logger.info(
                f"Cache HIT for key: {cache_key[:16]}... "
                f"(saved {cached_entry.get('generation_time', 0):.2f}s)"
            )

            # Decompress if needed
            response = cached_entry["response"]
            if cached_entry.get("compressed", False):
                response = self._decompress(response)

            return response

        except Exception as e:
            self.errors += 1
            logger.error(f"Error retrieving from cache: {e}")
            return None

    def cache_response(
        self,
        prompt: str,
        content: str,
        model: str,
        response: Any,
        generation_time: float = 0.0,
        **kwargs
    ) -> None:
        """
        Store LLM response in cache.

        Args:
            prompt: User prompt
            content: Content that was processed
            model: Model identifier
            response: LLM response to cache
            generation_time: Time taken to generate response (seconds)
            **kwargs: Additional cache key components
        """
        if not self.enabled:
            return

        try:
            # Check content size limit
            max_size = self.config.get("max_content_size", 100000)
            content_size = len(str(content))
            if content_size > max_size:
                logger.debug(f"Content too large to cache: {content_size} bytes")
                return

            # Generate cache key
            cache_key = self.generate_cache_key(
                prompt=prompt,
                content=content,
                model=model,
                temperature=kwargs.get("temperature", 0.0),
                schema=kwargs.get("schema"),
                additional_info=kwargs.get("additional_info")
            )

            # Prepare cache entry
            compressed = False
            cached_response = response

            if self.compression:
                cached_response = self._compress(response)
                compressed = True

            cache_entry = {
                "response": cached_response,
                "compressed": compressed,
                "model": model,
                "generation_time": generation_time,
                "cached_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "prompt_length": len(prompt),
                    "content_length": len(str(content)),
                    "response_size": len(str(response)),
                }
            }

            # Store in cache
            self.backend.set(cache_key, cache_entry, ttl=self.ttl)

            logger.debug(
                f"Cached response for key: {cache_key[:16]}... "
                f"(saved {generation_time:.2f}s for future requests)"
            )

        except Exception as e:
            self.errors += 1
            logger.error(f"Error caching response: {e}")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent cache keys."""
        import re
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _hash_schema(self, schema: Any) -> str:
        """Generate hash of Pydantic schema."""
        if hasattr(schema, 'model_json_schema'):
            schema_dict = schema.model_json_schema()
        else:
            schema_dict = str(schema)

        schema_string = json.dumps(schema_dict, sort_keys=True)
        return hashlib.md5(schema_string.encode('utf-8')).hexdigest()

    def _compress(self, data: Any) -> bytes:
        """Compress data for storage."""
        import gzip
        data_string = json.dumps(data) if not isinstance(data, str) else data
        return gzip.compress(data_string.encode('utf-8'))

    def _decompress(self, data: bytes) -> Any:
        """Decompress data from storage."""
        import gzip
        decompressed = gzip.decompress(data).decode('utf-8')
        try:
            return json.loads(decompressed)
        except json.JSONDecodeError:
            return decompressed

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "enabled": self.enabled,
            "backend": self.config.get("backend", "none"),
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_time_saved": f"{self.total_time_saved:.2f}s",
            "backend_stats": self.backend.get_stats() if self.backend else {}
        }

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        if self.enabled and self.backend:
            self.backend.clear()
            logger.info("LLM cache cleared")
