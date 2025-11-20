# RFC-0002: Multi-Model Fallback with Circuit Breaker

## Metadata

| Field | Value |
|-------|-------|
| **RFC** | 0002 |
| **Title** | Multi-Model Fallback with Circuit Breaker |
| **Author** | ScrapeGraphAI Team |
| **Status** | Draft |
| **Created** | 2025-11-20 |
| **Updated** | 2025-11-20 |
| **Priority** | High |
| **Complexity** | Medium |

---

## Abstract

This RFC proposes implementing an automatic fallback mechanism with circuit breaker pattern to handle LLM provider failures gracefully. The current architecture in `abstract_graph.py` creates a single point of failure where any LLM API failure results in complete graph execution failure. This proposal introduces a resilient multi-model strategy that automatically falls back to alternative providers when the primary model fails, while using circuit breaker patterns to prevent cascade failures and retry storms.

---

## Motivation

### Problem Statement

The current implementation in `/home/user/Scrapegraph-ai/scrapegraphai/graphs/abstract_graph.py` has several critical limitations:

1. **Single Point of Failure**: The `_create_llm()` method (lines 117-277) initializes a single LLM instance. If this provider experiences:
   - Rate limiting
   - API outages
   - Network failures
   - Authentication issues

   The entire graph execution fails immediately.

2. **No Retry Logic**: There's no built-in retry mechanism or exponential backoff for transient failures.

3. **Cascade Failures**: When a primary provider fails, all concurrent requests fail simultaneously, potentially overwhelming fallback systems if implemented manually.

4. **User Experience Degradation**: Users must manually handle provider failures and reconfigure their graphs, leading to poor developer experience.

5. **Cost Optimization**: Cannot automatically fall back to cheaper providers when premium providers are unavailable or rate-limited.

### Current Code Analysis

```python
# abstract_graph.py, lines 117-277
def _create_llm(self, llm_config: dict) -> object:
    """
    Create a large language model instance based on the configuration provided.
    """
    # ... initialization code ...

    try:
        if llm_params["model_provider"] not in {...}:
            # Single provider initialization
            return init_chat_model(**llm_params)
        else:
            # Custom provider initialization
            # Still single instance - no fallback
            return ProviderClass(**llm_params)
    except Exception as e:
        # Fails immediately, no retry or fallback
        raise Exception(f"Error instancing model: {e}")
```

**Issues:**
- Single `try/except` with immediate failure propagation
- No fallback provider configuration
- No circuit breaker to prevent retry storms
- No health checking of providers

### Use Cases

1. **High Availability Applications**: Production systems requiring 99.9%+ uptime
2. **Cost Optimization**: Automatic fallback to cheaper providers during high load
3. **Rate Limit Management**: Distribute load across multiple providers
4. **Geographic Redundancy**: Fall back to regional providers when primary is unavailable
5. **Development/Testing**: Seamless fallback to local models when API quota is exhausted

---

## Proposed Solution

### Overview

Implement a three-tier resilience strategy:

1. **Primary Provider**: The user's configured LLM provider
2. **Fallback Chain**: Ordered list of alternative providers
3. **Circuit Breaker**: Pattern to prevent cascade failures and retry storms

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AbstractGraph                        │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │          LLMProviderManager                       │ │
│  │                                                   │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │ │
│  │  │  Primary    │  │  Fallback   │  │ Fallback │ │ │
│  │  │  Provider   │→ │  Provider 1 │→ │Provider 2│ │ │
│  │  │             │  │             │  │          │ │ │
│  │  │  ┌────────┐ │  │  ┌────────┐ │  │┌────────┐│ │ │
│  │  │  │Circuit │ │  │  │Circuit │ │  ││Circuit ││ │ │
│  │  │  │Breaker │ │  │  │Breaker │ │  ││Breaker ││ │ │
│  │  │  └────────┘ │  │  └────────┘ │  │└────────┘│ │ │
│  │  └─────────────┘  └─────────────┘  └──────────┘ │ │
│  │                                                   │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │         Health Check Monitor                │ │ │
│  │  │  - Periodic health checks                   │ │ │
│  │  │  - Failure rate tracking                    │ │ │
│  │  │  - Auto-recovery detection                  │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Components

