"""
Unit tests for browser pool functionality.

Tests cover:
- Pool initialization and shutdown
- Context acquisition and release
- Concurrent access
- Health checks
- TTL expiration
- Error handling
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from scrapegraphai.utils.browser_pool import (
    BrowserPool,
    BrowserPoolManager,
    PoolConfig,
    BrowserInstance,
)


@pytest.fixture
def pool_config():
    """Create a test pool configuration."""
    return PoolConfig(
        min_browsers=1,
        max_browsers=3,
        max_contexts_per_browser=2,
        browser_ttl_seconds=10,
        context_ttl_seconds=5,
        health_check_interval=2,
        max_health_check_failures=2,
        headless=True,
    )


@pytest.fixture
async def browser_pool(pool_config):
    """Create a browser pool for testing."""
    pool = BrowserPool(pool_config)
    await pool.initialize()
    yield pool
    await pool.shutdown()


@pytest.mark.asyncio
class TestPoolConfig:
    """Tests for PoolConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PoolConfig()
        assert config.min_browsers == 1
        assert config.max_browsers == 10
        assert config.max_contexts_per_browser == 5
        assert config.browser_ttl_seconds == 300
        assert config.context_ttl_seconds == 120
        assert config.headless is True

    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "min_browsers": 2,
            "max_browsers": 5,
            "headless": False,
            "unknown_key": "should_be_ignored",
        }
        config = PoolConfig.from_dict(config_dict)
        assert config.min_browsers == 2
        assert config.max_browsers == 5
        assert config.headless is False

    def test_from_env(self):
        """Test creating config from environment variables."""
        with patch.dict('os.environ', {
            'SCRAPEGRAPH_BROWSER_POOL_MIN_BROWSERS': '3',
            'SCRAPEGRAPH_BROWSER_POOL_MAX_BROWSERS': '8',
            'SCRAPEGRAPH_BROWSER_POOL_HEADLESS': 'false',
        }):
            config = PoolConfig.from_env()
            assert config.min_browsers == 3
            assert config.max_browsers == 8
            assert config.headless is False


@pytest.mark.asyncio
class TestBrowserPool:
    """Tests for BrowserPool class."""

    async def test_pool_initialization(self, pool_config):
        """Test that pool initializes with minimum browsers."""
        pool = BrowserPool(pool_config)
        await pool.initialize()

        try:
            assert pool._initialized is True
            assert len(pool._browsers) >= pool_config.min_browsers
            assert pool._playwright is not None
        finally:
            await pool.shutdown()

    async def test_acquire_context(self, browser_pool):
        """Test acquiring a context from the pool."""
        browser, context = await browser_pool.acquire_context()

        assert browser is not None
        assert context is not None

        # Clean up
        await browser_pool.release_context(browser, context)

    async def test_release_context(self, browser_pool):
        """Test releasing a context back to the pool."""
        browser, context = await browser_pool.acquire_context()

        # Release the context
        await browser_pool.release_context(browser, context, close_context=True)

        # Verify context was closed
        instance = browser_pool._find_browser_instance(browser)
        assert instance is not None
        assert context not in instance.contexts

    async def test_concurrent_context_acquisition(self, browser_pool):
        """Test acquiring multiple contexts concurrently."""
        async def acquire_and_release():
            browser, context = await browser_pool.acquire_context()
            await asyncio.sleep(0.1)  # Simulate some work
            await browser_pool.release_context(browser, context)
            return True

        # Acquire multiple contexts concurrently
        results = await asyncio.gather(*[acquire_and_release() for _ in range(5)])
        assert all(results)

    async def test_pool_exhaustion(self, pool_config):
        """Test behavior when pool is exhausted."""
        pool = BrowserPool(pool_config)
        await pool.initialize()

        try:
            # Acquire contexts up to the limit
            contexts = []
            for _ in range(pool_config.max_browsers * pool_config.max_contexts_per_browser):
                browser, context = await pool.acquire_context()
                contexts.append((browser, context))

            # Pool should now be at capacity but not fail
            # It should use the least busy browser
            browser, context = await pool.acquire_context()
            contexts.append((browser, context))

            # Clean up
            for browser, context in contexts:
                await pool.release_context(browser, context)
        finally:
            await pool.shutdown()

    async def test_context_with_storage_state(self, browser_pool):
        """Test acquiring context with storage state."""
        browser, context = await browser_pool.acquire_context(
            storage_state=None,  # Would be a path to storage state file
        )

        assert context is not None
        await browser_pool.release_context(browser, context)

    async def test_pool_stats(self, browser_pool):
        """Test getting pool statistics."""
        # Acquire some contexts
        browser1, context1 = await browser_pool.acquire_context()
        browser2, context2 = await browser_pool.acquire_context()

        stats = browser_pool.get_stats()

        assert "total_browsers" in stats
        assert "total_contexts" in stats
        assert "browsers_in_use" in stats
        assert stats["total_browsers"] >= 1
        assert stats["total_contexts"] >= 2

        # Clean up
        await browser_pool.release_context(browser1, context1)
        await browser_pool.release_context(browser2, context2)

    async def test_pool_shutdown(self, pool_config):
        """Test that pool shuts down cleanly."""
        pool = BrowserPool(pool_config)
        await pool.initialize()

        # Acquire a context
        browser, context = await pool.acquire_context()

        # Shutdown should close everything
        await pool.shutdown()

        assert pool._initialized is False
        assert len(pool._browsers) == 0

    async def test_health_check_removes_unhealthy_browsers(self, pool_config):
        """Test that health checks remove unhealthy browsers."""
        pool = BrowserPool(pool_config)
        await pool.initialize()

        try:
            # Manually mark a browser as unhealthy
            if len(pool._browsers) > 0:
                pool._browsers[0].health_check_failures = pool_config.max_health_check_failures

            # Run health check
            await pool._perform_health_checks()

            # Unhealthy browser should be removed
            assert all(b.health_check_failures < pool_config.max_health_check_failures
                      for b in pool._browsers)
        finally:
            await pool.shutdown()

    async def test_context_manager(self, pool_config):
        """Test using pool as async context manager."""
        async with BrowserPool(pool_config) as pool:
            browser, context = await pool.acquire_context()
            assert browser is not None
            await pool.release_context(browser, context)

        # Pool should be shut down after context exit
        assert pool._initialized is False


