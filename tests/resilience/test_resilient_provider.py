"""
Unit tests for ResilientLLMProvider class.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from scrapegraphai.resilience import (
    ResilientLLMProvider,
    CircuitBreaker,
    CircuitBreakerState,
)
from scrapegraphai.resilience.exceptions import CircuitBreakerOpenError


class TestResilientLLMProvider:
    """Test suite for ResilientLLMProvider class."""

    def test_initialization(self):
        """Test provider initialization."""
        mock_provider = Mock()
        cb = CircuitBreaker()

        provider = ResilientLLMProvider(
            provider=mock_provider,
            circuit_breaker=cb,
            name="test-provider",
            priority=1
        )

        assert provider.provider == mock_provider
        assert provider.circuit_breaker == cb
        assert provider.name == "test-provider"
        assert provider.priority == 1
        assert provider.total_calls == 0
        assert provider.successful_calls == 0
        assert provider.failed_calls == 0

    def test_initialization_with_defaults(self):
        """Test provider initialization with default circuit breaker."""
        mock_provider = Mock()

        provider = ResilientLLMProvider(provider=mock_provider)

        assert provider.provider == mock_provider
        assert isinstance(provider.circuit_breaker, CircuitBreaker)
        assert provider.name == "unknown"
        assert provider.priority == 0

    def test_successful_invocation(self):
        """Test successful provider invocation."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="response")

        provider = ResilientLLMProvider(
            provider=mock_provider,
            name="test-provider"
        )

        result = provider.invoke("input")

        assert result == "response"
        mock_provider.invoke.assert_called_once_with("input")
        assert provider.total_calls == 1
        assert provider.successful_calls == 1
        assert provider.failed_calls == 0
        assert provider.last_success_time is not None

    def test_failed_invocation(self):
        """Test failed provider invocation."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(side_effect=ValueError("API error"))

        provider = ResilientLLMProvider(
            provider=mock_provider,
            name="test-provider"
        )

        with pytest.raises(ValueError) as exc_info:
            provider.invoke("input")

        assert "API error" in str(exc_info.value)
        assert provider.total_calls == 1
        assert provider.successful_calls == 0
        assert provider.failed_calls == 1
        assert provider.last_failure_time is not None
        assert provider.last_error == "API error"

    def test_circuit_breaker_integration(self):
        """Test that circuit breaker opens after threshold failures."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(side_effect=ValueError("API error"))

        cb = CircuitBreaker(failure_threshold=3)
        provider = ResilientLLMProvider(
            provider=mock_provider,
            circuit_breaker=cb,
            name="test-provider"
        )

        # Trigger failures to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                provider.invoke("input")

        assert cb.is_open
        assert provider.failed_calls == 3

        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            provider.invoke("input")

        # Total calls should not increment (circuit breaker rejected it)
        assert provider.total_calls == 3

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        mock_provider = Mock()

        provider = ResilientLLMProvider(provider=mock_provider)

        # No calls yet
        assert provider.success_rate == 0.0

        # Add some successful calls
        mock_provider.invoke = Mock(return_value="success")
        for _ in range(7):
            provider.invoke("input")

        # Add some failures
        mock_provider.invoke = Mock(side_effect=ValueError("error"))
        for _ in range(3):
            with pytest.raises(ValueError):
                provider.invoke("input")

        # Success rate should be 70%
        assert provider.success_rate == 0.7
        assert provider.total_calls == 10
        assert provider.successful_calls == 7
        assert provider.failed_calls == 3

    def test_average_latency_calculation(self):
        """Test average latency calculation."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="success")

        provider = ResilientLLMProvider(provider=mock_provider)

        # Make some calls
        for _ in range(5):
            provider.invoke("input")

        # Average latency should be calculated
        assert provider.average_latency >= 0
        assert provider.successful_calls == 5

    def test_health_status(self):
        """Test health status reporting."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="success")

        provider = ResilientLLMProvider(
            provider=mock_provider,
            name="test-provider",
            priority=2
        )

        # Make some calls
        for _ in range(3):
            provider.invoke("input")

        health = provider.health_status

        assert health["name"] == "test-provider"
        assert health["priority"] == 2
        assert health["circuit_state"] == "closed"
        assert health["total_calls"] == 3
        assert health["successful_calls"] == 3
        assert health["failed_calls"] == 0
        assert "100.00%" in health["success_rate"]
        assert health["last_success"] is not None
        assert health["last_error"] is None

    def test_reset_metrics(self):
        """Test metrics reset."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="success")

        provider = ResilientLLMProvider(provider=mock_provider)

        # Make some calls
        for _ in range(5):
            provider.invoke("input")

        assert provider.total_calls == 5

        # Reset metrics
        provider.reset_metrics()

        assert provider.total_calls == 0
        assert provider.successful_calls == 0
        assert provider.failed_calls == 0
        assert provider.total_latency == 0.0
        assert provider.last_success_time is None
        assert provider.last_failure_time is None
        assert provider.last_error is None

    @pytest.mark.asyncio
    async def test_async_invocation(self):
        """Test async provider invocation."""
        mock_provider = Mock()
        mock_provider.ainvoke = AsyncMock(return_value="async response")

        provider = ResilientLLMProvider(provider=mock_provider)

        result = await provider.ainvoke("input")

        assert result == "async response"
        mock_provider.ainvoke.assert_called_once_with("input")
        assert provider.successful_calls == 1

    @pytest.mark.asyncio
    async def test_async_invocation_failure(self):
        """Test async provider invocation failure."""
        mock_provider = Mock()
        mock_provider.ainvoke = AsyncMock(side_effect=ValueError("Async error"))

        provider = ResilientLLMProvider(provider=mock_provider)

        with pytest.raises(ValueError) as exc_info:
            await provider.ainvoke("input")

        assert "Async error" in str(exc_info.value)
        assert provider.failed_calls == 1
        assert provider.last_error == "Async error"

    def test_repr(self):
        """Test string representation."""
        mock_provider = Mock()
        provider = ResilientLLMProvider(
            provider=mock_provider,
            name="test-provider",
            priority=1
        )

        repr_str = repr(provider)

        assert "ResilientLLMProvider" in repr_str
        assert "test-provider" in repr_str
        assert "priority=1" in repr_str
        assert "state=closed" in repr_str

    def test_invoke_with_args_and_kwargs(self):
        """Test invocation with both args and kwargs."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="success")

        provider = ResilientLLMProvider(provider=mock_provider)

        result = provider.invoke("arg1", "arg2", kwarg1="value1", kwarg2="value2")

        assert result == "success"
        mock_provider.invoke.assert_called_once_with(
            "arg1", "arg2", kwarg1="value1", kwarg2="value2"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