#### 1. Circuit Breaker

Implements the circuit breaker pattern with three states:

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures, requests fail fast without hitting provider
- **HALF_OPEN**: Testing if provider has recovered

```python
class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """
    Circuit breaker to prevent cascade failures.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes needed to close circuit
        timeout: Seconds before attempting recovery (HALF_OPEN)
    """
```

#### 2. LLM Provider Wrapper

Wraps each LLM provider with monitoring and circuit breaker:

```python
class ResilientLLMProvider:
    """
    Wraps an LLM provider with circuit breaker and health monitoring.

    Attributes:
        provider: The underlying LLM instance
        circuit_breaker: Circuit breaker for this provider
        provider_config: Configuration dict
        health_status: Current health metrics
    """
```

#### 3. Provider Manager

Manages multiple providers and implements fallback logic:

```python
class LLMProviderManager:
    """
    Manages primary and fallback LLM providers.

    Features:
        - Automatic fallback on failure
        - Circuit breaker integration
        - Health monitoring
        - Provider priority management
    """
```

---

## Detailed Design

### Configuration Schema

Extend the current `config["llm"]` to support fallback providers:

```python
config = {
    "llm": {
        # Primary provider (existing)
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": "...",
        "temperature": 0.7,

        # NEW: Fallback configuration
        "fallback": {
            "enabled": True,
            "providers": [
                {
                    "model": "claude-3-sonnet",
                    "model_provider": "anthropic",
                    "api_key": "...",
                    "temperature": 0.7,
                    "priority": 1  # Lower = higher priority
                },
                {
                    "model": "mixtral-8x7b",
                    "model_provider": "groq",
                    "api_key": "...",
                    "temperature": 0.7,
                    "priority": 2
                }
            ],

            # Circuit breaker configuration
            "circuit_breaker": {
                "failure_threshold": 5,      # Open after 5 consecutive failures
                "success_threshold": 2,      # Close after 2 consecutive successes
                "timeout": 60,               # Try recovery after 60 seconds
                "half_open_max_calls": 1     # Only 1 test call in HALF_OPEN
            },

            # Retry configuration
            "retry": {
                "max_attempts": 3,
                "exponential_backoff": True,
                "initial_delay": 1,          # seconds
                "max_delay": 30,             # seconds
                "backoff_multiplier": 2
            },

            # Health check configuration
            "health_check": {
                "enabled": True,
                "interval": 300,             # Check every 5 minutes
                "timeout": 10                # Health check timeout
            }
        }
    }
}
```

### Implementation in AbstractGraph

Modify `abstract_graph.py`:

```python
class AbstractGraph(ABC):
    def __init__(self, prompt: str, config: dict, ...):
        # ... existing code ...

        # Replace single LLM with provider manager
        self.llm_model = self._create_llm_manager(config["llm"])

        # ... rest of initialization ...

    def _create_llm_manager(self, llm_config: dict) -> LLMProviderManager:
        """
        Create LLM provider manager with fallback support.

        Returns:
            LLMProviderManager: Manager handling primary and fallback providers
        """
        fallback_config = llm_config.get("fallback", {})

        if not fallback_config.get("enabled", False):
            # Backward compatibility: single provider
            return LLMProviderManager(
                primary=self._create_llm(llm_config),
                fallback_enabled=False
            )

        # Create primary provider
        primary = ResilientLLMProvider(
            provider=self._create_llm(llm_config),
            circuit_breaker=CircuitBreaker(**fallback_config.get("circuit_breaker", {})),
            name="primary"
        )

        # Create fallback providers
        fallbacks = []
        for fb_config in fallback_config.get("providers", []):
            fallback_llm = self._create_llm({**llm_config, **fb_config})
            fallbacks.append(
                ResilientLLMProvider(
                    provider=fallback_llm,
                    circuit_breaker=CircuitBreaker(**fallback_config.get("circuit_breaker", {})),
                    name=fb_config.get("model", "fallback"),
                    priority=fb_config.get("priority", 999)
                )
            )

        return LLMProviderManager(
            primary=primary,
            fallbacks=sorted(fallbacks, key=lambda x: x.priority),
            retry_config=fallback_config.get("retry", {}),
            health_check_config=fallback_config.get("health_check", {})
        )

    def _create_llm(self, llm_config: dict) -> object:
        """
        Create a single LLM instance (existing method).
        Keeps backward compatibility.
        """
        # Existing implementation unchanged
        # ... lines 117-277 stay the same ...
```

