"""
Retry policy module for handling scraping errors with intelligent retry strategies.

This module provides configurable retry policies with different backoff strategies,
error classification, and retry decision logic.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Type, Tuple
from enum import Enum
import time
import random


class RetryStrategy(Enum):
    """Retry strategy types."""
    IMMEDIATE = "immediate"  # Retry immediately
    FIXED_DELAY = "fixed"    # Fixed delay between retries
    EXPONENTIAL = "exponential"  # Exponential backoff
    EXPONENTIAL_JITTER = "exponential_jitter"  # Exponential backoff with jitter


class ErrorCategory(Enum):
    """Categories of errors for retry decisions."""
    TRANSIENT = "transient"  # Network timeouts, rate limits
    PERMANENT = "permanent"  # 404, 403, invalid URL
    UNKNOWN = "unknown"      # Uncategorized errors


@dataclass
class RetryPolicy:
    """
    Configurable retry policy for scraping operations.

    Examples:
        # Exponential backoff with jitter
        policy = RetryPolicy(
            max_attempts=5,
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
            base_delay=1.0,
            max_delay=60.0,
        )

        # Fixed delay
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.FIXED_DELAY,
            base_delay=5.0,
        )
    """

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    base_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter_range: float = 0.1  # Random jitter as fraction of delay (0.0 to 1.0)

    # Error classification
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        # Add more as needed
    )

    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        ValueError,  # Bad input
        FileNotFoundError,  # Local file issues
    )

    # Custom error classifier
    error_classifier: Optional[Callable[[Exception], ErrorCategory]] = None

    def __post_init__(self):
        """Convert strategy from string to enum if necessary."""
        if isinstance(self.strategy, str):
            self.strategy = RetryStrategy(self.strategy)

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an error should be retried.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-indexed)

        Returns:
            True if should retry, False otherwise
        """
        # Check if max attempts reached
        if attempt >= self.max_attempts:
            return False

        # Check if explicitly non-retryable
        if isinstance(error, self.non_retryable_exceptions):
            return False

        # Check if explicitly retryable
        if isinstance(error, self.retryable_exceptions):
            return True

        # Use custom classifier if provided
        if self.error_classifier:
            category = self.error_classifier(error)
            return category == ErrorCategory.TRANSIENT

        # Use default classifier
        category = self.default_error_classifier(error)
        return category == ErrorCategory.TRANSIENT or category == ErrorCategory.UNKNOWN

    def get_delay(self, attempt: int) -> float:
        """
        Calculate the delay before the next retry.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        elif self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.exponential_base ** (attempt - 1))
            delay = min(delay, self.max_delay)

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            delay = self.base_delay * (self.exponential_base ** (attempt - 1))
            delay = min(delay, self.max_delay)
            # Add random jitter
            jitter = delay * self.jitter_range * (random.random() * 2 - 1)
            delay = delay + jitter

        else:
            delay = self.base_delay

        return max(0.0, delay)

    @staticmethod
    def default_error_classifier(error: Exception) -> ErrorCategory:
        """
        Default error classification logic.

        Classifies errors based on common patterns in scraping.
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Transient errors (should retry)
        transient_patterns = [
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "rate limit",
            "429",  # Too Many Requests
            "503",  # Service Unavailable
            "502",  # Bad Gateway
            "504",  # Gateway Timeout
            "network",
            "temporary",
        ]

        # Permanent errors (should NOT retry)
        permanent_patterns = [
            "404",  # Not Found
            "403",  # Forbidden
            "401",  # Unauthorized
            "400",  # Bad Request
            "invalid url",
            "no such file",
            "not found",
        ]

        for pattern in transient_patterns:
            if pattern in error_str or pattern in error_type.lower():
                return ErrorCategory.TRANSIENT

        for pattern in permanent_patterns:
            if pattern in error_str:
                return ErrorCategory.PERMANENT

        return ErrorCategory.UNKNOWN


# Predefined policies
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    base_delay=1.0,
    max_delay=10.0,
)

AGGRESSIVE_RETRY_POLICY = RetryPolicy(
    max_attempts=5,
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    base_delay=2.0,
    max_delay=60.0,
)

NO_RETRY_POLICY = RetryPolicy(
    max_attempts=1,
    strategy=RetryStrategy.IMMEDIATE,
)
