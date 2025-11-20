"""
Pre-configured validation rule sets for common use cases.

This module provides ready-to-use validation rule configurations for
typical scraping scenarios like e-commerce, contact information, news, etc.
"""

from datetime import datetime
from typing import List
from .base import ValidationRule
from .rules import (
    NotNARule,
    NotEmptyRule,
    EmailRule,
    URLRule,
    PhoneRule,
    DateRule,
    NumericRangeRule,
    EnumRule,
    NoErrorMessageRule
)


def create_ecommerce_rules(
    strict: bool = False,
    require_price: bool = True,
    require_availability: bool = False
) -> List[ValidationRule]:
    """
    Create validation rules for e-commerce product scraping.

    Validates typical product fields: title, price, description, availability, etc.

    Args:
        strict: If True, all fields are required. If False, only title and price are required.
        require_price: Whether price field is required (default: True)
        require_availability: Whether availability field is required (default: False)

    Returns:
        List of validation rules for e-commerce data

    Example:
        >>> rules = create_ecommerce_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(product_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),

        # Title validation
        NotNARule("title", required=True),
        NotEmptyRule("title", required=True),
    ]

    # Price validation
    if require_price:
        rules.extend([
            NotNARule("price", required=True),
            NotEmptyRule("price", required=True),
            NumericRangeRule("price", min_value=0.0, required=True)
        ])

    # Description validation (optional unless strict mode)
    rules.extend([
        NotNARule("description", required=strict),
        NotEmptyRule("description", required=strict)
    ])

    # Availability validation
    if require_availability or strict:
        rules.extend([
            NotNARule("availability", required=True),
            EnumRule(
                "availability",
                allowed_values=["In Stock", "Out of Stock", "Pre-Order", "Backorder"],
                case_sensitive=False,
                required=True
            )
        ])

    # Rating validation (optional)
    rules.append(NumericRangeRule("rating", min_value=0.0, max_value=5.0, required=False))

    # Image URL validation (optional)
    rules.append(URLRule("image_url", required=False))

    return rules


def create_contact_info_rules(
    require_email: bool = True,
    require_phone: bool = False,
    require_both: bool = False
) -> List[ValidationRule]:
    """
    Create validation rules for contact information scraping.

    Validates email addresses, phone numbers, names, etc.

    Args:
        require_email: Whether email is required (default: True)
        require_phone: Whether phone is required (default: False)
        require_both: Whether both email AND phone are required (default: False)

    Returns:
        List of validation rules for contact information

    Example:
        >>> rules = create_contact_info_rules(require_both=True)
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(contact_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),
    ]

    # Email validation
    email_required = require_email or require_both
    rules.extend([
        NotNARule("email", required=email_required),
        EmailRule("email", required=email_required)
    ])

    # Phone validation
    phone_required = require_phone or require_both
    rules.extend([
        NotNARule("phone", required=phone_required),
        PhoneRule("phone", required=phone_required)
    ])

    # Name validation (optional)
    rules.extend([
        NotNARule("name", required=False),
        NotEmptyRule("name", required=False)
    ])

    # Company validation (optional)
    rules.extend([
        NotNARule("company", required=False),
        NotEmptyRule("company", required=False)
    ])

    # Website validation (optional)
    rules.append(URLRule("website", required=False))

    return rules