### Core Classes Implementation

#### CircuitBreaker Class

```python
import time
from enum import Enum
from threading import Lock
from typing import Callable, Any

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """
    Implements circuit breaker pattern to prevent cascade failures.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout  # seconds
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

        self._lock = Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is OPEN
            Exception: Original exception from function
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
        """Check if enough time has passed to attempt recovery."""
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

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN."""
    pass
```

#### ResilientLLMProvider Class

```python
from typing import Optional, Dict, Any
import time

class ResilientLLMProvider:
    """
    Wraps an LLM provider with circuit breaker and health monitoring.
    """

    def __init__(
        self,
        provider: Any,
        circuit_breaker: CircuitBreaker,
        name: str = "unknown",
        priority: int = 0
    ):
        self.provider = provider
        self.circuit_breaker = circuit_breaker
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

        except Exception as e:
            self.failed_calls += 1
            self.last_failure_time = time.time()
            self.last_error = str(e)

            logger.warning(
                f"Provider {self.name} failed: {e}"
            )
            raise

    async def ainvoke(self, *args, **kwargs) -> Any:
        """Async version of invoke."""
        # Similar implementation for async
        pass

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def average_latency(self) -> float:
        """Calculate average latency."""
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency / self.successful_calls

    @property
    def health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "name": self.name,
            "circuit_state": self.circuit_breaker.state.value,
            "total_calls": self.total_calls,
            "success_rate": f"{self.success_rate:.2%}",
            "average_latency": f"{self.average_latency:.2f}s",
            "last_success": self.last_success_time,
            "last_failure": self.last_failure_time,
            "last_error": self.last_error
        }
```

#### LLMProviderManager Class

