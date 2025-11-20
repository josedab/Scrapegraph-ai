"""
Unit tests for CircuitBreaker class.
"""

import time
import pytest
from unittest.mock import Mock

from scrapegraphai.resilience import CircuitBreaker, CircuitBreakerState
from scrapegraphai.resilience.exceptions import CircuitBreakerOpenError


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    def test_successful_call_in_closed_state(self):
        """Test that successful calls work in CLOSED state."""
        cb = CircuitBreaker()
        mock_func = Mock(return_value="success")

        result = cb.call(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_failed_call_increments_failure_count(self):
        """Test that failed calls increment failure counter."""
        cb = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(side_effect=ValueError("test error"))

        # First failure
        with pytest.raises(ValueError):
            cb.call(mock_func)

        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED

    def test_opens_after_threshold_failures(self):
        """Test that circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(side_effect=ValueError("test error"))

        # Trigger 3 failures
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open
        assert cb.failure_count == 3

    def test_rejects_calls_when_open(self):
        """Test that circuit breaker rejects calls when OPEN."""
        cb = CircuitBreaker(failure_threshold=2, timeout=10)
        mock_func = Mock(side_effect=ValueError("test error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.is_open

        # Try to call again - should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(mock_func)

        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_transitions_to_half_open_after_timeout(self):
        """Test transition from OPEN to HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        mock_func = Mock(side_effect=ValueError("test error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.is_open

        # Wait for timeout
        time.sleep(1.1)

        # Mock function should now succeed
        mock_func_success = Mock(return_value="success")

        # Should transition to HALF_OPEN and allow call
        result = cb.call(mock_func_success)
        assert result == "success"
        assert cb.is_half_open

    def test_closes_after_successful_recovery_in_half_open(self):
        """Test that circuit closes after successful calls in HALF_OPEN."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout=1,
            half_open_max_calls=2
        )
        mock_func_fail = Mock(side_effect=ValueError("test error"))
        mock_func_success = Mock(return_value="success")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func_fail)

        assert cb.is_open

        # Wait for timeout
        time.sleep(1.1)

        # Make successful calls to close circuit
        cb.call(mock_func_success)  # Transition to HALF_OPEN
        assert cb.is_half_open

        cb.call(mock_func_success)  # Should close circuit
        assert cb.is_closed

    def test_reopens_on_failure_in_half_open(self):
        """Test that circuit reopens on failure in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=2, timeout=1)
        mock_func_fail = Mock(side_effect=ValueError("test error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func_fail)

        assert cb.is_open

        # Wait for timeout
        time.sleep(1.1)

        # Fail in HALF_OPEN state
        with pytest.raises(ValueError):
            cb.call(mock_func_fail)

        # Should be OPEN again
        assert cb.is_open

    def test_limits_calls_in_half_open_state(self):
        """Test that HALF_OPEN state limits number of test calls."""
        cb = CircuitBreaker(
            failure_threshold=2,
            timeout=1,
            half_open_max_calls=1
        )
        mock_func_fail = Mock(side_effect=ValueError("test error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func_fail)

        # Wait for timeout
        time.sleep(1.1)

        # First call should be allowed (transitions to HALF_OPEN)
        with pytest.raises(ValueError):
            cb.call(mock_func_fail)

        # Second call should be rejected (max calls reached)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(Mock(return_value="success"))

        assert "max test calls reached" in str(exc_info.value)

    def test_manual_reset(self):
        """Test manual reset of circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2)
        mock_func = Mock(side_effect=ValueError("test error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(mock_func)

        assert cb.is_open

        # Manually reset
        cb.reset()

        assert cb.is_closed
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_thread_safety(self):
        """Test that circuit breaker is thread-safe."""
        import threading

        cb = CircuitBreaker(failure_threshold=10)
        mock_func = Mock(return_value="success")
        results = []
        errors = []

        def call_func():
            try:
                result = cb.call(mock_func)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=call_func) for _ in range(20)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All calls should succeed
        assert len(results) == 20
        assert len(errors) == 0
        assert all(r == "success" for r in results)

    def test_custom_thresholds(self):
        """Test circuit breaker with custom thresholds."""
        cb = CircuitBreaker(
            failure_threshold=5,
            success_threshold=3,
            timeout=30
        )

        assert cb.failure_threshold == 5
        assert cb.success_threshold == 3
        assert cb.timeout == 30

    def test_resets_success_count_on_failure(self):
        """Test that success count resets on any failure."""
        cb = CircuitBreaker(failure_threshold=5, success_threshold=2, timeout=1)
        mock_success = Mock(return_value="success")
        mock_fail = Mock(side_effect=ValueError("error"))

        # Open the circuit
        for _ in range(5):
            with pytest.raises(ValueError):
                cb.call(mock_fail)

        time.sleep(1.1)

        # One success in HALF_OPEN
        cb.call(mock_success)
        assert cb.success_count == 1

        # Failure should reset success count
        with pytest.raises(ValueError):
            cb.call(mock_fail)

        assert cb.success_count == 0
        assert cb.is_open


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
