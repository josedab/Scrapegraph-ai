"""
Unit tests for base configuration models.
"""
import pytest
from pydantic import ValidationError

from scrapegraphai.config import (
    BaseGraphConfig,
    LLMConfig,
    RateLimitConfig,
    SmartScraperConfig,
    SearchGraphConfig,
    ConfigurationError,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig model."""

    def test_valid_rate_limit_config(self):
        """Test creation of valid rate limit configuration."""
        config = RateLimitConfig(
            requests_per_second=10.0,
            max_retries=3
        )
        assert config.requests_per_second == 10.0
        assert config.max_retries == 3

    def test_negative_requests_per_second(self):
        """Test that negative requests_per_second is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(requests_per_second=-1.0)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("requests_per_second",) for e in errors)

    def test_negative_max_retries(self):
        """Test that negative max_retries is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(max_retries=-1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_retries",) for e in errors)

    def test_optional_fields(self):
        """Test that all fields are optional."""
        config = RateLimitConfig()
        assert config.requests_per_second is None
        assert config.max_retries is None

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            RateLimitConfig(invalid_field=True)


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_valid_llm_config(self):
        """Test creation of valid LLM configuration."""
        config = LLMConfig(
            model="gpt-4",
            temperature=0.7,
            streaming=True
        )
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.streaming is True

    def test_missing_required_model(self):
        """Test that missing model field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("model",) for e in errors)

    def test_empty_model_string(self):
        """Test that empty model string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(model="")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("model",) for e in errors)

    def test_whitespace_model_string(self):
        """Test that whitespace-only model string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(model="   ")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("model",) for e in errors)

    def test_temperature_range_validation(self):
        """Test temperature validation bounds."""
        # Valid temperatures
        LLMConfig(model="gpt-4", temperature=0.0)
        LLMConfig(model="gpt-4", temperature=1.0)
        LLMConfig(model="gpt-4", temperature=2.0)

        # Invalid temperatures
        with pytest.raises(ValidationError):
            LLMConfig(model="gpt-4", temperature=-0.1)

        with pytest.raises(ValidationError):
            LLMConfig(model="gpt-4", temperature=2.1)

    def test_max_tokens_validation(self):
        """Test max_tokens must be positive."""
        LLMConfig(model="gpt-4", max_tokens=100)

        with pytest.raises(ValidationError):
            LLMConfig(model="gpt-4", max_tokens=0)

        with pytest.raises(ValidationError):
            LLMConfig(model="gpt-4", max_tokens=-1)

    def test_model_instance_requires_tokens(self):
        """Test that model_instance requires model_tokens."""
        # Should work with both
        config = LLMConfig(
            model="gpt-4",
            model_instance=object(),
            model_tokens=8192
        )
        assert config.model_tokens == 8192

        # Should fail without model_tokens
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(
                model="gpt-4",
                model_instance=object()
            )

        assert "model_tokens must be specified" in str(exc_info.value)

    def test_api_key_not_in_repr(self):
        """Test that API key is masked in repr."""
        config = LLMConfig(
            model="gpt-4",
            api_key="secret-key-12345"
        )
        repr_str = repr(config)
        assert "secret-key-12345" not in repr_str
        assert "REDACTED" in repr_str

    def test_rate_limit_integration(self):
        """Test LLMConfig with nested RateLimitConfig."""
        config = LLMConfig(
            model="gpt-4",
            rate_limit=RateLimitConfig(
                requests_per_second=5.0,
                max_retries=3
            )
        )
        assert config.rate_limit.requests_per_second == 5.0
        assert config.rate_limit.max_retries == 3

    def test_default_values(self):
        """Test default values for optional fields."""
        config = LLMConfig(model="gpt-4")
        assert config.temperature == 0.0
        assert config.streaming is False
        assert config.max_tokens is None
        assert config.api_key is None

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            LLMConfig(model="gpt-4", invalid_field=True)