```python
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class LLMProviderManager:
    """
    Manages multiple LLM providers with automatic fallback.
    """

    def __init__(
        self,
        primary: ResilientLLMProvider,
        fallbacks: Optional[List[ResilientLLMProvider]] = None,
        retry_config: Optional[Dict] = None,
        health_check_config: Optional[Dict] = None,
        fallback_enabled: bool = True
    ):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.retry_config = retry_config or {}
        self.health_check_config = health_check_config or {}
        self.fallback_enabled = fallback_enabled

        # All providers in priority order
        self.all_providers = [primary] + self.fallbacks

    def invoke(self, *args, **kwargs) -> Any:
        """
        Invoke LLM with automatic fallback on failure.

        Returns:
            LLM response

        Raises:
            AllProvidersFailedError: When all providers have failed
        """
        errors = []

        for provider in self.all_providers:
            try:
                logger.info(f"Attempting provider: {provider.name}")
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
                continue

            except Exception as e:
                logger.error(
                    f"Provider {provider.name} failed: {e}"
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
                        f"Attempt {attempt + 1}/{max_attempts} failed, "
                        f"retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_attempts} attempts failed for "
                        f"provider {provider.name}"
                    )

        raise last_exception

    async def ainvoke(self, *args, **kwargs) -> Any:
        """Async version of invoke with fallback."""
        # Similar implementation for async
        pass

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all providers."""
        return {
            "primary": self.primary.health_status,
            "fallbacks": [fb.health_status for fb in self.fallbacks],
            "fallback_enabled": self.fallback_enabled
        }

    def get_active_provider(self) -> ResilientLLMProvider:
        """Get the currently active (healthy) provider."""
        for provider in self.all_providers:
            if provider.circuit_breaker.state == CircuitBreakerState.CLOSED:
                return provider

        # All circuits open, return primary (will likely fail fast)
        return self.primary

class AllProvidersFailedError(Exception):
    """Raised when all providers have failed."""

    def __init__(self, message: str, errors: List[Dict]):
        super().__init__(message)
        self.errors = errors
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)

**Tasks:**
1. Implement `CircuitBreaker` class
2. Implement `ResilientLLMProvider` wrapper
3. Add comprehensive unit tests
4. Update `abstract_graph.py` to support backward compatibility

**Deliverables:**
- Circuit breaker with all three states (CLOSED, OPEN, HALF_OPEN)
- Provider wrapper with health metrics
- 90%+ test coverage

### Phase 2: Provider Manager (Week 2-3)

**Tasks:**
1. Implement `LLMProviderManager` class
2. Add retry logic with exponential backoff
3. Integrate with existing `_create_llm()` method
4. Add configuration schema validation

**Deliverables:**
- Working fallback mechanism
- Retry logic with configurable backoff
- Configuration validation

### Phase 3: Integration & Testing (Week 3-4)

**Tasks:**
1. Update all graph classes to use new manager
2. Add integration tests with real providers
3. Performance testing and optimization
4. Documentation updates

**Deliverables:**
- All graphs using new system
- Integration test suite
- Performance benchmarks
- Updated documentation

### Phase 4: Monitoring & Observability (Week 4-5)

**Tasks:**
1. Add health check endpoints
2. Implement metrics collection
3. Add logging and tracing
4. Create monitoring dashboard templates

**Deliverables:**
- Health check API
- Prometheus/OpenTelemetry metrics
- Structured logging
- Grafana dashboard examples

### Phase 5: Advanced Features (Week 5-6)

**Tasks:**
1. Smart provider selection (cost, latency optimization)
2. Provider health scoring
3. Automatic provider discovery
4. Load balancing across providers

**Deliverables:**
- Cost-aware fallback
- Health-based routing
- Provider auto-discovery
- Round-robin load balancing

---

## Migration Guide

### Backward Compatibility

The implementation maintains 100% backward compatibility:

```python
# Existing code continues to work unchanged
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai"
    }
}

