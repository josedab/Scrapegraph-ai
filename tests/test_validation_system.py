"""
Unit tests for the data validation and confidence scoring system.

This module tests all components of the validation system:
- ValidationRule base classes
- Built-in validation rules
- ValidationEngine
- ConfidenceScorer
- ValidatedResponse
- Preset rule configurations
"""

import pytest
from datetime import datetime

from scrapegraphai.utils.validation import (
    # Base classes
    ValidationRule,
    FieldValidationRule,
    ValidationResult,
    ValidationSeverity,
    # Built-in rules
    NotNARule,
    NotEmptyRule,
    RegexRule,
    EmailRule,
    URLRule,
    PhoneRule,
    DateRule,
    NumericRangeRule,
    EnumRule,
    LengthRule,
    CustomRule,
    NoErrorMessageRule,
    # Engine and scorer
    ValidationEngine,
    ConfidenceScorer,
    # Response wrapper
    ValidatedResponse,
    # Presets
    create_ecommerce_rules,
    create_contact_info_rules,
    create_news_article_rules,
    create_job_listing_rules,
    create_real_estate_rules,
    create_social_media_post_rules,
    create_minimal_rules
)


class TestValidationRules:
    """Test individual validation rules."""

    def test_not_na_rule_passes(self):
        """Test NotNARule passes for valid values."""
        rule = NotNARule("price")
        data = {"price": "$99.99"}
        result = rule.validate(data, {})

        assert result.passed is True
        assert result.severity == ValidationSeverity.INFO

    def test_not_na_rule_fails(self):
        """Test NotNARule fails for NA values."""
        rule = NotNARule("price")
        data = {"price": "NA"}
        result = rule.validate(data, {})

        assert result.passed is False
        assert result.severity == ValidationSeverity.ERROR
        assert "placeholder value" in result.message.lower()

    def test_not_empty_rule_passes(self):
        """Test NotEmptyRule passes for non-empty values."""
        rule = NotEmptyRule("title")
        data = {"title": "Product Title"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_not_empty_rule_fails_empty_string(self):
        """Test NotEmptyRule fails for empty strings."""
        rule = NotEmptyRule("title")
        data = {"title": ""}
        result = rule.validate(data, {})

        assert result.passed is False
        assert "empty" in result.message.lower()

    def test_not_empty_rule_fails_empty_list(self):
        """Test NotEmptyRule fails for empty lists."""
        rule = NotEmptyRule("items")
        data = {"items": []}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_email_rule_passes(self):
        """Test EmailRule passes for valid emails."""
        rule = EmailRule("email")
        data = {"email": "user@example.com"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_email_rule_fails(self):
        """Test EmailRule fails for invalid emails."""
        rule = EmailRule("email")
        data = {"email": "not-an-email"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_url_rule_passes(self):
        """Test URLRule passes for valid URLs."""
        rule = URLRule("website")
        data = {"website": "https://example.com"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_url_rule_fails(self):
        """Test URLRule fails for invalid URLs."""
        rule = URLRule("website")
        data = {"website": "not a url"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_phone_rule_passes(self):
        """Test PhoneRule passes for valid phone numbers."""
        rule = PhoneRule("phone")

        valid_phones = [
            "+1-555-123-4567",
            "(555) 123-4567",
            "555.123.4567",
            "5551234567"
        ]

        for phone in valid_phones:
            data = {"phone": phone}
            result = rule.validate(data, {})
            assert result.passed is True, f"Phone {phone} should be valid"

    def test_date_rule_passes(self):
        """Test DateRule passes for valid dates."""
        rule = DateRule("date", date_format="%Y-%m-%d")
        data = {"date": "2023-01-15"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_date_rule_fails_invalid_format(self):
        """Test DateRule fails for invalid date format."""
        rule = DateRule("date", date_format="%Y-%m-%d")
        data = {"date": "01/15/2023"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_date_rule_validates_range(self):
        """Test DateRule validates date ranges."""
        rule = DateRule(
            "date",
            date_format="%Y-%m-%d",
            max_date=datetime(2023, 12, 31)
        )

        # Future date should fail
        data = {"date": "2024-01-01"}
        result = rule.validate(data, {})
        assert result.passed is False

    def test_numeric_range_rule_passes(self):
        """Test NumericRangeRule passes for valid numbers."""
        rule = NumericRangeRule("price", min_value=0.0, max_value=1000.0)
        data = {"price": 99.99}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_numeric_range_rule_fails_below_min(self):
        """Test NumericRangeRule fails for numbers below minimum."""
        rule = NumericRangeRule("price", min_value=0.0)
        data = {"price": -10.0}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_numeric_range_rule_handles_currency(self):
        """Test NumericRangeRule handles currency symbols."""
        rule = NumericRangeRule("price", min_value=0.0)
        data = {"price": "$99.99"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_enum_rule_passes(self):
        """Test EnumRule passes for allowed values."""
        rule = EnumRule("status", allowed_values=["In Stock", "Out of Stock"])
        data = {"status": "In Stock"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_enum_rule_fails(self):
        """Test EnumRule fails for disallowed values."""
        rule = EnumRule("status", allowed_values=["In Stock", "Out of Stock"])
        data = {"status": "Unknown"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_enum_rule_case_insensitive(self):
        """Test EnumRule with case-insensitive matching."""
        rule = EnumRule(
            "status",
            allowed_values=["In Stock", "Out of Stock"],
            case_sensitive=False
        )
        data = {"status": "in stock"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_length_rule_passes(self):
        """Test LengthRule passes for valid lengths."""
        rule = LengthRule("title", min_length=5, max_length=100)
        data = {"title": "Product Title"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_length_rule_fails_too_short(self):
        """Test LengthRule fails for strings too short."""
        rule = LengthRule("title", min_length=10)
        data = {"title": "Short"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_custom_rule_passes(self):
        """Test CustomRule with custom validation function."""
        def is_even(value):
            return value % 2 == 0

        rule = CustomRule("count", is_even, "even number check")
        data = {"count": 4}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_custom_rule_fails(self):
        """Test CustomRule fails when custom function returns False."""
        def is_even(value):
            return value % 2 == 0

        rule = CustomRule("count", is_even, "even number check")
        data = {"count": 3}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_no_error_message_rule_passes(self):
        """Test NoErrorMessageRule passes for clean data."""
        rule = NoErrorMessageRule()
        data = {"title": "Product", "price": "$99"}
        result = rule.validate(data, {})

        assert result.passed is True

    def test_no_error_message_rule_detects_error_field(self):
        """Test NoErrorMessageRule detects explicit error fields."""
        rule = NoErrorMessageRule()
        data = {"error": "Could not find price"}
        result = rule.validate(data, {})

        assert result.passed is False

    def test_no_error_message_rule_detects_error_indicators(self):
        """Test NoErrorMessageRule detects error indicators in values."""
        rule = NoErrorMessageRule()
        data = {"price": "couldn't find pricing information"}
        result = rule.validate(data, {})

        assert result.passed is False
        assert result.severity == ValidationSeverity.WARNING

    def test_field_validation_rule_missing_required_field(self):
        """Test FieldValidationRule fails for missing required fields."""
        rule = NotNARule("price", required=True)
        data = {"title": "Product"}  # price is missing
        result = rule.validate(data, {})

        assert result.passed is False
        assert "missing" in result.message.lower()

    def test_field_validation_rule_missing_optional_field(self):
        """Test FieldValidationRule passes for missing optional fields."""
        rule = NotNARule("description", required=False)
        data = {"title": "Product"}  # description is missing
        result = rule.validate(data, {})

        assert result.passed is True


class TestValidationEngine:
    """Test ValidationEngine functionality."""

    def test_engine_with_no_rules(self):
        """Test ValidationEngine with no rules passes."""
        engine = ValidationEngine()
        data = {"title": "Product"}
        result = engine.validate(data)

        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_engine_with_passing_rules(self):
        """Test ValidationEngine with all rules passing."""
        rules = [
            NotNARule("title"),
            NotEmptyRule("title")
        ]
        engine = ValidationEngine(rules)
        data = {"title": "Product Title"}
        result = engine.validate(data)

        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_engine_with_failing_rules(self):
        """Test ValidationEngine with failing rules."""
        rules = [
            NotNARule("price"),
            NumericRangeRule("price", min_value=0.0)
        ]
        engine = ValidationEngine(rules)
        data = {"price": "NA"}
        result = engine.validate(data)

        assert result["passed"] is False
        assert len(result["errors"]) > 0

    def test_engine_categorizes_by_severity(self):
        """Test ValidationEngine categorizes results by severity."""
        rules = [
            NotNARule("price", severity=ValidationSeverity.ERROR),
            NotEmptyRule("description", severity=ValidationSeverity.WARNING)
        ]
        engine = ValidationEngine(rules)
        data = {"price": "NA", "description": ""}
        result = engine.validate(data)

        assert len(result["errors"]) > 0
        assert len(result["warnings"]) > 0

    def test_engine_strict_mode(self):
        """Test ValidationEngine strict mode treats warnings as errors."""
        rules = [
            NotEmptyRule("description", severity=ValidationSeverity.WARNING)
        ]
        engine = ValidationEngine(rules)
        data = {"description": ""}

        # Normal mode: warnings don't cause failure
        result = engine.validate(data)
        assert result["passed"] is True  # Only warnings, no errors

        # Strict mode: warnings cause failure
        result_strict = engine.validate_strict(data)
        assert result_strict["passed"] is False

    def test_engine_get_failed_fields(self):
        """Test ValidationEngine can extract failed field names."""
        rules = [
            NotNARule("price"),
            NotEmptyRule("title")
        ]
        engine = ValidationEngine(rules)
        data = {"price": "NA", "title": ""}
        result = engine.validate(data)

        failed_fields = engine.get_failed_fields(result)
        assert "price" in failed_fields
        assert "title" in failed_fields

    def test_engine_get_missing_fields(self):
        """Test ValidationEngine can extract missing field names."""
        rules = [
            NotNARule("price", required=True),
            NotNARule("title", required=True)
        ]
        engine = ValidationEngine(rules)
        data = {}  # All fields missing
        result = engine.validate(data)

        missing_fields = engine.get_missing_fields(result)
        assert "price" in missing_fields
        assert "title" in missing_fields


class TestConfidenceScorer:
    """Test ConfidenceScorer functionality."""

    def test_scorer_perfect_data(self):
        """Test ConfidenceScorer with perfect data."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price", "description"],
            required_fields=["title", "price"]
        )

        data = {
            "title": "Product",
            "price": "$99",
            "description": "Great product"
        }

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        assert scores["overall_confidence"] > 0.9
        assert scores["completeness"] == 1.0
        assert scores["quality_score"] == 1.0

    def test_scorer_incomplete_data(self):
        """Test ConfidenceScorer with incomplete data."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price", "description"],
            required_fields=["title"]
        )

        data = {
            "title": "Product"
            # price and description missing
        }

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        assert scores["completeness"] < 0.5

    def test_scorer_with_placeholder_values(self):
        """Test ConfidenceScorer detects placeholder values."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price"],
            required_fields=["title", "price"]
        )

        data = {
            "title": "Product",
            "price": "NA"
        }

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        assert scores["has_placeholder_values"] is True
        assert scores["overall_confidence"] < 0.8  # Penalty for placeholder

    def test_scorer_missing_required_fields(self):
        """Test ConfidenceScorer detects missing required fields."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price"],
            required_fields=["title", "price"]
        )

        data = {
            "title": "Product"
            # price missing
        }

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        assert "price" in scores["missing_required_fields"]
        assert scores["overall_confidence"] < 0.6  # Penalty for missing required

    def test_scorer_field_confidence(self):
        """Test ConfidenceScorer calculates per-field confidence."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price"],
            required_fields=["title", "price"]
        )

        data = {
            "title": "Product",
            "price": "NA"  # Placeholder
        }

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        assert "title" in scores["field_confidence"]
        assert "price" in scores["field_confidence"]
        assert scores["field_confidence"]["title"] > scores["field_confidence"]["price"]

    def test_scorer_should_retry(self):
        """Test ConfidenceScorer should_retry logic."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price"],
            required_fields=["title", "price"]
        )

        # Low confidence data
        data = {"title": "Product", "price": "NA"}

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)

        should_retry = scorer.should_retry(scores, min_confidence=0.8)
        assert should_retry is True

    def test_scorer_get_retry_focus_fields(self):
        """Test ConfidenceScorer identifies fields to retry."""
        scorer = ConfidenceScorer(
            expected_fields=["title", "price", "description"],
            required_fields=["title", "price"]
        )

        data = {"title": "Product", "price": "NA"}  # description missing

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        scores = scorer.calculate_scores(data, validation_result)
        focus_fields = scorer.get_retry_focus_fields(scores)

        assert "description" in focus_fields  # Missing field
        assert "price" in focus_fields  # Low confidence (placeholder)


class TestValidatedResponse:
    """Test ValidatedResponse wrapper."""

    def test_validated_response_properties(self):
        """Test ValidatedResponse property access."""
        data = {"title": "Product", "price": "$99"}

        validation_result = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "all_results": [],
            "error_count": 0,
            "warning_count": 0
        }

        confidence_scores = {
            "overall_confidence": 0.95,
            "completeness": 1.0,
            "quality_score": 0.95,
            "field_confidence": {"title": 0.98, "price": 0.92},
            "has_placeholder_values": False,
            "missing_required_fields": []
        }

        response = ValidatedResponse(data, validation_result, confidence_scores)

        assert response.is_valid is True
        assert response.confidence == 0.95
        assert response.completeness == 1.0
        assert response.quality_score == 0.95
        assert response.has_errors is False
        assert response.has_warnings is False

    def test_validated_response_dict_access(self):
        """Test ValidatedResponse supports dict-like access."""
        data = {"title": "Product", "price": "$99"}

        validation_result = {"passed": True, "errors": [], "warnings": [], "all_results": [], "error_count": 0, "warning_count": 0}
        confidence_scores = {"overall_confidence": 0.95, "completeness": 1.0, "quality_score": 0.95, "field_confidence": {}, "has_placeholder_values": False, "missing_required_fields": []}

        response = ValidatedResponse(data, validation_result, confidence_scores)

        assert response["title"] == "Product"
        assert response["price"] == "$99"
        assert "title" in response
        assert response.get("title") == "Product"
        assert response.get("missing_field", "default") == "default"

    def test_validated_response_to_dict(self):
        """Test ValidatedResponse.to_dict() conversion."""
        data = {"title": "Product"}
        validation_result = {"passed": True, "errors": [], "warnings": [], "all_results": [], "error_count": 0, "warning_count": 0}
        confidence_scores = {"overall_confidence": 0.95, "completeness": 1.0, "quality_score": 0.95, "field_confidence": {}, "has_placeholder_values": False, "missing_required_fields": []}

        response = ValidatedResponse(data, validation_result, confidence_scores)
        result_dict = response.to_dict()

        assert "data" in result_dict
        assert "confidence" in result_dict
        assert "validation" in result_dict
        assert "metadata" in result_dict

    def test_validated_response_should_retry(self):
        """Test ValidatedResponse.should_retry() logic."""
        data = {"title": "Product", "price": "NA"}

        validation_result = {"passed": True, "errors": [], "warnings": [], "all_results": [], "error_count": 0, "warning_count": 0}
        confidence_scores = {
            "overall_confidence": 0.5,  # Low confidence
            "completeness": 0.5,
            "quality_score": 0.8,
            "field_confidence": {},
            "has_placeholder_values": True,
            "missing_required_fields": []
        }

        response = ValidatedResponse(data, validation_result, confidence_scores)

        assert response.should_retry(min_confidence=0.7) is True


class TestValidationPresets:
    """Test preset rule configurations."""

    def test_ecommerce_rules_basic(self):
        """Test e-commerce preset with valid product data."""
        rules = create_ecommerce_rules()
        engine = ValidationEngine(rules)

        data = {
            "title": "Product Name",
            "price": "$99.99",
            "description": "Product description",
            "availability": "In Stock"
        }

        result = engine.validate(data)
        assert result["passed"] is True

    def test_ecommerce_rules_missing_price(self):
        """Test e-commerce preset detects missing price."""
        rules = create_ecommerce_rules(require_price=True)
        engine = ValidationEngine(rules)

        data = {
            "title": "Product Name",
            "description": "Product description"
            # price missing
        }

        result = engine.validate(data)
        assert result["passed"] is False

    def test_contact_info_rules_valid(self):
        """Test contact info preset with valid data."""
        rules = create_contact_info_rules()
        engine = ValidationEngine(rules)

        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-123-4567"
        }

        result = engine.validate(data)
        assert result["passed"] is True

    def test_contact_info_rules_invalid_email(self):
        """Test contact info preset detects invalid email."""
        rules = create_contact_info_rules()
        engine = ValidationEngine(rules)

        data = {
            "email": "not-an-email",
            "phone": "555-123-4567"
        }

        result = engine.validate(data)
        assert result["passed"] is False

    def test_news_article_rules_valid(self):
        """Test news article preset with valid data."""
        rules = create_news_article_rules()
        engine = ValidationEngine(rules)

        data = {
            "title": "News Article Title",
            "content": "Article content goes here...",
            "author": "John Doe",
            "date": "2023-01-15"
        }

        result = engine.validate(data)
        assert result["passed"] is True

    def test_minimal_rules(self):
        """Test minimal rules preset."""
        rules = create_minimal_rules()
        engine = ValidationEngine(rules)

        # Should pass for any valid data
        data = {"any_field": "any_value"}
        result = engine.validate(data)
        assert result["passed"] is True

        # Should fail only for error messages
        data_with_error = {"error": "Something went wrong"}
        result = engine.validate(data_with_error)
        assert result["passed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