class TestBaseGraphConfig:
    """Tests for BaseGraphConfig model."""

    def test_valid_base_config(self):
        """Test creation of valid base configuration."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4"),
            verbose=True,
            timeout=300
        )
        assert config.verbose is True
        assert config.timeout == 300
        assert config.llm.model == "gpt-4"

    def test_missing_required_llm(self):
        """Test that missing required llm field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(verbose=True)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("llm",) for e in errors)

    def test_invalid_timeout_range(self):
        """Test timeout validation bounds."""
        # Valid timeouts
        BaseGraphConfig(llm=LLMConfig(model="gpt-4"), timeout=1)
        BaseGraphConfig(llm=LLMConfig(model="gpt-4"), timeout=3600)

        # Invalid timeouts - too small
        with pytest.raises(ValidationError):
            BaseGraphConfig(llm=LLMConfig(model="gpt-4"), timeout=0)

        # Invalid timeouts - too large
        with pytest.raises(ValidationError):
            BaseGraphConfig(llm=LLMConfig(model="gpt-4"), timeout=5000)

    def test_typo_detection(self):
        """Test that extra fields (typos) are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                headles=True  # Typo in 'headless'
            )

        # Should mention extra fields not permitted
        assert "extra" in str(exc_info.value).lower()

    def test_type_coercion(self):
        """Test automatic type conversion where safe."""
        # String to int
        config = BaseGraphConfig(
            llm={"model": "gpt-4"},
            timeout="480"
        )
        assert config.timeout == 480
        assert isinstance(config.timeout, int)

        # Dict to LLMConfig
        config = BaseGraphConfig(
            llm={"model": "gpt-4", "temperature": "0.7"}
        )
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.7

    def test_invalid_type_conversion(self):
        """Test that invalid types raise clear errors."""
        with pytest.raises(ValidationError):
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                timeout="forever"  # Can't convert to int
            )

    def test_default_values(self):
        """Test default values for optional fields."""
        config = BaseGraphConfig(llm=LLMConfig(model="gpt-4"))
        assert config.verbose is False
        assert config.headless is True
        assert config.timeout == 480
        assert config.cache_path is None
        assert config.loader_kwargs == {}
        assert config.browser_base is None
        assert config.scrape_do is None
        assert config.storage_state is None
        assert config.burr_kwargs is None

    def test_nested_dict_config(self):
        """Test creation from nested dict (backward compatibility)."""
        config_dict = {
            "llm": {
                "model": "gpt-4",
                "temperature": 0.7,
                "api_key": "test-key"
            },
            "verbose": True,
            "timeout": 300,
            "loader_kwargs": {"key": "value"}
        }
        config = BaseGraphConfig(**config_dict)
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.7
        assert config.verbose is True
        assert config.timeout == 300
        assert config.loader_kwargs == {"key": "value"}

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                unknown_field="value"
            )


class TestSmartScraperConfig:
    """Tests for SmartScraperConfig model."""

    def test_valid_smart_scraper_config(self):
        """Test creation of valid SmartScraperConfig."""
        config = SmartScraperConfig(
            llm=LLMConfig(model="gpt-4"),
            verbose=True
        )
        assert config.llm.model == "gpt-4"
        assert config.verbose is True

    def test_inherits_from_base(self):
        """Test that SmartScraperConfig inherits BaseGraphConfig fields."""
        config = SmartScraperConfig(
            llm=LLMConfig(model="gpt-4"),
            timeout=600
        )
        assert config.timeout == 600
        assert hasattr(config, "headless")
        assert hasattr(config, "verbose")


class TestSearchGraphConfig:
    """Tests for SearchGraphConfig model."""

    def test_valid_search_graph_config(self):
        """Test creation of valid SearchGraphConfig."""
        config = SearchGraphConfig(
            llm=LLMConfig(model="gpt-4"),
            max_results=20,
            search_engine="bing"
        )
        assert config.max_results == 20
        assert config.search_engine == "bing"

    def test_max_results_range(self):
        """Test max_results validation."""
        # Valid values
        SearchGraphConfig(llm=LLMConfig(model="gpt-4"), max_results=1)
        SearchGraphConfig(llm=LLMConfig(model="gpt-4"), max_results=100)

        # Invalid - too small
        with pytest.raises(ValidationError):
            SearchGraphConfig(llm=LLMConfig(model="gpt-4"), max_results=0)

        # Invalid - too large
        with pytest.raises(ValidationError):
            SearchGraphConfig(llm=LLMConfig(model="gpt-4"), max_results=101)

    def test_search_engine_literal(self):
        """Test search_engine only accepts specific values."""
        # Valid values
        SearchGraphConfig(llm=LLMConfig(model="gpt-4"), search_engine="google")
        SearchGraphConfig(llm=LLMConfig(model="gpt-4"), search_engine="bing")
        SearchGraphConfig(llm=LLMConfig(model="gpt-4"), search_engine="duckduckgo")

        # Invalid value
        with pytest.raises(ValidationError):
            SearchGraphConfig(llm=LLMConfig(model="gpt-4"), search_engine="yahoo")

    def test_default_values(self):
        """Test default values for SearchGraphConfig."""
        config = SearchGraphConfig(llm=LLMConfig(model="gpt-4"))
        assert config.max_results == 10
        assert config.search_engine == "google"

    def test_inherits_from_base(self):
        """Test that SearchGraphConfig inherits BaseGraphConfig fields."""
        config = SearchGraphConfig(
            llm=LLMConfig(model="gpt-4"),
            verbose=True,
            timeout=300
        )
        assert config.verbose is True
        assert config.timeout == 300


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_basic_configuration_error(self):
        """Test basic ConfigurationError creation."""
        error = ConfigurationError("Invalid config")
        assert str(error) == "Invalid config"

    def test_configuration_error_with_suggestions(self):
        """Test ConfigurationError with suggestions."""
        error = ConfigurationError(
            "Invalid config",
            suggestions=[
                "Add 'llm' field",
                "Check field types"
            ]
        )
        error_str = str(error)
        assert "Invalid config" in error_str
        assert "Suggestions:" in error_str
        assert "Add 'llm' field" in error_str
        assert "Check field types" in error_str

    def test_configuration_error_without_suggestions(self):
        """Test ConfigurationError without suggestions."""
        error = ConfigurationError("Invalid config")
        error_str = str(error)
        assert "Invalid config" in error_str
        assert "Suggestions:" not in error_str