graph = SmartScraperGraph(prompt, config)  # Works as before
```

### Enabling Fallback

To enable fallback, simply add configuration:

```python
# Opt-in to fallback mechanism
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",

        # Add fallback configuration
        "fallback": {
            "enabled": True,
            "providers": [
                {
                    "model": "claude-3-sonnet",
                    "model_provider": "anthropic"
                }
            ]
        }
    }
}
```

### Migration Steps

1. **No Action Required**: Existing code works without changes
2. **Optional Enhancement**: Add fallback providers to critical production graphs
3. **Recommended**: Configure circuit breaker thresholds based on your SLAs
4. **Advanced**: Enable health monitoring and metrics collection

---

## Alternatives Considered

### Alternative 1: Retry-Only Approach

**Description:** Only implement retry logic without fallback providers.

**Pros:**
- Simpler implementation
- Lower configuration complexity
- Works for transient failures

**Cons:**
- Doesn't handle prolonged outages
- No cost optimization
- No geographic redundancy
- Still single point of failure

**Decision:** Rejected - insufficient resilience

### Alternative 2: Manual Provider Switching

**Description:** Let users implement their own fallback logic.

**Pros:**
- Maximum flexibility
- No framework overhead
- Users control exact behavior

**Cons:**
- Inconsistent implementations
- Duplicated code across projects
- Poor developer experience
- No circuit breaker protection

**Decision:** Rejected - poor UX, missing critical patterns

### Alternative 3: External Service Mesh

**Description:** Use Istio/Linkerd for retry and circuit breaking.

**Pros:**
- Battle-tested implementations
- Infrastructure-level solution
- Language agnostic

**Cons:**
- Requires Kubernetes/service mesh infrastructure
- Overkill for Python library
- Doesn't handle provider-specific logic
- Complex deployment

**Decision:** Rejected - not suitable for library use

### Alternative 4: Provider Pooling

**Description:** Maintain pool of active connections to multiple providers.

**Pros:**
- Faster failover (connections already established)
- Can load balance requests

**Cons:**
- Higher resource consumption
- Complex state management
- Credential management challenges
- Connection pooling overhead

**Decision:** Considered for future enhancement

---

## Security Considerations

### API Key Management

**Risk:** Multiple provider credentials in configuration

**Mitigation:**
- Support environment variable references
- Integrate with secret management systems (AWS Secrets Manager, HashiCorp Vault)
- Never log API keys
- Clear documentation on credential security

```python
config = {
    "llm": {
        "api_key": "${OPENAI_API_KEY}",  # Environment variable
        "fallback": {
            "providers": [
                {
                    "api_key": "${ANTHROPIC_API_KEY}"  # Environment variable
                }
            ]
        }
    }
}
```

### Credential Leakage in Logs

**Risk:** Errors might expose API keys in stack traces

**Mitigation:**
- Sanitize all log output
- Redact sensitive fields in error messages
- Use structured logging with field filtering

### Provider Trust

**Risk:** Fallback provider may have different security posture

**Mitigation:**
- Document security implications of each provider
- Allow users to specify security-tier requirements
- Audit logging of which provider handled each request

### Data Exposure

**Risk:** Sensitive prompts sent to multiple providers during failover

**Mitigation:**
- Clear documentation about data flow
- Option to disable fallback for sensitive workloads
- Compliance-aware provider selection

---

## Performance Considerations

### Latency Impact

**Concern:** Additional overhead from circuit breaker and health checks

**Analysis:**
- Circuit breaker: ~0.1ms overhead per call (negligible)
- Health metrics: ~0.05ms overhead per call
- Total overhead: <1% of typical LLM API call (2-10s)

**Mitigation:**
- Lazy initialization of fallback providers
- Async health checks
- Efficient state management

### Memory Overhead

**Concern:** Multiple provider instances in memory

**Analysis:**
- Primary provider: Already in memory
- Each fallback: ~5-10 MB per provider instance
- Circuit breaker: ~1 KB per provider
- Total for 3 providers: ~15-30 MB

**Mitigation:**
- Lazy loading of fallback providers
- Shared connection pools
- Configurable provider limits

### Network Overhead

**Concern:** Health checks and retries increase network traffic

**Mitigation:**
- Configurable health check intervals (default: 5 minutes)
- Circuit breaker prevents retry storms
- Exponential backoff limits retry frequency

---

## Monitoring & Observability

### Metrics to Track

```python
# Provider-level metrics
- llm.provider.calls.total
- llm.provider.calls.success
- llm.provider.calls.failure
- llm.provider.latency
- llm.provider.circuit_breaker.state

# Fallback metrics
- llm.fallback.triggered.total
- llm.fallback.success.total
- llm.provider.active  # Which provider is active

# Circuit breaker metrics
- llm.circuit_breaker.open.total
- llm.circuit_breaker.half_open.total
- llm.circuit_breaker.closed.total
```

### Logging Strategy

```python
# INFO level
logger.info(f"Using fallback provider {provider.name}")
logger.info(f"Circuit breaker CLOSED - provider recovered")

# WARNING level
logger.warning(f"Provider {provider.name} circuit breaker is OPEN")
logger.warning(f"All retry attempts exhausted for {provider.name}")

# ERROR level
logger.error(f"All providers failed: {errors}")
```

### Health Check Endpoint

```python
# GET /health/llm
{
    "status": "healthy",
    "primary": {
        "name": "openai/gpt-4",
        "circuit_state": "closed",
        "success_rate": "98.5%",
        "average_latency": "2.3s"
    },
    "fallbacks": [
        {
            "name": "anthropic/claude-3",
            "circuit_state": "closed",
            "success_rate": "99.1%",
            "average_latency": "1.8s"
        }
    ]
}
```

---

## Testing Strategy

### Unit Tests

```python
class TestCircuitBreaker:
    def test_closed_state_allows_calls()
    def test_opens_after_threshold_failures()
    def test_transitions_to_half_open_after_timeout()
    def test_closes_after_successful_recovery()
    def test_thread_safety()

