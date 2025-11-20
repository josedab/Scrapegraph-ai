# Multi-Model Fallback with Circuit Breaker

## Overview

The Multi-Model Fallback system provides automatic resilience for LLM operations in ScrapeGraphAI. When your primary LLM provider fails, the system automatically falls back to alternative providers, ensuring high availability and reliability.

## Key Features

- **Automatic Fallback**: Seamlessly switch to backup providers when the primary fails
- **Circuit Breaker Pattern**: Prevent cascade failures and retry storms
- **Exponential Backoff**: Intelligent retry logic for transient failures
- **Health Monitoring**: Track success rates, latency, and provider health
- **Zero Breaking Changes**: Fully backward compatible with existing code

## Quick Start

### Basic Usage (No Fallback)

Existing code continues to work without any changes:

```python
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": "your-api-key"
    }
}

graph = SmartScraperGraph(
    prompt="Extract all article titles",
    source="https://example.com",
    config=config
)

result = graph.run()
```

### Enabling Fallback

Add fallback providers to your configuration:

```python
config = {
    "llm": {
        # Primary provider
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": "your-openai-key",

        # Enable fallback
        "fallback": {
            "enabled": True,

            # Fallback providers (in priority order)
            "providers": [
                {
                    "model": "claude-3-sonnet-20240229",
                    "model_provider": "anthropic",
                    "api_key": "your-anthropic-key",
                    "priority": 1
                },
                {
                    "model": "mixtral-8x7b-32768",
                    "model_provider": "groq",
                    "api_key": "your-groq-key",
                    "priority": 2
                }
            ]
        }
    }
}

graph = SmartScraperGraph(
    prompt="Extract all article titles",
    source="https://example.com",
    config=config
)

result = graph.run()
```

If OpenAI fails, the system automatically tries Anthropic, then Groq.

## Configuration Reference

### Full Configuration Example

```python
config = {
    "llm": {
        # Primary provider configuration
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": "your-openai-key",
        "temperature": 0.7,

        # Fallback configuration
        "fallback": {
            "enabled": True,

            # Fallback providers
            "providers": [
                {
                    "model": "claude-3-sonnet-20240229",
                    "model_provider": "anthropic",
                    "api_key": "your-anthropic-key",
                    "temperature": 0.7,
                    "priority": 1  # Lower = higher priority
                },
                {
                    "model": "mixtral-8x7b-32768",
                    "model_provider": "groq",
                    "api_key": "your-groq-key",
                    "temperature": 0.7,
                    "priority": 2
                },
                {
                    # Local fallback (no API key needed)
                    "model": "llama3",
                    "model_provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "temperature": 0.7,
                    "priority": 3
                }
            ],

            # Circuit breaker settings
            "circuit_breaker": {
                "failure_threshold": 5,      # Open after 5 consecutive failures
                "success_threshold": 2,      # Close after 2 consecutive successes
                "timeout": 60,               # Try recovery after 60 seconds
                "half_open_max_calls": 1     # Test with 1 call in HALF_OPEN state
            },

            # Retry settings
            "retry": {
                "max_attempts": 3,           # Retry up to 3 times
                "exponential_backoff": True, # Use exponential backoff
                "initial_delay": 1,          # Start with 1 second delay
                "max_delay": 30,             # Max 30 seconds delay
                "backoff_multiplier": 2      # Double delay each retry
            },

            # Health check settings
            "health_check": {
                "enabled": True,
                "interval": 300,             # Check every 5 minutes
                "timeout": 10                # Health check timeout
            }
        }
    }
}
```

### Configuration Parameters

#### Fallback Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `False` | Enable/disable fallback mechanism |
| `providers` | list | `[]` | List of fallback provider configurations |

#### Circuit Breaker Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `failure_threshold` | int | `5` | Number of failures before opening circuit |
| `success_threshold` | int | `2` | Number of successes to close circuit |
| `timeout` | int | `60` | Seconds before attempting recovery |
| `half_open_max_calls` | int | `1` | Max test calls in HALF_OPEN state |

#### Retry Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | int | `3` | Maximum retry attempts |
| `exponential_backoff` | bool | `True` | Use exponential backoff |
| `initial_delay` | int | `1` | Initial delay in seconds |
| `max_delay` | int | `30` | Maximum delay in seconds |
| `backoff_multiplier` | int | `2` | Backoff multiplier |

## Use Cases

### 1. High Availability Production Systems

Ensure 99.9%+ uptime by configuring multiple fallback providers:

```python
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": os.getenv("OPENAI_API_KEY"),

        "fallback": {
            "enabled": True,
            "providers": [
                {
                    "model": "claude-3-opus",
                    "model_provider": "anthropic",
                    "api_key": os.getenv("ANTHROPIC_API_KEY"),
                    "priority": 1
                },
                {
                    "model": "gpt-4",
                    "model_provider": "azure_openai",
                    "api_key": os.getenv("AZURE_API_KEY"),
                    "priority": 2
                }
            ],
            "circuit_breaker": {
                "failure_threshold": 3,
                "timeout": 30
            }
        }
    }
}
```

### 2. Cost Optimization

Automatically fall back to cheaper providers when primary is rate-limited:

```python
config = {
    "llm": {
        # Expensive but high-quality
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": os.getenv("OPENAI_API_KEY"),

        "fallback": {
            "enabled": True,
            "providers": [
                {
                    # Cheaper alternative
                    "model": "gpt-3.5-turbo",
                    "model_provider": "openai",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "priority": 1
                },
                {
                    # Free local model
                    "model": "llama3",
                    "model_provider": "ollama",
                    "priority": 2
                }
            ],
            "circuit_breaker": {
                "failure_threshold": 1  # Immediately fallback on rate limit
            }
        }
    }
}
```

