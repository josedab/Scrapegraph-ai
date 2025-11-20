"""
LLM Provider Manager for handling multiple providers with automatic fallback.
"""

import time
import logging
from typing import List, Optional, Dict, Any

from .circuit_breaker import CircuitBreakerState
from .resilient_provider import ResilientLLMProvider
from .exceptions import CircuitBreakerOpenError, AllProvidersFailedError

logger = logging.getLogger(__name__)


class LLMProviderManager:
    """
    Manages multiple LLM providers with automatic fallback.

    This class orchestrates multiple LLM providers, implementing:
    - Automatic fallback on provider failure
    - Retry logic with exponential backoff
    - Circuit breaker integration
    - Health monitoring and reporting

    The manager attempts to use the primary provider first, falling back to
    configured alternatives if the primary fails or has its circuit breaker open.

    Attributes:
        primary: Primary LLM provider (wrapped in ResilientLLMProvider)
        fallbacks: List of fallback providers in priority order
        retry_config: Configuration for retry behavior
        health_check_config: Configuration for health monitoring
        fallback_enabled: Whether fallback mechanism is active
        all_providers: Combined list of all providers in priority order
    """

    def __init__(
        self,
        primary: ResilientLLMProvider,
        fallbacks: Optional[List[ResilientLLMProvider]] = None,
        retry_config: Optional[Dict] = None,
        health_check_config: Optional[Dict] = None,
        fallback_enabled: bool = True
    ):
        """
        Initialize LLMProviderManager.

        Args:
            primary: Primary resilient provider
            fallbacks: List of fallback providers (sorted by priority)
            retry_config: Retry configuration dict
            health_check_config: Health check configuration dict
            fallback_enabled: Enable/disable fallback mechanism
        """
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.retry_config = retry_config or {}
        self.health_check_config = health_check_config or {}
        self.fallback_enabled = fallback_enabled

        # All providers in priority order
        self.all_providers = [primary] + self.fallbacks

        logger.info(
            f"LLMProviderManager initialized with primary={primary.name}, "
            f"fallbacks={[fb.name for fb in self.fallbacks]}, "
            f"fallback_enabled={fallback_enabled}"
        )

    def invoke(self, *args, **kwargs) -> Any:
        """
        Invoke LLM with automatic fallback on failure.

        Attempts to invoke the primary provider first. If it fails or its
        circuit breaker is open, automatically tries fallback providers in
        priority order.

        Args:
            *args: Positional arguments for provider.invoke()
            **kwargs: Keyword arguments for provider.invoke()

        Returns:
            LLM response from the first successful provider

        Raises:
            AllProvidersFailedError: When all providers have failed
        """
        errors = []

        for provider in self.all_providers:
            try:
                logger.debug(f"Attempting provider: {provider.name}")
                result = self._invoke_with_retry(provider, *args, **kwargs)

                if provider != self.primary:
                    logger.warning(
                        f"Using fallback provider {provider.name} "
                        f"(primary {self.primary.name} unavailable)"
                    )

                return result

            except CircuitBreakerOpenError as e:
                logger.warning(
                    f"Provider {provider.name} circuit breaker is OPEN, "
                    f"trying next provider"
                )
                errors.append({
                    "provider": provider.name,
                    "error": "Circuit breaker open",
                    "details": str(e)
                })

                if not self.fallback_enabled:
                    raise AllProvidersFailedError(
                        f"Provider {provider.name} circuit breaker open and fallback disabled",
                        errors=errors
                    )

                continue

            except Exception as e:
                logger.error(
                    f"Provider {provider.name} failed: {type(e).__name__}: {e}"
                )
                errors.append({
                    "provider": provider.name,
                    "error": type(e).__name__,
                    "details": str(e)
                })

                if not self.fallback_enabled:
                    raise

                continue

        # All providers failed
        raise AllProvidersFailedError(
            f"All {len(self.all_providers)} providers failed",
            errors=errors
        )

    def _invoke_with_retry(
        self,
        provider: ResilientLLMProvider,
        *args,
        **kwargs
    ) -> Any:
        """
        Invoke provider with exponential backoff retry.

        Implements retry logic with configurable exponential backoff to handle
        transient failures.

        Args:
            provider: Provider to invoke
            *args: Positional arguments for provider.invoke()
            **kwargs: Keyword arguments for provider.invoke()

        Returns:
            Provider response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open (no retry)
            Exception: Last exception if all retries exhausted
        """
        max_attempts = self.retry_config.get("max_attempts", 3)
        exponential_backoff = self.retry_config.get("exponential_backoff", True)
        initial_delay = self.retry_config.get("initial_delay", 1)
        max_delay = self.retry_config.get("max_delay", 30)
        backoff_multiplier = self.retry_config.get("backoff_multiplier", 2)

        last_exception = None

        for attempt in range(max_attempts):
            try:
                return provider.invoke(*args, **kwargs)

            except CircuitBreakerOpenError:
                # Don't retry if circuit breaker is open
                raise

            except Exception as e:
                last_exception = e

                if attempt < max_attempts - 1:
                    if exponential_backoff:
                        delay = min(
                            initial_delay * (backoff_multiplier ** attempt),
                            max_delay
                        )
                    else:
                        delay = initial_delay

                    logger.info(
                        f"Attempt {attempt + 1}/{max_attempts} failed for "
                        f"provider {provider.name}, retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_attempts} attempts failed for "
                        f"provider {provider.name}"
                    )

        raise last_exception

    async def ainvoke(self, *args, **kwargs) -> Any:
        """
        Async version of invoke with fallback.

        Asynchronously attempts to invoke providers with automatic fallback.

        Args:
            *args: Positional arguments for provider.ainvoke()
            **kwargs: Keyword arguments for provider.ainvoke()

        Returns:
            LLM response from the first successful provider

        Raises:
            AllProvidersFailedError: When all providers have failed
        """
        import asyncio

        errors = []

        for provider in self.all_providers:
            try:
                logger.debug(f"Attempting async provider: {provider.name}")
                result = await self._ainvoke_with_retry(provider, *args, **kwargs)

                if provider != self.primary:
                    logger.warning(
                        f"Using fallback provider {provider.name} "
                        f"(primary {self.primary.name} unavailable)"
                    )

                return result

            except CircuitBreakerOpenError as e:
                logger.warning(
                    f"Provider {provider.name} circuit breaker is OPEN, "
                    f"trying next provider"
                )
                errors.append({
                    "provider": provider.name,
                    "error": "Circuit breaker open",
                    "details": str(e)
                })

                if not self.fallback_enabled:
                    raise AllProvidersFailedError(
                        f"Provider {provider.name} circuit breaker open and fallback disabled",
                        errors=errors
                    )

                continue

            except Exception as e:
                logger.error(
                    f"Provider {provider.name} async failed: {type(e).__name__}: {e}"
                )
                errors.append({
                    "provider": provider.name,
                    "error": type(e).__name__,
                    "details": str(e)
                })

                if not self.fallback_enabled:
                    raise

                continue

        # All providers failed
        raise AllProvidersFailedError(
            f"All {len(self.all_providers)} providers failed",
            errors=errors
        )

    async def _ainvoke_with_retry(
        self,
        provider: ResilientLLMProvider,
        *args,
        **kwargs
    ) -> Any:
        """
        Async invoke with exponential backoff retry.

        Args:
            provider: Provider to invoke
            *args: Positional arguments for provider.ainvoke()
            **kwargs: Keyword arguments for provider.ainvoke()

        Returns:
            Provider response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            Exception: Last exception if all retries exhausted
        """
        import asyncio

        max_attempts = self.retry_config.get("max_attempts", 3)
        exponential_backoff = self.retry_config.get("exponential_backoff", True)
        initial_delay = self.retry_config.get("initial_delay", 1)
        max_delay = self.retry_config.get("max_delay", 30)
        backoff_multiplier = self.retry_config.get("backoff_multiplier", 2)

        last_exception = None

        for attempt in range(max_attempts):
            try:
                return await provider.ainvoke(*args, **kwargs)

            except CircuitBreakerOpenError:
                raise

            except Exception as e:
                last_exception = e

                if attempt < max_attempts - 1:
                    if exponential_backoff:
                        delay = min(
                            initial_delay * (backoff_multiplier ** attempt),
                            max_delay
                        )
                    else:
                        delay = initial_delay

                    logger.info(
                        f"Async attempt {attempt + 1}/{max_attempts} failed for "
                        f"provider {provider.name}, retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {max_attempts} async attempts failed for "
                        f"provider {provider.name}"
                    )

        raise last_exception

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of all providers.

        Returns:
            Dictionary with health status for primary and all fallback providers
        """
        return {
            "primary": self.primary.health_status,
            "fallbacks": [fb.health_status for fb in self.fallbacks],
            "fallback_enabled": self.fallback_enabled,
            "total_providers": len(self.all_providers)
        }

    def get_active_provider(self) -> ResilientLLMProvider:
        """
        Get the currently active (healthy) provider.

        Returns the first provider with a closed circuit breaker, or the
        primary provider if all circuits are open.

        Returns:
            Active provider (likely to succeed)
        """
        for provider in self.all_providers:
            if provider.circuit_breaker.state == CircuitBreakerState.CLOSED:
                return provider

        # All circuits open, return primary (will likely fail fast)
        logger.warning("All circuit breakers are OPEN, returning primary provider")
        return self.primary

    def reset_all_metrics(self):
        """Reset metrics for all providers."""
        for provider in self.all_providers:
            provider.reset_metrics()
        logger.info("Reset metrics for all providers")

    def reset_all_circuit_breakers(self):
        """Manually reset all circuit breakers to CLOSED state."""
        for provider in self.all_providers:
            provider.circuit_breaker.reset()
        logger.info("Reset all circuit breakers to CLOSED")

    def __getattr__(self, name: str) -> Any:
        """
        Proxy attribute access to the underlying primary provider.

        This allows the manager to be transparent for attribute access,
        delegating to the actual LLM instance for attributes like
        'format', 'model', etc.

        Args:
            name: Attribute name

        Returns:
            Attribute value from primary provider

        Raises:
            AttributeError: If attribute doesn't exist
        """
        # Avoid infinite recursion for our own attributes
        if name in ('primary', 'fallbacks', 'retry_config', 'health_check_config',
                    'fallback_enabled', 'all_providers'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Delegate to the primary provider's underlying LLM instance
        try:
            return getattr(self.primary.provider, name)
        except AttributeError:
            raise AttributeError(
                f"'{type(self).__name__}' object and underlying provider have no attribute '{name}'"
            )

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Proxy attribute setting to the underlying primary provider.

        This allows setting attributes on the actual LLM instance through
        the manager, maintaining transparency.

        Args:
            name: Attribute name
            value: Value to set
        """
        # Set our own attributes normally
        if name in ('primary', 'fallbacks', 'retry_config', 'health_check_config',
                    'fallback_enabled', 'all_providers'):
            object.__setattr__(self, name, value)
        else:
            # Try to set on the primary provider's underlying LLM instance
            if hasattr(self, 'primary') and hasattr(self.primary, 'provider'):
                setattr(self.primary.provider, name, value)
            else:
                # During initialization, set normally
                object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        """String representation of the manager."""
        return (
            f"LLMProviderManager(primary={self.primary.name}, "
            f"fallbacks={[fb.name for fb in self.fallbacks]}, "
            f"fallback_enabled={self.fallback_enabled})"
        )
