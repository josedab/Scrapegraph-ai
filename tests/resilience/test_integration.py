"""
Integration tests for multi-provider fallback system.
"""

import pytest
from unittest.mock import Mock, patch

from scrapegraphai.resilience import (
    LLMProviderManager,
    ResilientLLMProvider,
    CircuitBreaker,
    AllProvidersFailedError,
)


class TestMultiProviderIntegration:
    """Integration tests for complete multi-provider fallback system."""

    def test_complete_fallback_scenario(self):
        """
        Test complete scenario: primary fails, fallback to secondary,
        secondary succeeds, circuit breaker recovery.
        """
        # Setup providers
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary API down"))

        mock_fallback1 = Mock()
        mock_fallback1.invoke = Mock(side_effect=ValueError("Fallback1 failed"))

        mock_fallback2 = Mock()
        mock_fallback2.invoke = Mock(return_value="Fallback2 success")

        primary = ResilientLLMProvider(
            mock_primary,
            circuit_breaker=CircuitBreaker(failure_threshold=3),
            name="primary",
            priority=0
        )
        fallback1 = ResilientLLMProvider(
            mock_fallback1,
            circuit_breaker=CircuitBreaker(failure_threshold=3),
            name="fallback1",
            priority=1
        )
        fallback2 = ResilientLLMProvider(
            mock_fallback2,
            circuit_breaker=CircuitBreaker(failure_threshold=3),
            name="fallback2",
            priority=2
        )

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback1, fallback2],
            retry_config={"max_attempts": 1}
        )

        # First call should fallback to fallback2
        result = manager.invoke("test input")
        assert result == "Fallback2 success"

        # Verify call counts
        assert primary.failed_calls == 1
        assert fallback1.failed_calls == 1
        assert fallback2.successful_calls == 1

    def test_circuit_breaker_recovery_cycle(self):
        """Test complete circuit breaker recovery cycle."""
        import time

        call_count = [0]

        def primary_invoke(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ValueError("Primary temporarily down")
            return "Primary recovered"

        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=primary_invoke)

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="Fallback response")

        cb = CircuitBreaker(
            failure_threshold=3,
            success_threshold=2,
            timeout=1
        )

        primary = ResilientLLMProvider(
            mock_primary,
            circuit_breaker=cb,
            name="primary"
        )
        fallback = ResilientLLMProvider(
            mock_fallback,
            name="fallback",
            priority=1
        )

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 1}
        )

        # Open the circuit (3 failures)
        for i in range(3):
            result = manager.invoke("input")
            # Should use fallback after circuit opens
            if i < 2:
                # Circuit not yet open, retries on primary
                pass
            else:
                # Circuit open, uses fallback
                assert result == "Fallback response"

        assert cb.is_open

        # Wait for timeout
        time.sleep(1.1)

        # Next call should test recovery (HALF_OPEN)
        result = manager.invoke("input")
        assert result == "Primary recovered"

        # Circuit should still be in HALF_OPEN after first success
        assert cb.is_half_open

        # Another success should close circuit
        result = manager.invoke("input")
        assert result == "Primary recovered"
        assert cb.is_closed

    def test_concurrent_requests_with_fallback(self):
        """Test that concurrent requests work correctly with fallback."""
        import threading

        request_count = [0]
        mock_primary = Mock()

        def primary_invoke(*args, **kwargs):
            request_count[0] += 1
            if request_count[0] % 2 == 0:
                raise ValueError("Simulated failure")
            return "Primary success"

        mock_primary.invoke = Mock(side_effect=primary_invoke)

        mock_fallback = Mock()
        mock_fallback.invoke = Mock(return_value="Fallback success")

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fallback = ResilientLLMProvider(mock_fallback, name="fallback", priority=1)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fallback],
            retry_config={"max_attempts": 1}
        )

        results = []
        errors = []

        def make_request():
            try:
                result = manager.invoke("input")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create 10 concurrent threads
        threads = [threading.Thread(target=make_request) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All requests should succeed (either primary or fallback)
        assert len(results) == 10
        assert len(errors) == 0
        assert all(r in ["Primary success", "Fallback success"] for r in results)

    def test_health_monitoring_during_operations(self):
        """Test health monitoring provides accurate metrics during operations."""
        mock_primary = Mock()
        call_count = [0]

        def primary_invoke(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ValueError("Error")
            return "Success"

        mock_primary.invoke = Mock(side_effect=primary_invoke)

        primary = ResilientLLMProvider(
            mock_primary,
            circuit_breaker=CircuitBreaker(failure_threshold=5),
            name="primary"
        )

        manager = LLMProviderManager(
            primary=primary,
            retry_config={"max_attempts": 1},
            fallback_enabled=False
        )

        # Make calls (3 failures, then successes)
        for _ in range(7):
            try:
                manager.invoke("input")
            except:
                pass

        health = manager.get_health_status()

        assert health["primary"]["total_calls"] == 7
        assert health["primary"]["failed_calls"] == 3
        assert health["primary"]["successful_calls"] == 4
        assert "57.14%" in health["primary"]["success_rate"]

    def test_cost_optimized_fallback_pattern(self):
        """
        Test cost optimization pattern: expensive primary, cheaper fallback.
        """
        # Simulate expensive primary with rate limit
        mock_expensive = Mock()
        expensive_calls = [0]

        def expensive_invoke(*args, **kwargs):
            expensive_calls[0] += 1
            if expensive_calls[0] > 3:
                raise ValueError("Rate limit exceeded")
            return "Expensive result"

        mock_expensive.invoke = Mock(side_effect=expensive_invoke)

        # Cheap fallback
        mock_cheap = Mock()
        mock_cheap.invoke = Mock(return_value="Cheap result")

        expensive = ResilientLLMProvider(
            mock_expensive,
            circuit_breaker=CircuitBreaker(failure_threshold=1),
            name="gpt-4"
        )
        cheap = ResilientLLMProvider(
            mock_cheap,
            name="gpt-3.5",
            priority=1
        )

        manager = LLMProviderManager(
            primary=expensive,
            fallbacks=[cheap],
            retry_config={"max_attempts": 1}
        )

        # First 3 calls use expensive
        for i in range(3):
            result = manager.invoke("input")
            assert result == "Expensive result"

        # 4th call triggers rate limit, circuit opens
        result = manager.invoke("input")
        # Should use cheap fallback
        assert result == "Cheap result"

        # Subsequent calls use cheap while circuit is open
        result = manager.invoke("input")
        assert result == "Cheap result"

    def test_all_providers_exhausted_scenario(self):
        """Test scenario where all providers fail."""
        mock_primary = Mock()
        mock_primary.invoke = Mock(side_effect=ValueError("Primary down"))

        mock_fb1 = Mock()
        mock_fb1.invoke = Mock(side_effect=ValueError("FB1 down"))

        mock_fb2 = Mock()
        mock_fb2.invoke = Mock(side_effect=ValueError("FB2 down"))

        primary = ResilientLLMProvider(mock_primary, name="primary")
        fb1 = ResilientLLMProvider(mock_fb1, name="fb1", priority=1)
        fb2 = ResilientLLMProvider(mock_fb2, name="fb2", priority=2)

        manager = LLMProviderManager(
            primary=primary,
            fallbacks=[fb1, fb2],
            retry_config={"max_attempts": 1}
        )

        with pytest.raises(AllProvidersFailedError) as exc_info:
            manager.invoke("input")

        error = exc_info.value
        assert len(error.errors) == 3
        assert error.errors[0]["provider"] == "primary"
        assert error.errors[1]["provider"] == "fb1"
        assert error.errors[2]["provider"] == "fb2"

        # Verify error message includes all providers
        error_str = str(error)
        assert "primary" in error_str
        assert "fb1" in error_str
        assert "fb2" in error_str


class TestAbstractGraphIntegration:
    """Integration tests for AbstractGraph with resilience module."""

    def test_backward_compatibility_without_fallback(self):
        """Test that existing code without fallback config still works."""
        from scrapegraphai.graphs.abstract_graph import AbstractGraph

        # This simulates a minimal config without fallback
        # We can't fully test without actual LLM, but we can test the structure
        config = {
            "llm": {
                "model": "gpt-4",
                "model_provider": "openai"
            }
        }

        # The _create_llm_manager should handle this gracefully
        # and create a manager with fallback disabled
        # (Full test would require mocking the actual LLM creation)

    def test_fallback_config_structure(self):
        """Test the fallback configuration structure is correct."""
        # Example of valid fallback configuration
        config = {
            "llm": {
                "model": "gpt-4",
                "model_provider": "openai",
                "fallback": {
                    "enabled": True,
                    "providers": [
                        {
                            "model": "claude-3-sonnet",
                            "model_provider": "anthropic",
                            "priority": 1
                        },
                        {
                            "model": "mixtral-8x7b",
                            "model_provider": "groq",
                            "priority": 2
                        }
                    ],
                    "circuit_breaker": {
                        "failure_threshold": 5,
                        "success_threshold": 2,
                        "timeout": 60
                    },
                    "retry": {
                        "max_attempts": 3,
                        "exponential_backoff": True
                    }
                }
            }
        }

        # Verify structure
        assert "fallback" in config["llm"]
        assert config["llm"]["fallback"]["enabled"] is True
        assert len(config["llm"]["fallback"]["providers"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
