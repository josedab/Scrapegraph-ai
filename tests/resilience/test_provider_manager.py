"""
Unit tests for LLMProviderManager class.
"""

import time
import pytest
from unittest.mock import Mock, patch

from scrapegraphai.resilience import (
    LLMProviderManager,
    ResilientLLMProvider,
    CircuitBreaker,
)
from scrapegraphai.resilience.exceptions import (
    CircuitBreakerOpenError,
    AllProvidersFailedError,
)


class TestLLMProviderManager:
    """Test suite for LLMProviderManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        mock_provider1 = Mock()
        primary = ResilientLLMProvider(mock_provider1, name="primary")

        manager = LLMProviderManager(primary=primary)

        assert manager.primary == primary
        assert manager.fallbacks == []
        assert manager.fallback_enabled is True
        assert len(manager.all_providers) == 1

    def test_initialization_with_fallbacks(self):
        """Test manager initialization with fallback providers."""
        mock_provider1 = Mock()
        mock_provider2 = Mock()
        mock_provider3 = Mock()

        primary = ResilientLLMProvider(mock_provider1, name="primary", priority=0)
        fallback1 = ResilientLLMProvider(mock_provider2, name="fallback1", priority=1)
        fallback2 = ResilientLLMProvider(mock_provider3, name="fallback2", priority=2)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback1, fallback2]
        )

        assert manager.primary == primary
        assert len(manager.fallbacks) == 2
        assert len(manager.all_providers) == 3

    def test_successful_invocation_with_primary(self):
        """Test successful invocation using primary provider."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(return_value="primary response")

        primary = ResilientLLMProvider(mock_provider, name="primary")
        manager = LLMProviderManager(primary=primary)

        result = manager.invoke("input")

        assert result == "primary response"
        mock_provider.invoke.assert_called_once_with("input")
        assert primary.successful_calls == 1

    def test_fallback_on_primary_failure(self):
        """Test fallback to secondary provider when primary fails."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary failed"))

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="fallback response")

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 1}  # No retries for faster test
        )

        result = manager.invoke("input")

        assert result == "fallback response"
        assert primary.failed_calls == 1
        assert fallback.successful_calls == 1

    def test_fallback_disabled(self):
        """Test that fallback doesn't occur when disabled."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary failed"))

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="fallback response")

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            fallback_enabled=False,
            retry_config={"max_attempts": 1}
        )

        with pytest.raises(ValueError) as exc_info:
            manager.invoke("input")

        assert "Primary failed" in str(exc_info.value)
        assert fallback.total_calls == 0  # Fallback not attempted

    def test_all_providers_fail(self):
        """Test AllProvidersFailedError when all providers fail."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary failed"))

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(side_effect=ValueError("Fallback failed"))

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 1}
        )

        with pytest.raises(AllProvidersFailedError) as exc_info:
            manager.invoke("input")

        assert "All 2 providers failed" in str(exc_info.value)
        assert len(exc_info.value.errors) == 2
        assert exc_info.value.errors[0]["provider"] == "primary"
        assert exc_info.value.errors[1]["provider"] == "fallback"

    def test_circuit_breaker_triggers_fallback(self):
        """Test that open circuit breaker triggers fallback."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Error"))

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="fallback response")

        cb = CircuitBreaker(failure_threshold=2)
        primary = ResilientLLMProvider(mock_primary, circuit_breaker=cb, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 1}
        )

        # Open the circuit breaker
        for _ in range(2):
            try:
                manager.invoke("input")
            except:
                pass

        assert cb.is_open

        # Next call should use fallback
        result = manager.invoke("input")
        assert result == "fallback response"

    def test_retry_with_exponential_backoff(self):
        """Test retry logic with exponential backoff."""
        mock_provider = Mock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Transient error")
            return "success"

        mock_provider.invoke = Mock(side_effect=side_effect)

        primary = ResilientLLMProvider(mock_provider, name="primary")

        manager = LLMProviderManager(
            primary=primary,
            retry_config={
                "max_attempts": 3,
                "exponential_backoff": True,
                "initial_delay": 0.1,
                "backoff_multiplier": 2
            }
        )

        result = manager.invoke("input")

        assert result == "success"
        assert call_count[0] == 3  # Should have retried 3 times

    def test_no_retry_on_circuit_breaker_open(self):
        """Test that circuit breaker open doesn't trigger retries."""
        mock_provider = Mock()
        mock_provider.invoke = Mock(side_effect=ValueError("Error"))

        cb = CircuitBreaker(failure_threshold=1)
        primary = ResilientLLMProvider(mock_provider, circuit_breaker=cb, name="primary")

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="fallback response")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 5}
        )

        # First call opens circuit
        result = manager.invoke("input")
        assert result == "fallback response"

        # Second call should immediately use fallback (no retries on primary)
        result = manager.invoke("input")
        assert result == "fallback response"

    def test_get_health_status(self):
        """Test health status reporting."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(return_value="success")

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="success")

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback]
        )

        # Make some calls
        manager.invoke("input")

        health = manager.get_health_status()

        assert "primary" in health
        assert "fallbacks" in health
        assert health["fallback_enabled"] is True
        assert health["total_providers"] == 2
        assert health["primary"]["name"] == "primary"
        assert len(health["fallbacks"]) == 1

    def test_get_active_provider(self):
        """Test getting the active provider."""
        mock_primary = Mock()
        primary = ResilientLLMProvider(mock_primary, name="primary")

        mock_fallback = Mock()
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback]
        )

        # Primary should be active initially
        active = manager.get_active_provider()
        assert active == primary

    def test_reset_all_metrics(self):
        """Test resetting metrics for all providers."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(return_value="success")

        primary = ResilientLLMProvider(mock_primary, name="primary")

        manager = LLMProviderManager(primary=primary)

        # Make some calls
        manager.invoke("input")
        assert primary.total_calls == 1

        # Reset metrics
        manager.reset_all_metrics()

        assert primary.total_calls == 0

    def test_reset_all_circuit_breakers(self):
        """Test resetting all circuit breakers."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Error"))

        cb = CircuitBreaker(failure_threshold=1)
        primary = ResilientLLMProvider(mock_primary, circuit_breaker=cb, name="primary")

        manager = LLMProviderManager(
            primary=primary,
            fallback_enabled=False,
            retry_config={"max_attempts": 1}
        )

        # Open the circuit
        try:
            manager.invoke("input")
        except:
            pass

        assert cb.is_open

        # Reset circuit breakers
        manager.reset_all_circuit_breakers()

        assert cb.is_closed

    def test_priority_ordering(self):
        """Test that fallbacks are tried in priority order."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary failed"))

        mock_fb1 = Mock()
        mock_fb1.invoke = Mock(side_effect=ValueError("FB1 failed"))

        mock_fb2 = Mock()
        mock_fb2.invoke = Mock(return_value="FB2 success")

        primary = ResilientLLMProvider(mock_primary, name="primary", priority=0)
        fb1 = ResilientLLMProvider(mock_fb1, name="fb1", priority=1)
        fb2 = ResilientLLMProvider(mock_fb2, name="fb2", priority=2)

        # Provide fallbacks in wrong order
        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fb2, fb1],  # Wrong order
            retry_config={"max_attempts": 1}
        )

        result = manager.invoke("input")

        # Should still try in priority order and succeed with FB2
        assert result == "FB2 success"
        assert fb1.failed_calls == 1
        assert fb2.successful_calls == 1

    def test_attribute_proxy_getattr(self):
        """Test that attributes are proxied to underlying provider."""
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.format = "json"

        primary = ResilientLLMProvider(mock_provider, name="primary")
        manager = LLMProviderManager(primary=primary)

        # Should proxy to underlying provider
        assert manager.model == "gpt-4"
        assert manager.format == "json"

    def test_attribute_proxy_setattr(self):
        """Test that attribute setting is proxied to underlying provider."""
        mock_provider = Mock()
        mock_provider.format = None

        primary = ResilientLLMProvider(mock_provider, name="primary")
        manager = LLMProviderManager(primary=primary)

        # Should proxy to underlying provider
        manager.format = "json"
        assert mock_provider.format == "json"

    def test_repr(self):
        """Test string representation."""
        mock_primary = Mock()
        primary = ResilientLLMProvider(mock_primary, name="primary")

        mock_fallback = Mock()
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback]
        )

        repr_str = repr(manager)

        assert "LLMProviderManager" in repr_str
        assert "primary" in repr_str
        assert "fallback" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