### 3. Development with API Quota Limits

Seamlessly fall back to local models when API quota is exhausted:

```python
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",
        "api_key": os.getenv("OPENAI_API_KEY"),

        "fallback": {
            "enabled": True,
            "providers": [
                {
                    # Local model as fallback
                    "model": "llama3",
                    "model_provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "priority": 1
                }
            ]
        }
    }
}
```

### 4. Geographic Redundancy

Fall back to regional providers when primary is unavailable:

```python
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",  # US region
        "api_key": os.getenv("OPENAI_US_KEY"),

        "fallback": {
            "enabled": True,
            "providers": [
                {
                    "model": "gpt-4",
                    "model_provider": "azure_openai",  # EU region
                    "api_key": os.getenv("AZURE_EU_KEY"),
                    "priority": 1
                }
            ]
        }
    }
}
```

## Monitoring and Health Checks

### Get Health Status

```python
# After creating your graph
health = graph.llm_model.get_health_status()

print(f"Primary: {health['primary']['name']}")
print(f"Circuit State: {health['primary']['circuit_state']}")
print(f"Success Rate: {health['primary']['success_rate']}")
print(f"Avg Latency: {health['primary']['average_latency']}")

for fallback in health['fallbacks']:
    print(f"Fallback: {fallback['name']}")
    print(f"  Success Rate: {fallback['success_rate']}")
```

### Example Output

```
Primary: openai/gpt-4
Circuit State: closed
Success Rate: 98.50%
Avg Latency: 2.34s

Fallback: anthropic/claude-3-sonnet
  Success Rate: 100.00%
```

### Reset Metrics

```python
# Reset all health metrics
graph.llm_model.reset_all_metrics()

# Reset all circuit breakers
graph.llm_model.reset_all_circuit_breakers()
```

## Circuit Breaker States

The circuit breaker has three states:

### 1. CLOSED (Normal Operation)

- All requests pass through to the provider
- Failures increment the failure counter
- After `failure_threshold` failures, transitions to OPEN

### 2. OPEN (Failing Fast)

- Requests fail immediately without calling the provider
- Prevents overwhelming a failing service
- After `timeout` seconds, transitions to HALF_OPEN

### 3. HALF_OPEN (Testing Recovery)

- Allows limited test requests through
- If `success_threshold` successes: transitions to CLOSED
- If any failure: transitions back to OPEN

## Best Practices

### 1. Choose Appropriate Thresholds

```python
# For production systems
"circuit_breaker": {
    "failure_threshold": 5,   # More tolerant
    "success_threshold": 3,   # Verify recovery
    "timeout": 60             # Wait longer before retry
}

# For development
"circuit_breaker": {
    "failure_threshold": 2,   # Fail fast
    "success_threshold": 1,   # Quick recovery
    "timeout": 10             # Shorter timeout
}
```

### 2. Order Fallbacks by Preference

```python
"providers": [
    {"model": "gpt-4", "priority": 1},        # Best quality
    {"model": "claude-3", "priority": 2},     # Good quality
    {"model": "gpt-3.5", "priority": 3},      # Fast & cheap
    {"model": "llama3", "priority": 4}        # Local fallback
]
```

### 3. Use Environment Variables for API Keys

```python
import os

config = {
    "llm": {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "fallback": {
            "providers": [
                {
                    "api_key": os.getenv("ANTHROPIC_API_KEY"),
                    # ...
                }
            ]
        }
    }
}
```

### 4. Monitor Provider Health

```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.INFO)

# Check health periodically
health = graph.llm_model.get_health_status()

if health['primary']['circuit_state'] != 'closed':
    logging.warning("Primary provider circuit breaker is not closed!")
```

### 5. Test Fallback Behavior

```python
# Simulate provider failure for testing
graph.llm_model.primary.circuit_breaker.reset()

# Make requests and verify fallback works
result = graph.run()
```

## Troubleshooting

### All Providers Failed

If you see `AllProvidersFailedError`:

1. Check API keys are valid
2. Verify network connectivity
3. Check provider status pages
4. Review error details in exception

```python
try:
    result = graph.run()
except AllProvidersFailedError as e:
    print(f"All providers failed: {e}")
    for error in e.errors:
        print(f"  {error['provider']}: {error['details']}")
```

### Circuit Breaker Stuck Open

If a circuit breaker won't close:

1. Check if provider is actually recovered
2. Verify `timeout` has elapsed
3. Manually reset if needed:

```python
graph.llm_model.reset_all_circuit_breakers()
```

### Fallback Not Triggering

If fallback isn't working:

1. Verify `enabled: True` in config
2. Check fallback providers are configured correctly
3. Ensure API keys are valid
4. Check logs for detailed error messages

## Migration from Existing Code

Existing code requires **zero changes**. Simply add fallback configuration when you're ready:

### Before (Still Works)

```python
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai"
    }
}
```

### After (Enhanced)

```python
config = {
    "llm": {
        "model": "gpt-4",
        "model_provider": "openai",
        "fallback": {
            "enabled": True,
            "providers": [...]
        }
    }
}
```

## Performance Impact

- Circuit breaker overhead: ~0.1ms per call
- Health metrics tracking: ~0.05ms per call
- Total overhead: <1% of typical LLM API call latency

## Security Considerations

- Store API keys in environment variables
- Never commit API keys to version control
- Use secret management systems in production
- Audit which provider handled sensitive requests

## Additional Resources

- [RFC-0002: Multi-Model Fallback](../analysis-output/rfcs/RFC-0002-multi-model-fallback.md)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Retry Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/retry)

## Support

For issues or questions:
- GitHub Issues: https://github.com/Scrapegraph-ai/Scrapegraph-ai/issues
- Documentation: https://scrapegraph-ai.readthedocs.io
