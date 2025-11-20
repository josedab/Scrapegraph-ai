"""
Pydantic models for configuration validation.

This module provides validated configuration schemas for all graph types,
ensuring type safety, sensible defaults, and early error detection.
"""
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

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class LLMConfig(BaseModel):
    """LLM provider configuration with validation."""

    model: str = Field(..., description="Model identifier (e.g., 'gpt-4', 'openai/gpt-4')")
    model_provider: Optional[str] = Field(None, description="Explicit provider name")
    api_key: Optional[str] = Field(None, repr=False, description="API key for the provider")
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

    def __repr__(self):
        """Custom repr that masks sensitive data."""
        safe_dict = self.model_dump(exclude={"api_key"})
        if self.api_key:
            safe_dict["api_key"] = "***REDACTED***"
        return f"LLMConfig({safe_dict})"

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
        "str_strip_whitespace": True,
    }


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

    model_config = {
        "extra": "forbid",  # Catch typos in configuration keys
        "validate_assignment": True,  # Validate on attribute assignment
    }


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
