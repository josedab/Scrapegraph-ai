# RFC-0005: Configuration Schema Validation with Pydantic

**Status:** Draft
**Created:** 2025-11-20
**Author:** Analysis Team
**Target Version:** 2.0.0

---

## Summary

Implement Pydantic-based configuration validation for all graph types to catch misconfigurations at graph creation time, providing clear error messages, type checking, and sensible defaults. This will improve developer experience and prevent runtime errors caused by invalid configuration.

---

## Motivation

### Current Problems

The ScrapeGraphAI codebase currently handles configuration through plain Python dictionaries, leading to several issues:

1. **Runtime Errors**: Configuration errors are discovered late during execution
   - `config["llm"]` on line 66 of `abstract_graph.py` raises KeyError if missing
   - No validation until the configuration value is actually accessed
   - Stack traces are unhelpful for configuration errors

2. **Inconsistent Defaults**: Default values scattered across the codebase
   - 97+ occurrences of `config.get()` across 17 graph files
   - Same configuration keys have different defaults in different locations
   - No central source of truth for configuration schema

3. **Type Safety Issues**: No type checking for configuration values
   - `timeout` could be passed as a string instead of int
   - Boolean flags could be passed as strings ("true" vs True)
   - Nested configuration structures lack validation

4. **Poor Developer Experience**
   - No IDE autocomplete for configuration options
   - No documentation of valid configuration keys
   - Difficult to discover available configuration options
   - Unclear which options are required vs optional

### Example of Current Issues

```python
# This code will fail at runtime with unhelpful error
graph = SmartScraperGraph(
    prompt="...",
    source="...",
    config={
        # Missing required "llm" key - will raise KeyError
        "timeout": "480",  # Wrong type - should be int
        "headles": True,   # Typo - will be silently ignored
    }
)
```

---

## Proposed Solution

Implement a layered Pydantic configuration system with:

1. **Base Configuration Schema**: Core settings shared across all graphs
2. **Graph-Specific Schemas**: Extended configurations for specific graph types
3. **LLM Provider Schemas**: Validated schemas for each LLM provider
4. **Backward Compatibility**: Support both dict and Pydantic models during migration

### Architecture

```
BaseGraphConfig (Pydantic BaseModel)
    ├── LLMConfig (nested model)
    │   ├── model: str
    │   ├── api_key: Optional[str]
    │   ├── temperature: float = 0.0
    │   ├── rate_limit: Optional[RateLimitConfig]
    │   └── model_instance: Optional[Any]
    │
    ├── verbose: bool = False
    ├── headless: bool = True
    ├── timeout: int = 480
    ├── cache_path: Optional[str] = None
    ├── loader_kwargs: dict = {}
    └── burr_kwargs: Optional[dict] = None

SmartScraperConfig(BaseGraphConfig)
    └── # Graph-specific extensions

SearchGraphConfig(BaseGraphConfig)
    ├── max_results: int = 10
    └── search_engine: str = "google"
```

---

## Implementation Details

### Phase 1: Core Configuration Models

**File:** `scrapegraphai/config/models.py`

```python
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class RateLimitConfig(BaseModel):
    """Rate limiting configuration for LLM requests."""
    requests_per_second: Optional[float] = Field(
        None,
        gt=0,
        description="Maximum requests per second"
    )
    max_retries: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of retries"
    )

class LLMConfig(BaseModel):
    """LLM provider configuration with validation."""

    model: str = Field(..., description="Model identifier (e.g., 'gpt-4', 'openai/gpt-4')")
    model_provider: Optional[str] = Field(None, description="Explicit provider name")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="Sampling temperature")
    streaming: bool = Field(False, description="Enable streaming responses")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    rate_limit: Optional[RateLimitConfig] = None
    model_instance: Optional[Any] = Field(None, description="Pre-configured model instance")
    model_tokens: Optional[int] = Field(None, description="Token limit for model_instance")

    @field_validator('model')
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        """Validate model identifier format."""
        if not v or v.isspace():
            raise ValueError("Model identifier cannot be empty")
        return v

    @model_validator(mode='after')
    def validate_model_instance_requirements(self):
        """Ensure model_tokens is provided when using model_instance."""
        if self.model_instance is not None and self.model_tokens is None:
            raise ValueError("model_tokens must be specified when using model_instance")
        return self

class BaseGraphConfig(BaseModel):
    """Base configuration for all graph types."""

    llm: LLMConfig = Field(..., description="LLM configuration")
    verbose: bool = Field(False, description="Enable verbose logging")
    headless: bool = Field(True, description="Run browser in headless mode")
    timeout: int = Field(480, gt=0, le=3600, description="Timeout in seconds")
    cache_path: Optional[str] = Field(None, description="Path for caching")
    loader_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Loader arguments")
    browser_base: Optional[str] = Field(None, description="BrowserBase configuration")
    scrape_do: Optional[Dict[str, Any]] = Field(None, description="ScrapeDo configuration")
    storage_state: Optional[str] = Field(None, description="Browser storage state")
    burr_kwargs: Optional[Dict[str, Any]] = Field(None, description="Burr framework config")

    class Config:
        extra = "forbid"  # Catch typos in configuration keys
        validate_assignment = True  # Validate on attribute assignment

class SmartScraperConfig(BaseGraphConfig):
    """Configuration specific to SmartScraperGraph."""
    pass  # Can be extended with graph-specific options

class SearchGraphConfig(BaseGraphConfig):
    """Configuration for SearchGraph."""
    max_results: int = Field(10, gt=0, le=100, description="Maximum search results")
    search_engine: Literal["google", "bing", "duckduckgo"] = Field(
        "google",
        description="Search engine to use"
    )
```

