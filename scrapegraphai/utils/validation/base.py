"""
Base classes for validation rules and results.

This module provides the foundation for the data validation and confidence
scoring system in ScrapeGraphAI.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Critical failure, extraction unusable
    WARNING = "warning"  # Quality concern, but data might be usable
    INFO = "info"        # Informational, doesn't affect quality score


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    severity: ValidationSeverity
    rule_name: str
    message: str
    field_name: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "passed": self.passed,
            "severity": self.severity.value,
            "rule_name": self.rule_name,
            "message": self.message,
            "field_name": self.field_name,
            "expected": self.expected,
            "actual": self.actual,
            "suggestion": self.suggestion
        }


class ValidationRule(ABC):
    """
    Base class for all validation rules.

    Validation rules check extracted data against expected patterns,
    formats, or business logic.
    """

    def __init__(self, severity: ValidationSeverity = ValidationSeverity.ERROR):
        self.severity = severity

    @abstractmethod
    def validate(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate data according to the rule.

        Args:
            data: The data to validate (could be full extraction or single field)
            context: Additional context (schema, user_prompt, source URL, etc.)

        Returns:
            ValidationResult indicating if validation passed
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this rule."""
        pass


class FieldValidationRule(ValidationRule):
    """Base class for rules that validate a single field."""

    def __init__(
        self,
        field_name: str,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        required: bool = True
    ):
        super().__init__(severity)
        self.field_name = field_name
        self.required = required

    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        """
        Validate a specific field in the data.

        First checks if field exists, then delegates to validate_field()
        for field-specific validation.
        """
        if self.field_name not in data:
            if self.required:
                return ValidationResult(
                    passed=False,
                    severity=self.severity,
                    rule_name=self.name,
                    message=f"Required field '{self.field_name}' is missing",
                    field_name=self.field_name,
                    suggestion="Check if LLM prompt requests this field"
                )
            else:
                # Optional field missing is not a failure
                return ValidationResult(
                    passed=True,
                    severity=ValidationSeverity.INFO,
                    rule_name=self.name,
                    message=f"Optional field '{self.field_name}' is missing",
                    field_name=self.field_name
                )

        field_value = data[self.field_name]
        return self.validate_field(field_value, context)

    @abstractmethod
    def validate_field(self, value: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the specific field value."""
        pass