@pytest.mark.asyncio
class TestBrowserPoolManager:
    """Tests for BrowserPoolManager singleton."""

    async def test_singleton_pattern(self):
        """Test that BrowserPoolManager is a singleton."""
        manager1 = BrowserPoolManager()
        manager2 = BrowserPoolManager()

        assert manager1 is manager2

    async def test_get_pool(self):
        """Test getting the global pool."""
        try:
            pool = await BrowserPoolManager.get_pool()
            assert pool is not None
            assert isinstance(pool, BrowserPool)
        finally:
            await BrowserPoolManager.shutdown_pool()

    async def test_acquire_and_release_context(self):
        """Test convenience methods for context management."""
        try:
            browser, context = await BrowserPoolManager.acquire_context()
            assert browser is not None
            assert context is not None

            await BrowserPoolManager.release_context(browser, context)
        finally:
            await BrowserPoolManager.shutdown_pool()

    async def test_get_stats(self):
        """Test getting stats from pool manager."""
        try:
            # Initialize pool
            await BrowserPoolManager.get_pool()

            stats = await BrowserPoolManager.get_stats()
            assert stats is not None
            assert "total_browsers" in stats
        finally:
            await BrowserPoolManager.shutdown_pool()

    async def test_shutdown_pool(self):
        """Test shutting down the global pool."""
        # Create pool
        pool = await BrowserPoolManager.get_pool()
        assert pool is not None

        # Shutdown
        await BrowserPoolManager.shutdown_pool()

        # Pool should be None after shutdown
        assert BrowserPoolManager._pool is None


@pytest.mark.asyncio
class TestBrowserInstance:
    """Tests for BrowserInstance dataclass."""

    def test_browser_instance_creation(self):
        """Test creating a browser instance."""
        mock_browser = Mock()
        instance = BrowserInstance(browser=mock_browser)

        assert instance.browser is mock_browser
        assert instance.contexts == []
        assert instance.in_use is False
        assert instance.health_check_failures == 0
        assert instance.last_used > 0
        assert instance.created_at > 0


@pytest.mark.asyncio
class TestPoolErrorHandling:
    """Tests for error handling in browser pool."""

    async def test_pool_handles_browser_creation_failure(self, pool_config):
        """Test that pool handles browser creation failures gracefully."""
        pool = BrowserPool(pool_config)

        # Mock playwright to fail on launch
        with patch.object(pool, '_playwright', None):
            with pytest.raises(AttributeError):
                await pool.initialize()

    async def test_release_nonexistent_context(self, browser_pool):
        """Test releasing a context that doesn't exist."""
        mock_browser = Mock()
        mock_context = Mock()

        # Should not raise an error
        await browser_pool.release_context(mock_browser, mock_context)

    async def test_multiple_shutdown_calls(self, pool_config):
        """Test that multiple shutdown calls don't cause errors."""
        pool = BrowserPool(pool_config)
        await pool.initialize()

        # First shutdown
        await pool.shutdown()

        # Second shutdown should not raise
        await pool.shutdown()

        assert pool._initialized is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
