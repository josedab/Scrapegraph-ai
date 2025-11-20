# Data Validation & Confidence Scoring

A comprehensive validation and confidence scoring system for LLM-extracted data in ScrapeGraphAI.

## Overview

This module provides tools to validate and assess the quality of data extracted by LLMs, enabling:

- **Data validation**: Check if extracted data meets quality standards
- **Confidence scoring**: Measure how confident we are in the extraction quality
- **Automatic retry logic**: Identify low-quality extractions that need retry
- **Quality metrics**: Track completeness, format compliance, and field-level confidence

## Quick Start

### Basic Usage

```python
from scrapegraphai.utils.validation import (
    ValidationEngine,
    ConfidenceScorer,
    create_ecommerce_rules
)

# Create validation rules for e-commerce data
rules = create_ecommerce_rules()
engine = ValidationEngine(rules)

# Validate extracted data
data = {
    "title": "Product Name",
    "price": "$99.99",
    "description": "Product description"
}

result = engine.validate(data)

if result["passed"]:
    print("✓ Validation passed!")
else:
    print(f"✗ Validation failed with {len(result['errors'])} errors")
    for error in result["errors"]:
        print(f"  - {error['message']}")

# Calculate confidence scores
scorer = ConfidenceScorer(
    expected_fields=["title", "price", "description"],
    required_fields=["title", "price"]
)

scores = scorer.calculate_scores(data, result)
print(f"Confidence: {scores['overall_confidence']:.2f}")
print(f"Completeness: {scores['completeness']:.2f}")
```

### Integration with GenerateAnswerNode

Enable validation in your graph configuration:

```python
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils.validation import create_ecommerce_rules

graph_config = {
    "llm": {
        "model": "openai/gpt-4",
        "api_key": "your-api-key"
    },
    # Enable validation
    "enable_validation": True,
    "validation_rules": create_ecommerce_rules(),
    "expected_fields": ["title", "price", "description"],
    "required_fields": ["title", "price"],
    "min_confidence": 0.7,
    "min_completeness": 0.8
}

smart_scraper = SmartScraperGraph(
    prompt="Extract product information",
    source="https://example.com/product",
    config=graph_config
)

result = smart_scraper.run()

# result is now a ValidatedResponse object
if result.is_valid:
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Data: {result.data}")

    # Check if retry is recommended
    if result.should_retry(min_confidence=0.8):
        print("Low confidence - consider retry")
```

## Components

### 1. Validation Rules

Built-in rules for common validation scenarios:

```python
from scrapegraphai.utils.validation import (
    NotNARule,      # Check for "NA" placeholder values
    NotEmptyRule,   # Check for empty fields
    EmailRule,      # Validate email format
    URLRule,        # Validate URL format
    PhoneRule,      # Validate phone numbers
    DateRule,       # Validate dates and date ranges
    NumericRangeRule,  # Validate numeric ranges
    EnumRule,       # Validate enum values
    LengthRule,     # Validate string/list length
    CustomRule,     # Custom validation function
    NoErrorMessageRule  # Detect LLM error messages
)

# Example: Validate email field
email_rule = EmailRule("email", required=True)
data = {"email": "user@example.com"}
result = email_rule.validate(data, {})

# Example: Validate price is positive
price_rule = NumericRangeRule("price", min_value=0.0)
data = {"price": "$99.99"}
result = price_rule.validate(data, {})

# Example: Custom validation
def is_valid_sku(value):
    return len(value) >= 6 and value.isalnum()

sku_rule = CustomRule(
    "sku",
    is_valid_sku,
    "SKU format check",
    error_message="SKU must be at least 6 alphanumeric characters"
)
```

### 2. Validation Engine

Orchestrate multiple validation rules:

```python
from scrapegraphai.utils.validation import ValidationEngine

# Create engine with multiple rules
engine = ValidationEngine([
    NotNARule("title"),
    NotEmptyRule("title"),
    NotNARule("price"),
    NumericRangeRule("price", min_value=0.0),
    EmailRule("email", required=False)
])

# Validate data
result = engine.validate(data, context={})

# Check results
print(f"Passed: {result['passed']}")
print(f"Errors: {len(result['errors'])}")
print(f"Warnings: {len(result['warnings'])}")

# Get failed fields
failed_fields = engine.get_failed_fields(result)
missing_fields = engine.get_missing_fields(result)

# Strict mode (warnings also cause failure)
strict_result = engine.validate_strict(data)
```

### 3. Confidence Scorer

Calculate quality metrics:

```python
from scrapegraphai.utils.validation import ConfidenceScorer

scorer = ConfidenceScorer(
    expected_fields=["title", "price", "description"],
    required_fields=["title", "price"]
)

scores = scorer.calculate_scores(data, validation_result)

# Overall metrics
print(f"Overall Confidence: {scores['overall_confidence']}")
print(f"Completeness: {scores['completeness']}")
print(f"Quality Score: {scores['quality_score']}")

# Per-field confidence
for field, confidence in scores['field_confidence'].items():
    print(f"{field}: {confidence:.2f}")

# Check for issues
if scores['has_placeholder_values']:
    print("Warning: Contains placeholder values like 'NA'")

if scores['missing_required_fields']:
    print(f"Missing: {scores['missing_required_fields']}")

# Determine if retry is needed
should_retry = scorer.should_retry(
    scores,
    min_confidence=0.7,
    min_completeness=0.8
)

# Get fields to focus on in retry
if should_retry:
    focus_fields = scorer.get_retry_focus_fields(scores)
    print(f"Retry focusing on: {focus_fields}")
```

### 4. Validated Response

Enhanced response wrapper:

```python
from scrapegraphai.utils.validation import ValidatedResponse

response = ValidatedResponse(
    data=extracted_data,
    validation_result=validation_result,
    confidence_scores=confidence_scores
)

# Access validation status
if response.is_valid:
    print("Validation passed")

# Access confidence metrics
print(f"Confidence: {response.confidence}")
print(f"Completeness: {response.completeness}")
print(f"Quality: {response.quality_score}")

# Check for issues
if response.has_errors:
    for error in response.errors:
        print(f"Error: {error['message']}")

if response.has_warnings:
    print(f"{len(response.warnings)} warnings")

# Dictionary-like access to data
title = response["title"]
price = response.get("price", "N/A")

# Check if retry is recommended
if response.should_retry(min_confidence=0.8):
    low_conf_fields = response.get_low_confidence_fields(threshold=0.7)
    print(f"Low confidence fields: {low_conf_fields}")

# Convert to dict for serialization
result_dict = response.to_dict()

# Convert to legacy format (just the data)
legacy_data = response.to_legacy_format()
```

### 5. Preset Configurations

Pre-built rule sets for common scenarios:

```python
from scrapegraphai.utils.validation import (
    create_ecommerce_rules,
    create_contact_info_rules,
    create_news_article_rules,
    create_job_listing_rules,
    create_real_estate_rules,
    create_social_media_post_rules,
    create_minimal_rules
)

# E-commerce products
rules = create_ecommerce_rules(
    strict=False,              # All fields optional except basics
    require_price=True,        # Price is required
    require_availability=False # Availability optional
)

# Contact information
rules = create_contact_info_rules(
    require_email=True,   # Email required
    require_phone=False,  # Phone optional
    require_both=False    # Don't require both
)

# News articles
rules = create_news_article_rules(strict=False)

# Job listings
rules = create_job_listing_rules(strict=False)

# Real estate listings
rules = create_real_estate_rules(strict=False)

# Social media posts
rules = create_social_media_post_rules(strict=False)

# Minimal validation (just error detection)
rules = create_minimal_rules()
```

## Advanced Usage

### Custom Validation Rules

Create your own validation rules:

```python
from scrapegraphai.utils.validation import (
    FieldValidationRule,
    ValidationResult,
    ValidationSeverity
)

class ProductSKURule(FieldValidationRule):
    """Validate product SKU format."""

    @property
    def name(self) -> str:
        return "ProductSKURule"

    def validate_field(self, value, context):
        # SKU must be: XXX-YYYY-ZZ format
        import re
        pattern = r'^[A-Z]{3}-\d{4}-\d{2}$'

        if not isinstance(value, str):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"SKU must be a string",
                field_name=self.field_name,
                actual=type(value).__name__
            )

        if not re.match(pattern, value):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"SKU doesn't match format XXX-YYYY-ZZ",
                field_name=self.field_name,
                actual=value,
                suggestion="Expected format: ABC-1234-56"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"SKU format is valid",
            field_name=self.field_name
        )

# Use custom rule
sku_rule = ProductSKURule("sku", required=True)
engine = ValidationEngine([sku_rule])
```

### Validation Context

Pass additional context to validation rules:

```python
# Context can include schema, prompts, source URLs, etc.
context = {
    "user_prompt": "Extract product information",
    "schema": ProductSchema,
    "source_url": "https://example.com/product",
    "scraping_timestamp": datetime.now()
}

result = engine.validate(data, context)
```

### Conditional Retry Logic

