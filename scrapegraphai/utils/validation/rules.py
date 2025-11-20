"""
Built-in validation rules for common data validation scenarios.

This module provides pre-built validation rules for common patterns like
email validation, URL validation, date validation, etc.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Pattern, Callable
from .base import FieldValidationRule, ValidationResult, ValidationSeverity, ValidationRule


class NotNARule(FieldValidationRule):
    """
    Validates that a field doesn't contain placeholder values like "NA" or "N/A".

    Common when LLM can't find data but follows the instruction:
    "If you don't find the answer put as value 'NA'."
    """

    @property
    def name(self) -> str:
        return "NotNARule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        na_patterns = ["NA", "N/A", "n/a", "na", "Not Available", "Not Found", "None"]

        if isinstance(value, str) and value.strip() in na_patterns:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' contains placeholder value: {value}",
                field_name=self.field_name,
                actual=value,
                suggestion="LLM couldn't find this information; consider retry with different strategy"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' has valid value",
            field_name=self.field_name
        )


class NotEmptyRule(FieldValidationRule):
    """Validates that a field is not empty."""

    @property
    def name(self) -> str:
        return "NotEmptyRule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        is_empty = (
            value is None or
            (isinstance(value, str) and value.strip() == "") or
            (isinstance(value, (list, dict)) and len(value) == 0)
        )

        if is_empty:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' is empty",
                field_name=self.field_name,
                actual=value,
                suggestion="Field exists but has no content"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' is not empty",
            field_name=self.field_name
        )


class RegexRule(FieldValidationRule):
    """Validates that a field matches a regex pattern."""

    def __init__(
        self,
        field_name: str,
        pattern: str,
        pattern_description: str = "expected format",
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.pattern: Pattern = re.compile(pattern)
        self.pattern_description = pattern_description

    @property
    def name(self) -> str:
        return f"RegexRule({self.pattern_description})"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' must be a string for regex validation",
                field_name=self.field_name,
                actual=type(value).__name__
            )

        if not self.pattern.match(value):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' doesn't match {self.pattern_description}",
                field_name=self.field_name,
                expected=self.pattern_description,
                actual=value,
                suggestion=f"Expected format: {self.pattern_description}"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' matches {self.pattern_description}",
            field_name=self.field_name
        )


class EmailRule(RegexRule):
    """Validates email address format."""

    EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    def __init__(self, field_name: str, **kwargs):
        super().__init__(
            field_name,
            pattern=self.EMAIL_REGEX,
            pattern_description="valid email address",
            **kwargs
        )


class URLRule(RegexRule):
    """Validates URL format."""

    URL_REGEX = r'^https?://[^\s/$.?#].[^\s]*$'

    def __init__(self, field_name: str, **kwargs):
        super().__init__(
            field_name,
            pattern=self.URL_REGEX,
            pattern_description="valid URL",
            **kwargs
        )


class PhoneRule(RegexRule):
    """Validates phone number format (flexible)."""

    # Matches: +1-555-123-4567, (555) 123-4567, 555.123.4567, etc.
    PHONE_REGEX = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$'

    def __init__(self, field_name: str, **kwargs):
        super().__init__(
            field_name,
            pattern=self.PHONE_REGEX,
            pattern_description="valid phone number",
            **kwargs
        )


class DateRule(FieldValidationRule):
    """Validates date format and optionally date range."""

    def __init__(
        self,
        field_name: str,
        date_format: str = "%Y-%m-%d",
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.date_format = date_format
        self.min_date = min_date
        self.max_date = max_date

    @property
    def name(self) -> str:
        return "DateRule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' must be a string for date parsing",
                field_name=self.field_name,
                actual=type(value).__name__
            )

        try:
            parsed_date = datetime.strptime(value, self.date_format)
        except ValueError:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' is not a valid date",
                field_name=self.field_name,
                expected=f"Date in format {self.date_format}",
                actual=value,
                suggestion=f"Expected format: {self.date_format}"
            )

        # Check date range if specified
        if self.min_date and parsed_date < self.min_date:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' date is before minimum allowed date",
                field_name=self.field_name,
                expected=f"Date >= {self.min_date}",
                actual=value
            )

        if self.max_date and parsed_date > self.max_date:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' date is after maximum allowed date",
                field_name=self.field_name,
                expected=f"Date <= {self.max_date}",
                actual=value
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' is a valid date",
            field_name=self.field_name
        )


class NumericRangeRule(FieldValidationRule):
    """Validates that a numeric field is within a specified range."""

    def __init__(
        self,
        field_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.min_value = min_value
        self.max_value = max_value

    @property
    def name(self) -> str:
        return "NumericRangeRule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        # Try to convert to float
        try:
            if isinstance(value, str):
                # Remove common currency symbols and commas
                cleaned_value = re.sub(r'[$,£€¥]', '', value)
                numeric_value = float(cleaned_value)
            elif isinstance(value, (int, float)):
                numeric_value = float(value)
            else:
                return ValidationResult(
                    passed=False,
                    severity=self.severity,
                    rule_name=self.name,
                    message=f"Field '{self.field_name}' is not numeric",
                    field_name=self.field_name,
                    actual=type(value).__name__
                )
        except (ValueError, TypeError):
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' cannot be converted to number",
                field_name=self.field_name,
                actual=value
            )

        # Check range
        if self.min_value is not None and numeric_value < self.min_value:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' is below minimum value",
                field_name=self.field_name,
                expected=f">= {self.min_value}",
                actual=numeric_value
            )

        if self.max_value is not None and numeric_value > self.max_value:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' exceeds maximum value",
                field_name=self.field_name,
                expected=f"<= {self.max_value}",
                actual=numeric_value
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' is within valid range",
            field_name=self.field_name
        )


class EnumRule(FieldValidationRule):
    """Validates that a field value is one of allowed values."""

    def __init__(
        self,
        field_name: str,
        allowed_values: List[Any],
        case_sensitive: bool = True,
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.allowed_values = allowed_values
        self.case_sensitive = case_sensitive

    @property
    def name(self) -> str:
        return "EnumRule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        if self.case_sensitive:
            is_valid = value in self.allowed_values
        else:
            # Case-insensitive comparison for strings
            if isinstance(value, str):
                is_valid = value.lower() in [str(v).lower() for v in self.allowed_values]
            else:
                is_valid = value in self.allowed_values

        if not is_valid:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' has invalid value",
                field_name=self.field_name,
                expected=f"One of: {', '.join(str(v) for v in self.allowed_values)}",
                actual=value,
                suggestion=f"Allowed values: {', '.join(str(v) for v in self.allowed_values)}"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' has valid enum value",
            field_name=self.field_name
        )


class LengthRule(FieldValidationRule):
    """Validates that a field's length is within specified bounds."""

    def __init__(
        self,
        field_name: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.min_length = min_length
        self.max_length = max_length

    @property
    def name(self) -> str:
        return "LengthRule"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        # Get length
        try:
            length = len(value)
        except TypeError:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' does not have a length",
                field_name=self.field_name,
                actual=type(value).__name__
            )

        # Check minimum length
        if self.min_length is not None and length < self.min_length:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' is too short",
                field_name=self.field_name,
                expected=f"Length >= {self.min_length}",
                actual=f"Length = {length}"
            )

        # Check maximum length
        if self.max_length is not None and length > self.max_length:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' is too long",
                field_name=self.field_name,
                expected=f"Length <= {self.max_length}",
                actual=f"Length = {length}"
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' has valid length",
            field_name=self.field_name
        )


