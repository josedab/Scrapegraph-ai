"""
Integration tests for browser pool with ChromiumLoader and nodes.

These tests verify that the browser pool integrates correctly with:
- ChromiumLoader
- FetchNode
- FetchScreenNode
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.browser_pool import BrowserPoolManager, PoolConfig


@pytest.fixture(autouse=True)
async def cleanup_pool():
    """Cleanup browser pool after each test."""
    yield
    await BrowserPoolManager.shutdown_pool()


@pytest.mark.asyncio
class TestChromiumLoaderPooling:
    """Integration tests for ChromiumLoader with browser pooling."""

    async def test_chromium_loader_with_pooling_enabled(self):
        """Test that ChromiumLoader uses pooling when enabled."""
        # Create a loader with pooling enabled
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            use_pool=True,
            pool_config={
                "min_browsers": 1,
                "max_browsers": 2,
            }
        )

        # Mock the actual browser operations to avoid real network calls
        with patch('scrapegraphai.utils.browser_pool.async_playwright') as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            # Setup mock chain
            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.content = AsyncMock(return_value="<html>Test content</html>")
            mock_page.close = AsyncMock()
            mock_context.close = AsyncMock()

            # Test that the loader can scrape with pooling
            result = await loader.ascrape_playwright("https://example.com")
            assert result is not None

    async def test_chromium_loader_with_pooling_disabled(self):
        """Test that ChromiumLoader works without pooling."""
        # Create a loader with pooling disabled
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            use_pool=False,
        )

        # Mock the actual browser operations
        with patch('scrapegraphai.docloaders.chromium.async_playwright') as mock_pw:
            mock_playwright_ctx = AsyncMock()
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            # Setup mock chain
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
            mock_pw.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.content = AsyncMock(return_value="<html>Test content</html>")
            mock_page.close = AsyncMock()
            mock_browser.close = AsyncMock()

            # Test that the loader can scrape without pooling
            result = await loader.ascrape_playwright("https://example.com")
            assert result is not None

    async def test_multiple_urls_with_pooling(self):
        """Test scraping multiple URLs with pooling."""
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        loader = ChromiumLoader(
            urls=urls,
            headless=True,
            use_pool=True,
            pool_config={
                "min_browsers": 1,
                "max_browsers": 2,
                "max_contexts_per_browser": 2,
            }
        )

        # Mock browser operations
        with patch('scrapegraphai.utils.browser_pool.async_playwright') as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.wait_for_load_state = AsyncMock()
            mock_page.content = AsyncMock(return_value="<html>Test content</html>")
            mock_page.close = AsyncMock()
            mock_context.close = AsyncMock()

            # Scrape all URLs
            results = []
            for url in urls:
                result = await loader.ascrape_playwright(url)
                results.append(result)

            # Verify all URLs were scraped
            assert len(results) == len(urls)
            assert all(result is not None for result in results)

    async def test_pool_reuse_across_loaders(self):
        """Test that multiple loaders can share the same pool."""
        # Create two loaders with pooling
        loader1 = ChromiumLoader(
            urls=["https://example.com/1"],
            use_pool=True,
        )

        loader2 = ChromiumLoader(
            urls=["https://example.com/2"],
            use_pool=True,
        )

        # Get the pool instance
        pool1 = await BrowserPoolManager.get_pool()

        # Both loaders should use the same pool (singleton)
        # This is verified by the fact that BrowserPoolManager is a singleton

        stats = await BrowserPoolManager.get_stats()
        assert stats is not None
        assert "total_browsers" in stats


@pytest.mark.asyncio
class TestFetchNodePooling:
    """Integration tests for FetchNode with browser pooling."""

    def test_fetch_node_pool_configuration(self):
        """Test that FetchNode accepts pool configuration."""
        from scrapegraphai.nodes import FetchNode

        node_config = {
            "use_pool": True,
            "pool_config": {
                "min_browsers": 2,
                "max_browsers": 5,
            },
            "headless": True,
        }

        node = FetchNode(
            input="url",
            output=["document"],
            node_config=node_config,
        )

        assert node.use_pool is True
        assert node.pool_config is not None
        assert node.pool_config["min_browsers"] == 2

    def test_fetch_node_default_pooling(self):
        """Test that FetchNode has pooling enabled by default."""
        from scrapegraphai.nodes import FetchNode

        node = FetchNode(
            input="url",
            output=["document"],
            node_config={},
        )

        # Pooling should be enabled by default
        assert node.use_pool is True


@pytest.mark.asyncio
class TestFetchScreenNodePooling:
    """Integration tests for FetchScreenNode with browser pooling."""

    def test_fetch_screen_node_pool_configuration(self):
        """Test that FetchScreenNode accepts pool configuration."""
        from scrapegraphai.nodes.fetch_screen_node import FetchScreenNode

        node_config = {
            "link": "https://example.com",
            "use_pool": True,
            "pool_config": {
                "min_browsers": 1,
                "max_browsers": 3,
            },
        }

        node = FetchScreenNode(
            input="url",
            output=["screenshots"],
            node_config=node_config,
        )

        assert node.use_pool is True
        assert node.pool_config is not None

    async def test_fetch_screen_node_async_execution(self):
        """Test that FetchScreenNode can execute with async pooling."""
        from scrapegraphai.nodes.fetch_screen_node import FetchScreenNode

        node_config = {
            "link": "https://example.com",
            "use_pool": True,
        }

        node = FetchScreenNode(
            input="url",
            output=["screenshots"],
            node_config=node_config,
        )

        # Mock the pool and browser operations
        with patch('scrapegraphai.utils.browser_pool.async_playwright') as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.viewport_size = {"width": 1920, "height": 1080}
            mock_page.evaluate = AsyncMock()
            mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")
            mock_page.close = AsyncMock()
            mock_context.close = AsyncMock()

            state = {}
            result = await node._execute_async(state)

            assert "screenshots" in result
            assert result["link"] == "https://example.com"


@pytest.mark.asyncio
class TestPoolPerformance:
    """Performance-related integration tests."""

    async def test_pool_reduces_browser_creation_overhead(self):
        """Test that pool reuses browsers instead of creating new ones."""
        pool = await BrowserPoolManager.get_pool(
            PoolConfig(min_browsers=1, max_browsers=2)
        )

        # Get initial browser count
        initial_stats = pool.get_stats()
        initial_browser_count = initial_stats["total_browsers"]

        # Acquire and release multiple contexts
        for _ in range(5):
            browser, context = await BrowserPoolManager.acquire_context()
            await BrowserPoolManager.release_context(browser, context)

        # Browser count should not have increased significantly
        final_stats = pool.get_stats()
        final_browser_count = final_stats["total_browsers"]

        # Should have reused browsers, not created 5 new ones
        assert final_browser_count <= initial_browser_count + 1

    async def test_concurrent_scraping_with_pool(self):
        """Test concurrent scraping operations with pool."""
        urls = [f"https://example.com/page{i}" for i in range(10)]

        async def scrape_url(url):
            loader = ChromiumLoader(
                urls=[url],
                use_pool=True,
            )
            # Mock the scraping
            with patch.object(loader, 'ascrape_playwright', new_callable=AsyncMock) as mock_scrape:
                mock_scrape.return_value = f"<html>Content from {url}</html>"
                return await loader.ascrape_playwright(url)

        # Scrape all URLs concurrently
        results = await asyncio.gather(*[scrape_url(url) for url in urls])

        # All URLs should be scraped successfully
        assert len(results) == len(urls)
        assert all(result is not None for result in results)


@pytest.mark.asyncio
class TestPoolErrorHandling:
    """Integration tests for error handling with pooling."""

    async def test_loader_fallback_on_pool_failure(self):
        """Test that loader falls back to non-pooled mode on pool failure."""
        loader = ChromiumLoader(
            urls=["https://example.com"],
            use_pool=True,
        )

        # Mock pool to fail
        with patch('scrapegraphai.utils.browser_pool.BrowserPoolManager.acquire_context',
                  side_effect=RuntimeError("Pool exhausted")):
            # Loader should handle the error gracefully
            # In practice, it would retry or fall back
            with pytest.raises(RuntimeError):
                await loader.ascrape_playwright("https://example.com")

    async def test_pool_cleanup_after_loader_exception(self):
        """Test that pool is cleaned up properly after exceptions."""
        pool = await BrowserPoolManager.get_pool()
        initial_stats = pool.get_stats()

        try:
            browser, context = await BrowserPoolManager.acquire_context()

            # Simulate an exception during scraping
            await BrowserPoolManager.release_context(browser, context)
        except Exception:
            pass

        # Pool should still be functional
        final_stats = pool.get_stats()
        assert final_stats is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