Implement intelligent retry strategies:

```python
response = smart_scraper.run()

# Retry with different strategy based on failure reason
if response.should_retry():
    if response.completeness < 0.5:
        # Very incomplete - try with more specific prompt
        retry_prompt = f"Focus on extracting: {', '.join(response.missing_required_fields)}"

    elif response.has_placeholder_values:
        # LLM couldn't find data - try different extraction strategy
        retry_prompt = "Look more carefully for the information"

    # Retry extraction
    result = smart_scraper.run(prompt=retry_prompt)
```

## Configuration Options

When using validation with GenerateAnswerNode:

```python
node_config = {
    "llm_model": llm_model,

    # Enable validation
    "enable_validation": True,

    # Validation rules (list of ValidationRule objects)
    "validation_rules": [
        NotNARule("title"),
        NotEmptyRule("title"),
        # ... more rules
    ],

    # Or use a preset
    # "validation_rules": create_ecommerce_rules(),

    # Expected fields (for completeness calculation)
    "expected_fields": ["title", "price", "description"],

    # Required fields (must be present and non-empty)
    "required_fields": ["title", "price"],

    # Minimum acceptable confidence (0.0-1.0)
    "min_confidence": 0.7,

    # Minimum acceptable completeness (0.0-1.0)
    "min_completeness": 0.8,
}
```

## Best Practices

### 1. Start with Preset Rules

Use preset rules as a starting point:

```python
# Start with e-commerce preset
rules = create_ecommerce_rules()

# Add custom rules as needed
from scrapegraphai.utils.validation import ValidationEngine

engine = ValidationEngine(rules)
engine.add_rule(CustomRule("sku", validate_sku_format, "SKU validation"))
```

### 2. Use Appropriate Severity Levels

- `ERROR`: Critical failures (missing required fields, invalid formats)
- `WARNING`: Quality concerns (unusual values, potential issues)
- `INFO`: Informational (successful validations)

```python
# Required field - use ERROR
NotNARule("price", severity=ValidationSeverity.ERROR, required=True)

# Optional field - use WARNING
NotEmptyRule("description", severity=ValidationSeverity.WARNING, required=False)
```

### 3. Set Realistic Thresholds

```python
# For critical applications
min_confidence = 0.9
min_completeness = 0.95

# For general use
min_confidence = 0.7
min_completeness = 0.8

# For exploratory scraping
min_confidence = 0.5
min_completeness = 0.6
```

### 4. Log Validation Results

```python
if verbose:
    print(f"Validation: {result['passed']}")
    print(f"Confidence: {scores['overall_confidence']:.2f}")
    print(f"Completeness: {scores['completeness']:.2f}")

    if result['errors']:
        print("Errors:")
        for error in result['errors']:
            print(f"  - {error['field_name']}: {error['message']}")
```

### 5. Handle Validation Failures Gracefully

```python
try:
    result = smart_scraper.run()

    if isinstance(result, ValidatedResponse):
        if result.should_retry():
            # Automatic retry with adjusted parameters
            result = smart_scraper.run(use_fallback_strategy=True)

        if result.is_valid:
            return result.data
        else:
            # Log errors and return partial data or None
            logger.warning(f"Validation failed: {result.errors}")
            return result.data if result.confidence > 0.5 else None
    else:
        # Legacy format (validation not enabled)
        return result

except Exception as e:
    logger.error(f"Extraction failed: {e}")
    return None
```

## Troubleshooting

### High False Positive Rate

If validation is too strict:

```python
# Use WARNING severity for less critical fields
rule = NotEmptyRule("optional_field", severity=ValidationSeverity.WARNING)

# Lower confidence thresholds
min_confidence = 0.6
```

### Low Confidence Scores

If scores are consistently low:

```python
# Check if expected_fields matches actual extraction
# Review validation rules for overly strict requirements
# Examine field_confidence to identify problem fields

for field, conf in response.field_confidence.items():
    if conf < 0.5:
        print(f"Low confidence field: {field} = {response[field]}")
```

### Validation Performance

For large-scale scraping:

```python
# Use minimal validation
rules = create_minimal_rules()

# Or disable validation for bulk operations
config["enable_validation"] = False
```

## API Reference

See the module docstrings for detailed API documentation:

- `ValidationRule`: Base class for validation rules
- `ValidationEngine`: Rule orchestration
- `ConfidenceScorer`: Quality metrics calculation
- `ValidatedResponse`: Enhanced response wrapper

## Examples

See `tests/test_validation_system.py` for comprehensive examples.

## License

Part of ScrapeGraphAI - MIT License
