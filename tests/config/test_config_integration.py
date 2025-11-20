"""
Integration tests for configuration validation with graphs.
"""
import pytest
from pydantic import ValidationError

from scrapegraphai.config import (
    BaseGraphConfig,
    LLMConfig,
    SmartScraperConfig,
    ConfigurationError,
)


class TestBackwardCompatibility:
    """Tests for backward compatibility with dict configs."""

    def test_dict_config_is_validated(self):
        """Test that dict configs are validated when passed to graphs."""
        # Valid dict config
        config_dict = {
            "llm": {"model": "gpt-4"},
            "verbose": True,
            "timeout": 300
        }
        # Should convert to BaseGraphConfig without error
        validated_config = BaseGraphConfig(**config_dict)
        assert validated_config.llm.model == "gpt-4"
        assert validated_config.verbose is True
        assert validated_config.timeout == 300

    def test_invalid_dict_config_raises_error(self):
        """Test that invalid dict configs raise ConfigurationError."""
        # Missing required 'llm' field
        config_dict = {
            "verbose": True
        }
        with pytest.raises(ValidationError):
            BaseGraphConfig(**config_dict)

    def test_dict_with_typo_raises_error(self):
        """Test that dict with typo raises validation error."""
        config_dict = {
            "llm": {"model": "gpt-4"},
            "headles": True  # Typo
        }
        with pytest.raises(ValidationError):
            BaseGraphConfig(**config_dict)

    def test_dict_with_wrong_type_raises_error(self):
        """Test that dict with wrong type raises validation error."""
        config_dict = {
            "llm": {"model": "gpt-4"},
            "timeout": "forever"  # Should be int
        }
        with pytest.raises(ValidationError):
            BaseGraphConfig(**config_dict)


class TestPydanticConfigUsage:
    """Tests for using Pydantic config models directly."""

    def test_pydantic_config_creation(self):
        """Test creating config with Pydantic models."""
        config = SmartScraperConfig(
            llm=LLMConfig(model="gpt-4", temperature=0.7),
            verbose=True,
            timeout=300
        )
        assert isinstance(config, BaseGraphConfig)
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.7

    def test_pydantic_config_validation(self):
        """Test that Pydantic configs are validated."""
        with pytest.raises(ValidationError):
            SmartScraperConfig(
                llm=LLMConfig(model="gpt-4"),
                timeout=5000  # Exceeds max
            )

    def test_pydantic_config_defaults(self):
        """Test that Pydantic configs use proper defaults."""
        config = SmartScraperConfig(
            llm=LLMConfig(model="gpt-4")
        )
        assert config.verbose is False
        assert config.headless is True
        assert config.timeout == 480


class TestConfigValidationMessages:
    """Tests for validation error messages."""

    def test_missing_field_error_message(self):
        """Test error message for missing required field."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(verbose=True)

        error = exc_info.value
        assert "llm" in str(error).lower()

    def test_type_error_message(self):
        """Test error message for wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                timeout="not-a-number"
            )

        error = exc_info.value
        assert "timeout" in str(error).lower()

    def test_range_error_message(self):
        """Test error message for out-of-range value."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                timeout=10000  # Too large
            )

        error = exc_info.value
        assert "timeout" in str(error).lower()

    def test_extra_field_error_message(self):
        """Test error message for extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(
                llm=LLMConfig(model="gpt-4"),
                unknown_field="value"
            )

        error = exc_info.value
        assert "extra" in str(error).lower()


class TestNestedConfigValidation:
    """Tests for nested configuration validation."""

    def test_nested_llm_config_validation(self):
        """Test validation of nested LLM config."""
        # Valid nested config
        config = BaseGraphConfig(
            llm={
                "model": "gpt-4",
                "temperature": 0.5,
                "max_tokens": 1000
            }
        )
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.5
        assert config.llm.max_tokens == 1000

    def test_nested_llm_config_invalid_temperature(self):
        """Test validation of nested LLM config with invalid temperature."""
        with pytest.raises(ValidationError) as exc_info:
            BaseGraphConfig(
                llm={
                    "model": "gpt-4",
                    "temperature": 3.0  # Too high
                }
            )

        error = exc_info.value
        assert "temperature" in str(error).lower()

    def test_nested_rate_limit_config(self):
        """Test validation of nested rate limit config."""
        config = BaseGraphConfig(
            llm={
                "model": "gpt-4",
                "rate_limit": {
                    "requests_per_second": 5.0,
                    "max_retries": 3
                }
            }
        )
        assert config.llm.rate_limit.requests_per_second == 5.0
        assert config.llm.rate_limit.max_retries == 3

    def test_nested_rate_limit_invalid(self):
        """Test validation of invalid nested rate limit config."""
        with pytest.raises(ValidationError):
            BaseGraphConfig(
                llm={
                    "model": "gpt-4",
                    "rate_limit": {
                        "requests_per_second": -1.0  # Invalid
                    }
                }
            )


class TestConfigModelDump:
    """Tests for converting config back to dict."""

    def test_model_dump(self):
        """Test converting config to dict."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4", temperature=0.7),
            verbose=True,
            timeout=300
        )
        config_dict = config.model_dump()

        assert config_dict["llm"]["model"] == "gpt-4"
        assert config_dict["llm"]["temperature"] == 0.7
        assert config_dict["verbose"] is True
        assert config_dict["timeout"] == 300

    def test_model_dump_exclude_none(self):
        """Test converting config to dict excluding None values."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4")
        )
        config_dict = config.model_dump(exclude_none=True)

        assert "api_key" not in config_dict["llm"]
        assert "cache_path" not in config_dict

    def test_model_dump_api_key_excluded_from_repr(self):
        """Test that API key is not exposed in repr."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4", api_key="secret-key")
        )
        repr_str = repr(config)
        assert "secret-key" not in repr_str


class TestConfigImmutabilityAndValidation:
    """Tests for config validation on assignment."""

    def test_validate_assignment(self):
        """Test that assignment validation works."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4")
        )

        # Valid assignment
        config.timeout = 600
        assert config.timeout == 600

        # Invalid assignment should raise
        with pytest.raises(ValidationError):
            config.timeout = 10000  # Too large

    def test_extra_field_assignment_forbidden(self):
        """Test that adding extra fields is forbidden."""
        config = BaseGraphConfig(
            llm=LLMConfig(model="gpt-4")
        )

        # Should not be able to add new attributes
        with pytest.raises(ValidationError):
            config.new_field = "value"