### Phase 2: Backward Compatible Integration

**Update:** `scrapegraphai/graphs/abstract_graph.py`

```python
from typing import Union
from ..config.models import BaseGraphConfig

class AbstractGraph(ABC):
    """
    Scaffolding class for creating a graph representation and executing it.

    Args:
        prompt (str): The prompt for the graph.
        config (Union[dict, BaseGraphConfig]): Configuration parameters.
        source (str, optional): The source of the graph.
        schema (BaseModel, optional): The schema for the graph output.
    """

    def __init__(
        self,
        prompt: str,
        config: Union[dict, BaseGraphConfig],
        source: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
    ):
        # Convert dict to Pydantic model with validation
        if isinstance(config, dict):
            try:
                self.config = BaseGraphConfig(**config)
            except ValidationError as e:
                raise ConfigurationError(
                    f"Invalid configuration:\n{self._format_validation_error(e)}"
                ) from e
        else:
            self.config = config

        self.prompt = prompt
        self.source = source
        self.schema = schema

        # Clean, validated access to configuration
        self.llm_model = self._create_llm(self.config.llm)
        self.verbose = self.config.verbose
        self.headless = self.config.headless
        self.loader_kwargs = self.config.loader_kwargs
        self.cache_path = self.config.cache_path
        self.browser_base = self.config.browser_base
        self.scrape_do = self.config.scrape_do
        self.storage_state = self.config.storage_state
        self.timeout = self.config.timeout

        # ... rest of initialization

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        """Format Pydantic validation errors for user-friendly display."""
        messages = []
        for err in error.errors():
            field = ".".join(str(x) for x in err["loc"])
            message = err["msg"]
            messages.append(f"  - {field}: {message}")
        return "\n".join(messages)
```

### Phase 3: Custom Exception Types

**File:** `scrapegraphai/config/exceptions.py`

```python
class ConfigurationError(Exception):
    """Raised when graph configuration is invalid."""

    def __init__(self, message: str, suggestions: Optional[List[str]] = None):
        super().__init__(message)
        self.suggestions = suggestions or []

    def __str__(self):
        msg = super().__str__()
        if self.suggestions:
            msg += "\n\nSuggestions:\n"
            msg += "\n".join(f"  - {s}" for s in self.suggestions)
        return msg
```

---

## Migration Strategy

### Phase 1: Foundation (Week 1)
- Create `scrapegraphai/config/` package
- Implement base Pydantic models
- Add comprehensive unit tests
- Update documentation

### Phase 2: Core Graphs (Week 2)
- Migrate `AbstractGraph` to support both dict and Pydantic
- Migrate `SmartScraperGraph`
- Migrate `SearchGraph`
- Add integration tests

### Phase 3: All Graphs (Week 3)
- Migrate remaining 24 graph types
- Update all examples to use validated configs
- Add deprecation warnings for dict-only usage

### Phase 4: Documentation & Tools (Week 4)
- Generate JSON Schema for configuration
- Create configuration validator CLI tool
- Update all documentation
- Create migration guide

### Backward Compatibility

```python
# Old way (still works, with validation)
config = {
    "llm": {"model": "gpt-4"},
    "verbose": True
}
graph = SmartScraperGraph(prompt, source, config)

# New way (recommended, with IDE support)
from scrapegraphai.config import SmartScraperConfig, LLMConfig

config = SmartScraperConfig(
    llm=LLMConfig(model="gpt-4"),
    verbose=True
)
graph = SmartScraperGraph(prompt, source, config)
```

---

## Benefits

### 1. Immediate Error Detection