class TestResilientLLMProvider:
    def test_successful_invocation()
    def test_circuit_breaker_integration()
    def test_health_metrics_tracking()

class TestLLMProviderManager:
    def test_primary_provider_success()
    def test_fallback_on_primary_failure()
    def test_all_providers_failure()
    def test_retry_with_exponential_backoff()
    def test_circuit_breaker_prevents_retry_storm()
```

### Integration Tests

```python
class TestMultiProviderFallback:
    def test_real_openai_to_anthropic_fallback()
    def test_circuit_breaker_recovery_cycle()
    def test_concurrent_requests_with_fallback()
    def test_health_check_monitoring()
```

### Load Tests

- Simulate provider outages under load
- Measure fallback latency
- Test circuit breaker behavior with concurrent requests
- Verify no resource leaks during extended failover

---

## Documentation Requirements

1. **User Guide**: How to configure fallback providers
2. **API Reference**: All new classes and methods
3. **Migration Guide**: Upgrading existing code
4. **Best Practices**: Recommended configurations for different scenarios
5. **Troubleshooting**: Common issues and solutions
6. **Examples**: Sample configurations for various use cases

---

## Success Metrics

### Reliability Metrics

- **Target:** 99.9% graph execution success rate (up from ~95%)
- **Metric:** Reduction in complete graph failures
- **Measurement:** Monitor `AllProvidersFailedError` exceptions

### Performance Metrics

- **Target:** <5% latency overhead for happy path
- **Metric:** P50, P95, P99 latency with fallback enabled
- **Measurement:** Compare against baseline without fallback

### Cost Metrics

- **Target:** Configurable cost optimization via smart fallback
- **Metric:** Average cost per request with fallback
- **Measurement:** Track provider usage distribution

### Developer Experience

- **Target:** Zero breaking changes
- **Metric:** Existing test suite passes without modification
- **Measurement:** Run full test suite on new implementation

---

## Dependencies

### New Dependencies

None - implementation uses only standard library and existing dependencies:
- `threading` (standard library)
- `time` (standard library)
- `enum` (standard library)
- `typing` (standard library)

### Existing Dependencies

- `langchain` - for LLM initialization
- `pydantic` - for configuration validation

---

## Risks & Mitigation

### Risk 1: Increased Complexity

**Impact:** Medium
**Probability:** High
**Mitigation:**
- Maintain backward compatibility (opt-in feature)
- Comprehensive documentation
- Clear configuration examples
- Sensible defaults

### Risk 2: Circuit Breaker False Positives

**Impact:** Medium
**Probability:** Low
**Mitigation:**
- Configurable thresholds
- HALF_OPEN state for testing recovery
- Detailed logging for debugging
- Manual circuit reset capability

### Risk 3: Credential Management

**Impact:** High
**Probability:** Low
**Mitigation:**
- Support for secret management systems
- Environment variable integration
- Clear security documentation
- Credential sanitization in logs

### Risk 4: Unexpected Behavior Differences

**Impact:** Medium
**Probability:** Medium
**Mitigation:**
- Document provider compatibility
- Validation of provider responses
- Option to validate response structure
- Fallback provider testing recommendations

---

## Future Enhancements

### Short-term (v2)

1. **Smart Provider Selection**: Choose provider based on:
   - Cost optimization
   - Latency requirements
   - Geographic proximity
   - Success rate history

2. **Provider Health Scoring**: Composite score based on:
   - Circuit breaker state
   - Success rate
   - Average latency
   - Recent failures

3. **Request-level Fallback Control**:
   ```python
   graph.run(
       fallback_strategy="cost_optimized",  # or "fastest", "most_reliable"
       max_cost_per_request=0.05
   )
   ```

### Medium-term (v3)

1. **Load Balancing**: Distribute requests across multiple providers
2. **A/B Testing**: Compare provider output quality
3. **Cost Analytics**: Detailed cost tracking per provider
4. **Provider Marketplace**: Easy integration of new providers

### Long-term (v4)

1. **ML-based Provider Selection**: Learn optimal provider based on request patterns
2. **Automatic Provider Discovery**: Detect and integrate new compatible providers
3. **Federated Execution**: Split complex graphs across multiple providers
4. **Provider Quality Metrics**: Track and compare output quality

---

## References

### Design Patterns

- [Circuit Breaker Pattern - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Retry Pattern - Microsoft](https://docs.microsoft.com/en-us/azure/architecture/patterns/retry)
- [Bulkhead Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/bulkhead)

### Implementations

- [Polly - .NET Resilience Library](https://github.com/App-vNext/Polly)
- [Resilience4j - Java](https://github.com/resilience4j/resilience4j)
- [PyBreaker - Python Circuit Breaker](https://github.com/danielfm/pybreaker)

### Related RFCs

- RFC-0001: LLM Response Caching (referenced in metrics-summary.md)
- RFC-0005: Parallel Node Execution (referenced in metrics-summary.md)

---

## Appendix

### Example: Complete Configuration

```python
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": {
        # Primary provider
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": "${OPENAI_API_KEY}",
        "temperature": 0.7,

        # Fallback configuration
        "fallback": {
            "enabled": True,

            # Fallback providers in priority order
            "providers": [
                {
                    "model": "claude-3-sonnet-20240229",
                    "model_provider": "anthropic",
                    "api_key": "${ANTHROPIC_API_KEY}",
                    "temperature": 0.7,
                    "priority": 1
                },
                {
                    "model": "mixtral-8x7b-32768",
                    "model_provider": "groq",
                    "api_key": "${GROQ_API_KEY}",
                    "temperature": 0.7,
                    "priority": 2
                },
                {
                    "model": "llama3-70b",
                    "model_provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "temperature": 0.7,
                    "priority": 3
                }
            ],

            # Circuit breaker configuration
            "circuit_breaker": {
                "failure_threshold": 5,
                "success_threshold": 2,
                "timeout": 60,
                "half_open_max_calls": 1
            },

            # Retry configuration
            "retry": {
                "max_attempts": 3,
                "exponential_backoff": True,
                "initial_delay": 1,
                "max_delay": 30,
                "backoff_multiplier": 2
            },

            # Health check configuration
            "health_check": {
                "enabled": True,
                "interval": 300,
                "timeout": 10
            }
        }
    },
    "verbose": True,
    "headless": True
}

