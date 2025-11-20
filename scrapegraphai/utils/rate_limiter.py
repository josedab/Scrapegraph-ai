"""
Rate limiting utilities for ScrapeGraphAI.

This module provides per-domain rate limiting with exponential backoff and jitter
to improve scraping reliability and respectfulness.
"""

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse

from .logging import get_logger

logger = get_logger("rate-limiter")


@dataclass
class DomainState:
    """Tracks request state for a single domain."""

    last_request_time: float = 0.0
    request_count: int = 0
    min_delay: float = 1.0  # Minimum seconds between requests
    max_delay: float = 3.0  # Maximum seconds between requests
    retry_after: Optional[float] = None  # From Retry-After header
    blocked_until: Optional[float] = None  # If domain is temporarily blocked


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiting."""

    default_min_delay: float = 1.0  # Default min delay between requests
    default_max_delay: float = 3.0  # Default max delay between requests
    randomize_delay: bool = True  # Add jitter to delays
    respect_retry_after: bool = True  # Honor Retry-After headers
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    max_backoff_delay: float = 60.0  # Maximum backoff delay
    per_domain_limits: Dict[str, tuple] = field(
        default_factory=dict
    )  # Example: {"example.com": (2.0, 5.0)}


class DomainRateLimiter:
    """
    Manages per-domain rate limiting with exponential backoff and jitter.

    Features:
    - Per-domain request tracking
    - Configurable min/max delays per domain
    - Exponential backoff on retries
    - Retry-After header support
    - Request timing randomization
    - Domain blocking/cooldown
    """

    def __init__(self, config: Optional[RateLimiterConfig] = None):
        self.config = config or RateLimiterConfig()
        self._domain_states: Dict[str, DomainState] = defaultdict(
            self._create_domain_state
        )
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _create_domain_state(self) -> DomainState:
        """Create a new domain state with default configuration."""
        return DomainState(
            min_delay=self.config.default_min_delay,
            max_delay=self.config.default_max_delay,
        )

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0]

    def configure_domain(self, domain: str, min_delay: float, max_delay: float):
        """
        Configure custom rate limits for a specific domain.

        Args:
            domain: The domain name (e.g., "example.com")
            min_delay: Minimum seconds between requests
            max_delay: Maximum seconds between requests
        """
        state = self._domain_states[domain]
        state.min_delay = min_delay
        state.max_delay = max_delay

    async def acquire(self, url: str, retry_attempt: int = 0) -> float:
        """
        Acquire permission to make a request to the given URL.

        This method blocks until it's safe to make the request based on
        rate limiting rules. Returns the delay that was applied.

        Args:
            url: The URL to request
            retry_attempt: The current retry attempt number (0 for first attempt)

        Returns:
            float: The delay in seconds that was applied
        """
        domain = self._get_domain(url)
        async with self._locks[domain]:
            state = self._domain_states[domain]
            now = time.time()

            # Check if domain is temporarily blocked
            if state.blocked_until and now < state.blocked_until:
                wait_time = state.blocked_until - now
                logger.info(f"Domain {domain} blocked, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                state.blocked_until = None

            # Calculate required delay
            delay = self._calculate_delay(state, retry_attempt)

            # Calculate time since last request
            if state.last_request_time > 0:
                elapsed = now - state.last_request_time
                remaining = delay - elapsed

                if remaining > 0:
                    logger.debug(f"Rate limiting {domain}: waiting {remaining:.2f}s")
                    await asyncio.sleep(remaining)

            # Update state
            state.last_request_time = time.time()
            state.request_count += 1

            return delay

    def _calculate_delay(self, state: DomainState, retry_attempt: int) -> float:
        """
        Calculate the delay for the next request.

        Applies:
        - Base delay from config
        - Exponential backoff for retries
        - Randomization/jitter
        - Retry-After header overrides
        """
        # Check for Retry-After override
        if self.config.respect_retry_after and state.retry_after:
            delay = state.retry_after
            state.retry_after = None  # Clear after use
            return delay

        # Base delay
        min_delay = state.min_delay
        max_delay = state.max_delay

        # Apply exponential backoff for retries
        if retry_attempt > 0:
            backoff = min_delay * (self.config.backoff_multiplier ** retry_attempt)
            backoff = min(backoff, self.config.max_backoff_delay)
            min_delay = backoff
            max_delay = max(max_delay, backoff)

        # Add randomization
        if self.config.randomize_delay:
            delay = random.uniform(min_delay, max_delay)
        else:
            delay = min_delay

        return delay

    def handle_429(self, url: str, retry_after: Optional[int] = None):
        """
        Handle a 429 (Too Many Requests) response.

        Args:
            url: The URL that returned 429
            retry_after: Value from Retry-After header (seconds)
        """
        domain = self._get_domain(url)
        state = self._domain_states[domain]

        if retry_after:
            state.retry_after = retry_after
            state.blocked_until = time.time() + retry_after
            logger.warning(
                f"Domain {domain} rate limited, backing off for {retry_after}s"
            )
        else:
            # Default backoff if no Retry-After header
            backoff = min(state.min_delay * 10, self.config.max_backoff_delay)
            state.blocked_until = time.time() + backoff
            logger.warning(
                f"Domain {domain} rate limited, backing off for {backoff}s"
            )

    def get_stats(self, domain: Optional[str] = None) -> Dict:
        """
        Get statistics for rate limiting.

        Args:
            domain: Specific domain to get stats for, or None for all domains

        Returns:
            Dict containing rate limiting statistics
        """
        if domain:
            state = self._domain_states.get(domain)
            if state:
                return {
                    "domain": domain,
                    "request_count": state.request_count,
                    "last_request": state.last_request_time,
                    "blocked": state.blocked_until is not None,
                }
            return {}

        return {
            domain: {
                "request_count": state.request_count,
                "last_request": state.last_request_time,
                "blocked": state.blocked_until is not None,
            }
            for domain, state in self._domain_states.items()
        }