**Before:**
```python
# Fails during execution with unhelpful traceback
config = {"timeout": "480"}  # Wrong type
graph = SmartScraperGraph(prompt, source, config)
result = graph.run()  # Fails here, deep in execution
```

**After:**
```python
# Fails immediately at graph creation with clear message
config = {"llm": {"model": "gpt-4"}, "timeout": "480"}
graph = SmartScraperGraph(prompt, source, config)
# ValidationError: timeout: Input should be a valid integer
```

### 2. Self-Documenting Configuration

```python
# IDE shows all available options with descriptions
config = SmartScraperConfig(
    llm=LLMConfig(
        model="gpt-4",
        temperature=0.7,  # IDE shows: "Sampling temperature (0.0-2.0)"
    ),
    timeout=300,  # IDE shows: "Timeout in seconds (1-3600)"
)
```

### 3. Typo Detection

**Before:** Silently ignored
```python
config = {"headles": True}  # Typo, will be ignored
```

**After:** Immediate error
```python
config = SmartScraperConfig(headles=True)
# ValidationError: Extra inputs are not permitted [extra='forbid']
```

### 4. Type Safety

```python
# Automatic type conversion where safe
config = BaseGraphConfig(
    llm={"model": "gpt-4", "temperature": "0.7"},  # String converted to float
    timeout="480"  # String converted to int
)

# Clear errors for invalid types
config = BaseGraphConfig(
    llm={"model": "gpt-4"},
    timeout="forever"  # ValidationError: Input should be a valid integer
)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/config/test_base_config.py
def test_base_config_valid():
    """Test valid configuration creation."""
    config = BaseGraphConfig(
        llm=LLMConfig(model="gpt-4"),
        verbose=True,
        timeout=300
    )
    assert config.verbose is True
    assert config.timeout == 300

def test_missing_required_field():
    """Test that missing required fields raise validation error."""
    with pytest.raises(ValidationError) as exc_info:
        BaseGraphConfig(verbose=True)  # Missing llm

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("llm",) for e in errors)

def test_invalid_timeout_range():
    """Test timeout validation bounds."""
    with pytest.raises(ValidationError) as exc_info:
        BaseGraphConfig(
            llm=LLMConfig(model="gpt-4"),
            timeout=5000  # Exceeds max of 3600
        )

def test_typo_detection():
    """Test that extra fields are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        BaseGraphConfig(
            llm=LLMConfig(model="gpt-4"),
            headles=True  # Typo
        )

def test_backward_compatibility_dict():
    """Test that dict configs still work."""
    config_dict = {
        "llm": {"model": "gpt-4"},
        "verbose": True
    }
    # Should not raise
    graph = SmartScraperGraph("prompt", "source", config_dict)
    assert graph.config.verbose is True
```

### Integration Tests

```python
# tests/integration/test_config_validation.py
def test_end_to_end_with_valid_config():
    """Test complete workflow with validated config."""
    config = SmartScraperConfig(
        llm=LLMConfig(model="openai/gpt-4"),
        verbose=False,
        timeout=300
    )
    graph = SmartScraperGraph(
        prompt="List all links",
        source="https://example.com",
        config=config
    )
    # Should execute without configuration errors
    # (may fail for other reasons like network)
```

---

## Performance Impact

**Minimal impact expected:**

1. **Validation Cost**: One-time at graph creation (~1-5ms)
2. **Memory**: Pydantic models slightly larger than dicts (~10% overhead)
3. **Runtime**: No impact after initialization

**Benchmark targets:**
- Configuration validation: < 5ms for typical config
- Memory overhead: < 1MB for 100 graph instances
- No measurable impact on graph execution time

---

## Security Considerations

### Benefits

1. **Input Sanitization**: Automatic validation prevents injection attacks
2. **Schema Enforcement**: Prevents unexpected configuration keys
3. **Type Validation**: Ensures configuration values are expected types

### Sensitive Data Handling

```python
class LLMConfig(BaseModel):
    api_key: Optional[str] = Field(None, repr=False)  # Excluded from repr

    class Config:
        # Prevent API keys from appearing in logs
        str_strip_whitespace = True

    def __repr__(self):
        """Custom repr that masks sensitive data."""
        safe_dict = self.model_dump(exclude={"api_key"})
        if self.api_key:
            safe_dict["api_key"] = "***REDACTED***"
        return f"LLMConfig({safe_dict})"
```

---

## Alternatives Considered

### 1. Dataclasses with dacite

**Pros:**
- Lighter weight than Pydantic
- Part of standard library (dataclasses)

**Cons:**
- No built-in validation
- Less powerful type coercion
- No JSON schema generation
- Requires external library (dacite) for dict conversion

**Decision:** Rejected - Pydantic already a dependency, provides more features