class CustomRule(FieldValidationRule):
    """
    Validates a field using a custom validation function.

    Useful for complex business rules that don't fit other validators.
    """

    def __init__(
        self,
        field_name: str,
        validation_func: Callable[[Any], bool],
        rule_description: str = "custom validation",
        error_message: Optional[str] = None,
        **kwargs
    ):
        super().__init__(field_name, **kwargs)
        self.validation_func = validation_func
        self.rule_description = rule_description
        self.error_message = error_message or f"Field '{field_name}' failed {rule_description}"

    @property
    def name(self) -> str:
        return f"CustomRule({self.rule_description})"

    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        try:
            is_valid = self.validation_func(value)
        except Exception as e:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=f"Field '{self.field_name}' validation error: {str(e)}",
                field_name=self.field_name,
                actual=value
            )

        if not is_valid:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message=self.error_message,
                field_name=self.field_name,
                actual=value
            )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message=f"Field '{self.field_name}' passed {self.rule_description}",
            field_name=self.field_name
        )


class NoErrorMessageRule(ValidationRule):
    """
    Validates that the response doesn't contain error messages or
    explanations instead of structured data.
    """

    def __init__(self, severity: ValidationSeverity = ValidationSeverity.ERROR):
        super().__init__(severity)
        self.error_indicators = [
            "error", "couldn't find", "unable to", "failed to",
            "not found", "no information", "couldn't extract",
            "sorry", "I don't", "I cannot", "I can't"
        ]

    @property
    def name(self) -> str:
        return "NoErrorMessageRule"

    def validate(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """Check if data contains error messages."""
        if not isinstance(data, dict):
            return ValidationResult(
                passed=True,
                severity=ValidationSeverity.INFO,
                rule_name=self.name,
                message="Data is not a dictionary, skipping error message check"
            )

        # Check if there's an explicit error field
        if "error" in data and data["error"]:
            return ValidationResult(
                passed=False,
                severity=self.severity,
                rule_name=self.name,
                message="Response contains explicit error field",
                actual=data.get("error"),
                suggestion="LLM returned an error instead of extracted data"
            )

        # Check if any field values contain error indicators
        for field_name, value in data.items():
            if isinstance(value, str):
                value_lower = value.lower()
                for indicator in self.error_indicators:
                    if indicator in value_lower:
                        return ValidationResult(
                            passed=False,
                            severity=ValidationSeverity.WARNING,
                            rule_name=self.name,
                            message=f"Field '{field_name}' may contain an error message",
                            field_name=field_name,
                            actual=value,
                            suggestion="LLM may have returned explanation instead of data"
                        )

        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            rule_name=self.name,
            message="No error messages detected in response"
        )
