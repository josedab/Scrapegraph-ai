"""
Custom exceptions for the resilience module.
"""

from typing import List, Dict, Any


class CircuitBreakerOpenError(Exception):
    """
    Raised when circuit breaker is in OPEN state and rejects a call.

    This exception indicates that a provider has experienced too many failures
    and the circuit breaker is preventing further calls to avoid cascading failures.
    """

    pass


class AllProvidersFailedError(Exception):
    """
    Raised when all configured LLM providers have failed.

    This exception aggregates errors from all attempted providers and indicates
    that no fallback options remain.

    Attributes:
        errors: List of error details from each provider attempt
    """

    def __init__(self, message: str, errors: List[Dict[str, Any]]):
        """
        Initialize AllProvidersFailedError.

        Args:
            message: Error message
            errors: List of dictionaries containing provider error details
        """
        super().__init__(message)
        self.errors = errors

    def __str__(self):
        """Return formatted error message with details from all providers."""
        base_msg = super().__str__()
        error_details = "\n".join(
            f"  - {err['provider']}: {err['error']} - {err['details']}"
            for err in self.errors
        )
        return f"{base_msg}\n\nProvider errors:\n{error_details}"