### 2. attrs with validators

**Pros:**
- Fast and lightweight
- Good validation support

**Cons:**
- Not as widely known as Pydantic
- Less tooling support
- No automatic JSON schema generation

**Decision:** Rejected - Pydantic has better ecosystem

### 3. TypedDict

**Pros:**
- Standard library
- Type hints for dicts

**Cons:**
- No runtime validation
- No default values
- No coercion

**Decision:** Rejected - Doesn't solve validation problem

### 4. Custom validation functions

**Pros:**
- Full control
- No dependencies

**Cons:**
- High maintenance burden
- Error-prone
- Difficult to keep consistent
- No automatic documentation

**Decision:** Rejected - Reinventing the wheel

---

## Open Questions

1. **Should we support JSON/YAML config files?**
   - Could provide `Config.from_json()` and `Config.from_yaml()`
   - Useful for command-line tools
   - Low priority for initial implementation

2. **How to handle environment variables?**
   - Pydantic supports `env_prefix` for automatic env var loading
   - Should we support `LLM_API_KEY` environment variable?
   - Could be added in Phase 2

3. **Should we validate URLs in configuration?**
   - Could use `pydantic.HttpUrl` for URL fields
   - May be overly strict for local file paths
   - Suggest making this configurable

4. **How to handle deprecation of old config keys?**
   - Use Pydantic validators to provide warnings
   - Create migration helper: `config.migrate_from_legacy()`

---

## Success Metrics

1. **Developer Experience**
   - Reduce configuration-related issues by 80%
   - Faster onboarding for new contributors
   - Positive community feedback

2. **Code Quality**
   - Remove 90+ scattered `config.get()` calls
   - Centralize all defaults in one location
   - Achieve 100% type coverage for config

3. **Reliability**
   - Catch 100% of configuration errors at creation time
   - Zero runtime KeyErrors from missing config keys
   - Clear, actionable error messages

---

## Implementation Timeline

**Total Effort:** 3-4 weeks (1 engineer)

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Foundation** | Week 1 | Core Pydantic models, tests, exceptions |
| **Phase 2: Core Graphs** | Week 2 | Migrate 3 main graphs, integration tests |
| **Phase 3: All Graphs** | Week 3 | Migrate remaining graphs, update examples |
| **Phase 4: Polish** | Week 4 | Documentation, CLI tools, migration guide |

---

## Related Work

- **RFC-0001**: LLM Response Caching - Will need validated cache config
- **RFC-0002**: Structured Logging - Will benefit from validated log config
- **RFC-0004**: Performance Benchmarking - Will standardize benchmark config

---

## References

1. [Pydantic Documentation](https://docs.pydantic.dev/)
2. [LangChain Configuration Patterns](https://python.langchain.com/docs/guides/structured_output)
3. [FastAPI Configuration](https://fastapi.tiangolo.com/advanced/settings/) - Similar pattern
4. [Current AbstractGraph Implementation](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636/scrapegraphai/graphs/abstract_graph.py)

---

## Appendix A: Example Error Messages

### Before (Unhelpful)

```
Traceback (most recent call last):
  File "example.py", line 10, in <module>
    graph = SmartScraperGraph(prompt, source, config)
  File "scrapegraphai/graphs/abstract_graph.py", line 66, in __init__
    self.llm_model = self._create_llm(config["llm"])
KeyError: 'llm'
```

### After (Helpful)

```
ConfigurationError: Invalid configuration:
  - llm: Field required

Suggestions:
  - Add 'llm' configuration with model specification
  - Example: config = {"llm": {"model": "gpt-4"}}
  - See documentation: https://docs.scrapegraphai.com/config
```

---

## Appendix B: Configuration JSON Schema

With Pydantic, we can automatically generate JSON Schema:

```python
# Generate schema for documentation and validation
schema = BaseGraphConfig.model_json_schema()

# Output can be used for:
# - API documentation
# - VS Code IntelliSense
# - Configuration file validation
```

Example output:

```json
{
  "title": "BaseGraphConfig",
  "type": "object",
  "properties": {
    "llm": {
      "title": "LLM Configuration",
      "description": "LLM configuration",
      "allOf": [{"$ref": "#/definitions/LLMConfig"}]
    },
    "verbose": {
      "title": "Verbose",
      "description": "Enable verbose logging",
      "default": false,
      "type": "boolean"
    },
    "timeout": {
      "title": "Timeout",
      "description": "Timeout in seconds",
      "default": 480,
      "exclusiveMinimum": 0,
      "maximum": 3600,
      "type": "integer"
    }
  },
  "required": ["llm"]
}
```

---

**END OF RFC-0005**
