"""
Tests for the DomainRateLimiter and related classes.
"""

import asyncio
import time
import pytest
from scrapegraphai.utils.rate_limiter import (
    DomainRateLimiter,
    RateLimiterConfig,
    DomainState,
)


class TestDomainState:
    """Tests for DomainState dataclass."""

    def test_domain_state_initialization(self):
        """Test default initialization of DomainState."""
        state = DomainState()
        assert state.last_request_time == 0.0
        assert state.request_count == 0
        assert state.min_delay == 1.0
        assert state.max_delay == 3.0
        assert state.retry_after is None
        assert state.blocked_until is None

    def test_domain_state_custom_values(self):
        """Test DomainState with custom values."""
        state = DomainState(
            last_request_time=123.45,
            request_count=5,
            min_delay=2.0,
            max_delay=5.0,
            retry_after=10.0,
            blocked_until=200.0,
        )
        assert state.last_request_time == 123.45
        assert state.request_count == 5
        assert state.min_delay == 2.0
        assert state.max_delay == 5.0
        assert state.retry_after == 10.0
        assert state.blocked_until == 200.0


class TestRateLimiterConfig:
    """Tests for RateLimiterConfig dataclass."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = RateLimiterConfig()
        assert config.default_min_delay == 1.0
        assert config.default_max_delay == 3.0
        assert config.randomize_delay is True
        assert config.respect_retry_after is True
        assert config.backoff_multiplier == 2.0
        assert config.max_backoff_delay == 60.0
        assert config.per_domain_limits == {}

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = RateLimiterConfig(
            default_min_delay=2.0,
            default_max_delay=5.0,
            randomize_delay=False,
            respect_retry_after=False,
            backoff_multiplier=1.5,
            max_backoff_delay=30.0,
            per_domain_limits={"example.com": (1.0, 2.0)},
        )
        assert config.default_min_delay == 2.0
        assert config.default_max_delay == 5.0
        assert config.randomize_delay is False
        assert config.respect_retry_after is False
        assert config.backoff_multiplier == 1.5
        assert config.max_backoff_delay == 30.0
        assert config.per_domain_limits == {"example.com": (1.0, 2.0)}


class TestDomainRateLimiter:
    """Tests for DomainRateLimiter class."""

    def test_initialization(self):
        """Test DomainRateLimiter initialization."""
        limiter = DomainRateLimiter()
        assert limiter.config is not None
        assert isinstance(limiter.config, RateLimiterConfig)
        assert limiter._domain_states is not None
        assert limiter._locks is not None

    def test_initialization_with_config(self):
        """Test DomainRateLimiter initialization with custom config."""
        config = RateLimiterConfig(default_min_delay=2.0)
        limiter = DomainRateLimiter(config)
        assert limiter.config.default_min_delay == 2.0

    def test_get_domain(self):
        """Test domain extraction from URLs."""
        limiter = DomainRateLimiter()

        # Test standard URL
        domain = limiter._get_domain("https://example.com/path")
        assert domain == "example.com"

        # Test URL with port
        domain = limiter._get_domain("https://example.com:8080/path")
        assert domain == "example.com:8080"

        # Test URL with subdomain
        domain = limiter._get_domain("https://www.example.com/path")
        assert domain == "www.example.com"

    def test_configure_domain(self):
        """Test configuring domain-specific rate limits."""
        limiter = DomainRateLimiter()

        # Configure custom limits
        limiter.configure_domain("example.com", min_delay=2.0, max_delay=5.0)

        # Access the domain state (this creates it if it doesn't exist)
        state = limiter._domain_states["example.com"]
        assert state.min_delay == 2.0
        assert state.max_delay == 5.0

    @pytest.mark.asyncio
    async def test_acquire_first_request(self):
        """Test that first request doesn't wait."""
        config = RateLimiterConfig(default_min_delay=1.0, default_max_delay=1.0)
        limiter = DomainRateLimiter(config)

        start = time.time()
        delay = await limiter.acquire("https://example.com/test")
        elapsed = time.time() - start

        # First request should be immediate
        assert elapsed < 0.1  # Allow some tolerance
        assert delay == 1.0

    @pytest.mark.asyncio
    async def test_acquire_respects_delay(self):
        """Test that subsequent requests respect minimum delay."""
        config = RateLimiterConfig(
            default_min_delay=0.5,
            default_max_delay=0.5,
            randomize_delay=False,
        )
        limiter = DomainRateLimiter(config)

        # First request
        await limiter.acquire("https://example.com/test1")

        # Second request should wait
        start = time.time()
        await limiter.acquire("https://example.com/test2")
        elapsed = time.time() - start

        # Should wait approximately min_delay
        assert elapsed >= 0.4  # Allow some tolerance
        assert elapsed < 0.7

    @pytest.mark.asyncio
    async def test_acquire_different_domains(self):
        """Test that different domains don't interfere with each other."""
        config = RateLimiterConfig(
            default_min_delay=1.0,
            default_max_delay=1.0,
            randomize_delay=False,
        )
        limiter = DomainRateLimiter(config)

        # Request to first domain
        await limiter.acquire("https://example1.com/test")

        # Request to second domain should be immediate
        start = time.time()
        await limiter.acquire("https://example2.com/test")
        elapsed = time.time() - start

        # Should be immediate since it's a different domain
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_acquire_with_retry_attempt(self):
        """Test that retry attempts apply exponential backoff."""
        config = RateLimiterConfig(
            default_min_delay=0.5,
            default_max_delay=0.5,
            randomize_delay=False,
            backoff_multiplier=2.0,
        )
        limiter = DomainRateLimiter(config)

        # First attempt
        delay = await limiter.acquire("https://example.com/test", retry_attempt=0)
        assert delay == 0.5

        # Second attempt (retry 1) should have exponential backoff
        start = time.time()
        delay = await limiter.acquire("https://example.com/test", retry_attempt=1)
        elapsed = time.time() - start

        # Expected: 0.5 * (2.0 ** 1) = 1.0
        assert delay == 1.0
        assert elapsed >= 0.9  # Should wait for the backoff

    def test_calculate_delay_without_randomization(self):
        """Test delay calculation without randomization."""
        config = RateLimiterConfig(
            default_min_delay=1.0,
            default_max_delay=3.0,
            randomize_delay=False,
        )
        limiter = DomainRateLimiter(config)
        state = DomainState(min_delay=1.0, max_delay=3.0)

        delay = limiter._calculate_delay(state, retry_attempt=0)
        assert delay == 1.0

    def test_calculate_delay_with_randomization(self):
        """Test delay calculation with randomization."""
        config = RateLimiterConfig(
            default_min_delay=1.0,
            default_max_delay=3.0,
            randomize_delay=True,
        )
        limiter = DomainRateLimiter(config)
        state = DomainState(min_delay=1.0, max_delay=3.0)

        # Run multiple times to test randomness
        delays = [limiter._calculate_delay(state, retry_attempt=0) for _ in range(10)]

        # All delays should be within range
        assert all(1.0 <= d <= 3.0 for d in delays)

        # With randomization, we should see some variation
        # (Note: there's a small chance this could fail due to random chance)
        assert len(set(delays)) > 1

    def test_calculate_delay_with_exponential_backoff(self):
        """Test delay calculation with exponential backoff."""
        config = RateLimiterConfig(
            default_min_delay=1.0,
            default_max_delay=3.0,
            randomize_delay=False,
            backoff_multiplier=2.0,
        )
        limiter = DomainRateLimiter(config)
        state = DomainState(min_delay=1.0, max_delay=3.0)

        # No retry
        delay = limiter._calculate_delay(state, retry_attempt=0)
        assert delay == 1.0

        # First retry: 1.0 * 2^1 = 2.0
        delay = limiter._calculate_delay(state, retry_attempt=1)
        assert delay == 2.0

        # Second retry: 1.0 * 2^2 = 4.0 (but max_delay is now 4.0)
        delay = limiter._calculate_delay(state, retry_attempt=2)
        assert delay == 4.0

    def test_calculate_delay_respects_max_backoff(self):
        """Test that delay calculation respects max_backoff_delay."""
        config = RateLimiterConfig(
            default_min_delay=1.0,
            default_max_delay=3.0,
            randomize_delay=False,
            backoff_multiplier=2.0,
            max_backoff_delay=5.0,
        )
        limiter = DomainRateLimiter(config)
        state = DomainState(min_delay=1.0, max_delay=3.0)

        # High retry attempt that would exceed max_backoff
        # 1.0 * 2^10 = 1024, but should be capped at 5.0
        delay = limiter._calculate_delay(state, retry_attempt=10)
        assert delay == 5.0

    def test_calculate_delay_with_retry_after(self):
        """Test that Retry-After header overrides normal delay."""
        config = RateLimiterConfig(respect_retry_after=True)
        limiter = DomainRateLimiter(config)
        state = DomainState(min_delay=1.0, max_delay=3.0, retry_after=10.0)

        delay = limiter._calculate_delay(state, retry_attempt=0)
        assert delay == 10.0

        # retry_after should be cleared after use
        assert state.retry_after is None

    def test_handle_429_with_retry_after(self):
        """Test handling 429 response with Retry-After header."""
        limiter = DomainRateLimiter()

        limiter.handle_429("https://example.com/test", retry_after=30)

        state = limiter._domain_states["example.com"]
        assert state.retry_after == 30
        assert state.blocked_until is not None
        assert state.blocked_until > time.time()

    def test_handle_429_without_retry_after(self):
        """Test handling 429 response without Retry-After header."""
        config = RateLimiterConfig(default_min_delay=2.0)
        limiter = DomainRateLimiter(config)

        limiter.handle_429("https://example.com/test")

        state = limiter._domain_states["example.com"]
        assert state.blocked_until is not None
        assert state.blocked_until > time.time()

    @pytest.mark.asyncio
    async def test_acquire_after_429(self):
        """Test that acquire waits for blocked_until after 429."""
        config = RateLimiterConfig(
            default_min_delay=0.1,
            default_max_delay=0.1,
            randomize_delay=False,
        )
        limiter = DomainRateLimiter(config)

        # Simulate 429 with short retry_after
        limiter.handle_429("https://example.com/test", retry_after=0.5)

        # Next request should wait for blocked_until
        start = time.time()
        await limiter.acquire("https://example.com/test")
        elapsed = time.time() - start

        # Should wait approximately 0.5 seconds
        assert elapsed >= 0.4
        assert elapsed < 0.7

    def test_get_stats_single_domain(self):
        """Test getting stats for a single domain."""
        limiter = DomainRateLimiter()

        # Manually create a domain state
        state = limiter._domain_states["example.com"]
        state.request_count = 5
        state.last_request_time = 123.45

        stats = limiter.get_stats("example.com")
        assert stats["domain"] == "example.com"
        assert stats["request_count"] == 5
        assert stats["last_request"] == 123.45
        assert stats["blocked"] is False

    def test_get_stats_all_domains(self):
        """Test getting stats for all domains."""
        limiter = DomainRateLimiter()

        # Create states for multiple domains
        limiter._domain_states["example1.com"].request_count = 3
        limiter._domain_states["example2.com"].request_count = 7

        stats = limiter.get_stats()
        assert "example1.com" in stats
        assert "example2.com" in stats
        assert stats["example1.com"]["request_count"] == 3
        assert stats["example2.com"]["request_count"] == 7

    def test_get_stats_nonexistent_domain(self):
        """Test getting stats for a domain that doesn't exist."""
        limiter = DomainRateLimiter()

        stats = limiter.get_stats("nonexistent.com")
        assert stats == {}

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_domain(self):
        """Test that concurrent requests to the same domain are serialized."""
        config = RateLimiterConfig(
            default_min_delay=0.2,
            default_max_delay=0.2,
            randomize_delay=False,
        )
        limiter = DomainRateLimiter(config)

        # Launch concurrent requests
        start = time.time()
        tasks = [
            limiter.acquire(f"https://example.com/page{i}")
            for i in range(3)
        ]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # First request is immediate, then each waits 0.2s
        # Total should be at least 0.4s (2 delays)
        assert elapsed >= 0.3

        # Check that all requests were counted
        stats = limiter.get_stats("example.com")
        assert stats["request_count"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
