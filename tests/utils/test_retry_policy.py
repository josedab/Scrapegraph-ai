"""
Unit tests for retry_policy module.
"""

import pytest
from scrapegraphai.utils.retry_policy import (
    RetryPolicy,
    RetryStrategy,
    ErrorCategory,
    DEFAULT_RETRY_POLICY,
    AGGRESSIVE_RETRY_POLICY,
    NO_RETRY_POLICY,
)


class TestRetryStrategy:
    """Test RetryStrategy enum."""

    def test_strategy_values(self):
        """Test that all strategy values are defined."""
        assert RetryStrategy.IMMEDIATE.value == "immediate"
        assert RetryStrategy.FIXED_DELAY.value == "fixed"
        assert RetryStrategy.EXPONENTIAL.value == "exponential"
        assert RetryStrategy.EXPONENTIAL_JITTER.value == "exponential_jitter"


class TestErrorCategory:
    """Test ErrorCategory enum."""

    def test_category_values(self):
        """Test that all category values are defined."""
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.PERMANENT.value == "permanent"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestRetryPolicy:
    """Test RetryPolicy class."""

    def test_default_initialization(self):
        """Test default initialization."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.strategy == RetryStrategy.EXPONENTIAL_JITTER
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0

    def test_custom_initialization(self):
        """Test custom initialization."""
        policy = RetryPolicy(
            max_attempts=5,
            strategy=RetryStrategy.FIXED_DELAY,
            base_delay=2.0,
            max_delay=30.0,
        )
        assert policy.max_attempts == 5
        assert policy.strategy == RetryStrategy.FIXED_DELAY
        assert policy.base_delay == 2.0
        assert policy.max_delay == 30.0

    def test_strategy_from_string(self):
        """Test initialization with strategy as string."""
        policy = RetryPolicy(strategy="fixed")
        assert policy.strategy == RetryStrategy.FIXED_DELAY

    def test_should_retry_max_attempts_reached(self):
        """Test that retry is denied when max attempts reached."""
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(Exception("test"), 3) is False
        assert policy.should_retry(Exception("test"), 4) is False

    def test_should_retry_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        policy = RetryPolicy()
        assert policy.should_retry(ValueError("test"), 1) is False
        assert policy.should_retry(FileNotFoundError("test"), 1) is False

    def test_should_retry_retryable_exception(self):
        """Test that retryable exceptions are retried."""
        policy = RetryPolicy()
        assert policy.should_retry(TimeoutError("test"), 1) is True
        assert policy.should_retry(ConnectionError("test"), 1) is True

    def test_should_retry_with_custom_classifier(self):
        """Test retry with custom error classifier."""
        def custom_classifier(error):
            if "retry" in str(error).lower():
                return ErrorCategory.TRANSIENT
            return ErrorCategory.PERMANENT

        policy = RetryPolicy(error_classifier=custom_classifier)
        assert policy.should_retry(Exception("should retry"), 1) is True
        assert policy.should_retry(Exception("permanent failure"), 1) is False

    def test_get_delay_immediate(self):
        """Test immediate retry strategy."""
        policy = RetryPolicy(strategy=RetryStrategy.IMMEDIATE)
        assert policy.get_delay(1) == 0.0
        assert policy.get_delay(2) == 0.0

    def test_get_delay_fixed(self):
        """Test fixed delay strategy."""
        policy = RetryPolicy(strategy=RetryStrategy.FIXED_DELAY, base_delay=5.0)
        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(2) == 5.0
        assert policy.get_delay(3) == 5.0

    def test_get_delay_exponential(self):
        """Test exponential backoff strategy."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
        )
        assert policy.get_delay(1) == 1.0  # 1.0 * 2^0
        assert policy.get_delay(2) == 2.0  # 1.0 * 2^1
        assert policy.get_delay(3) == 4.0  # 1.0 * 2^2
        assert policy.get_delay(4) == 8.0  # 1.0 * 2^3
        assert policy.get_delay(5) == 10.0  # Capped at max_delay

    def test_get_delay_exponential_jitter(self):
        """Test exponential backoff with jitter."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter_range=0.1,
        )

        # Delay should be around base value with jitter
        delay1 = policy.get_delay(1)
        assert 0.9 <= delay1 <= 1.1  # 1.0 ± 10%

        delay2 = policy.get_delay(2)
        assert 1.8 <= delay2 <= 2.2  # 2.0 ± 10%

        # Test that max delay is respected
        delay_high = policy.get_delay(10)
        assert delay_high <= 11.0  # max_delay + jitter

    def test_default_error_classifier_transient(self):
        """Test default classifier for transient errors."""
        policy = RetryPolicy()

        # Timeout errors
        assert policy.default_error_classifier(TimeoutError("timeout")) == ErrorCategory.TRANSIENT
        assert policy.default_error_classifier(Exception("timed out")) == ErrorCategory.TRANSIENT

        # Network errors
        assert policy.default_error_classifier(Exception("connection reset")) == ErrorCategory.TRANSIENT
        assert policy.default_error_classifier(Exception("connection refused")) == ErrorCategory.TRANSIENT

        # Rate limit errors
        assert policy.default_error_classifier(Exception("rate limit")) == ErrorCategory.TRANSIENT
        assert policy.default_error_classifier(Exception("429 error")) == ErrorCategory.TRANSIENT
        assert policy.default_error_classifier(Exception("503 Service Unavailable")) == ErrorCategory.TRANSIENT

    def test_default_error_classifier_permanent(self):
        """Test default classifier for permanent errors."""
        policy = RetryPolicy()

        # 404 Not Found
        assert policy.default_error_classifier(Exception("404 not found")) == ErrorCategory.PERMANENT

        # 403 Forbidden
        assert policy.default_error_classifier(Exception("403 forbidden")) == ErrorCategory.PERMANENT

        # Invalid URL
        assert policy.default_error_classifier(Exception("invalid url")) == ErrorCategory.PERMANENT

    def test_default_error_classifier_unknown(self):
        """Test default classifier for unknown errors."""
        policy = RetryPolicy()

        # Random errors should be unknown
        assert policy.default_error_classifier(Exception("something went wrong")) == ErrorCategory.UNKNOWN
        assert policy.default_error_classifier(Exception("unexpected error")) == ErrorCategory.UNKNOWN


class TestPredefinedPolicies:
    """Test predefined retry policies."""

    def test_default_retry_policy(self):
        """Test DEFAULT_RETRY_POLICY."""
        assert DEFAULT_RETRY_POLICY.max_attempts == 3
        assert DEFAULT_RETRY_POLICY.strategy == RetryStrategy.EXPONENTIAL_JITTER
        assert DEFAULT_RETRY_POLICY.base_delay == 1.0
        assert DEFAULT_RETRY_POLICY.max_delay == 10.0

    def test_aggressive_retry_policy(self):
        """Test AGGRESSIVE_RETRY_POLICY."""
        assert AGGRESSIVE_RETRY_POLICY.max_attempts == 5
        assert AGGRESSIVE_RETRY_POLICY.strategy == RetryStrategy.EXPONENTIAL_JITTER
        assert AGGRESSIVE_RETRY_POLICY.base_delay == 2.0
        assert AGGRESSIVE_RETRY_POLICY.max_delay == 60.0

    def test_no_retry_policy(self):
        """Test NO_RETRY_POLICY."""
        assert NO_RETRY_POLICY.max_attempts == 1
        assert NO_RETRY_POLICY.strategy == RetryStrategy.IMMEDIATE


class TestRetryPolicyIntegration:
    """Integration tests for RetryPolicy."""

    def test_retry_flow_success_on_second_attempt(self):
        """Test that retry logic works correctly for success on second attempt."""
        policy = RetryPolicy(max_attempts=3)

        # First attempt fails
        error1 = TimeoutError("timeout")
        assert policy.should_retry(error1, 1) is True
        delay1 = policy.get_delay(1)
        assert delay1 > 0

        # Second attempt would succeed (not tested here, just checking delay)
        # This would be where the actual retry happens

    def test_retry_flow_exhausted_attempts(self):
        """Test that retry logic stops after max attempts."""
        policy = RetryPolicy(max_attempts=3, strategy=RetryStrategy.FIXED_DELAY, base_delay=1.0)

        # Attempt 1
        error = TimeoutError("timeout")
        assert policy.should_retry(error, 1) is True
        assert policy.get_delay(1) == 1.0

        # Attempt 2
        assert policy.should_retry(error, 2) is True
        assert policy.get_delay(2) == 1.0

        # Attempt 3 (last attempt)
        assert policy.should_retry(error, 3) is False  # Max reached

    def test_retry_flow_permanent_error(self):
        """Test that permanent errors stop retry immediately."""
        policy = RetryPolicy(max_attempts=5)

        # Permanent error on first attempt
        error = ValueError("invalid input")
        assert policy.should_retry(error, 1) is False

        # Should not retry even if attempts remaining
        assert policy.should_retry(error, 2) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