# Create graph with multi-provider fallback
graph = SmartScraperGraph(
    prompt="Extract all article titles",
    source="https://example.com",
    config=config
)

# Run with automatic fallback
result = graph.run()

# Check which provider was used
health = graph.llm_model.get_health_status()
print(f"Active provider: {health['primary']['name']}")
```

### Example: Monitoring Integration

```python
from prometheus_client import Counter, Histogram, Gauge

# Prometheus metrics
llm_calls_total = Counter(
    'llm_calls_total',
    'Total LLM calls',
    ['provider', 'status']
)

llm_latency = Histogram(
    'llm_latency_seconds',
    'LLM call latency',
    ['provider']
)

llm_circuit_state = Gauge(
    'llm_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)',
    ['provider']
)

# Integration in ResilientLLMProvider
class ResilientLLMProvider:
    def invoke(self, *args, **kwargs):
        start = time.time()
        try:
            result = self.circuit_breaker.call(...)
            llm_calls_total.labels(provider=self.name, status='success').inc()
            llm_latency.labels(provider=self.name).observe(time.time() - start)
            return result
        except Exception as e:
            llm_calls_total.labels(provider=self.name, status='failure').inc()
            raise
```

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-20 | 0.1 | Initial draft |

---

## Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| **Author** | ScrapeGraphAI Team | ✅ Draft | 2025-11-20 |
| **Reviewer** | TBD | ⏳ Pending | - |
| **Approver** | TBD | ⏳ Pending | - |

---

**Status**: 📝 **Draft** - Ready for Review
