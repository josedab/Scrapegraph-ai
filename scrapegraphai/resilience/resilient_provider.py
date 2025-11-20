"""
Resilient LLM provider wrapper with circuit breaker and health monitoring.
"""

import time
import logging
from typing import Any, Dict, Optional

from .circuit_breaker import CircuitBreaker
from .exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class ResilientLLMProvider:
    """
    Wraps an LLM provider with circuit breaker and health monitoring.

    This class provides a resilient wrapper around any LLM provider, adding:
    - Circuit breaker protection
    - Health metrics tracking
    - Success/failure rate monitoring
    - Latency tracking

    Attributes:
        provider: The underlying LLM instance
        circuit_breaker: Circuit breaker for this provider
        name: Human-readable name for this provider
        priority: Priority level (lower = higher priority)
        total_calls: Total number of invocation attempts
        successful_calls: Number of successful invocations
        failed_calls: Number of failed invocations
        total_latency: Cumulative latency for successful calls
        last_success_time: Timestamp of last successful call
        last_failure_time: Timestamp of last failed call
        last_error: Most recent error message
    """

    def __init__(
        self,
        provider: Any,
        circuit_breaker: Optional[CircuitBreaker] = None,
        name: str = "unknown",
        priority: int = 0
    ):
        """
        Initialize ResilientLLMProvider.

        Args:
            provider: The underlying LLM provider instance
            circuit_breaker: Circuit breaker instance (creates default if None)
            name: Human-readable name for logging/monitoring
            priority: Priority level for provider selection (lower = higher priority)
        """
        self.provider = provider
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.name = name
        self.priority = priority

        # Health metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_latency = 0.0
        self.last_success_time = None
        self.last_failure_time = None
        self.last_error = None

    def invoke(self, *args, **kwargs) -> Any:
        """
        Invoke the LLM provider with circuit breaker protection.

        This method wraps the provider's invoke method with:
        - Circuit breaker protection
        - Performance metrics tracking
        - Error logging

        Args:
            *args: Positional arguments for provider.invoke()
            **kwargs: Keyword arguments for provider.invoke()

        Returns:
            Provider response

        Raises:
            CircuitBreakerOpenError: When circuit breaker is open
            Exception: Provider-specific exceptions
        """
        start_time = time.time()
        self.total_calls += 1

        try:
            result = self.circuit_breaker.call(
                self.provider.invoke,
                *args,
                **kwargs
            )

            # Track success metrics
            latency = time.time() - start_time
            self.successful_calls += 1
            self.total_latency += latency
            self.last_success_time = time.time()

            logger.debug(
                f"Provider {self.name} succeeded in {latency:.2f}s"
            )

            return result

        except CircuitBreakerOpenError:
            # Circuit breaker is open, don't count as provider failure
            self.total_calls -= 1  # Adjust count since call didn't reach provider
            logger.warning(
                f"Provider {self.name} circuit breaker is OPEN, call rejected"
            )
            raise

        except Exception as e:
            self.failed_calls += 1
            self.last_failure_time = time.time()
            self.last_error = str(e)

            logger.warning(
                f"Provider {self.name} failed: {type(e).__name__}: {e}"
            )
            raise

    async def ainvoke(self, *args, **kwargs) -> Any:
        """
        Async version of invoke.

        Invokes the LLM provider asynchronously with circuit breaker protection
        and metrics tracking.

        Args:
            *args: Positional arguments for provider.ainvoke()
            **kwargs: Keyword arguments for provider.ainvoke()

        Returns:
            Provider response

        Raises:
            CircuitBreakerOpenError: When circuit breaker is open
            Exception: Provider-specific exceptions
        """
        import asyncio

        start_time = time.time()
        self.total_calls += 1

        # Helper function for async circuit breaker call
        async def async_call():
            return await self.provider.ainvoke(*args, **kwargs)

        try:
            # Note: Circuit breaker's call method is synchronous
            # For async, we need to handle it differently
            if self.circuit_breaker.is_open:
                if not self.circuit_breaker._should_attempt_reset():
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Last failure: {self.circuit_breaker.last_failure_time}"
                    )

            result = await async_call()

            # Track success
            latency = time.time() - start_time
            self.successful_calls += 1
            self.total_latency += latency
            self.last_success_time = time.time()
            self.circuit_breaker._on_success()

            logger.debug(
                f"Provider {self.name} async succeeded in {latency:.2f}s"
            )

            return result

        except Exception as e:
            self.failed_calls += 1
            self.last_failure_time = time.time()
            self.last_error = str(e)
            self.circuit_breaker._on_failure()

            logger.warning(
                f"Provider {self.name} async failed: {type(e).__name__}: {e}"
            )
            raise

    @property
    def success_rate(self) -> float:
        """
        Calculate success rate.

        Returns:
            Success rate as a float between 0.0 and 1.0
        """
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def average_latency(self) -> float:
        """
        Calculate average latency for successful calls.

        Returns:
            Average latency in seconds
        """
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency / self.successful_calls

    @property
    def health_status(self) -> Dict[str, Any]:
        """
        Get current health status.

        Returns:
            Dictionary containing health metrics and status information
        """
        return {
            "name": self.name,
            "priority": self.priority,
            "circuit_state": self.circuit_breaker.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": f"{self.success_rate:.2%}",
            "average_latency": f"{self.average_latency:.2f}s",
            "last_success": self.last_success_time,
            "last_failure": self.last_failure_time,
            "last_error": self.last_error
        }

    def reset_metrics(self):
        """Reset all health metrics to initial state."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_latency = 0.0
        self.last_success_time = None
        self.last_failure_time = None
        self.last_error = None
        logger.info(f"Reset metrics for provider {self.name}")

    def __repr__(self) -> str:
        """String representation of the provider."""
        return (
            f"ResilientLLMProvider(name={self.name}, "
            f"priority={self.priority}, "
            f"state={self.circuit_breaker.state.value}, "
            f"success_rate={self.success_rate:.2%})"
        )
