"""
Data validation and confidence scoring system for ScrapeGraphAI.

This module provides a comprehensive validation and confidence scoring system
for LLM-extracted data, enabling quality assessment and automatic retry logic.

Main components:
- ValidationRule: Base classes for creating validation rules
- ValidationEngine: Orchestrates running validation rules
- ConfidenceScorer: Calculates confidence scores for extracted data
- ValidatedResponse: Enhanced response wrapper with validation metadata
- Presets: Pre-configured rule sets for common use cases

Example usage:
    >>> from scrapegraphai.utils.validation import ValidationEngine, create_ecommerce_rules
    >>>
    >>> # Create validation engine with e-commerce rules
    >>> rules = create_ecommerce_rules()
    >>> engine = ValidationEngine(rules)
    >>>
    >>> # Validate extracted data
    >>> result = engine.validate(extracted_data)
    >>> if result["passed"]:
    >>>     print("Validation passed!")
    >>> else:
    >>>     print(f"Validation failed with {len(result['errors'])} errors")
"""

# Base classes
from .base import (
    ValidationRule,
    FieldValidationRule,
    ValidationResult,
    ValidationSeverity
)

# Built-in validation rules
from .rules import (
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
    NoErrorMessageRule
)

# Validation engine
from .engine import ValidationEngine

# Confidence scorer
from .scorer import ConfidenceScorer

# Enhanced response wrapper
from .response import ValidatedResponse

# Preset rule configurations
from .presets import (
    create_ecommerce_rules,
    create_contact_info_rules,
    create_news_article_rules,
    create_job_listing_rules,
    create_real_estate_rules,
    create_social_media_post_rules,
    create_minimal_rules
)

__all__ = [
    # Base classes
    "ValidationRule",
    "FieldValidationRule",
    "ValidationResult",
    "ValidationSeverity",
    # Built-in rules
    "NotNARule",
    "NotEmptyRule",
    "RegexRule",
    "EmailRule",
    "URLRule",
    "PhoneRule",
    "DateRule",
    "NumericRangeRule",
    "EnumRule",
    "LengthRule",
    "CustomRule",
    "NoErrorMessageRule",
    # Engine and scorer
    "ValidationEngine",
    "ConfidenceScorer",
    # Response wrapper
    "ValidatedResponse",
    # Presets
    "create_ecommerce_rules",
    "create_contact_info_rules",
    "create_news_article_rules",
    "create_job_listing_rules",
    "create_real_estate_rules",
    "create_social_media_post_rules",
    "create_minimal_rules"
]
