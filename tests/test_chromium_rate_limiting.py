"""
Integration tests for ChromiumLoader with rate limiting and anti-bot features.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from scrapegraphai.docloaders.chromium import ChromiumLoader
from scrapegraphai.utils.rate_limiter import RateLimiterConfig
from scrapegraphai.utils.anti_bot import AntiBotConfig


class TestChromiumLoaderRateLimiting:
    """Test ChromiumLoader with rate limiting enabled."""

    def test_rate_limiter_initialization_enabled(self):
        """Test that rate limiter is initialized when enabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=True,
        )
        assert loader.rate_limiter is not None
        assert loader.enable_rate_limiting is True

    def test_rate_limiter_initialization_disabled(self):
        """Test that rate limiter is None when disabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=False,
        )
        assert loader.rate_limiter is None
        assert loader.enable_rate_limiting is False

    def test_rate_limiter_custom_config(self):
        """Test that custom rate limiter config is applied."""
        rate_config = {
            "default_min_delay": 2.0,
            "default_max_delay": 5.0,
        }
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=True,
            rate_limit_config=rate_config,
        )
        assert loader.rate_limiter.config.default_min_delay == 2.0
        assert loader.rate_limiter.config.default_max_delay == 5.0

    def test_anti_bot_initialization_enabled(self):
        """Test that anti-bot manager is initialized when enabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_anti_bot=True,
        )
        assert loader.anti_bot is not None
        assert loader.enable_anti_bot is True

    def test_anti_bot_initialization_disabled(self):
        """Test that anti-bot manager is None when disabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_anti_bot=False,
        )
        assert loader.anti_bot is None
        assert loader.enable_anti_bot is False

    def test_anti_bot_custom_config(self):
        """Test that custom anti-bot config is applied."""
        anti_bot_config = {
            "rotate_user_agents": False,
            "randomize_headers": False,
        }
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_anti_bot=True,
            anti_bot_config=anti_bot_config,
        )
        assert loader.anti_bot.config.rotate_user_agents is False
        assert loader.anti_bot.config.randomize_headers is False

    @pytest.mark.asyncio
    async def test_ascrape_playwright_calls_rate_limiter(self):
        """Test that ascrape_playwright calls rate limiter when enabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=True,
            rate_limit_config={"default_min_delay": 0.1, "default_max_delay": 0.1},
        )

        # Mock the rate limiter's acquire method
        original_acquire = loader.rate_limiter.acquire
        call_count = 0

        async def mock_acquire(url, retry_attempt=0):
            nonlocal call_count
            call_count += 1
            return await original_acquire(url, retry_attempt)

        loader.rate_limiter.acquire = mock_acquire

        # Mock playwright to avoid actual browser launch
        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {}

            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = (
                mock_browser
            )
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html>test</html>"
            mock_browser.close = AsyncMock()

            # Also mock Malenia.apply_stealth
            with patch("undetected_playwright.Malenia.apply_stealth", new=AsyncMock()):
                try:
                    await loader.ascrape_playwright("http://example.com")
                except Exception:
                    pass  # Ignore any errors from mocking

        # Verify rate limiter was called
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_ascrape_playwright_handles_429(self):
        """Test that ascrape_playwright handles 429 responses correctly."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=True,
            retry_limit=2,
        )

        # Mock playwright to return 429
        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_response = MagicMock()
            mock_response.status = 429
            mock_response.headers = {"retry-after": "1"}

            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = (
                mock_browser
            )
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.goto.return_value = mock_response
            mock_browser.close = AsyncMock()

            with patch("undetected_playwright.Malenia.apply_stealth", new=AsyncMock()):
                with pytest.raises(RuntimeError) as exc_info:
                    await loader.ascrape_playwright("http://example.com")

                # Should fail after retries
                assert "Failed to scrape" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ascrape_playwright_applies_anti_bot(self):
        """Test that ascrape_playwright applies anti-bot measures."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_anti_bot=True,
        )

        # Track calls to anti-bot methods
        apply_to_context_calls = 0
        original_apply = loader.anti_bot.apply_to_context

        async def mock_apply(*args, **kwargs):
            nonlocal apply_to_context_calls
            apply_to_context_calls += 1
            return await original_apply(*args, **kwargs)

        loader.anti_bot.apply_to_context = mock_apply

        # Mock playwright
        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.headers = {}

            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = (
                mock_browser
            )
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.goto.return_value = mock_response
            mock_page.content.return_value = "<html>test</html>"
            mock_browser.close = AsyncMock()

            with patch("undetected_playwright.Malenia.apply_stealth", new=AsyncMock()):
                try:
                    await loader.ascrape_playwright("http://example.com")
                except Exception:
                    pass

        # Verify anti-bot methods were called
        assert apply_to_context_calls >= 1

    @pytest.mark.asyncio
    async def test_alazy_load_sequential_with_rate_limiting(self):
        """Test that alazy_load processes URLs sequentially when rate limiting is enabled."""
        urls = [f"http://example.com/page{i}" for i in range(3)]
        loader = ChromiumLoader(
            urls,
            enable_rate_limiting=True,
            rate_limit_config={"default_min_delay": 0.1, "default_max_delay": 0.1},
        )

        # Mock the scraping function
        async def mock_scraper(url):
            await asyncio.sleep(0.05)  # Simulate scraping time
            return f"<html>content for {url}</html>"

        loader.ascrape_playwright = mock_scraper

        # Track timing
        start = time.time()
        docs = [doc async for doc in loader.alazy_load()]
        elapsed = time.time() - start

        # Should have gotten all documents
        assert len(docs) == 3

        # Should have taken at least 0.2s (2 delays between 3 requests)
        # Plus 0.15s for scraping (3 * 0.05s)
        # Total minimum: 0.35s
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_alazy_load_parallel_without_rate_limiting(self):
        """Test that alazy_load processes URLs in parallel when rate limiting is disabled."""
        urls = [f"http://example.com/page{i}" for i in range(3)]
        loader = ChromiumLoader(
            urls,
            enable_rate_limiting=False,
        )

        # Mock the scraping function
        async def mock_scraper(url):
            await asyncio.sleep(0.1)  # Simulate scraping time
            return f"<html>content for {url}</html>"

        loader.ascrape_playwright = mock_scraper

        # Track timing
        start = time.time()
        docs = [doc async for doc in loader.alazy_load()]
        elapsed = time.time() - start

        # Should have gotten all documents
        assert len(docs) == 3

        # Should have taken approximately 0.1s (parallel execution)
        # Allow some overhead
        assert elapsed < 0.3

    @pytest.mark.asyncio
    async def test_alazy_load_handles_errors_gracefully(self):
        """Test that alazy_load handles errors and yields error documents."""
        urls = ["http://example.com/page1", "http://example.com/page2"]
        loader = ChromiumLoader(
            urls,
            enable_rate_limiting=True,
        )

        # Mock scraper that fails
        async def mock_scraper(url):
            if "page1" in url:
                raise Exception("Scraping failed")
            return f"<html>content for {url}</html>"

        loader.ascrape_playwright = mock_scraper

        docs = [doc async for doc in loader.alazy_load()]

        # Should have 2 documents (one error, one success)
        assert len(docs) == 2

        # First should be error document
        assert docs[0].page_content == ""
        assert "error" in docs[0].metadata

        # Second should be success
        assert "content for" in docs[1].page_content

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_retry(self):
        """Test that exponential backoff is applied on retries."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=True,
            retry_limit=3,
        )

        attempt_times = []

        # Mock playwright to fail twice, then succeed
        attempt_count = 0

        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            async def mock_goto(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                attempt_times.append(time.time())
                if attempt_count < 3:
                    raise Exception("Temporary failure")
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.headers = {}
                return mock_response

            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = (
                mock_browser
            )
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.goto = mock_goto
            mock_page.content.return_value = "<html>test</html>"
            mock_browser.close = AsyncMock()

            with patch("undetected_playwright.Malenia.apply_stealth", new=AsyncMock()):
                try:
                    result = await loader.ascrape_playwright("http://example.com")
                except Exception as e:
                    pass

        # Check that attempts were properly spaced with exponential backoff
        if len(attempt_times) >= 2:
            # Second attempt should wait ~2 seconds after first
            delay1 = attempt_times[1] - attempt_times[0]
            assert delay1 >= 1.9  # 2^1 = 2 seconds backoff

        if len(attempt_times) >= 3:
            # Third attempt should wait ~4 seconds after second
            delay2 = attempt_times[2] - attempt_times[1]
            assert delay2 >= 3.9  # 2^2 = 4 seconds backoff


class TestChromiumLoaderAntiBotIntegration:
    """Test ChromiumLoader integration with anti-bot features."""

    @pytest.mark.asyncio
    async def test_context_options_include_anti_bot_settings(self):
        """Test that browser context includes anti-bot settings."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_anti_bot=True,
        )

        # Get context options from anti-bot manager
        options = loader.anti_bot.get_context_options()

        # Should include randomized settings
        assert "user_agent" in options
        assert "viewport" in options
        assert "locale" in options
        assert "timezone_id" in options

    def test_default_enables_both_features(self):
        """Test that both rate limiting and anti-bot are enabled by default."""
        loader = ChromiumLoader(["http://example.com"])

        assert loader.enable_rate_limiting is True
        assert loader.rate_limiter is not None
        assert loader.enable_anti_bot is True
        assert loader.anti_bot is not None

    def test_can_disable_both_features(self):
        """Test that both features can be disabled."""
        loader = ChromiumLoader(
            ["http://example.com"],
            enable_rate_limiting=False,
            enable_anti_bot=False,
        )

        assert loader.enable_rate_limiting is False
        assert loader.rate_limiter is None
        assert loader.enable_anti_bot is False
        assert loader.anti_bot is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
