"""
Circuit breaker implementation for preventing cascade failures.

Implements the circuit breaker pattern with three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail fast
- HALF_OPEN: Testing if provider has recovered
"""

import time
import logging
from enum import Enum
from threading import Lock
from typing import Callable, Any, TypeVar

from .exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Implements circuit breaker pattern to prevent cascade failures.

    The circuit breaker monitors calls to a function and transitions between
    states based on success/failure patterns:

    - CLOSED: Normal operation, all calls pass through
    - OPEN: After threshold failures, calls fail fast without execution
    - HALF_OPEN: After timeout, allows limited test calls to check recovery

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        success_threshold: Number of consecutive successes to close circuit from HALF_OPEN
        timeout: Seconds to wait before attempting recovery (transition to HALF_OPEN)
        half_open_max_calls: Maximum number of test calls allowed in HALF_OPEN state
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        half_open_max_calls: int = 1
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit (default: 5)
            success_threshold: Number of successes needed to close circuit (default: 2)
            timeout: Seconds before attempting recovery (default: 60)
            half_open_max_calls: Max test calls in HALF_OPEN state (default: 1)
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

        self._lock = Lock()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is OPEN and not ready for recovery
            Exception: Original exception from the function call
        """
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}"
                    )

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        "Circuit breaker in HALF_OPEN, max test calls reached"
                    )
                self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.

        Returns:
            True if timeout period has elapsed since last failure
        """
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.timeout

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.half_open_calls = 0
        logger.info("Circuit breaker transitioning to HALF_OPEN")

    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            self.failure_count = 0

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()

    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_closed(self):
        """Transition to CLOSED state (normal operation)."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("Circuit breaker CLOSED - provider recovered")

    def _transition_to_open(self):
        """Transition to OPEN state (failing fast)."""
        self.state = CircuitBreakerState.OPEN
        logger.warning(
            f"Circuit breaker OPEN - {self.failure_count} failures detected"
        )

    def reset(self):
        """
        Manually reset the circuit breaker to CLOSED state.

        This can be used for administrative intervention or testing.
        """
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            logger.info("Circuit breaker manually reset to CLOSED")

    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is in CLOSED state."""
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is in OPEN state."""
        return self.state == CircuitBreakerState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is in HALF_OPEN state."""
        return self.state == CircuitBreakerState.HALF_OPEN
