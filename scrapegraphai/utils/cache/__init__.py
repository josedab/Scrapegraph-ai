"""
Cache module for ScrapeGraphAI

Provides LLM response caching to reduce costs and improve performance.
"""

from .llm_cache_manager import LLMCacheManager, LLMCacheBackend

__all__ = ["LLMCacheManager", "LLMCacheBackend"]