def create_news_article_rules(strict: bool = False) -> List[ValidationRule]:
    """
    Create validation rules for news article scraping.

    Validates article title, date, author, content, etc.

    Args:
        strict: If True, all fields are required. If False, only title and content are required.

    Returns:
        List of validation rules for news articles

    Example:
        >>> rules = create_news_article_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(article_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),

        # Title validation
        NotNARule("title", required=True),
        NotEmptyRule("title", required=True),

        # Content validation
        NotNARule("content", required=True),
        NotEmptyRule("content", required=True),
    ]

    # Date validation - articles shouldn't be dated in the future
    rules.append(
        DateRule(
            "date",
            date_format="%Y-%m-%d",
            max_date=datetime.now(),
            required=strict
        )
    )

    # Author validation (optional unless strict)
    rules.extend([
        NotNARule("author", required=strict),
        NotEmptyRule("author", required=strict)
    ])

    # URL validation (optional)
    rules.append(URLRule("url", required=False))

    return rules


def create_job_listing_rules(strict: bool = False) -> List[ValidationRule]:
    """
    Create validation rules for job listing scraping.

    Validates job title, company, location, salary, etc.

    Args:
        strict: If True, more fields are required

    Returns:
        List of validation rules for job listings

    Example:
        >>> rules = create_job_listing_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(job_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),

        # Title validation
        NotNARule("title", required=True),
        NotEmptyRule("title", required=True),

        # Company validation
        NotNARule("company", required=True),
        NotEmptyRule("company", required=True),

        # Location validation (optional unless strict)
        NotNARule("location", required=strict),
        NotEmptyRule("location", required=strict),
    ]

    # Salary validation (optional, but if present should be positive)
    rules.append(NumericRangeRule("salary", min_value=0.0, required=False))

    # Employment type validation (optional)
    rules.append(
        EnumRule(
            "employment_type",
            allowed_values=["Full-Time", "Part-Time", "Contract", "Temporary", "Internship"],
            case_sensitive=False,
            required=False
        )
    )

    # URL validation (optional)
    rules.append(URLRule("url", required=False))

    return rules


def create_real_estate_rules(strict: bool = False) -> List[ValidationRule]:
    """
    Create validation rules for real estate listing scraping.

    Validates property address, price, bedrooms, bathrooms, etc.

    Args:
        strict: If True, more fields are required

    Returns:
        List of validation rules for real estate listings

    Example:
        >>> rules = create_real_estate_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(property_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),

        # Address validation
        NotNARule("address", required=True),
        NotEmptyRule("address", required=True),

        # Price validation
        NotNARule("price", required=True),
        NumericRangeRule("price", min_value=0.0, required=True),
    ]

    # Bedrooms validation (optional unless strict)
    rules.append(
        NumericRangeRule("bedrooms", min_value=0.0, max_value=50.0, required=strict)
    )

    # Bathrooms validation (optional unless strict)
    rules.append(
        NumericRangeRule("bathrooms", min_value=0.0, max_value=50.0, required=strict)
    )

    # Square footage validation (optional)
    rules.append(
        NumericRangeRule("square_feet", min_value=0.0, required=False)
    )

    # Property type validation (optional)
    rules.append(
        EnumRule(
            "property_type",
            allowed_values=["House", "Apartment", "Condo", "Townhouse", "Land", "Commercial"],
            case_sensitive=False,
            required=False
        )
    )

    # Listing URL validation (optional)
    rules.append(URLRule("url", required=False))

    return rules


def create_social_media_post_rules(strict: bool = False) -> List[ValidationRule]:
    """
    Create validation rules for social media post scraping.

    Validates post content, author, timestamp, engagement metrics, etc.

    Args:
        strict: If True, more fields are required

    Returns:
        List of validation rules for social media posts

    Example:
        >>> rules = create_social_media_post_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(post_data)
    """
    rules = [
        # Always check for error messages
        NoErrorMessageRule(),

        # Content validation
        NotNARule("content", required=True),
        NotEmptyRule("content", required=True),

        # Author validation
        NotNARule("author", required=True),
        NotEmptyRule("author", required=True),
    ]

    # Timestamp validation (optional unless strict, shouldn't be in future)
    rules.append(
        DateRule(
            "timestamp",
            date_format="%Y-%m-%d",
            max_date=datetime.now(),
            required=strict
        )
    )

    # Engagement metrics (optional, but should be non-negative if present)
    rules.extend([
        NumericRangeRule("likes", min_value=0.0, required=False),
        NumericRangeRule("shares", min_value=0.0, required=False),
        NumericRangeRule("comments", min_value=0.0, required=False)
    ])

    # Post URL validation (optional)
    rules.append(URLRule("url", required=False))

    return rules


def create_minimal_rules() -> List[ValidationRule]:
    """
    Create minimal validation rules that apply to any extraction.

    Just checks for error messages and ensures the response is not empty.

    Returns:
        List of minimal validation rules

    Example:
        >>> rules = create_minimal_rules()
        >>> engine = ValidationEngine(rules)
        >>> result = engine.validate(data)
    """
    return [
        NoErrorMessageRule()
    ]
